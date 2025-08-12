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
from reportlab.platypus import Table, TableStyle
import math

LOGO_PATH = "logo.png"
MAX_DYNAMIC_FIELDS = 10

last_calc_data = None  # (inputs, results, debug)

# ----------------------------- Helpers -----------------------------

def parse_load(raw, voltage):
    """If value ≤500: treat as breaker amps (A*V*0.8).

    Values greater than 500 are treated as watts. Blank, invalid, or
    non‑positive values return 0.
    """
    s = raw.strip()
    if not s:
        return 0.0
    try:
        val = float(s)
        if val <= 0:
            return 0.0
        if val <= 500:
            return val * voltage * 0.8
        return val
    except Exception:
        return 0.0

def range_demand_w(watts):
    """CEC: single range = 6000 W + 40% over 12 kW."""
    if watts <= 0: return 0.0
    return 6000.0 if watts <= 12000 else 6000.0 + 0.4 * (watts - 12000.0)

def heat_demand_w(heat_w):
    """Residential space heat: first 10 kW @100%, remainder @75%."""
    return heat_w if heat_w <= 10000 else 10000 + 0.75 * (heat_w - 10000)

def additional_factored_w(total_additional_w, has_range):
    """
    8-200(1)(a)(vii) loads >1500 W:
    - If range: 25% of sum.
    - If no range: 100% of first 6000 W + 25% remainder.
    """
    if total_additional_w <= 0: return 0.0
    if has_range:
        return 0.25 * total_additional_w
    return total_additional_w if total_additional_w <= 6000 else 6000 + 0.25 * (total_additional_w - 6000)

