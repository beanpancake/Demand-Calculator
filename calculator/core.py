import math
from typing import List, Dict, Tuple, Optional, Any

__all__ = [
    "parse_load",
    "range_demand_w",
    "heat_demand_w",
    "additional_factored_w",
    "basic_load_w",
    "calculate_demand",
]


def parse_load(raw: str, voltage: float) -> float:
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


def range_demand_w(watts: float) -> float:
    """CEC: single range = 6000 W + 40% over 12 kW."""
    if watts <= 0:
        return 0.0
    return 6000.0 if watts <= 12000 else 6000.0 + 0.4 * (watts - 12000.0)


def heat_demand_w(heat_w: float) -> float:
    """Residential space heat: first 10 kW @100%, remainder @75%."""
    return heat_w if heat_w <= 10000 else 10000 + 0.75 * (heat_w - 10000)


def additional_factored_w(total_additional_w: float, has_range: bool) -> float:
    """8-200(1)(a)(vii) loads >1500 W factor."""
    if total_additional_w <= 0:
        return 0.0
    if has_range:
        return 0.25 * total_additional_w
    return (
        total_additional_w
        if total_additional_w <= 6000
        else 6000 + 0.25 * (total_additional_w - 6000)
    )


def basic_load_w(area_m2: float) -> float:
    """8-200(1)(a)(i)(ii): 5000 W first 90 m² + 1000 W per additional 90 m²."""
    return 5000.0 if area_m2 <= 90 else 5000.0 + 1000.0 * math.ceil((area_m2 - 90.0) / 90.0)


