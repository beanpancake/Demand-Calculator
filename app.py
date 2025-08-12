from flask import Flask, render_template, request
from calculator.core import parse_load, calculate_demand

app = Flask(__name__)


def _parse_list(raw: str, voltage: float):
    """Parse comma separated loads using parse_load."""
    items = []
    for part in raw.split(','):
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
            area = float(request.form.get('area', '0'))
            range_w = parse_load(request.form.get('range', ''), voltage)
            heat_w = parse_load(request.form.get('heat', ''), voltage)
            ac_w = parse_load(request.form.get('ac', ''), voltage)
            evse_w = parse_load(request.form.get('evse', ''), voltage)
            interlocked = bool(request.form.get('interlocked'))
            add_all = _parse_list(request.form.get('additional', ''), voltage)
            add_list = [w for w in add_all if w > 1500]
            tankless_w = parse_load(request.form.get('tankless', ''), voltage)
            sps_all = _parse_list(request.form.get('sps', ''), voltage)

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
            )
            result = results
        except Exception as exc:
            error = str(exc)
    return render_template('index.html', result=result, error=error)


if __name__ == '__main__':
    app.run()
