Task 3/4: Fremont and Honolulu CP-SET transfer
=============================================

Use the existing project Python environment:
  /Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python run_venues.py
  python run_venues.py --core-only       # nominal coefficients and MILP
  python run_venues.py --figures-only    # redraw frozen JSON/CSV; no optimization
  python verify_results.py              # conservation, bounds, scale and budgets
  python independent_audit.py           # independent psychrometrics / H enumeration

Dependencies: numpy, scipy (milp/HiGHS), matplotlib, PsychroLib, pythermalcomfort.
The existing thermal_backend.py and shared_model/delivery.py are unchanged.
The backend intentionally rejects 45 C in a negative self-test; its two warnings
are not venue extrapolations. All venue calls retain SET limit_inputs=True.

inputs.json is the complete input record. The source-derived canopy length is
419.1 m. Effective width 20 m, areas 2400/3600/2382 m2 and the 10 m by 6 m zoo
customer area are assumptions. The conceptual zones are not surveyed sections.
Four hourly populations are uniform within their demand zone. A zone is distinct
from each device's three equal-area local delivery strips. Local speed adds the
reference strip increment to the prescribed natural wind. Pressure is 101325 Pa;
standing 1.2 met / 0.5 clo, chi=0 and 26 C SET-excess reference apply throughout.

The outdoor background is fixed. Crowd changes affect person-time weighting,
not an uncalibrated humidity-storage balance. beta is a dry-air mixing fraction,
not a geometric coverage fraction. Device supply flow is counted once when
calculating water, not three times for three strips. Energy includes full power.
The same scalar mixing and SET modules are used for both venues.

Task 3 has only the efficiency objective eta=U/E. A feasible plan's eta is an
energy-weighted average of individual device/zone ratios. The maximum ratio is
an attainable upper bound when that complete footprint fits. This is a result
within the area-allocation abstraction; it does not certify a surveyed two-
dimensional equipment layout or calibrated flow field. Complete footprints are
nonoverlapping in the nominal model; area packing is assumed feasible. Pure
largest-fit benchmarks have different person-time coverage, especially C1 at
Honolulu (2/3). They are not equal-coverage comparisons.

Task 4 alone imposes q>=0.8, mean SET-excess relief>=1.5 C, equipment clearance
<=3.5% of total area, and annual electricity<=30 kWh/m2. Annual cost is linear
in integer zone/type counts; scipy milp certifies status/gap. Annual hours=600,
5-year life, discount rate .05, electricity $.20/kWh and water $3/m3. No Pareto
frontier enumeration or experimental optimization claim is made. Nominal
Fremont/Honolulu plans are A266C16 and A1B1. The Honolulu A3 alternative misses
the 1.5 C requirement by only .009194657 C; target sensitivity is reported.

Numerical outputs
-----------------
results.json: nominal thermal states, exact eta bound/attaining one-device plan,
  pure_largest_fit A/B/C, policy.selected, policy solver certificate, maximum
  achievable relief under the remaining policy conditions.
linear_coefficients.csv: per zone/type single-device U, E, power, coverage
  person-hours, cost components, water and footprint coefficients.
local_conditions.csv: 18 strip states with beta, h, w, RH, SET, speed and outlet.
physical_sensitivity.csv: RH +/-10 pp; MRT -2/+2 C (Fremont upper perturbation
  is +1 C to remain at 40 C); v0=.2/.35/.8/1.2; area .75/1.25 with fixed people.
  best_single_eta_A/B/C are the highest-density-zone single-device ratios.
  Status 2 explicitly records infeasibility (Honolulu area 45 m2).
climate_cross.csv: common 120 m2 and .4 person/m2 plus each original geometry
  and occupancy under both climates. Climate includes natural-wind assumption.
density_scaling.csv: same area/weather, demand .5/1/2; eta scales with density.
scale_checks.csv: Honolulu climate/density, area and demand x1/x2/x4/x8;
  fixed A3 versus replicated A3*n. Scale identities are model properties.
boundary_clipping.csv: one device, area 5--120 m2, retained near/middle/far
  areas. Remove far then middle strip; full electricity and water remain.
cost_sensitivity.csv: 243 independent price combinations per venue, solved MILP.
policy_curves.csv: sampled relief requirements, each with certified MILP result.
threshold_sensitivity.csv: dedicated 1.4/1.49/1.5/1.6 C policy cases.
verification.json: internal checks and numerical residuals.
independent_audit.json: separate direct psychrometric and enumeration audit.
figure_verification.json: final independent-PDF hashes and visual inspection.

Standalone figures (no embedded LaTeX drawing code)
-------------------------------------------------
27_venue_comparison.pdf: largest-fit eta, service numerator and coverage labels.
28_effectiveness.pdf: policy cost shares/totals and sampled requirement costs.
30_scale_transfer.pdf: scale identities and explicit strip truncation.
31_venue_layouts.pdf: conceptual domains and prescribed occupancy time series.
make_figures.py reads the frozen result files. All PDFs embed their plot fonts.

Units: U person-degC-hour, E kWh, eta person-degC-hour/kWh; water m3; power kW;
dry-air flow kg_da/s. For four-hour service, annual cost uses its separate
600-hour operating assumption. The figures and exported inputs describe their
assumptions; no queue length, weather snapshot or cooling installation is claimed
as a measurement.
