"""Task 2 efficiency-only figures from frozen CSVs; no thermal/SET solve.

The figure units are person·degC·h/kWh. CSV local_heat_fraction_alpha is
manuscript chi (pre-delivery electrical heat), not the geometric usable fraction.
All source CSVs are read-only; hashes are verified again after figure export.
"""
from pathlib import Path
import csv
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
FIG = PROJECT / "figures"
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SOURCES = {
    "station": "deployment_model/candidate_results.csv",
    "delivery": "deployment_model/delivery_sensitivity.csv",
    "bus": "model/scenario_results.csv",
    "coverage": "deployment_model/coverage_sensitivity.csv",
}
BENCH = ["A36", "B24", "C18", "AB30", "AC27", "ABC24"]
FAMILY_COLOR = {"A": "#2379A5", "B": "#D18C32", "C": "#76559A", "Mixed": "#268467"}
PLAN_COLOR = dict(zip(BENCH, ["#2379A5", "#D18C32", "#76559A", "#268467", "#b35e7c", "#8c564b"]))
UNIT = "η unit: person·°C·h/kWh."
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12,
    "axes.labelsize": 13, "axes.titlesize": 13,
    "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})


def read_source(relative):
    with (PROJECT / relative).open(newline="") as handle:
        return list(csv.DictReader(handle))


def digest_sources():
    return {relative: hashlib.sha256((PROJECT / relative).read_bytes()).hexdigest()
            for relative in SOURCES.values()}


def number(row, key):
    value = float(row[key])
    if not np.isfinite(value):
        raise ValueError(f"Nonfinite {key}: {row}")
    return value


def export(fig, stem):
    # Keep the standalone PDFs fully vector, including future mesh collections.
    for ax in fig.axes:
        for collection in ax.collections:
            collection.set_rasterized(False)
    path = FIG / (stem + ".pdf")
    fig.savefig(path, bbox_inches="tight", pad_inches=.03, facecolor="white")
    plt.close(fig)
    return path


def station_figure(rows):
    ranked = sorted(rows, key=lambda row: number(row, "efficiency"), reverse=True)
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 7.8), layout="constrained",
                            gridspec_kw={"width_ratios": [1.12, 1.]})
    for pos, row in enumerate(ranked):
        eta = number(row, "efficiency"); color = FAMILY_COLOR[row["family"]]
        axs[0].hlines(pos, 0, eta, color=color, alpha=.28, linewidth=1.2)
        axs[0].scatter(eta, pos, color=color, marker="D" if row["family"] == "Mixed" else "o",
                       s=42, zorder=3)
        if row["plan"] in ("A3", "A36"):
            axs[0].scatter(eta, pos, facecolors="none", edgecolors="#17212b",
                           s=105, linewidths=1.1, zorder=4)
            axs[0].annotate(f"{eta:.2f}", (eta, pos), xytext=(8, 0),
                            textcoords="offset points", va="center", fontsize=12)
    axs[0].set(yticks=range(len(ranked)), yticklabels=[r["plan"] for r in ranked],
               xlabel="Service efficiency η", xlim=(0, 45),
               ylim=(len(ranked)-.45, -.65), title="A. All 24 sampled plans")
    for label in axs[0].get_yticklabels():
        if label.get_text() in ("A3", "A36"):
            label.set_fontweight("bold")
    axs[0].grid(axis="x", alpha=.2); axs[0].set_axisbelow(True)
    for family in ["A", "B", "C"]:
        subset = sorted((r for r in rows if r["family"] == family),
                        key=lambda r: number(r, "total_devices"))
        axs[1].plot([number(r, "total_devices") for r in subset],
                    [number(r, "efficiency") for r in subset], "-o",
                    color=FAMILY_COLOR[family], label=family, linewidth=1.8, markersize=5)
    axs[1].set(xlabel="Total device count", ylabel="Service efficiency η",
               title="B. Pure-device count sweeps", ylim=(0, 41), xlim=(0, 54))
    axs[1].legend(title="Device type", loc="center right", fontsize=12, title_fontsize=12)
    axs[1].grid(alpha=.2)
    fig.suptitle("Station cooling efficiency", fontsize=15, fontweight="bold")
    fig.supxlabel("A3: largest η among 24 sampled plans. A36: largest η among six equal-coverage benchmarks.\n"
                   "A: fan; B/C: evaporative devices. Plan numbers are total unit counts. " + UNIT,
                   fontsize=12)
    return export(fig, "22_station_efficiency")


