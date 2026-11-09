CP-SET VISUAL UPGRADE — REPRODUCTION AND SCOPE
============================================

Main script: visual_upgrade/make_figures.py
Optional online downloader: visual_upgrade/fetch_climate.py
Both run from any current directory; paths resolve relative to the script.

Requirements (tested): Python 3, numpy, scipy, matplotlib, psychrolib,
pythermalcomfort (the original model environment uses version 4.8.1).
All climate responses and the state geometry are archived in data/. Normal
figure reproduction is OFFLINE and does not require re-downloading anything.

From the project root:
  python visual_upgrade/make_figures.py
  zsh compile.command

The first command exports each of six figures to figures/ as a vector/hybrid
PDF and a 300-DPI PNG. The three main composites are:
  34_continuous_thermal_fields: 3180 x 2220 px
  35_us_climate_potential:     3180 x 2340 px
  36_energy_service_radar:    3180 x 3060 px
The two consolidated figures, 37 and 38, save manuscript space. Figure 39
updates the original bus local-state color palette without changing values.
PDF typography and curves remain vector; filled thermal contours and the
climate background are embedded at 300 DPI. A PDF does not have a single overall DPI.

1. CONTINUOUS STATION FIELDS
---------------------------
This is an explicitly assumed spatial reconstruction of the existing
three-zone Canberra solution. It is NOT a new CFD/momentum solution or a
validated map of surveyed equipment/pedestrian locations.

Inputs are frozen deployment_model/time_series.csv at t=117.833333 min and
the exact AB30 / AB30-R zone counts in candidate_results.csv. The 300 x 100
grid spans 220 m x 4.8 m; the transverse axis is expanded for visibility.
Background enthalpy h, humidity ratio w and MRT are interpolated with a
shape-preserving PCHIP through zone centers, held at the end-zone values
at the ends of the strip. No additional crowd heat is introduced.

Each device uses the original wet-bulb-limited evaporative outlet and
electrical heating assumption chi=1. Device locations alternate between
y=1.0 and 3.8 m and are evenly spaced within each zone. Device types are
interleaved, with exact original counts. The Gaussian is centered 1 m
downstream of each device. Its principal widths satisfy:
  2*pi*sigma_x*sigma_y = unit footprint (20 or 30 m^2)
  sigma_x/sigma_y = 4.
The footprint sets a display-kernel length scale; it is NOT redefined as
a probability or a thresholded coverage area.

K_j=exp(-0.5*((x-x_j-1)/sigma_x)^2-0.5*((y-y_j)/sigma_y)^2).
Weights g_j=K_j/max(1,sum K_j) bound total supply mixing:
  h_local = h_background + 0.5*sum g_j*(h_supply,j-h_background)
  w_local = w_background + 0.5*sum g_j*(w_supply,j-w_background).
T and RH are recovered from h,w; RH is not directly averaged. This convex
mixing has total beta <= 0.5. Prescribed velocity vectors use the same
weights, a 0.2 m/s background, original zone/device speeds, and assumed
inward angles +/-0.12 radians. SET is recomputed with the original
pythermalcomfort model, met=1.2, clo=0.5 and active applicability limits.
Streamlines only visualize this kinematic velocity interpolation.

Faint crowd dots are a seeded uniform sample inside each original demand
zone; counts round the snapshot's mean occupancy to the nearest integer.
The identical dot layout is used in all three comparisons. They are not
tracked persons or evidence for a subzone crowd hotspot.

Field values are saved in spatial_*.npz; x/y device and crowd coordinates
are exported as CSV. Reported U, E, q and eta are copied from the original
two-hour zonal totals. They are NOT re-integrated from the reconstructed
field. Changing the illustrative kernels cannot change the paper's MILP
solutions or service totals.

2. U.S. CLIMATE CONTEXT
----------------------
Source: NASA POWER climatology point API, parameters T2M (C), RH2M (%) and
PS (kPa), community SB, July. At retrieval on 2026-11-08 the API metadata
specified January 2001-December 2025, a 25-year climatology. All 77 raw
responses, source URLs, hashes and period metadata are archived.

Wet-bulb temperature is evaluated at each paired monthly mean T/RH/PS
state using PsychroLib. The resulting depression is NOT the monthly
average of hourly wet-bulb depression: nonlinear averaging differs.
77 geographic samples include 72 contiguous-U.S. locations and five in
Hawaii. These are reanalysis grid queries, not individual station data.
The display uses linear interpolation in lon/lat; nearest-sample values
fill edges outside the sampling hull. State polygons clip the field.
Alaska is not shown. The regional field is illustrative geographic context,
not design weather or a high-resolution climatological product.

State boundaries: PublicaMundi MappingAPI, data/geojson/us-states.json.
The equirectangular panels preserve the local aspect at 38N (CONUS) and
21N (Hawaii); they have separate scales. Location markers are approximate
city/venue anchors, not an assertion that a specific NYC shelter was surveyed.

Callouts retain the original design scenarios, independent of NASA means:
  NYC:      34 C, RH 30/70%; nominal uniform occupancy, 12 people.
  Fremont:  38 C, RH 20%; original pure fits and selected A266C16.
  Honolulu: 31 C, RH 65%; original pure fits and selected A1B1.
Mini-bar axes share an absolute 0-100 eta scale. Cross-venue differences
also reflect occupancy density and delivered speed, not climate alone.

3. ELECTRICITY, SERVICE AND RADAR
-------------------------------
Electrical E (kWh) is plotted separately from useful SET-excess reduction
U and remaining SET excess R (person*degC*h). Only U+R=R0 is a partition.
SET relief is not an amount of heat absorbed by people and must not be
drawn as a fraction of electrical joules. The original outputs do not
identify motor-loss, ventilation-loss or empty-area-loss energy shares.
The graphic therefore does not invent those shares. It explicitly retains
the user's intended 'where does the input go?' comparison through separate
input and service accounting linked by eta=U/E.

Radar plots compare largest-fitting pure A/B/C and the policy-selected
mixed plan. Five display scores, each increasing outward:
  coverage:         q, unchanged on 0-1;
  mean SET relief:  relief / maximum among the four displayed plans;
  efficiency:       eta / maximum among the four displayed plans;
  spatial access:   1-X, unchanged on 0-1 (no truncated radial range);
  cost economy:     minimum displayed annual cost / plan annual cost.
Normalization is WITHIN each venue. Raw values and denominators are
exported to radar_values.csv. This is a diagnostic display of existing
solutions, not a fifth optimization objective, a new Pareto computation,
or a claim that the mixed plans dominate every pure plan. Largest-fitting
pure plans can violate the policy constraints, as explained in the text.

4. VERIFICATION AND ARCHIVE
--------------------------
frozen_manifest.json records SHA-256 hashes of 74 original CSV/JSON/Python
files. make_figures.py verifies them both before and after plotting.
verification.json records finite fields, physical RH, dimensions, exact
device counts, climate range and the service-account identity.
No original model input, solver code, calculated output or equation is
changed by the visualization phase. The source archive retains all model
files and previous graphics; consolidated/replaced graphics are simply no
longer included in the main LaTeX document.

Main manuscript page budget: Summary Sheet through References <=25 pages;
the separately appended Report on Use of AI Tools is excluded from that count.