def basic_load_w(area_m2):
    """8-200(1)(a)(i)(ii): 5000 W first 90 m² + 1000 W per additional 90 m² (or portion)."""
    return 5000.0 if area_m2 <= 90 else 5000.0 + 1000.0 * math.ceil((area_m2 - 90.0) / 90.0)

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
    debug = []

    try:
        voltage = float(voltage_var.get())
        area_main_raw = float(area_var.get())
        area_main = area_main_raw * 0.092903 if area_sqft_var.get() else area_main_raw

        # Main inputs
        range_main_w = parse_load(range_var.get(), voltage)
        heat_main_w  = parse_load(heat_var.get(), voltage)
        ac_main_w    = parse_load(ac_var.get(), voltage)
        evse_main_w  = parse_load(evse_var.get(), voltage)
        interlocked  = bool(interlock_var.get())

        add_main_all = to_watts_list(additional_vars_main, voltage)
        add_main_list_w = [w for w in add_main_all if w > 1500]  # only >1500 W
        tankless_main_w = parse_load(tankless_var_main.get(), voltage)  # single input @100%
        sps_main_all = to_watts_list(sps_vars_main, voltage)            # list @100%

        debug.append(f"Voltage: {voltage:.0f} V")
        if area_sqft_var.get():
            debug.append(f"Main area input: {area_main_raw:.1f} ft² -> {area_main:.1f} m²")
        else:
            debug.append(f"Main area: {area_main:.1f} m²")

        base_main_w = basic_load_w(area_main)
        debug.append(f"Basic load (main): {base_main_w:.0f} W")

        heat_main_d = heat_demand_w(heat_main_w)
        if interlocked:
            debug.append(f"Heat raw: {heat_main_w:.0f} -> demand: {heat_main_d:.0f} W")
            debug.append(f"AC raw: {ac_main_w:.0f} W")
            heat_ac_main_d = max(heat_main_d, ac_main_w)
            ac_main_d = 0.0
            debug.append(f"Interlocked: using max(heat_demand, AC) = {heat_ac_main_d:.0f} W")
        else:
            ac_main_d = ac_main_w
            heat_ac_main_d = heat_main_d + ac_main_d
            debug.append(f"Heat raw: {heat_main_w:.0f} -> demand: {heat_main_d:.0f} W")
            debug.append(f"AC (100%): {ac_main_d:.0f} W")

        range_main_d = range_demand_w(range_main_w)
        debug.append(f"Range raw: {range_main_w:.0f} -> demand: {range_main_d:.0f} W")

        add_main_sum = sum(add_main_list_w)
        add_main_d = additional_factored_w(add_main_sum, range_main_w > 0)
        debug.append(f"Additional >1500 W (main) raw sum: {add_main_sum:.0f} -> factored: {add_main_d:.0f} W")

        # 100% categories
        tankless_main_d = tankless_main_w
        sps_main_sum = sum(sps_main_all)
        sps_main_d = sps_main_sum
        evse_main_d = evse_main_w

        debug.append(f"Tankless WH (main) 100%: {tankless_main_d:.0f} W")
        debug.append(f"Steamers/Pools/Spas (main) 100% sum: {sps_main_d:.0f} W")
        debug.append(f"EVSE (main) 100%: {evse_main_d:.0f} W")

        # 8-200(1)(a) for main
        main_a = base_main_w + range_main_d + add_main_d + tankless_main_d + sps_main_d + heat_ac_main_d + evse_main_d
        # 8-200(1)(b) for main
        main_b = 24000.0 if area_main >= 80.0 else 14400.0

        debug.append(f"Main total per 8-200(1)(a): {main_a:.0f} W")
        debug.append(f"Main total per 8-200(1)(b): {main_b:.0f} W")

        main_total = max(main_a, main_b)
        debug.append(f"Main chosen total: {main_total:.0f} W")

        total_final = main_total

        # ---------------- Suite ----------------
        suite_included = bool(suite_var.get())
        suite_inputs = {}
        if suite_included:
            debug.append("\n--- Suite ---")
            area_suite_raw = float(suite_area_var.get())
            area_suite = area_suite_raw * 0.092903 if area_sqft_var.get() else area_suite_raw
            range_suite_w = parse_load(suite_range_var.get(), voltage)
            evse_suite_w  = parse_load(suite_evse_var.get(), voltage)

            add_suite_all = to_watts_list(additional_vars_suite, voltage)
            add_suite_list_w = [w for w in add_suite_all if w > 1500]
            tankless_suite_w = parse_load(tankless_var_suite.get(), voltage)
            sps_suite_all = to_watts_list(sps_vars_suite, voltage)

            if area_sqft_var.get():
                debug.append(f"Suite area input: {area_suite_raw:.1f} ft² -> {area_suite:.1f} m²")
            else:
                debug.append(f"Suite area: {area_suite:.1f} m²")

            base_suite_w = basic_load_w(area_suite)
            range_suite_d = range_demand_w(range_suite_w)
            add_suite_sum = sum(add_suite_list_w)
            add_suite_d = additional_factored_w(add_suite_sum, range_suite_w > 0)
            tankless_suite_d = tankless_suite_w
            sps_suite_sum = sum(sps_suite_all)
            sps_suite_d = sps_suite_sum

            suite_core = base_suite_w + range_suite_d + add_suite_d + tankless_suite_d + sps_suite_d
            debug.append(f"Basic (suite): {base_suite_w:.0f} W")
            debug.append(f"Range (suite) raw: {range_suite_w:.0f} -> demand: {range_suite_d:.0f} W")
            debug.append(f"Additional >1500 W (suite) raw sum: {add_suite_sum:.0f} -> factored: {add_suite_d:.0f} W")
            debug.append(f"Tankless (suite) 100%: {tankless_suite_d:.0f} W")
            debug.append(f"Steamers/Pools/Spas (suite) 100% sum: {sps_suite_d:.0f} W")

            # Remove main heat/AC/EVSE to form main_core
            main_core = main_total - heat_ac_main_d - evse_main_d
            debug.append(f"Main core (excl heat/AC/EVSE): {main_core:.0f} W")
            debug.append(f"Suite core (excl heat/AC/EVSE): {suite_core:.0f} W")

            heavier = max(main_core, suite_core)
            lighter = min(main_core, suite_core)
            combined_core = heavier + 0.65 * lighter
            debug.append(f"Two-unit combination: {heavier:.0f} + 65%*{lighter:.0f} = {combined_core:.0f} W")

            total_final = combined_core + heat_ac_main_d + evse_main_d + evse_suite_w
            debug.append(f"+ Add back heat/AC (main) + EVSE (main+suite): {heat_ac_main_d + evse_main_d + evse_suite_w:.0f} W")
            debug.append(f"Total with suite: {total_final:.0f} W")

            suite_inputs = {
                "Suite Area (m²)": area_suite,
            }
            if area_sqft_var.get():
                suite_inputs["Suite Area (ft²)"] = area_suite_raw
            suite_inputs.update({
                "Suite Range (W)": range_suite_w if range_suite_w > 0 else "Not applicable",
                "Suite EVSE (W)": evse_suite_w if evse_suite_w > 0 else "Not applicable",
                "Suite Additional Loads Raw (W)": sum(add_suite_list_w) if add_suite_list_w else "Not applicable",
                "Suite Additional Loads Factored (W)": add_suite_d if add_suite_sum > 0 else "Not applicable",
                "Suite Tankless WH (W)": int(tankless_suite_w) if tankless_suite_w > 0 else "Not applicable",
                "Suite Steamers/Pools/Spas (W)": ", ".join(str(int(x)) for x in sps_suite_all) if sps_suite_all else "Not applicable",
            })

        # ---------------- Prepare PDF data ----------------
        inputs = {
            "Voltage (V)": voltage,
            "Main Area (m²)": area_main,
        }
        if area_sqft_var.get():
            inputs["Main Area (ft²)"] = area_main_raw
        inputs.update({
            "Range (W)": range_main_w if range_main_w > 0 else "Not applicable",
            "Heating (W)": heat_main_w if heat_main_w > 0 else "Not applicable",
            "AC (W)": ac_main_w if ac_main_w > 0 else "Not applicable",
            "Interlocked (Heat/AC)": "Yes" if interlocked else "No",
            "EVSE (W)": evse_main_w if evse_main_w > 0 else "Not applicable",
            "Additional Loads >1500W (W)": ", ".join(str(int(x)) for x in add_main_list_w) if add_main_list_w else "Not applicable",
            "Tankless WH (W) [100%]": int(tankless_main_w) if tankless_main_w > 0 else "Not applicable",
            "Steamers/Pools/Spas WH (W) [100%]": ", ".join(str(int(x)) for x in sps_main_all) if sps_main_all else "Not applicable",
            "Suite Included": "Yes" if suite_included else "No"
        })
        if suite_included:
            inputs.update(suite_inputs)

        results = {"Final Calculated Load (W)": f"{total_final:.0f}"}

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

    def draw_table_section(title, rows):
        nonlocal y
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, y, title)
        y -= 18
        table_data = [["Item", "Value"]] + rows
        table = Table(table_data, colWidths=[200, width - 2*margin - 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        tw, th = table.wrapOn(c, width - 2*margin, y)
        if y - th < margin:
            c.showPage(); y = height - margin - 18
            c.setFont("Helvetica-Bold", 13)
            c.drawString(margin, y, title)
            y -= 18
            tw, th = table.wrapOn(c, width - 2*margin, y)
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

if __name__ == "__main__":
    # ----------------------------- UI Setup -----------------------------

    root = tk.Tk()
    root.title("CEC Single Dwelling Demand Calculator (CEC 2024)")

    # Scrollable content container
    canvas = tk.Canvas(root)
    v_scroll = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=v_scroll.set)
    v_scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    content = tk.Frame(canvas)
    canvas.create_window((0, 0), window=content, anchor="nw")

    def _on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    content.bind("<Configure>", _on_frame_configure)

    # Mouse wheel scrolling
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
    canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

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

    root.mainloop()