def delivery_figure(rows):
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 4.9), layout="constrained", sharey=True)
    for ax, chi in zip(axs, [0., .5, 1.]):
        for plan in BENCH:
            subset = sorted((r for r in rows if r["plan"] == plan
                             and number(r, "local_heat_fraction_alpha") == chi),
                            key=lambda r: number(r, "delivery_beta"))
            ax.plot([number(r, "delivery_beta") for r in subset],
                    [number(r, "efficiency") for r in subset], "-o", label=plan,
                    color=PLAN_COLOR[plan], linewidth=1.8, markersize=4)
        ax.set(title=f"Heat fraction χ = {chi:g}", xlabel="Supply fraction β",
               xticks=[0, .25, .5, .75, 1.], ylim=(0, 41))
        ax.set_xticklabels(["0", "0.25", "0.5", "0.75", "1"])
        ax.grid(alpha=.2)
    axs[0].set_ylabel("Service efficiency η")
    axs[0].legend(ncol=2, loc="center", bbox_to_anchor=(.5, .69),
                  fontsize=12, columnspacing=.8, handlelength=1.5)
    fig.suptitle("Local-delivery sensitivity of cooling efficiency", fontsize=15, fontweight="bold")
    fig.supxlabel("Six equal-coverage benchmarks; unchanged bulk trajectories. Nominal: β = 0.5, χ = 1.\n"
                   "β and χ are assumed delivery parameters. " + UNIT, fontsize=12)
    return export(fig, "23_delivery_efficiency")


def bus_figure(rows):
    selected = [r for r in rows if r["occupancy"] == "Uniform"]
    fig, ax = plt.subplots(figsize=(9., 4.9), layout="constrained")
    x = np.arange(2); width = .23
    for index, kind in enumerate(["A", "B", "C"]):
        values = [number(next(r for r in selected if r["device"] == kind
                              and number(r, "climate_rh") == rh), "efficiency")
                  for rh in [.3, .7]]
        bars = ax.bar(x + (index-1)*width, values, width, label=kind,
                       color=FAMILY_COLOR[kind])
        ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=12)
    ax.set(xticks=x, xticklabels=["Dry (RH 30%)", "Humid (RH 70%)"],
           ylabel="Service efficiency η", ylim=(0, 112),
           title="Bus-shelter cooling efficiency")
    ax.legend(ncol=3, loc="upper center", fontsize=12)
    ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
    fig.supxlabel("Nominal uniform occupancy; fixed ambient background; local motor/pump heat neglected.\n"
                   "A: fan; B/C: evaporative devices. " + UNIT, fontsize=12)
    return export(fig, "24_bus_efficiency")


def coverage_figure(rows):
    fig, ax = plt.subplots(figsize=(9., 4.9), layout="constrained")
    for plan in BENCH:
        subset = sorted((r for r in rows if r["plan"] == plan),
                        key=lambda r: number(r, "coverage_scale"))
        xx = [number(r, "coverage_scale") for r in subset]
        yy = [number(r, "efficiency") for r in subset]
        ax.plot(xx, yy, "-o", color=PLAN_COLOR[plan], label=plan,
                 linewidth=1.8, markersize=5)
        if plan == "A36":
            for x, y in zip(xx, yy):
                ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 8),
                            textcoords="offset points", ha="center", fontsize=12)
    ax.set(xlabel="Assumed footprint multiplier", ylabel="Service efficiency η",
           xticks=[.75, 1., 1.25], xlim=(.71, 1.29), ylim=(0, 51),
           title="Sensitivity to direct-airflow footprint assumptions")
    ax.legend(ncol=2, loc="upper left", fontsize=12)
    ax.grid(alpha=.2)
    fig.supxlabel("Thermal trajectories and device electricity are fixed; only service footprints vary.\n"
                   "Nominal local delivery: β = 0.5, χ = 1. " + UNIT, fontsize=12)
    return export(fig, "25_coverage_efficiency")


