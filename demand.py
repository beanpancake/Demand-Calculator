import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
from PIL import Image, ImageTk
try:
    from PIL.Image import Resampling
    RESAMPLE_FILTER = Resampling.LANCZOS
except ImportError:
    RESAMPLE_FILTER = Image.ANTIALIAS

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle

from calculator.core import (
    parse_load,
    calculate_demand as core_calculate_demand,
)

LOGO_PATH = "logo.png"
MAX_DYNAMIC_FIELDS = 10

last_calc_data = None  # (inputs, results, debug)

# ----------------------------- Helpers -----------------------------

def to_watts_list(vars_list, voltage):
    """Convert list of StringVars to list of watts (0 if blank/invalid)."""
    out = []
    for v in vars_list:
        s = v.get().strip()
        if s:
            out.append(parse_load(s, voltage))
    return out

# ------------------------- Calculation Core ------------------------

def calculate_demand():
    global last_calc_data
    try:
        voltage = float(voltage_var.get())
        area_main_raw = float(area_var.get())
        area_main = area_main_raw * 0.092903 if area_sqft_var.get() else area_main_raw

        range_main_w = parse_load(range_var.get(), voltage)
        heat_main_w = parse_load(heat_var.get(), voltage)
        ac_main_w = parse_load(ac_var.get(), voltage)
        evse_main_w = parse_load(evse_var.get(), voltage)
        interlocked = bool(interlock_var.get())

        add_main_all = to_watts_list(additional_vars_main, voltage)
        add_main_list_w = [w for w in add_main_all if w > 1500]
        tankless_main_w = parse_load(tankless_var_main.get(), voltage)
        sps_main_all = to_watts_list(sps_vars_main, voltage)

        suite_data = None
        if bool(suite_var.get()):
            area_suite_raw = float(suite_area_var.get())
            area_suite = area_suite_raw * 0.092903 if area_sqft_var.get() else area_suite_raw
            range_suite_w = parse_load(suite_range_var.get(), voltage)
            evse_suite_w = parse_load(suite_evse_var.get(), voltage)
            add_suite_all = to_watts_list(additional_vars_suite, voltage)
            add_suite_list_w = [w for w in add_suite_all if w > 1500]
            tankless_suite_w = parse_load(tankless_var_suite.get(), voltage)
            sps_suite_all = to_watts_list(sps_vars_suite, voltage)

            suite_data = {
                "area": area_suite,
                "area_ft2": area_suite_raw if area_sqft_var.get() else None,
                "range_w": range_suite_w,
                "evse_w": evse_suite_w,
                "add_loads": add_suite_list_w,
                "tankless_w": tankless_suite_w,
                "sps": sps_suite_all,
            }

        inputs, results, debug = core_calculate_demand(
            voltage=voltage,
            area_main=area_main,
            range_main_w=range_main_w,
            heat_main_w=heat_main_w,
            ac_main_w=ac_main_w,
            evse_main_w=evse_main_w,
            interlocked=interlocked,
            add_main_list_w=add_main_list_w,
            tankless_main_w=tankless_main_w,
            sps_main_all=sps_main_all,
            area_main_ft2=area_main_raw if area_sqft_var.get() else None,
            suite=suite_data,
        )

        last_calc_data = (inputs, results, debug)
        show_debug_popup(debug)

    except Exception as e:
        messagebox.showerror("Error", f"Calculation failed:\n{e}")

# ----------------------------- Dynamic UI helpers -----------------------------

def add_dynamic_row_if_needed(vars_list, entries_list):
    """Show first row by default; when last visible has text, show one more (up to cap). Hide trailing empties."""
    # last non-empty index
    last_nonempty = -1
    for i, v in enumerate(vars_list):
        if v.get().strip():
            last_nonempty = i
    target_visible = min(last_nonempty + 2, len(vars_list))  # ensure one empty row is visible
    for i, ent in enumerate(entries_list):
        if i < target_visible or (target_visible == 0 and i == 0):
            ent.grid(row=i, column=0, sticky='w', padx=2, pady=1)
        else:
            ent.grid_remove()
    # ensure at least the first shows
    if target_visible == 0 and entries_list:
        entries_list[0].grid(row=0, column=0, sticky='w', padx=2, pady=1)

