"""Independent output audit for the distinct Task 3 and Task 4 candidate scopes."""
from pathlib import Path
import csv,json,math
ROOT=Path(__file__).resolve().parent
summary=json.loads((ROOT/'results.json').read_text())
inputs=json.loads((ROOT/'inputs.json').read_text())
econ=inputs['economics'];checks={};details={}
for venue,result in summary.items():
    rows=list(csv.DictReader((ROOT/(venue.lower()+'_all_allocations.csv')).open()))
    positive=[r for r in rows if float(r['energy_kwh'])>0]
    eligible=[r for r in positive if float(r['coverage'])>=econ['coverage_min']-1e-10]
    vv=inputs['venues'][venue]
    policy=[r for r in eligible if float(r['mean_residual_c'])<=vv['residual_cap_c']+1e-10
            and float(r['floor_loss'])<=econ['floor_loss_max']+1e-10
            and float(r['energy_kwh_year'])<=vv['energy_cap_kwh_year']+1e-10]
    best_eta=max(float(r['efficiency']) for r in positive)
    ties=[r for r in positive if abs(float(r['efficiency'])-best_eta)<1e-9]
    checks[venue+'_eta_from_unfiltered_positive_domain']=abs(best_eta-result['efficiency_best']['efficiency'])<1e-9
    checks[venue+'_eta_ties_reported']=len(ties)==result['efficiency_tie_count']
    checks[venue+'_smallest_tied_maximizer']=abs(min(float(r['energy_kwh']) for r in ties)-result['efficiency_best']['energy_kwh'])<1e-9
    # This comparison uses the entire eligible allocation set, not grouped counts.
    brute=min(float(r['annual_cost_usd']) for r in policy)
    checks[venue+'_grouping_preserves_full_policy_minimum']=abs(brute-result['selected']['annual_cost_usd'])<1e-8
    groups={}
    for r in eligible:groups.setdefault(r['counts'],[]).append(r)
    checks[venue+'_counts_fix_other_three_objectives']=all(
        max(float(r[key]) for r in group)-min(float(r[key]) for r in group)<1e-10
        for group in groups.values() for key in ['annual_cost_usd','energy_kwh_year','floor_loss'])
    checks[venue+'_group_count_matches']=len(groups)==result['distinct_coverage_feasible']
    checks[venue+'_all_layouts_obey_nonoverlap']=all(
        sum(n*inputs['devices'][k]['footprint_m2'] for n,k in zip(z,'ABC'))<=a+1e-10
        for r in rows for z,a in zip(json.loads(r['x']),vv['areas_m2']))
    for k,bench in result['equal_coverage_benchmarks'].items():
        matches=[r for r in positive if r['family']==k and abs(float(r['coverage'])-econ['comparison_coverage'])<1e-10]
        checks[venue+'_equal_coverage_'+k]=abs(bench['coverage']-econ['comparison_coverage'])<1e-10 and abs(bench['energy_kwh']-min(float(r['energy_kwh']) for r in matches))<1e-9
    checks[venue+'_annual_and_session_energy_consistent']=all(abs(float(r['energy_kwh_year'])-float(r['energy_kwh'])*econ['hours_year']/econ['period_h'])<1e-9 for r in rows)
    price_rows=[r for r in csv.DictReader((ROOT/'cost_sensitivity.csv').open()) if r['venue']==venue]
    feasible_names={r['plan'] for r in policy}
    checks[venue+'_all_price_winners_are_policy_feasible']=len(price_rows)==243 and all(r['plan'] in feasible_names for r in price_rows)
    details[venue]=dict(full_layouts=len(rows),positive_energy_layouts=len(positive),
        efficiency_max=best_eta,tied_layouts=len(ties),coverage_eligible_layouts=len(eligible),
        coverage_eligible_count_groups=len(groups),full_policy_feasible_layouts=len(policy),
        brute_force_annual_cost_minimum=brute)
assert all(checks.values()),checks
report=dict(checks=checks,details=details,
    interpretation='Numerical accounting/scope verification; the Pareto domain is conditioned on q>=.80, while Task3 eta is unfiltered.')
(ROOT/'verification_scope.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
