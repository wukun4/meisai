Task 3-5 reproducible venue applications
=======================================
Run from any directory:
  /Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python run_venues.py

Dependencies are the project's existing Python environment: numpy, matplotlib,
PsychroLib 2.5.0, pythermalcomfort 4.8.1. The imported model/thermal_backend.py
and shared_model/delivery.py are used unchanged. The backend's deliberate
out-of-domain self-check emits two warnings for45C; no venue calculation uses
that state.

inputs.json is the complete generated assumption record; the import preserves
source A/B/C powers, outlet caps, epsilon and delivered-strip beta/speed values.
New geometry, occupancy, flow/coverage/clearance/cost and operating assumptions
are defined at the start of run_venues.py. These are hypothetical design studies
at identified real venues, not field-calibrated installations.

Outputs:
* *_all_allocations.csv: full finite integer design spaces, including E=0 baseline.
* *_distinct_candidates.csv: q>=.8 representatives for Task4 ONLY. For fixed
  counts, E, X and annual cost are position-invariant in this fixed-background
  model, so minimizing R among coverage-eligible layouts preserves the optimum.
* results.json: full-set Task3 eta maxima (with ties), q=.6 pure-type benchmarks,
  and separate Task4 coverage-constrained frontier and policy winner.
* local_conditions.csv: all device-specific local states for both climates.
* physical_sensitivity.csv, cost_sensitivity.csv, scale_checks.csv: stress tests.
* policy_curves.csv: least cost as the service threshold changes.
* verification.json: numerical consistency checks, not experimental validation.
* ../figures/27_venue_comparison.pdf and28_effectiveness.pdf: standalone vector PDFs.

Energy is kWh; useful service is person-degC-hour of reduced SET excess; water is
m3 except where reporting converts to liters. Rates use kg dry air/s. Airflow
footprint and equipment/maintenance clearance area are different quantities.
The three delivery strips partition one unit's footprint; supply water is counted
once per physical unit. Baseline humidity and temperature remain prescribed, so
crowd-generated accumulation is outside this outdoor approximation; use the
paper's rail model when that mechanism is important.

Primary-source audit and LaTeX bibitems: ../references/venue_sources.txt.