def build_dynamic_block(parent, label_text, vars_list, entries_list, on_change_cb, max_fields=MAX_DYNAMIC_FIELDS):
    """Create a labeled dynamic block (single column) with one visible entry initially."""
    tk.Label(parent, text=label_text, font=("Helvetica", 10, "bold")).grid(sticky='w', padx=10, pady=(8,2))
    frame = tk.Frame(parent)
    frame.grid(sticky='w', padx=10, pady=(0,4))
    for _ in range(max_fields):
        var = tk.StringVar()
        var.trace_add('write', lambda *_: on_change_cb())
        ent = tk.Entry(frame, textvariable=var, width=14)
        vars_list.append(var)
        entries_list.append(ent)
    # show first input immediately
    entries_list[0].grid(row=0, column=0, sticky='w', padx=2, pady=1)
    return frame

# ----------------------------- PDF Generation -----------------------------

def generate_pdf_report(filename, inputs, results, debug_lines):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin

    # White band behind logo for cleanliness
    c.setFillColor(colors.white)
    band_h = 60
    c.rect(margin-5, y-band_h, width - 2*margin + 10, band_h, fill=1, stroke=0)
    c.setFillColor(colors.black)

    # Logo at top-right
    try:
        logo = ImageReader(LOGO_PATH)
        logo_w, logo_h = 150, 40
        c.drawImage(logo, width - margin - logo_w, y - logo_h, width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask='auto')
    except Exception as e:
        print(f"PDF logo load failed: {e}")
    y -= band_h + 20

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "CEC Single Dwelling Demand Calculation Report")
    y -= 30

    normal_style = ParagraphStyle("table_normal", fontName="Helvetica", fontSize=10)
    header_style = ParagraphStyle(
        "table_header", parent=normal_style, fontName="Helvetica-Bold", textColor=colors.white
    )

    def draw_table_section(title, rows):
        nonlocal y
        c.setFont("Helvetica-Bold", 13)
        table_data = [[Paragraph("Item", header_style), Paragraph("Value", header_style)]]
        for item, value in rows:
            table_data.append(
                [Paragraph(str(item), normal_style), Paragraph(str(value), normal_style)]
            )
        table = Table(table_data, colWidths=[200, width - 2 * margin - 200])
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]
            )
        )
        tw, th = table.wrapOn(c, width - 2 * margin, y - 18)
        if y - 18 - th < margin:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica-Bold", 13)
            tw, th = table.wrapOn(c, width - 2 * margin, y - 18)
        c.drawString(margin, y, title)
        y -= 18
        table.drawOn(c, margin, y - th)
        y -= th + 20

    # Site Info table
    site_rows = [["Voltage (V)", inputs.get('Voltage (V)')],
                 ["Main Area (m²)", inputs.get('Main Area (m²)')]]
    if 'Main Area (ft²)' in inputs:
        site_rows.append(["Main Area (ft²)", inputs.get('Main Area (ft²)')])
    draw_table_section("Site Info", site_rows)

    # Loads (Main Dwelling) table
    main_fields = [
        ("Range (W)", inputs.get('Range (W)', 'Not applicable')),
        ("Heating (W)", inputs.get('Heating (W)', 'Not applicable')),
        ("AC (W)", inputs.get('AC (W)', 'Not applicable')),
        ("Interlocked (Heat/AC)", inputs.get('Interlocked (Heat/AC)', 'Not applicable')),
        ("EVSE (W)", inputs.get('EVSE (W)', 'Not applicable')),
        ("Additional Loads >1500W (W)", inputs.get('Additional Loads >1500W (W)', 'Not applicable')),
        ("Tankless WH (W) [100%]", inputs.get('Tankless WH (W) [100%]', 'Not applicable')),
        ("Steamers/Pools/Spas WH (W) [100%]", inputs.get('Steamers/Pools/Spas WH (W) [100%]', 'Not applicable')),
    ]
    draw_table_section("Loads (Main Dwelling)", main_fields)

    # Suite table
    if inputs.get("Suite Included") == "Yes":
        suite_rows = [
            ["Suite Area (m²)", inputs.get('Suite Area (m²)')],
        ]
        if 'Suite Area (ft²)' in inputs:
            suite_rows.append(["Suite Area (ft²)", inputs.get('Suite Area (ft²)')])
        suite_rows.extend([
            ["Suite Range (W)", inputs.get('Suite Range (W)', 'Not applicable')],
            ["Suite EVSE (W)", inputs.get('Suite EVSE (W)', 'Not applicable')],
            ["Suite Additional Loads Raw (W)", inputs.get('Suite Additional Loads Raw (W)', 'Not applicable')],
            ["Suite Additional Loads Factored (W)", inputs.get('Suite Additional Loads Factored (W)', 'Not applicable')],
            ["Suite Tankless WH (W)", inputs.get('Suite Tankless WH (W)', 'Not applicable')],
            ["Suite Steamers/Pools/Spas (W)", inputs.get('Suite Steamers/Pools/Spas (W)', 'Not applicable')],
        ])
        draw_table_section("Loads (Secondary Suite)", suite_rows)

    # Results table
    result_rows = [[k, v] for k, v in results.items()]
    draw_table_section("Results", result_rows)

    # Calculation Details table
    debug_rows = []
    for line in debug_lines:
        if ':' in line:
            k, v = line.split(':', 1)
            debug_rows.append([k.strip(), v.strip()])
        else:
            debug_rows.append([line.strip(), ''])
    draw_table_section("Calculation Details", debug_rows)

    c.save()

