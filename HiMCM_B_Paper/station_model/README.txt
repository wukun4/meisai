Semi-open rail-station model: Requirement 2(b)

Reproduce with the same Python environment as ../model:
  python station_model/simulate_station.py
For a nominal-only numerical run without checks or figure export:
  python station_model/simulate_station.py --quick

Input: scenario.json. Shared psychrometric and SET backend: ../model/thermal_backend.py.
Dependencies are listed in ../model/requirements.txt. No additional dependencies.
Output: time_series.csv, scenario_results.csv, conservation_budgets.csv,
warmup_states.json, ventilation_sweep.csv, timestep_convergence.csv,
results_summary.json. The three figures are separate PDF assets:
  ../figures/10_rail_dynamics.pdf
  ../figures/11_rail_efficiency.pdf
  ../figures/12_rail_ventilation.pdf
They can be replaced individually in the paper; no plotting code is embedded in TeX.

Interpretation
--------------
This is an illustrative station, not a calibrated model of a named station.
All geometry, human loads, exchange rates, equipment flow rates, velocity maps,
and schedules are explicit assumptions. Device powers and outlet-drop caps carry
forward the stated interpretation of the problem table. One unit per zone means
three units in total. All their electrical input is counted and assigned to zone
sensible heat. The local air speeds are assumed representative speeds at occupied
positions, not calculated from the mass exchange rates or rated power.

The station has three adjacent, equal, well-mixed dry-air control volumes and
one effective envelope/radiant node per zone. The model evolves moist-air specific
enthalpy h [J/kg dry air], humidity ratio w [kg water/kg dry air], and surface
node temperature [deg C]. Air temperature/RH are recovered consistently from h,w.
Each dry-air storage mass M [kg] is fixed at its outdoor-reference density times
zone volume; this is a constant-density approximation, not a compressible flow
solution. ACH is converted to balanced dry-air mass flow as M*ACH/3600.
Adjacent zones exchange equal dry-air mass rates in both directions.

The air/surface conductance is equal and opposite in the two energy balances.
Human vapor contributes g*hv(T) to air enthalpy and g to water storage; the
45-W quantity used to estimate g is NOT added again. Convective and radiant
human loads go to air and surface nodes separately. Effective solar load enters
the envelope node. Surface MRT is a fourth-power weighted mixture of that node
and a separately specified shaded outdoor radiant temperature; direct solar
radiation on a person is excluded in this example.

A direct evaporative device recirculates its own zone's current air. Its inlet
RH is recalculated at every integration stage. Under the existing approximately
isenthalpic pad model, recirculation adds water and changes dry-bulb temperature
without artificially extracting moist-air enthalpy. Water supply enthalpy and
carryover are omitted. Fan/pump electrical heat is added separately. Thus the
outlet depression can change as station humidity changes. There is no fixed
bus-stop dilution fraction in this station model.

The 15-minute train cycle and last-two-minute exchange pulse are assumed
schedules. The exchange pulse is a surrogate for an arrival/opening disturbance;
it is not a train-speed/piston-flow prediction and is not imported from an
underground-station measurement. Occupancies rise linearly and reset at departure.
SET remains a quasi-steady human-response proxy, even though the environment is
dynamic; a passenger's physiological exposure history is not integrated.

Initial conditions and fair accounting
-------------------------------------
For each outdoor climate and ventilation multiplier, the no-active-cooling
station warms for two hours from outdoor air/surface conditions. This is a
specified initialization, not an assertion of periodic equilibrium. The final
warm-up state is shared by the baseline and all active strategies, which then
run for two hours. Cooling starts at t=0; all active energy from that time is
counted. The warm-up contains no active energy or credited relief. Cooling
stored at the end of the two-hour horizon earns no unobserved future benefit.
Each strategy is compared with the same simultaneously simulated no-active-cooling
baseline for its climate/exchange case, with matched weather, initial state,
geometry and crowd schedule. Signed service is
U=sum n*(D_baseline-D_strategy)*dt_hours. No floor-area multiplier is added.

Numerics and verification
-------------------------
Fixed-step RK4 uses 10-second steps, with scheduled forcing frozen at each step
midpoint. Steps align with train/pulse boundaries. Mid-state environmental
conditions are used for the person-time SET quadrature. Repeat at 5 seconds
checks convergence of service efficiency, mean remaining discomfort and peak core RH. The balances integrate in seconds, then service and
operating electricity use hours. No supersaturation is silently clipped; the
shared backend rejects it. SET input-domain checks remain active.

The internal tests cover global energy and moisture conservation, cancellation
of internal exchange, unloaded equilibrium, service+remaining=baseline, complete
device energy, zero-occupancy service, signed adverse effects, gas-phase/domain
limits, and timestep convergence. These verify numerical/internal consistency;
they do not establish empirical predictive accuracy. Ventilation sensitivity
multiplies both base and pulse exchange while retaining the prescribed local
comfort-speed profiles, so it isolates air/moisture-exchange sensitivity rather
than a complete wind-speed model. Ventilation cases have matched baselines and
initialization within each case.
