Canberra occupied-area deployment planning (Task 2(b) extension)

Run with the same dependencies as ../model/requirements.txt:
  python deployment_model/simulate_deployment.py
The solver imports the existing station_model and thermal_backend; retain the
whole project folder. No field data or new empirical device specifications are
claimed. scenario.json is the editable input; this folder's script regenerates
all CSV/JSON and separate PDFs 14/15/16/20/21 in ../figures.

Purpose and scope
-----------------
Device counts x[z,k] are nonnegative integers for zones z=Access/Core/Edge and
types k=A/B/C. Multiple types can coexist within a zone. Total count, electricity,
moisture production and coverage are recalculated; the code never multiplies the
old three-unit efficiency or adds individual device efficiencies.

The approximate 220 m station length comes from the user-supplied schematic;
source audit is in ../station_model/source_audit.txt. The following are assumptions:
aggregate usable waiting-strip width 6 m, usable fraction 0.8, effective air height
4 m. Occupied area=1056 m2 and each aggregate thermal zone=352 m2. This is not an
as-built platform plan, building footprint, site area or a use of the 17 m column
height as platform clearance. The three thermal zones can represent collections
of similar locations; placement is only at zone level, not geometric coordinates.

Air volume, envelope conductance/storage, absorbed envelope load, interzone
mass exchange and occupancy scale by 4.4 from the previous 240 m2 local scenario.
ACH and view factors remain unchanged. This prescribed similarity rule is not
validated architectural scaling. Mean occupancy is 220 people, giving 440
person-hours over two hours; crowd/headway assumptions are not operating records.
Weather is the 33 C, 70% RH illustrative Canberra humid scenario.

Mixed-device physics
--------------------
The h/w/Tm balances preserve equal/opposite internal exchange terms. Each device
contributes its own electrical sensible heat. B/C recirculate the current zone
air, adding water at their summed dry-air flow rates with approximately unchanged
moist-air enthalpy. Pump power is already part of the stated total. Human water
vapor's enthalpy is included once; no duplicate latent source is added.

Per-device DIRECT AIRFLOW footprints are assumed A20/B30/C40 m2. Subpopulation
fractions are f[z,k]=x[z,k]*a[k]/352; footprints are disjoint, so sum_k f<=1.
Uncovered fraction f[z,0]=1-sum f. Footprints define service weights, not air
storage volumes. Uncovered people use bulk T/RH; A/B/C-covered people use local
delivery T/RH (below) and prescribed device/zone speeds. All share zone MRT.
Speeds are NOT added for adjacent devices. Uniform within-zone
occupancy makes these area fractions equal passenger fractions within that zone.
Zone-average discomfort is sum_k f[z,k]*max(SET[z,k]-26,0). This prevents double
credit for one person. It also means bulk evaporative effects may reach uncovered
passengers; 'coverage' specifically describes direct-airflow coverage, not every
possible thermal influence. Detailed jets/overlap require measured maps or CFD.

Accounting and comparisons
--------------------------
All cases share a two-hour uncooled initialization and identical no-device
baseline, weather, occupancy and geometry. Every deployed unit runs for the
full two-hour evaluation; electricity includes all units. U is signed discomfort
relief integrated over people/time; eta=U/E. Remaining discomfort is reported
separately. Neither a winning efficiency nor a covered fraction demonstrates
adequate comfort.

24 sampled count/layout plans are compared. Pure count sweeps:
A: 3/9/18/27/36/45/51 units; B:3/6/12/18/24/30/33; C:3/6/9/12/18/24.
The six matched-area benchmarks are A36, B24, C18, AB30 (18A+12B),
AC27 (18A+9C), ABC24 (9A+6B+9C). Each has equal per-zone coverage of
240/352=68.18%. All are assumed layouts, not procurement recommendations.
AB30-R keeps 18A+12B but redistributes x rows to [3,4,0],[12,3,0],[3,5,0].
Its area coverage is unchanged, but passenger-time coverage increases because the
core carries more people. The sampled Pareto set only means no sampled plan has
both lower/equal energy and lower/equal remaining discomfort with one strict.
It is not a global optimum over all integer designs, nor an optimization of cost,
water, safety, maintenance or installation constraints.

Coverage uncertainty
--------------------
coverage_sensitivity.csv evaluates footprint multipliers 0.75/1/1.25 for the
six matched-area benchmarks. All fractions remain <=1. The same thermal
trajectories and type-specific SET values are reweighted: this isolates direct
flow-coverage assumptions with bulk recirculation unchanged. A physical device
redesign could also change flow, local speed and heat transfer, which this sweep
does not predict. No mixed plan is forced to win.

