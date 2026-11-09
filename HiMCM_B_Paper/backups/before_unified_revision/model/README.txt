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