def main():
    before = digest_sources()
    data = {key: read_source(source) for key, source in SOURCES.items()}
    required = {"service_person_c_h", "energy_kwh", "efficiency"}
    checks = {}
    for key, rows in data.items():
        assert rows and required.issubset(rows[0]), (key, list(rows[0]) if rows else [])
        checks[key + "_eta_equals_service_over_energy"] = all(
            abs(number(r, "efficiency") - number(r, "service_person_c_h") /
                number(r, "energy_kwh")) < 1e-10 for r in rows)
    station = data["station"]; by_plan = {r["plan"]: r for r in station}
    checks["24_distinct_station_candidates"] = len(station) == len(by_plan) == 24
    checks["all_station_counts_match_type_sum"] = all(number(r, "total_devices") ==
        sum(number(r, k) for k in ["A", "B", "C"]) for r in station)
    checks["six_benchmarks_share_coverage"] = all(
        abs(number(by_plan[p], "area_coverage_fraction") - 720/1056) < 1e-12 for p in BENCH)
    all_best = max(station, key=lambda r: number(r, "efficiency"))
    bench_best = max((by_plan[p] for p in BENCH), key=lambda r: number(r, "efficiency"))
    checks["sample_highest_eta_is_A3"] = all_best["plan"] == "A3"
    checks["equal_coverage_highest_eta_is_A36"] = bench_best["plan"] == "A36"
    checks["delivery_has_five_beta_values_per_benchmark_per_chi"] = all(
        sorted(number(r, "delivery_beta") for r in data["delivery"] if r["plan"] == p
               and number(r, "local_heat_fraction_alpha") == chi) == [0., .25, .5, .75, 1.]
        for p in BENCH for chi in [0., .5, 1.])
    checks["bus_uniform_has_six_device_climate_pairs"] = sorted(
        (r["device"], number(r, "climate_rh")) for r in data["bus"] if r["occupancy"] == "Uniform"
    ) == [(k, rh) for k in ["A", "B", "C"] for rh in [.3, .7]]
    checks["coverage_nominal_matches_station_efficiency"] = all(
        abs(number(r, "efficiency") - number(by_plan[r["plan"]], "efficiency")) < 1e-10
        for r in data["coverage"] if number(r, "coverage_scale") == 1.)
    assert all(checks.values()), checks
    FIG.mkdir(exist_ok=True)
    outputs = [station_figure(station), delivery_figure(data["delivery"]),
               bus_figure(data["bus"]), coverage_figure(data["coverage"])]
    checks["source_csv_hashes_unchanged"] = digest_sources() == before
    assert checks["source_csv_hashes_unchanged"]
    report = {
        "scope": "Task 2: service efficiency eta only; no discomfort/Pareto/selection-threshold axis",
        "source_hashes": before,
        "source_row_counts": {key: len(rows) for key, rows in data.items()},
        "checks": checks,
        "station_highest_sampled_eta": {"plan": all_best["plan"], "efficiency": number(all_best, "efficiency")},
        "station_highest_equal_coverage_eta": {"plan": bench_best["plan"], "efficiency": number(bench_best, "efficiency")},
        "bus_uniform_efficiency": [
            {"device": r["device"], "rh": number(r, "climate_rh"), "efficiency": number(r, "efficiency")}
            for r in data["bus"] if r["occupancy"] == "Uniform"],
        "A36_coverage_efficiency": [
            {"footprint_multiplier": number(r, "coverage_scale"), "efficiency": number(r, "efficiency")}
            for r in data["coverage"] if r["plan"] == "A36"],
        "outputs": [str(path.relative_to(PROJECT)) for path in outputs],
        "plot_source": "Frozen CSV values; no calls to ODE, SET or physical-model modules",
        "notation": "CSV local_heat_fraction_alpha corresponds to manuscript chi",
    }
    (ROOT / "efficiency_scope_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