Verification
------------
RK4 uses 20 s steps and midpoint forcing, aligned with pulse/boarding boundaries.
SET is evaluated in vectorized form with the same package, standing posture,
limit_inputs=True and unrounded output as the shared scalar backend. Any nonfinite
SET or supersaturated air is rejected. Three mixed plans are repeated at10 s.
Tests cover integer/nonoverlapping coverage, equal benchmark coverage, complete
power accounting, service+remaining=baseline, global energy/water budgets,
pure-device reduction, zero occupancy with positive energy, signed adverse heat,
valid SET/humidity and timestep convergence. These are internal tests, not
measurement validation. Exact results are in results_summary.json.

Files
-----
candidate_results.csv: all24 plans, counts by zone, area and person-time coverage,
  E/U/eta/remaining discomfort, core humidity and conservation residuals.
coverage_sensitivity.csv: 18 fixed-trajectory reweightings.
time_series.csv: baseline, six matched-area plans and redistributed AB30-R.
timestep_convergence.csv:20s versus10s mixed-plan checks.
results_summary.json: checks, benchmark results, sample nondominance and initial state.

Unified local delivery revision
-------------------------------
shared_model/delivery.py implements the common bus/station h,w stream mixture.
Each station unit draws m_d from bulk, entrains r*m_d, and returns all mixed air.
beta=1/(1+r); x_local=(1-beta)*x_bulk+beta*x_supply for x=h,w. Before mixing,
h_supply=h_pure_evap+alpha*P/m_d. Nominal beta=.5 and alpha=1 for all types;
A/B/C assumed recirculating supply flows are .6/.6/1.2 kg dry air/s. A has no
evaporation water source, but does have circulating flow and local motor heat.
alpha=1 conservatively puts all electricity into the supply before passengers.
It is not a measured or neutral estimate. The ODE still counts P exactly once
and uses only the pure evaporative h/w difference in its device source. The
local diagnostic adds no second source: returning and withdrawing flows cancel
to m_d*(x_pure_evap-x_bulk) plus alpha*P for h; the remaining (1-alpha)*P is
dissipated directly to bulk. Existing bulk trajectories are unchanged.

The local jet core is assumed to have negligible storage on the 120-s forcing
time scale. Its hold-up M_local and residence time M_local/[(1+r)*m_d] require
measurement. It is not coverage area times the 4-m bulk mixing height.
Scalar transport is separated from prescribed speed. beta=0 is the infinite-r
diagnostic limit and restores old shared-bulk T/RH while retaining local speed.

Sensitivity and verification outputs
-----------------------------------
delivery_sensitivity.csv: all24 plans x beta(0,.25,.5,.75,1) x alpha(0,.5,1).
delivery_sensitivity_rankings.csv: each pair's matched-area winners and sampled
Pareto set; lower discomfort and higher electricity efficiency remain separate.
airflow_sensitivity.csv: A supply .3/.6/1.2 at nominal beta/alpha, same bulk.
bulk_limit_regression.csv: beta=0 versus the archived original24 CSV rows.
shared_model/reference_bulk_candidates.json: frozen pre-revision reference.
20_local_delivery_sensitivity.pdf: beta/alpha uncertainty, separate PDFs.
21_model_reduction_checks.pdf: original-limit recovery and local/bulk dynamics.
All original checks remain, plus stream/return closure, unchanged bulk, the
24-plan beta-zero regression and shared scalar/vector map equivalence.

Notation alignment: internal code/JSON/CSV alpha denotes the manuscript local
pre-delivery electrical-heat fraction chi (Greek chi). It is not the geometry
usable-area fraction alpha. Figures20/21 display chi; internal keys remain
unchanged for reproducibility.

Replot only figures20/21 from frozen CSVs without any numerical solve:
  python deployment_model/simulate_deployment.py --delivery-figures-only

Manuscript scope revision (2026-11-08)
--------------------------------------
Requirement 2 compares eta=U/E only; direct coverage remains a service weight.
A3 has the highest eta among all 24 sampled plans; A36 has the highest eta
among the six equal-coverage benchmarks. Figures22/23/25 replot these frozen
CSV outputs with efficiency-only axes (figure_sources/make_efficiency_scope.py).
The energy/remaining-discomfort projection (Figure14), service thresholds and
conditional selection rules now belong to Requirement4. They do not constitute
a calibrated four-objective recommendation without cost and experience inputs.
No physical code, scenario input or numerical result changed in this revision.
