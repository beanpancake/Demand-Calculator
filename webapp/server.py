from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List
import io

app = FastAPI(title="Demand Calculator API")

# ------------------------- Core Calculation -------------------------

# The following helper functions mirror the logic of the desktop tool.

def parse_load(raw, voltage: float) -> float:
    """Return wattage. Values <=500 are treated as breaker amps."""
    try:
        val = float(raw)
    except Exception:
        return 0.0
    if val <= 0:
        return 0.0
    return val * voltage * 0.8 if val <= 500 else val

def range_demand_w(watts: float) -> float:
    if watts <= 0:
        return 0.0
    return 6000.0 if watts <= 12000 else 6000.0 + 0.4 * (watts - 12000.0)

def heat_demand_w(heat_w: float) -> float:
    return heat_w if heat_w <= 10000 else 10000 + 0.75 * (heat_w - 10000)

def additional_factored_w(total_additional_w: float, has_range: bool) -> float:
    if total_additional_w <= 0:
        return 0.0
    if has_range:
        return 0.25 * total_additional_w
    return total_additional_w if total_additional_w <= 6000 else 6000 + 0.25 * (total_additional_w - 6000)

def basic_load_w(area_m2: float) -> float:
    """5000 W for first 90 m² + 1000 W per additional 90 m² (or portion)."""
    import math
    return 5000.0 if area_m2 <= 90 else 5000.0 + 1000.0 * math.ceil((area_m2 - 90.0) / 90.0)

class CalcRequest(BaseModel):
    voltage: float = 240.0
    area: float
    area_is_sqft: bool = False
    range: float = 0.0
    heat: float = 0.0
    ac: float = 0.0
    evse: float = 0.0
    additional: List[float] = []

class CalcResponse(BaseModel):
    basic: float
    range_demand: float
    heat_demand: float
    ac: float
    evse: float
    additional: float
    total: float

def calculate_core(req: CalcRequest) -> CalcResponse:
    voltage = req.voltage
    area_m2 = req.area * 0.092903 if req.area_is_sqft else req.area

    range_w = parse_load(req.range, voltage)
    heat_w = parse_load(req.heat, voltage)
    ac_w = parse_load(req.ac, voltage)
    evse_w = parse_load(req.evse, voltage)
    additional_w = [parse_load(v, voltage) for v in req.additional]

    base = basic_load_w(area_m2)
    range_d = range_demand_w(range_w)
    heat_d = heat_demand_w(heat_w)
    add_factored = additional_factored_w(sum(w for w in additional_w if w > 1500), range_w > 0)

    total = base + range_d + heat_d + ac_w + evse_w + add_factored

    return CalcResponse(
        basic=base,
        range_demand=range_d,
        heat_demand=heat_d,
        ac=ac_w,
        evse=evse_w,
        additional=add_factored,
        total=total,
    )

# ------------------------------ API --------------------------------

@app.post("/calculate", response_model=CalcResponse)
def calculate_endpoint(req: CalcRequest):
    return calculate_core(req)

# ----------------------------- PDF ---------------------------------

def _pdf_from_lines(lines: List[str]) -> bytes:
    """Create a very small PDF containing the provided lines."""
    content_text = "\n".join(lines).replace("(", r"\(").replace(")", r"\)")
    content_stream = f"BT /F1 12 Tf 50 750 Td ({content_text}) Tj ET"
    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        "2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n",
        "4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
        f"5 0 obj<< /Length {len(content_stream)} >>stream\n{content_stream}\nendstream endobj\n",
    ]
    buf = io.BytesIO()
    buf.write(b"%PDF-1.1\n")
    offsets = [0]
    for obj in objects:
        offsets.append(buf.tell())
        buf.write(obj.encode("latin-1"))
    xref_start = buf.tell()
    buf.write(f"xref\n0 {len(offsets)}\n".encode())
    buf.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.write(f"{off:010d} 00000 n \n".encode())
    buf.write(f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n".encode())
    buf.write(b"startxref\n")
    buf.write(f"{xref_start}\n".encode())
    buf.write(b"%%EOF")
    return buf.getvalue()

@app.post("/report")
def report_endpoint(req: CalcRequest):
    res = calculate_core(req)
    lines = ["Demand Calculation Report", f"Total: {res.total:.0f} W"]
    pdf_bytes = _pdf_from_lines(lines)
    return Response(pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=report.pdf"})
