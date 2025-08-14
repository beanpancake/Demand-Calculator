from flask import Flask, render_template, request
from flask import Flask, render_template, request
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


@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    error = None
    if request.method == 'POST':
        try:
            voltage = float(request.form.get('voltage', '0'))

            area_raw = float(request.form.get('area', '0'))
            area_unit = request.form.get('area_unit', 'm2')
            area = area_raw * 0.092903 if area_unit == 'ft2' else area_raw

            range_w = parse_load(request.form.get('range', ''), voltage)
            heat_w = parse_load(request.form.get('heat', ''), voltage)
            ac_w = parse_load(request.form.get('ac', ''), voltage)
            evse_w = parse_load(request.form.get('evse', ''), voltage)
            interlocked = bool(request.form.get('interlocked'))

            add_all = _parse_list(request.form.getlist('additional'), voltage)
            add_list = [w for w in add_all if w > 1500]
            tankless_w = parse_load(request.form.get('tankless', ''), voltage)
            sps_all = _parse_list(request.form.getlist('sps'), voltage)

            suite = None
            if request.form.get('suite'):
                suite_area_raw = float(request.form.get('suite_area', '0'))
                suite_area = suite_area_raw * 0.092903 if area_unit == 'ft2' else suite_area_raw
                suite_range_w = parse_load(request.form.get('suite_range', ''), voltage)
                suite_evse_w = parse_load(request.form.get('suite_evse', ''), voltage)
                suite_add_all = _parse_list(request.form.getlist('suite_additional'), voltage)
                suite_add_list = [w for w in suite_add_all if w > 1500]
                suite_tankless_w = parse_load(request.form.get('suite_tankless', ''), voltage)
                suite_sps_all = _parse_list(request.form.getlist('suite_sps'), voltage)
                suite = {
                    'area': suite_area,
                    'range_w': suite_range_w,
                    'evse_w': suite_evse_w,
                    'add_loads': suite_add_list,
                    'tankless_w': suite_tankless_w,
                    'sps': suite_sps_all,
                }
                if area_unit == 'ft2':
                    suite['area_ft2'] = suite_area_raw

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
                area_main_ft2=area_raw if area_unit == 'ft2' else None,
                suite=suite,
            )
            result = results
        except Exception as exc:
            error = str(exc)
    return render_template('index.html', result=result, error=error)


if __name__ == '__main__':
    app.run()
