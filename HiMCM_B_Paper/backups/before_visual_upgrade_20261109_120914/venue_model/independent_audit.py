"""Independent audit of the Fremont/Honolulu scenario outputs.

This script does not import the venue solver or its evaluator.  Psychrometric
states are independently reconstructed using PsychroLib and the ASHRAE SI
enthalpy coefficients; SET is evaluated directly with pythermalcomfort.  The
small Honolulu integer problem is solved by exhaustive enumeration.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import csv
import copy
from pathlib import Path

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/himcm-independent-numba")
import psychrolib
from pythermalcomfort.models import set_tmp

ROOT = Path(__file__).resolve().parent
psychrolib.SetUnitSystem(psychrolib.SI)
CHECKS: dict[str, bool] = {}


def check(label: str, condition: bool) -> None:
    CHECKS[label] = bool(condition)
    if not condition:
        raise AssertionError(label)


def close(label: str, left: float, right: float, atol=1e-7, rtol=1e-9) -> None:
    check(label, math.isclose(float(left), float(right), abs_tol=atol, rel_tol=rtol))


def set_direct(t, tr, speed, rh, econ):
    value = float(set_tmp(tdb=t, tr=tr, v=speed, rh=100 * rh,
                          met=econ["met"], clo=econ["clo"],
                          p_atm=101325., position=econ["position"],
                          limit_inputs=True, round_output=False).set)
    if not math.isfinite(value):
        raise AssertionError("A local SET input is outside its applicability domain")
    return value


def thermal_independent(venue, devices, econ):
    t, rh, tr = venue["t_c"], venue["rh"], venue["tr_c"]
    w0 = float(psychrolib.GetHumRatioFromRelHum(t, rh, 101325.))
    h0 = 1006 * t + w0 * (2501000 + 1860 * t)
    twb = float(psychrolib.GetTWetBulbFromRelHum(t, rh, 101325.))
    s0 = set_direct(t, tr, venue["baseline_v"], rh, econ)
    d0 = max(s0 - econ["set_reference_c"], 0.)
    result = {"baseline_set_c": s0, "baseline_residual_c": d0,
              "wet_bulb_c": twb, "devices": {}, "local": []}
    for key in "ABC":
        device = devices[key]
        drop = min(device["epsilon"] * max(t - twb, 0.), device["max_drop_c"])
        tout = t - drop
        wout = (h0 - 1006 * tout) / (2501000 + 1860 * tout)
        # Keeping A's exact ambient state avoids a spurious roundoff water flow.
        if key == "A":
            wout = w0
        residuals = []
        reliefs = []
        for strip, (beta, reference_speed) in enumerate(zip(device["beta"],
                                                            device["v_reference_m_s"]), 1):
            speed = venue["baseline_v"] + reference_speed - .2
            w = (1 - beta) * w0 + beta * wout
            temp = (h0 - 2501000 * w) / (1006 + 1860 * w)
            relhum = float(psychrolib.GetRelHumFromHumRatio(temp, w, 101325.))
            theta = set_direct(temp, tr, speed, relhum, econ)
            discomfort = max(theta - econ["set_reference_c"], 0.)
            residuals.append(discomfort)
            reliefs.append(d0 - discomfort)
            result["local"].append({"device": key, "strip": strip, "beta": beta,
                                    "t_c": temp, "rh": relhum, "v_m_s": speed,
                                    "set_c": theta, "outlet_t_c": tout})
            check(f"{venue['name']}_{key}_{strip}_gas_phase", 0 <= relhum <= 1 + 1e-10)
            close(f"{venue['name']}_{key}_{strip}_enthalpy", 1006 * temp + w * (2501000 + 1860 * temp), h0)
        average_d = sum(residuals) / 3
        water = 3600 * device["supply_kg_da_s"] * (wout - w0) * econ["make_up_factor"] / 1000
        result["devices"][key] = {"residual_c": average_d,
                                  "benefit_c": d0 - average_d,
                                  "strip_benefit_c": reliefs,
                                  "water_m3_h": max(water, 0.), "outlet_t_c": tout}
    return result


def mean_people(venue, econ):
    return [sum(hour[z] for hour in venue["people_by_hour"]) * econ["time_step_h"] / econ["period_h"]
            for z in range(len(venue["areas_m2"]))]


def evaluate_independent(venue, thermal, x, devices, econ):
    areas, people = venue["areas_m2"], mean_people(venue, econ)
    total_a, total_n = sum(areas), sum(people)
    count = [sum(row[k] for row in x) for k in range(3)]
    occupied, relief = 0., 0.
    for z, row in enumerate(x):
        covered = sum(row[k] * devices[key]["footprint_m2"] for k, key in enumerate("ABC"))
        if covered > areas[z] + 1e-8:
            raise AssertionError("Full device footprints overlap or exceed the zone")
        density = people[z] / areas[z]
        occupied += density * covered
        relief += density * sum(row[k] * devices[key]["footprint_m2"] *
                                thermal["devices"][key]["benefit_c"] for k, key in enumerate("ABC"))
    power = sum(count[k] * devices[key]["power_kw"] for k, key in enumerate("ABC"))
    water_h = sum(count[k] * thermal["devices"][key]["water_m3_h"] for k, key in enumerate("ABC"))
    capital = sum(count[k] * devices[key]["capital_usd"] for k, key in enumerate("ABC"))
    maintenance = sum(count[k] * devices[key]["maintenance_usd_year"] for k, key in enumerate("ABC"))
    r, life = econ["discount_rate"], econ["life_year"]
    crf = r * (1 + r) ** life / ((1 + r) ** life - 1)
    annual_energy, annual_water = power * econ["hours_year"], water_h * econ["hours_year"]
    components = {"ownership": crf * capital, "maintenance": maintenance,
                  "electricity": econ["electricity_usd_kwh"] * annual_energy,
                  "water": econ["water_usd_m3"] * annual_water}
    return {"x": x, "counts": count, "coverage": occupied / total_n,
            "mean_benefit_c": relief / total_n,
            "mean_residual_c": thermal["baseline_residual_c"] - relief / total_n,
            "service_person_c_h": relief * econ["period_h"],
            "energy_kwh": power * econ["period_h"],
            "efficiency": relief / power if power else None,
            "water_m3": water_h * econ["period_h"],
            "energy_kwh_year": annual_energy, "water_m3_year": annual_water,
            "floor_loss": sum(count[k] * devices[key]["floor_clearance_m2"] for k, key in enumerate("ABC")) / total_a,
            "annual_cost_usd": sum(components.values()), "components": components,
            "power_kw": power,
            "covered_person_hours": occupied * econ["period_h"],
            "service_by_hour_person_c_h": [econ["time_step_h"] * sum(hour[z] / areas[z] * sum(
                x[z][k] * devices[key]["footprint_m2"] * thermal["devices"][key]["benefit_c"]
                for k, key in enumerate("ABC")) for z in range(len(areas))) for hour in venue["people_by_hour"]]}


def feasible(venue, row, required_relief=1.5):
    return (row["coverage"] >= .8 - 1e-10 and row["mean_benefit_c"] >= required_relief - 1e-10
            and row["floor_loss"] <= .035 + 1e-10
            and row["energy_kwh_year"] <= 30 * sum(venue["areas_m2"]) + 1e-10)


def compare_plan(label, actual, expected):
    for key in ("coverage", "mean_benefit_c", "mean_residual_c", "service_person_c_h",
                "energy_kwh", "water_m3", "energy_kwh_year", "water_m3_year",
                "floor_loss", "annual_cost_usd", "power_kw", "covered_person_hours"):
        close(f"{label}_{key}", actual[key], expected[key])
    if expected["efficiency"] is not None:
        close(f"{label}_efficiency", actual["efficiency"], expected["efficiency"])
    for component in expected["components"]:
        close(f"{label}_cost_{component}", actual["components"][component], expected["components"][component])
    for hour, service in enumerate(expected["service_by_hour_person_c_h"]):
        close(f"{label}_hour_{hour}_service", actual["service_by_hour_person_c_h"][hour], service)


def find_exported_plans(node, prefix=""):
    if isinstance(node, dict):
        if "x" in node and "energy_kwh" in node and "components" in node:
            yield prefix, node
        else:
            for key, value in node.items():
                yield from find_exported_plans(value, f"{prefix}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from find_exported_plans(value, f"{prefix}[{i}]")


def enumerate_small(venue, th, devices, econ):
    area = venue["areas_m2"][0]
    rows = []
    for counts in itertools.product(*(range(math.floor(area / devices[k]["footprint_m2"]) + 1) for k in "ABC")):
        if sum(counts[i] * devices[k]["footprint_m2"] for i, k in enumerate("ABC")) <= area + 1e-9:
            rows.append(evaluate_independent(venue, th, [list(counts)], devices, econ))
    return rows


def read_csv(name):
    with (ROOT / name).open() as stream:
        return list(csv.DictReader(stream))


def audit_sensitivities(inputs, results, audit):
    venues, devices, econ = inputs["venues"], inputs["devices"], inputs["common"]
    thermal = {key: thermal_independent(venue, devices, econ) for key, venue in venues.items()}
    small = enumerate_small(venues["Honolulu"], thermal["Honolulu"], devices, econ)
    nominal_feasible = [row for row in small if feasible(venues["Honolulu"], row)]
    csv_counts = {}
    rows = read_csv("cost_sensitivity.csv")
    csv_counts["cost_sensitivity"] = len(rows)
    check("price_grid_has_243_per_venue", all(sum(row["venue"] == key for row in rows) == 243 for key in venues))
    for i, row in enumerate(rows):
        key = row["venue"]
        check(f"price_{i}_certificate_status", int(row["status"]) == 0 and float(row["mip_gap"]) <= 1e-8)
        def price(plan):
            ownership = sum(plan["counts"][j] * devices[k]["capital_usd"] * float(row[f"capital_{k}"])
                            for j, k in enumerate("ABC")) * inputs["crf"]
            return (ownership + plan["components"]["maintenance"] +
                    float(row["electricity"]) * plan["components"]["electricity"] +
                    float(row["water"]) * plan["components"]["water"])
        selected = evaluate_independent(venues[key], thermal[key], json.loads(row["x"]), devices, econ)
        check(f"price_{i}_physical_feasibility", feasible(venues[key], selected))
        close(f"price_{i}_cost_accounting", row["annual_cost_usd"], price(selected))
        if key == "Honolulu":
            close(f"price_{i}_Honolulu_exhaustive_minimum", row["annual_cost_usd"], min(price(plan) for plan in nominal_feasible))
    for filename in ("policy_curves.csv", "threshold_sensitivity.csv"):
        rows = read_csv(filename)
        csv_counts[filename[:-4]] = len(rows)
        for i, row in enumerate(rows):
            key, level = row["venue"], float(row["required_relief_c"])
            candidates = [plan for plan in small if feasible(venues[key], plan, level)] if key == "Honolulu" else None
            if int(row["status"]) == 2:
                if key == "Honolulu":
                    check(f"{filename}_{i}_infeasible_exhaustive", not candidates)
                continue
            selected = evaluate_independent(venues[key], thermal[key], json.loads(row["x"]), devices, econ)
            check(f"{filename}_{i}_feasible", feasible(venues[key], selected, level))
            close(f"{filename}_{i}_cost", row["annual_cost_usd"], selected["annual_cost_usd"])
            close(f"{filename}_{i}_relief", row["attained_relief_c"], selected["mean_benefit_c"])
            if key == "Honolulu":
                close(f"{filename}_{i}_exhaustive_minimum", row["annual_cost_usd"], min(plan["annual_cost_usd"] for plan in candidates))
    rows = read_csv("physical_sensitivity.csv")
    csv_counts["physical_sensitivity"] = len(rows)
    for i, row in enumerate(rows):
        key = row["venue"]
        changed = copy.deepcopy(venues[key])
        changed.update(t_c=float(row["t_c"]), rh=float(row["rh"]), tr_c=float(row["tr_c"]),
                       baseline_v=float(row["background_v"]), name=f"{key}_physical_{i}")
        factor = float(row["total_area_m2"]) / sum(changed["areas_m2"])
        changed["areas_m2"] = [factor * area for area in changed["areas_m2"]]
        response = thermal_independent(changed, devices, econ)
        density = mean_people(changed, econ)
        upper = max(density[z] / area * devices[k]["footprint_m2"] * response["devices"][k]["benefit_c"] /
                    devices[k]["power_kw"] for z, area in enumerate(changed["areas_m2"]) for k in "ABC"
                    if devices[k]["footprint_m2"] <= area)
        close(f"physical_{i}_efficiency_bound", row["efficiency_upper_bound"], upper)
        if key == "Honolulu":
            candidates = [plan for plan in enumerate_small(changed, response, devices, econ) if feasible(changed, plan)]
            check(f"physical_{i}_feasibility_status", bool(candidates) == (int(row["policy_status"]) == 0))
            if candidates:
                close(f"physical_{i}_exhaustive_minimum", row["policy_cost_usd"], min(plan["annual_cost_usd"] for plan in candidates))
        if int(row["policy_status"]) == 0:
            selected = evaluate_independent(changed, response, json.loads(row["policy_x"]), devices, econ)
            check(f"physical_{i}_selected_feasible", feasible(changed, selected))
            close(f"physical_{i}_selected_cost", row["policy_cost_usd"], selected["annual_cost_usd"])
    rows = read_csv("boundary_clipping.csv")
    csv_counts["boundary_clipping"] = len(rows)
    density = sum(mean_people(venues["Honolulu"], econ)) / 60.
    h = econ["period_h"]
    for i, row in enumerate(rows):
        k, available = row["device"], float(row["available_area_m2"])
        device = devices[k]
        remaining = available
        retained = []
        for _ in range(3):
            take = min(device["footprint_m2"] / 3, remaining)
            retained.append(take)
            remaining -= take
        for zone, area in zip(("near", "middle", "far"), retained):
            close(f"clipping_{i}_{zone}_retained", row[f"retained_{zone}_m2"], area)
        u = h * density * sum(area * relief for area, relief in zip(retained, thermal["Honolulu"]["devices"][k]["strip_benefit_c"]))
        energy = h * device["power_kw"]
        water = h * thermal["Honolulu"]["devices"][k]["water_m3_h"]
        for field, value in {"coverage": sum(retained) / available, "service_person_c_h": u,
                             "energy_kwh": energy, "water_m3": water, "efficiency": u / energy,
                             "mean_benefit_c": u / (h * density * available)}.items():
            close(f"clipping_{i}_{field}", row[field], value)
    rows = read_csv("scale_checks.csv")
    csv_counts["scale_checks"] = len(rows)
    for i, row in enumerate(rows):
        factor = int(row["area_multiplier"])
        scaled = copy.deepcopy(venues["Honolulu"])
        scaled["areas_m2"] = [60. * factor]
        scaled["people_by_hour"] = [[n * factor for n in hour] for hour in scaled["people_by_hour"]]
        n = 3 if row["case"] == "Fixed A3" else 3 * factor
        plan = evaluate_independent(scaled, thermal["Honolulu"], [[n, 0, 0]], devices, econ)
        for field in ("coverage", "mean_benefit_c", "service_person_c_h", "energy_kwh", "efficiency"):
            close(f"scaling_{i}_{field}", row[field], plan[field])
    rows = read_csv("density_scaling.csv")
    csv_counts["density_scaling"] = len(rows)
    for i, row in enumerate(rows):
        nominal = results[row["venue"]]["pure_largest_fit"][row["device"]]
        scale = float(row["density_multiplier"])
        close(f"density_{i}_efficiency", row["efficiency"], scale * nominal["efficiency"])
        close(f"density_{i}_coverage", row["coverage"], nominal["coverage"])
        close(f"density_{i}_mean_relief", row["mean_benefit_c"], nominal["mean_benefit_c"])
    rows = read_csv("climate_cross.csv")
    csv_counts["climate_cross"] = len(rows)
    for i, row in enumerate(rows):
        climate = row["climate"]
        if row["case"].startswith("Matched"):
            venue = dict(venues[climate], areas_m2=[120.], people_by_hour=[[48.]] * 4)
        else:
            geometry = row["case"].split()[1]
            venue = dict(venues[geometry])
            for field in ("t_c", "rh", "tr_c", "baseline_v"):
                venue[field] = venues[climate][field]
        k = row["device"]
        x = [[math.floor(area / devices[k]["footprint_m2"]) if device == k else 0 for device in "ABC"]
             for area in venue["areas_m2"]]
        plan = evaluate_independent(venue, thermal[climate], x, devices, econ)
        for field in ("coverage", "mean_benefit_c", "energy_kwh", "service_person_c_h", "efficiency"):
            close(f"climate_cross_{i}_{field}", row[field], plan[field])
    audit["sensitivity_rows_audited"] = csv_counts


def main():
    inputs = json.loads((ROOT / "inputs.json").read_text())
    results = json.loads((ROOT / "results.json").read_text())
    venues, devices, econ = inputs["venues"], inputs["devices"], inputs["common"]
    check("new_venues_only", set(venues) == {"Fremont", "Honolulu"})
    check("standing_response", econ["position"] == "standing" and econ["met"] == 1.2 and econ["clo"] == .5)
    check("honolulu_one_zone", len(venues["Honolulu"]["areas_m2"]) == 1)
    check("fremont_three_zones", len(venues["Fremont"]["areas_m2"]) == 3)
    close("honolulu_area", sum(venues["Honolulu"]["areas_m2"]), 60.)
    close("fremont_area", sum(venues["Fremont"]["areas_m2"]), 8382.)
    check("four_common_policy_requirements", inputs["policy"] == {
        "coverage_min": .8, "mean_relief_min_c": 1.5, "floor_loss_max": .035,
        "annual_energy_cap_kwh_per_m2": 30.})
    audit = {"method": __doc__, "venues": {}}
    for key, venue in venues.items():
        th = thermal_independent(venue, devices, econ)
        stored = results[key]["thermal"]
        for quantity in ("baseline_set_c", "baseline_residual_c", "wet_bulb_c"):
            close(f"{key}_{quantity}", stored[quantity], th[quantity])
        for k in "ABC":
            for quantity in ("residual_c", "benefit_c", "water_m3_h", "outlet_t_c"):
                close(f"{key}_{k}_{quantity}", stored["devices"][k][quantity], th["devices"][k][quantity])
        for stored_local, local in zip(stored["local"], th["local"]):
            check(f"{key}_local_order_{local['device']}{local['strip']}",
                  stored_local["device"] == local["device"] and stored_local["strip"] == local["strip"])
            for quantity in ("beta", "t_c", "rh", "v_m_s", "set_c"):
                close(f"{key}_{local['device']}{local['strip']}_{quantity}", stored_local[quantity], local[quantity])
        coefficient = [[mean_people(venue, econ)[z] / area * devices[k]["footprint_m2"] * th["devices"][k]["benefit_c"] /
                        devices[k]["power_kw"] for k in "ABC"] for z, area in enumerate(venue["areas_m2"])]
        upper = max(value for row in coefficient for value in row)
        close(f"{key}_task3_analytic_upper_attained", results[key]["efficiency_optimum"]["attaining_plan"]["efficiency"], upper)
        close(f"{key}_task3_analytic_upper_reported", results[key]["efficiency_optimum"]["upper_bound"], upper)
        check(f"{key}_task3_no_coverage_gate", results[key]["efficiency_optimum"]["attaining_plan"]["coverage"] < .8)
        exported_count = 0
        for label, row in find_exported_plans(results[key]):
            independent = evaluate_independent(venue, th, row["x"], devices, econ)
            compare_plan(key + label, row, independent)
            if independent["efficiency"] is not None:
                check(key + label + "_weighted_average_bound", independent["efficiency"] <= upper + 1e-8)
            exported_count += 1
        check(f"{key}_plans_audited", exported_count > 0)
        winner = results[key]["policy"]["selected"]
        check(f"{key}_solver_certificate_status", results[key]["policy"]["status"] == 0)
        check(f"{key}_solver_certificate_gap", results[key]["policy"]["mip_gap"] <= 1e-8)
        independent_winner = evaluate_independent(venue, th, winner["x"], devices, econ)
        check(f"{key}_task4_all_four_constraints", feasible(venue, independent_winner))
        double = dict(venue, areas_m2=[2 * a for a in venue["areas_m2"]],
                      people_by_hour=[[2 * p for p in hour] for hour in venue["people_by_hour"]])
        same = evaluate_independent(double, th, winner["x"], devices, econ)
        replica = evaluate_independent(double, th, [[2 * n for n in row] for row in winner["x"]], devices, econ)
        for quantity in ("service_person_c_h", "energy_kwh", "water_m3", "efficiency"):
            close(f"{key}_fixed_devices_scale_{quantity}", same[quantity], independent_winner[quantity])
        close(f"{key}_fixed_devices_scale_coverage", same["coverage"], independent_winner["coverage"] / 2)
        for quantity in ("service_person_c_h", "energy_kwh", "water_m3"):
            close(f"{key}_replicated_scale_{quantity}", replica[quantity], 2 * independent_winner[quantity])
        for quantity in ("coverage", "mean_benefit_c", "efficiency"):
            close(f"{key}_replicated_scale_{quantity}", replica[quantity], independent_winner[quantity])
        audit["venues"][key] = {"analytic_efficiency_upper": upper, "single_device_coefficients": coefficient,
                                  "exported_plans_audited": exported_count}
        if key == "Honolulu":
            area = venue["areas_m2"][0]
            layouts = []
            for counts in itertools.product(*(range(math.floor(area / devices[k]["footprint_m2"]) + 1) for k in "ABC")):
                if sum(counts[i] * devices[k]["footprint_m2"] for i, k in enumerate("ABC")) <= area + 1e-9:
                    row = evaluate_independent(venue, th, [list(counts)], devices, econ)
                    row["feasible"] = feasible(venue, row)
                    layouts.append(row)
            check("Honolulu_all_nine_layouts", len(layouts) == 9)
            possible = [r for r in layouts if r["feasible"]]
            check("Honolulu_some_feasible", len(possible) > 0)
            optimum = min(possible, key=lambda r: (r["annual_cost_usd"], r["energy_kwh_year"], r["mean_residual_c"]))
            close("Honolulu_MILP_matches_exhaustive_minimum_cost", winner["annual_cost_usd"], optimum["annual_cost_usd"])
            check("Honolulu_MILP_counts_match_exhaustive_optimum", winner["counts"] == optimum["counts"])
            fan3 = next(r for r in layouts if r["counts"] == [3, 0, 0])
            check("Honolulu_A3_below_1p5", fan3["mean_benefit_c"] < 1.5)
            check("Honolulu_A3_within_0p01_of_1p5", 0 < 1.5 - fan3["mean_benefit_c"] < .01)
            relaxed = min((r for r in layouts if feasible(venue, r, 1.49)), key=lambda r: r["annual_cost_usd"])
            check("Honolulu_1p49_policy_selects_pure_A3", relaxed["counts"] == [3, 0, 0])
            audit["venues"][key].update({"all_layouts": layouts, "feasible_count": len(possible),
                "exhaustive_optimum_counts": optimum["counts"], "A3_relief": fan3["mean_benefit_c"],
                "A3_shortfall_to_1p5": 1.5 - fan3["mean_benefit_c"],
                "relaxed_1p49_optimum_counts": relaxed["counts"],
                "interpretation": "The mixed selection is threshold-sensitive; it is not a universal superiority result."})
    audit_sensitivities(inputs, results, audit)
    audit["complete"] = True
    audit["checks"] = CHECKS
    audit["passed_count"] = len(CHECKS)
    audit["source_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ("run_venues.py", "inputs.json", "results.json", "cost_sensitivity.csv",
                                           "policy_curves.csv", "physical_sensitivity.csv", "boundary_clipping.csv",
                                           "scale_checks.csv", "climate_cross.csv", "density_scaling.csv",
                                           "threshold_sensitivity.csv")}
    (ROOT / "independent_audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": len(CHECKS), "venues": {k: {a: b for a, b in v.items() if a != "all_layouts"}
                                                       for k, v in audit["venues"].items()}}, indent=2))


if __name__ == "__main__":
    main()
