from flask import Flask, request, jsonify
from calculator.core import parse_load, calculate_demand

app = Flask(__name__)


def _parse_list(values, voltage: float):
    """Parse a list of string load entries using parse_load."""
    if isinstance(values, str):
        values = [values]
    items = []
    for part in values:
        part = part.strip()
        if part:
            items.append(parse_load(part, voltage))
    return items


@app.get("/")
def index():
    return "Demand Calculator API"


@app.post("/api/calculate")
def api_calculate():
    data = request.get_json(force=True) or {}
    try:
        voltage = float(data.get("voltage", 0))

        area_raw = float(data.get("area", 0))
        area_unit = data.get("area_unit", "m2")
        area = area_raw * 0.092903 if area_unit == "ft2" else area_raw

        range_w = parse_load(data.get("range", ""), voltage)
        heat_w = parse_load(data.get("heat", ""), voltage)
        ac_w = parse_load(data.get("ac", ""), voltage)
        evse_w = parse_load(data.get("evse", ""), voltage)
        interlocked = bool(data.get("interlocked"))

        add_all = _parse_list(data.get("additional", []), voltage)
        add_list = [w for w in add_all if w > 1500]
        tankless_w = parse_load(data.get("tankless", ""), voltage)
        sps_all = _parse_list(data.get("sps", []), voltage)

        suite_data = data.get("suite")
        suite = None
        if suite_data:
            suite_area_raw = float(suite_data.get("area", 0))
            suite_area = (
                suite_area_raw * 0.092903 if area_unit == "ft2" else suite_area_raw
            )
            suite_range_w = parse_load(suite_data.get("range", ""), voltage)
            suite_evse_w = parse_load(suite_data.get("evse", ""), voltage)
            suite_add_all = _parse_list(suite_data.get("additional", []), voltage)
            suite_add_list = [w for w in suite_add_all if w > 1500]
            suite_tankless_w = parse_load(suite_data.get("tankless", ""), voltage)
            suite_sps_all = _parse_list(suite_data.get("sps", []), voltage)
            suite = {
                "area": suite_area,
                "range_w": suite_range_w,
                "evse_w": suite_evse_w,
                "add_loads": suite_add_list,
                "tankless_w": suite_tankless_w,
                "sps": suite_sps_all,
            }
            if area_unit == "ft2":
                suite["area_ft2"] = suite_area_raw

        inputs, results, debug = calculate_demand(
            voltage=voltage,
            area_main=area,
            range_main_w=range_w,
            heat_main_w=heat_w,
            ac_main_w=ac_w,
            evse_main_w=evse_w,
            interlocked=interlocked,
            add_main_list_w=add_list,
            tankless_main_w=tankless_w,
            sps_main_all=sps_all,
            area_main_ft2=area_raw if area_unit == "ft2" else None,
            suite=suite,
        )
        return jsonify({"inputs": inputs, "result": results, "debug": debug})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


if __name__ == '__main__':
    app.run()