def calculate_demand(
    voltage: float,
    area_main: float,
    range_main_w: float,
    heat_main_w: float,
    ac_main_w: float,
    evse_main_w: float,
    interlocked: bool,
    add_main_list_w: List[float],
    tankless_main_w: float,
    sps_main_all: List[float],
    area_main_ft2: Optional[float] = None,
    suite: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Pure demand calculation.

    Parameters are primitive types; areas are in m². Optionally provide
    area_main_ft2 and suite dict containing suite data with keys:
    ``area`` (m²), optional ``area_ft2`` (float), ``range_w``, ``evse_w``,
    ``add_loads`` (list of >1500 W values), ``tankless_w`` and ``sps`` (list).
    """

    debug: List[str] = []

    debug.append(f"Voltage: {voltage:.0f} V")
    if area_main_ft2 is not None:
        debug.append(
            f"Main area input: {area_main_ft2:.1f} ft² -> {area_main:.1f} m²"
        )
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
        debug.append(
            f"Interlocked: using max(heat_demand, AC) = {heat_ac_main_d:.0f} W"
        )
    else:
        ac_main_d = ac_main_w
        heat_ac_main_d = heat_main_d + ac_main_d
        debug.append(f"Heat raw: {heat_main_w:.0f} -> demand: {heat_main_d:.0f} W")
        debug.append(f"AC (100%): {ac_main_d:.0f} W")

    range_main_d = range_demand_w(range_main_w)
    debug.append(
        f"Range raw: {range_main_w:.0f} -> demand: {range_main_d:.0f} W"
    )

    add_main_sum = sum(add_main_list_w)
    add_main_d = additional_factored_w(add_main_sum, range_main_w > 0)
    debug.append(
        f"Additional >1500 W (main) raw sum: {add_main_sum:.0f} -> factored: {add_main_d:.0f} W"
    )

    tankless_main_d = tankless_main_w
    sps_main_sum = sum(sps_main_all)
    sps_main_d = sps_main_sum
    evse_main_d = evse_main_w

    debug.append(f"Tankless WH (main) 100%: {tankless_main_d:.0f} W")
    debug.append(
        f"Steamers/Pools/Spas (main) 100% sum: {sps_main_d:.0f} W"
    )
    debug.append(f"EVSE (main) 100%: {evse_main_d:.0f} W")

    main_a = (
        base_main_w
        + range_main_d
        + add_main_d
        + tankless_main_d
        + sps_main_d
        + heat_ac_main_d
        + evse_main_d
    )
    main_b = 24000.0 if area_main >= 80.0 else 14400.0

    debug.append(f"Main total per 8-200(1)(a): {main_a:.0f} W")
    debug.append(f"Main total per 8-200(1)(b): {main_b:.0f} W")

    main_total = max(main_a, main_b)
    debug.append(f"Main chosen total: {main_total:.0f} W")

    total_final = main_total

    suite_inputs: Dict[str, Any] = {}
    if suite:
        debug.append("\n--- Suite ---")
        area_suite = suite.get("area", 0.0)
        area_suite_ft2 = suite.get("area_ft2")
        range_suite_w = suite.get("range_w", 0.0)
        evse_suite_w = suite.get("evse_w", 0.0)
        add_suite_list_w = suite.get("add_loads", [])
        tankless_suite_w = suite.get("tankless_w", 0.0)
        sps_suite_all = suite.get("sps", [])

        if area_suite_ft2 is not None:
            debug.append(
                f"Suite area input: {area_suite_ft2:.1f} ft² -> {area_suite:.1f} m²"
            )
        else:
            debug.append(f"Suite area: {area_suite:.1f} m²")

        base_suite_w = basic_load_w(area_suite)
        range_suite_d = range_demand_w(range_suite_w)
        add_suite_sum = sum(add_suite_list_w)
        add_suite_d = additional_factored_w(add_suite_sum, range_suite_w > 0)
        tankless_suite_d = tankless_suite_w
        sps_suite_sum = sum(sps_suite_all)
        sps_suite_d = sps_suite_sum

        debug.append(f"Basic (suite): {base_suite_w:.0f} W")
        debug.append(
            f"Range (suite) raw: {range_suite_w:.0f} -> demand: {range_suite_d:.0f} W"
        )
        debug.append(
            f"Additional >1500 W (suite) raw sum: {add_suite_sum:.0f} -> factored: {add_suite_d:.0f} W"
        )
        debug.append(
            f"Tankless (suite) 100%: {tankless_suite_d:.0f} W"
        )
        debug.append(
            f"Steamers/Pools/Spas (suite) 100% sum: {sps_suite_d:.0f} W"
        )

        suite_core = (
            base_suite_w
            + range_suite_d
            + add_suite_d
            + tankless_suite_d
            + sps_suite_d
        )

        main_core = main_total - heat_ac_main_d - evse_main_d
        debug.append(f"Main core (excl heat/AC/EVSE): {main_core:.0f} W")
        debug.append(f"Suite core (excl heat/AC/EVSE): {suite_core:.0f} W")

        heavier = max(main_core, suite_core)
        lighter = min(main_core, suite_core)
        combined_core = heavier + 0.65 * lighter
        debug.append(
            f"Two-unit combination: {heavier:.0f} + 65%*{lighter:.0f} = {combined_core:.0f} W"
        )

        total_final = combined_core + heat_ac_main_d + evse_main_d + evse_suite_w
        debug.append(
            f"+ Add back heat/AC (main) + EVSE (main+suite): {heat_ac_main_d + evse_main_d + evse_suite_w:.0f} W"
        )
        debug.append(f"Total with suite: {total_final:.0f} W")

        suite_inputs = {
            "Suite Area (m²)": area_suite,
        }
        if area_suite_ft2 is not None:
            suite_inputs["Suite Area (ft²)"] = area_suite_ft2
        suite_inputs.update(
            {
                "Suite Range (W)": range_suite_w if range_suite_w > 0 else "Not applicable",
                "Suite EVSE (W)": evse_suite_w if evse_suite_w > 0 else "Not applicable",
                "Suite Additional Loads Raw (W)": add_suite_sum if add_suite_list_w else "Not applicable",
                "Suite Additional Loads Factored (W)": add_suite_d if add_suite_sum > 0 else "Not applicable",
                "Suite Tankless WH (W)": int(tankless_suite_w) if tankless_suite_w > 0 else "Not applicable",
                "Suite Steamers/Pools/Spas (W)": ", ".join(str(int(x)) for x in sps_suite_all)
                if sps_suite_all
                else "Not applicable",
            }
        )

    inputs: Dict[str, Any] = {
        "Voltage (V)": voltage,
        "Main Area (m²)": area_main,
    }
    if area_main_ft2 is not None:
        inputs["Main Area (ft²)"] = area_main_ft2
    inputs.update(
        {
            "Range (W)": range_main_w if range_main_w > 0 else "Not applicable",
            "Heating (W)": heat_main_w if heat_main_w > 0 else "Not applicable",
            "AC (W)": ac_main_w if ac_main_w > 0 else "Not applicable",
            "Interlocked (Heat/AC)": "Yes" if interlocked else "No",
            "EVSE (W)": evse_main_w if evse_main_w > 0 else "Not applicable",
            "Additional Loads >1500W (W)": ", ".join(
                str(int(x)) for x in add_main_list_w
            )
            if add_main_list_w
            else "Not applicable",
            "Tankless WH (W) [100%]": int(tankless_main_w)
            if tankless_main_w > 0
            else "Not applicable",
            "Steamers/Pools/Spas WH (W) [100%]": ", ".join(
                str(int(x)) for x in sps_main_all
            )
            if sps_main_all
            else "Not applicable",
            "Suite Included": "Yes" if suite else "No",
        }
    )
    if suite:
        inputs.update(suite_inputs)

    results = {"Final Calculated Load (W)": f"{total_final:.0f}"}

    return inputs, results, debug
