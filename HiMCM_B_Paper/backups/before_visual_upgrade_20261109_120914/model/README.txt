Reproduce the bus-stop model and its separate figure PDFs

Run Python with requirements.txt installed:
  python model/simulate.py

The script reads model/scenario.json and writes CSV/JSON results to model/.
It exports six independent vector PDF files to figures/ one directory above.
Replacing a figure PDF with the same filename updates the paper on its next
LaTeX compilation. To recalculate all numerical results and checks while
preserving the existing six PDF assets:
  python model/simulate.py --no-figures

NYC regular-shelter geometry
---------------------------
The adopted dimensions are 14 ft x 5 ft x 8 ft 11 in from NYC DOT's Street Design
Manual, regular-size shelter: exactly 4.2672 m x 1.524 m x 2.7178 m. This is one
New York City shelter configuration, not a universal New York State standard.
Source URL, imperial dimensions and access date are in scenario.json.

geometry.py derives three equal strips along the length. The assumed device
end is x=0. Each strip has gross area 2.1677376 m2, and the total gross plan
area is 6.5032128 m2. geometry_zones.csv records bounds, centers and areas;
geometry_occupancy.csv records the implied gross densities for each case.
The bench and frame have not been subtracted, so these are not net standing
areas or rated capacities. Height describes the configuration and does not
define a closed, uniformly cooled air volume in this open shelter.

Occupancy may be specified per zone in either of two mutually exclusive ways:
  "Uniform": [4, 4, 4]
  "Uniform": {"gross_density_people_m2": [1.0, 1.0, 1.0]}
The explicit {"people": [4, 4, 4]} form is also supported. Density input is
converted once with n_z=rho_z*A_z. A second area multiplier is never applied.
Densities are per gross plan area, not available standing area. Noninteger
counts represent mean simultaneous occupancy during the comparison period.

The original counts (4,4,4), (8,3,1) and (1,3,8) are retained as illustrative
crowd-concentration stress cases, not measured NYC occupancy or capacity.
The uniform gross density is approximately 1.845 people/m2; the eight-person
zone has approximately 3.690 people/m2 of gross footprint. Neither density
asserts that the bench and structure leave sufficient space for that crowd.

The air speeds and cooled-air fractions remain assumed zone profiles.
Geometry maps their spatial support; no airflow distribution is inferred from
the dimensions. At fixed counts and unchanged local fields, changing geometry
leaves the original SET/service/efficiency values unchanged. At fixed gross
density and unchanged local fields, changing area changes n_z and hence total
service. This is an accounting property, not a physical scaling law for air
flow. geometry_checks.json tests both interfaces, the SI conversion, area
partitioning, and invalid-input rejection. results_summary.json retains the
seven thermal/service checks and numerical results. See source_audit.txt and
the paper for model interpretations and limits.

Figure-export audit
-------------------
figure_export_checks.json records the earlier six-PDF vector-export audit.
The NYC geometry adoption preserves these six numerical figures; the added
zoning diagram has a separate generator in figure_sources/ and is not made
by simulate.py. All weather, occupancy and local delivery profiles remain
illustrative assumptions. Only the shelter's nominal dimensions are sourced.

Unified delivery map revision
----------------------------
The legacy scenario key cooled_mass_fractions is retained to preserve all
existing sensitivity mutators, but its physical name is delivery beta.
local_conditions.csv exports delivery_beta and derived entrainment_ratio_r.
r=(1-beta)/beta is assumed, not measured; beta=0 is its infinite-r limit.
The nominal bus map calls shared_model/delivery.py with a fixed ambient
background and alpha=0. This additionally neglects local motor/pump heat;
openness alone does not justify zero heat. Original results are regression-
checked against shared_model/reference_bus_results.json and stay unchanged.
No absolute flow is inferred for the three local sampling zones.

python shared_model/verify_bus_delivery.py additionally writes
local_heat_sensitivity.csv and unified_mapping_regression.csv plus
unified_delivery_checks.json. That separate diagnostic assumes unit supply
A/B/C=.6/.6/1.2 kg_da/s, alpha=0/.5/1, and assigns A the B beta profile
[.8,.45,.1] only for this sweep. At alpha=0 the A profile cannot change its
ambient scalar state, so all original zone outputs are recovered exactly.
These flows/profiles are explicit assumptions; the three maps are not three
independent copies of the device's full flow. Existing nominal/sensitivity
outputs and figures01-06 retain their original physical assumptions.

Notation alignment: internal code/JSON/CSV alpha denotes the manuscript local
pre-delivery electrical-heat fraction chi (Greek chi). It is not the geometry
usable-area fraction alpha. Figures20/21 display chi; internal keys remain
unchanged for reproducibility.