def save_pdf_report():
    if not last_calc_data:
        messagebox.showwarning("No Data", "Please calculate the demand first.")
        return
    inputs, results, debug_lines = last_calc_data
    filename = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")],
        title="Save Demand Calculation Report"
    )
    if filename:
        try:
            generate_pdf_report(filename, inputs, results, debug_lines)
            messagebox.showinfo("Saved", f"PDF report saved to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save PDF:\n{e}")

def show_debug_popup(debug_lines):
    win = tk.Toplevel()
    win.title("Calculation Details")
    st = scrolledtext.ScrolledText(win, width=90, height=34)
    st.pack(fill="both", expand=True)
    st.insert(tk.END, "\n".join(debug_lines))
    st.configure(state="disabled")


def show_help():
    """Display a popup describing how to use the program."""
    help_text = (
        "CEC Single Dwelling Demand Calculator\n\n"
        "Enter the site information and any applicable loads. "
        "Loads may be provided in watts or breaker amperes (values \u2264500 are "
        "treated as breaker amps).\n\n"
        "Use 'Calculate Demand' to perform the calculation and view details.\n"
        "After a calculation, 'Generate PDF Report' saves a summary of the inputs "
        "and results."
    )
    messagebox.showinfo("Help", help_text)

if __name__ == "__main__":
    # ----------------------------- UI Setup -----------------------------

    root = tk.Tk()
    root.title("CEC Single Dwelling Demand Calculator (CEC 2024)")

    # Scrollable content container
    scroll_canvas = tk.Canvas(root)
    v_scroll = tk.Scrollbar(root, orient="vertical", command=scroll_canvas.yview)
    scroll_canvas.configure(yscrollcommand=v_scroll.set)
    v_scroll.pack(side="right", fill="y")
    scroll_canvas.pack(side="left", fill="both", expand=True)
    content = tk.Frame(scroll_canvas)
    scroll_canvas.create_window((0, 0), window=content, anchor="nw")

    def _on_frame_configure(event):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
    content.bind("<Configure>", _on_frame_configure)

    # Mouse wheel scrolling
    scroll_canvas.bind_all("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    scroll_canvas.bind_all("<Button-4>", lambda e: scroll_canvas.yview_scroll(-1, "units"))
    scroll_canvas.bind_all("<Button-5>", lambda e: scroll_canvas.yview_scroll(1, "units"))

    # Logo
    try:
        img = Image.open(LOGO_PATH)
        img = img.resize((300, 80), RESAMPLE_FILTER)
        photo = ImageTk.PhotoImage(img)
        tk.Label(content, image=photo).grid(row=0, column=0, sticky='w', padx=10, pady=10)
    except Exception as e:
        print(f"Logo load failed: {e}")

    row = 1  # main column row counter

    def section_label(text):
        global row
        tk.Label(content, text=text, font=("Helvetica", 11, "bold")).grid(row=row, column=0, sticky='w', padx=10, pady=(10,2))
        row += 1

    def add_labeled_entry(label_text, var, width=14):
        global row
        frm = tk.Frame(content)
        frm.grid(row=row, column=0, sticky='w', padx=10, pady=2)
        tk.Label(frm, text=label_text, width=34, anchor='w').pack(side='left')
        tk.Entry(frm, textvariable=var, width=width).pack(side='left')
        row += 1

    area_label_main = None
    suite_area_label = None
    area_sqft_var = tk.IntVar()
    def update_area_labels():
        unit = "ft²" if area_sqft_var.get() else "m²"
        area_label_main.config(text=f"Main Area ({unit}):")
        if suite_area_label:
            suite_area_label.config(text=f"Suite Area ({unit}):")

    # Site Info
    section_label("Site Info")
    voltage_var = tk.StringVar(value="240")
    add_labeled_entry("Voltage (V):", voltage_var)
    area_var = tk.StringVar()
    frm_area = tk.Frame(content); frm_area.grid(row=row, column=0, sticky='w', padx=10, pady=2)
    area_label_main = tk.Label(frm_area, width=34, anchor='w')
    area_label_main.pack(side='left')
    tk.Entry(frm_area, textvariable=area_var, width=14).pack(side='left')
    row += 1
    frm_unit = tk.Frame(content); frm_unit.grid(row=row, column=0, sticky='w', padx=10, pady=(0,2))
    tk.Checkbutton(frm_unit, text="Input areas in square feet", variable=area_sqft_var, command=update_area_labels).pack(side='left')
    row += 1
    update_area_labels()

    # Loads — Main
    section_label("Loads — Main")
    range_var = tk.StringVar();    add_labeled_entry("Range (W or breaker A):", range_var)
    heat_var  = tk.StringVar();    add_labeled_entry("Space Heating (W or breaker A):", heat_var)
    ac_var    = tk.StringVar();    add_labeled_entry("Air Conditioning (W or breaker A):", ac_var)

    interlock_var = tk.IntVar()
    frm_il = tk.Frame(content); frm_il.grid(row=row, column=0, sticky='w', padx=10, pady=2)
    tk.Checkbutton(frm_il, text="Heat and AC Interlocked", variable=interlock_var).pack(side='left')
    row += 1

    evse_var = tk.StringVar();     add_labeled_entry("EVSE (W or breaker A):", evse_var)

    # Additional Loads >1500 W — Main (dynamic)
    section_label("Additional Loads >1500 W — Main (dryer, storage WH, etc.)")
    additional_vars_main, additional_entries_main = [], []
    def on_change_additional_main():
        add_dynamic_row_if_needed(additional_vars_main, additional_entries_main)
    def build_additional_main():
        global row
        frame = tk.Frame(content)
        frame.grid(row=row, column=0, sticky='w', padx=10, pady=(0,4))
        row += 1
        for _ in range(MAX_DYNAMIC_FIELDS):
            var = tk.StringVar()
            var.trace_add('write', lambda *_: on_change_additional_main())
            ent = tk.Entry(frame, textvariable=var, width=14)
            additional_vars_main.append(var)
            additional_entries_main.append(ent)
        additional_entries_main[0].grid(row=0, column=0, sticky='w', padx=2, pady=1)
    build_additional_main()

    # Tankless WH (single)
    section_label("Tankless Water Heater — Main (100%)")
    tankless_var_main = tk.StringVar(); add_labeled_entry("Tankless WH (W or breaker A):", tankless_var_main)

    # Steamers/Pools/Spas WH — Main (dynamic)
    section_label("Steamers / Pools / Hot tubs / Spas WH — Main (100%)")
    sps_vars_main, sps_entries_main = [], []
    def on_change_sps_main():
        add_dynamic_row_if_needed(sps_vars_main, sps_entries_main)
    def build_sps_main():
        global row
        frame = tk.Frame(content)
        frame.grid(row=row, column=0, sticky='w', padx=10, pady=(0,4))
        row += 1
        for _ in range(MAX_DYNAMIC_FIELDS):
            var = tk.StringVar()
            var.trace_add('write', lambda *_: on_change_sps_main())
            ent = tk.Entry(frame, textvariable=var, width=14)
            sps_vars_main.append(var)
            sps_entries_main.append(ent)
        sps_entries_main[0].grid(row=0, column=0, sticky='w', padx=2, pady=1)
    build_sps_main()

    # Secondary Suite
    section_label("Secondary Suite")
    suite_var = tk.IntVar()
    def toggle_suite():
        suite_frame.grid() if suite_var.get() else suite_frame.grid_remove()
    frm_suite_cb = tk.Frame(content); frm_suite_cb.grid(row=row, column=0, sticky='w', padx=10, pady=2)
    tk.Checkbutton(frm_suite_cb, text="Include Secondary Suite", variable=suite_var, command=toggle_suite).pack(side='left')
    row += 1

    suite_frame = tk.Frame(content, bd=2, relief='groove')
    suite_frame.grid(row=row, column=0, sticky='we', padx=10, pady=(2,10))
    suite_frame.grid_remove()
    row += 1

    # Suite inputs (single column)
    suite_row = 0  # suite-area-local row

    def s_add_entry(label_text, var):
        global suite_row
        frm = tk.Frame(suite_frame)
        frm.grid(row=suite_row, column=0, sticky='w', padx=10, pady=2)
        tk.Label(frm, text=label_text, width=34, anchor='w').pack(side='left')
        tk.Entry(frm, textvariable=var, width=14).pack(side='left')
        suite_row += 1

    suite_area_var = tk.StringVar()
    frm_suite_area = tk.Frame(suite_frame); frm_suite_area.grid(row=suite_row, column=0, sticky='w', padx=10, pady=2)
    suite_area_label = tk.Label(frm_suite_area, width=34, anchor='w')
    suite_area_label.pack(side='left')
    tk.Entry(frm_suite_area, textvariable=suite_area_var, width=14).pack(side='left')
    suite_row += 1

    suite_range_var = tk.StringVar(); s_add_entry("Suite Range (W or breaker A):", suite_range_var)
    suite_evse_var  = tk.StringVar(); s_add_entry("Suite EVSE (W or breaker A):", suite_evse_var)
    update_area_labels()

    tk.Label(suite_frame, text="Additional Loads >1500 W — Suite", font=("Helvetica", 10, "bold")).grid(row=suite_row, column=0, sticky='w', padx=10, pady=(8,2))
    suite_row += 1
    additional_vars_suite, additional_entries_suite = [], []
    def on_change_additional_suite():
        add_dynamic_row_if_needed(additional_vars_suite, additional_entries_suite)
    frame_suite_add = tk.Frame(suite_frame); frame_suite_add.grid(row=suite_row, column=0, sticky='w', padx=10, pady=(0,4))
    suite_row += 1
    for _ in range(MAX_DYNAMIC_FIELDS):
        var = tk.StringVar()
        var.trace_add('write', lambda *_: on_change_additional_suite())
        ent = tk.Entry(frame_suite_add, textvariable=var, width=14)
        additional_vars_suite.append(var)
        additional_entries_suite.append(ent)
    additional_entries_suite[0].grid(row=0, column=0, sticky='w', padx=2, pady=1)

    tk.Label(suite_frame, text="Tankless Water Heater — Suite (100%)", font=("Helvetica", 10, "bold")).grid(row=suite_row, column=0, sticky='w', padx=10, pady=(8,2))
    suite_row += 1
    tankless_var_suite = tk.StringVar(); s_add_entry("Tankless WH (W or breaker A):", tankless_var_suite)

    tk.Label(suite_frame, text="Steamers / Pools / Hot tubs / Spas WH — Suite (100%)", font=("Helvetica", 10, "bold")).grid(row=suite_row, column=0, sticky='w', padx=10, pady=(8,2))
    suite_row += 1
    sps_vars_suite, sps_entries_suite = [], []
    frame_suite_sps = tk.Frame(suite_frame); frame_suite_sps.grid(row=suite_row, column=0, sticky='w', padx=10, pady=(0,4))
    suite_row += 1
    def on_change_sps_suite():
        add_dynamic_row_if_needed(sps_vars_suite, sps_entries_suite)
    for _ in range(MAX_DYNAMIC_FIELDS):
        var = tk.StringVar()
        var.trace_add('write', lambda *_: on_change_sps_suite())
        ent = tk.Entry(frame_suite_sps, textvariable=var, width=14)
        sps_vars_suite.append(var)
        sps_entries_suite.append(ent)
    sps_entries_suite[0].grid(row=0, column=0, sticky='w', padx=2, pady=1)

    # Buttons
    btn_frame = tk.Frame(content); btn_frame.grid(row=row, column=0, sticky='w', padx=10, pady=12)
    tk.Button(btn_frame, text="Calculate Demand", command=calculate_demand).pack(side='left', padx=(0,10))
    tk.Button(btn_frame, text="Generate PDF Report", command=save_pdf_report).pack(side='left')
    # Size the window to fit all initial content before starting the event loop
    root.update_idletasks()
    req_w = content.winfo_reqwidth() + v_scroll.winfo_reqwidth()
    req_h = content.winfo_reqheight()
    root.geometry(f"{req_w}x{req_h}")

    tk.Button(root, text="Help", command=show_help).place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)

    root.mainloop()
