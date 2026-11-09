"""Extreme dry-heat audit of the unchanged bus psychrometric/SET model.

Default SET input guards remain active for all accepted tests. Only explicitly
labelled diagnostic extrapolations call set_tmp(limit_inputs=False), after the
default guard has rejected at least one baseline/local condition. Diagnostics
are exported separately and never plotted in the paper's figure26.
"""
from pathlib import Path
import copy
import csv
import hashlib
import importlib.metadata
import json
import os
import sys
import warnings

ROOT=Path(__file__).resolve().parent; PROJECT=ROOT.parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'.cache'))
os.environ.setdefault('NUMBA_CACHE_DIR',str(ROOT/'.numba_cache'))
sys.path.insert(0,str(PROJECT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pythermalcomfort.models import set_tmp
from thermal_backend import air_state,direct_evaporative,wet_bulb_c
from shared_model.delivery import local_delivery
from geometry import occupancy_counts
import simulate as bus

CFG=copy.deepcopy(bus.CFG)
SOURCE_PATHS=['model/simulate.py','model/thermal_backend.py','model/scenario.json',
              'shared_model/delivery.py','model/scenario_results.csv']
COL={'A':'#2379A5','B':'#D18C32','C':'#76559A'}


def source_hashes():
    return {name:hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() for name in SOURCE_PATHS}


def write_csv(name,rows):
    with (ROOT/name).open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def evaluate_case(ta,rh,tr):
    """Same delivery and service equations as simulate.evaluate; audited guard."""
    background=air_state(ta,rh)
    n=np.asarray(occupancy_counts(CFG,'Uniform'),dtype=float)
    descriptors=[]
    for kind,device in CFG['devices'].items():
        outlet=direct_evaporative(ta,rh,device['epsilon'],max_drop_c=device['max_drop_c'])
        for z,beta in enumerate(device['cooled_mass_fractions']):
            state=local_delivery(background,outlet,beta)
            descriptors.append((kind,z,beta,state,outlet))
    # Evaluate the baseline and all nine local states with the default mask first.
    temperatures=np.array([ta]+[item[3].t_c for item in descriptors])
    humidities=np.array([rh]+[item[3].rh for item in descriptors])
    speeds=np.array([CFG['baseline_air_speed_m_s']]+[
        CFG['devices'][kind]['v_m_s'][z] for kind,z,*_ in descriptors])
    args=dict(tdb=temperatures,tr=tr,v=speeds,rh=100*humidities,
              met=CFG['met'],clo=CFG['clo'],p_atm=101325.,position='standing',
              wme=0.,body_surface_area=1.8258,round_output=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        guarded=np.asarray(set_tmp(**args,limit_inputs=True).set,dtype=float)
    accepted=bool(np.all(np.isfinite(guarded)))
    if accepted:
        mode='guard_boundary' if np.any(temperatures==40.) or tr==40. else 'strict_interior'
        theta=guarded; guard_enabled=True
    else:
        mode='diagnostic_extrapolation'; guard_enabled=False
        # This is the only unguarded call. Its output is labelled and stored
        # separately; it cannot enter figure26 or accepted-results CSVs.
        theta=np.asarray(set_tmp(**args,limit_inputs=False).set,dtype=float)
        print(f'DIAGNOSTIC EXTRAPOLATION ONLY: Ta={ta:g}, RH={rh:g}, Tr={tr:g}',flush=True)
    if not np.all(np.isfinite(theta)):
        raise ValueError('SET algorithm failed to converge for a diagnostic test')
    baseline=float(theta[0]);d0=max(baseline-CFG['discomfort_threshold_set_c'],0.)
    common=dict(temperature_c=ta,ambient_rh=rh,radiant_temperature_c=tr,
                radiant_offset_c=tr-ta,set_mode=mode,limit_inputs=guard_enabled,
                default_guard_accepted=accepted,baseline_set_c=baseline,
                wet_bulb_c=wet_bulb_c(ta,rh))
    local=[];summary=[]
    for i,(kind,z,beta,state,outlet) in enumerate(descriptors,1):
        local.append(dict(**common,device=kind,zone=CFG['zone_names'][z],people=float(n[z]),
                          local_temperature_c=state.t_c,local_rh=state.rh,
                          local_speed_m_s=float(speeds[i]),delivery_beta=beta,
                          outlet_temperature_c=outlet.t_c,outlet_drop_c=ta-outlet.t_c,
                          outlet_enthalpy_error_j_kg=outlet.h_j_kg_da-background.h_j_kg_da,
                          outlet_water_increment_kg_kg=outlet.w-background.w,
                          local_set_c=float(theta[i]),set_relief_c=baseline-float(theta[i]),
                          discomfort_relief_c=d0-max(float(theta[i])-CFG['discomfort_threshold_set_c'],0.),
                          default_guard_local_set_c=float(guarded[i]) if np.isfinite(guarded[i]) else ''))
    for kind,device in CFG['devices'].items():
        group=[r for r in local if r['device']==kind]
        relief=np.array([r['discomfort_relief_c'] for r in group])
        set_relief=np.array([r['set_relief_c'] for r in group])
        service=float(n@relief)*CFG['period_h']
        energy=device['power_kw']*CFG['period_h']
        summary.append(dict(**common,device=kind,period_h=CFG['period_h'],person_hours=float(n.sum())*CFG['period_h'],
                            energy_kwh=energy,service_person_c_h=service,efficiency=service/energy,
                            mean_set_relief_c=float(n@set_relief/n.sum()),
                            mean_discomfort_relief_c=float(n@relief/n.sum()),
                            mean_air_temperature_reduction_c=float(n@np.array([ta-r['local_temperature_c'] for r in group])/n.sum()),
                            outlet_drop_c=group[0]['outlet_drop_c']))
    audit=dict(temperature_c=ta,ambient_rh=rh,radiant_temperature_c=tr,mode=mode,
               default_guard_accepted=accepted,rejected_point_count=int(np.count_nonzero(~np.isfinite(guarded))),
               guard_warnings=sorted(set(str(w.message) for w in captured)),
               efficiency_order=[r['device'] for r in sorted(summary,key=lambda r:r['efficiency'],reverse=True)])
    return summary,local,audit


def make_figure(rows):
    selected=[r for r in rows if r['temperature_c']==40. and r['radiant_temperature_c']==40.
              and r['ambient_rh'] in [.15,.20]]
    assert len(selected)==6 and all(r['default_guard_accepted'] for r in selected)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.labelsize':12,
                         'axes.titlesize':13,'xtick.labelsize':12,'ytick.labelsize':12,
                         'legend.fontsize':12,'pdf.fonttype':42,'ps.fonttype':42,
                         'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,2,figsize=(10.3,4.6),layout='constrained')
    x=np.arange(2);width=.23
    for k,kind in enumerate('ABC'):
        rr=[next(r for r in selected if r['device']==kind and r['ambient_rh']==rh) for rh in [.15,.20]]
        for ax,key,fmt in zip(axs,['efficiency','mean_set_relief_c'],['%.1f','%.2f']):
            bars=ax.bar(x+(k-1)*width,[r[key] for r in rr],width,label=kind,color=COL[kind])
            ax.bar_label(bars,fmt=fmt,padding=3,fontsize=12)
    for ax in axs:
        ax.set(xticks=x,xticklabels=['RH 15%','RH 20%'])
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axs[0].set(title='A. Efficiency comparison',ylabel='Service efficiency η',ylim=(0,88))
    axs[1].set(title='B. SET relief explains the numerator',ylabel='Mean SET relief (°C)',ylim=(0,4.3))
    axs[0].legend(ncol=3,loc='upper center',fontsize=12)
    fig.suptitle('Extreme dry heat: unchanged devices and delivery',fontsize=15,fontweight='bold')
    fig.supxlabel('Upper applicability boundary of the standard ASHRAE SET physiological model (40°C).\n'
                   'η is the comparison criterion; SET relief describes its numerator. η unit: person·°C·h/kWh.',fontsize=12)
    path=PROJECT/'figures/26_extreme_heat.pdf'
    fig.savefig(path,bbox_inches='tight',pad_inches=.03,facecolor='white');plt.close(fig)
    return path


def main():
    before=source_hashes();accepted=[];diagnostic=[];accepted_local=[];diagnostic_local=[];audits=[]
    cases={(ta,rh,ta+offset) for ta in [40.,41.,42.] for rh in [.15,.175,.20] for offset in [0.,2.]}
    cases.update((39.,rh,39.) for rh in [.15,.20])
    for ta,rh,tr in sorted(cases):
        rows,local,audit=evaluate_case(ta,rh,tr);audits.append(audit)
        if audit['default_guard_accepted']:accepted+=rows;accepted_local+=local
        else:diagnostic+=rows;diagnostic_local+=local
    checks={}
    checks['accepted_cases_keep_default_SET_guard']=all(r['limit_inputs'] for r in accepted)
    checks['diagnostics_explicitly_marked_and_separated']=all(r['set_mode']=='diagnostic_extrapolation' and not r['limit_inputs'] for r in diagnostic)
    checks['all_42C_cases_rejected_by_default_guard']=all(not a['default_guard_accepted'] for a in audits if a['temperature_c']==42.)
    checks['all_requested_Tr_equals_Ta_plus_2_cases_separated']=all(a['mode']=='diagnostic_extrapolation' for a in audits if a['radiant_temperature_c']==a['temperature_c']+2.)
    checks['39C_strict_interior_guard_accepted']=all(a['mode']=='strict_interior' for a in audits if a['temperature_c']==39.)
    checks['40C_Tr40_boundary_guard_accepted']=all(a['mode']=='guard_boundary' for a in audits if a['temperature_c']==a['radiant_temperature_c']==40.)
    checks['efficiency_equals_signed_service_over_energy']=all(abs(r['efficiency']-r['service_person_c_h']/r['energy_kwh'])<1e-12 for r in accepted+diagnostic)
    checks['unchanged_device_power_and_period']=all(r['energy_kwh']==CFG['devices'][r['device']]['power_kw']*CFG['period_h'] for r in accepted+diagnostic)
    local_all=accepted_local+diagnostic_local
    checks['outlet_caps_preserved']=all(-1e-10<=r['outlet_drop_c']<=CFG['devices'][r['device']]['max_drop_c']+1e-10 for r in local_all)
    checks['isenthalpic_outlets_and_nonnegative_added_water']=all(abs(r['outlet_enthalpy_error_j_kg'])<1e-8 and r['outlet_water_increment_kg_kg']>=-1e-12 for r in local_all)
    checks['single_phase_local_air']=all(0<=r['local_rh']<=1 for r in local_all)
    # Independently match the existing scalar implementation on every accepted case.
    max_reference_error=0.
    for audit in audits:
        if not audit['default_guard_accepted']:continue
        cfg=copy.deepcopy(CFG);cfg.update(temperature_c=audit['temperature_c'],radiant_temperature_c=audit['radiant_temperature_c'])
        _,old=bus.evaluate(audit['ambient_rh'],cfg)
        for previous in old:
            current=next(r for r in accepted if r['temperature_c']==audit['temperature_c']
                         and r['ambient_rh']==audit['ambient_rh'] and r['radiant_temperature_c']==audit['radiant_temperature_c']
                         and r['device']==previous['device'])
            max_reference_error=max(max_reference_error,abs(current['efficiency']-previous['efficiency']),
                                    abs(current['service_person_c_h']-previous['service_person_c_h']))
    checks['accepted_results_reproduce_original_bus_solver']=max_reference_error<1e-10
    write_csv('extreme_heat_valid_results.csv',accepted);write_csv('extreme_heat_valid_local.csv',accepted_local)
    write_csv('extreme_heat_diagnostic_results.csv',diagnostic);write_csv('extreme_heat_diagnostic_local.csv',diagnostic_local)
    figure=make_figure(accepted)
    checks['original_model_and_csv_hashes_unchanged']=source_hashes()==before
    assert all(checks.values()),checks
    assumptions={'temperature_grid_c':[40.,41.,42.],'interior_confirmation_temperature_c':39.,
      'rh_grid':[.15,.175,.20],'interior_confirmation_rh':[.15,.20],
      'radiant_offsets_c':[0.,2.],'pressure_pa':101325.,'occupancy':list(occupancy_counts(CFG,'Uniform')),
      'period_h':CFG['period_h'],'met':CFG['met'],'clo':CFG['clo'],'posture':'standing',
      'body_surface_area_m2':1.8258,'external_work_met':0.,'baseline_speed_m_s':CFG['baseline_air_speed_m_s'],
      'set_service_reference_c':CFG['discomfort_threshold_set_c'],'local_heat_fraction_chi':0.,
      'device_parameters_unchanged':CFG['devices'],
      'background':'fixed outdoor reservoir; no bus accumulation or solar-load solution',
      'data_status':'hypothetical stress scenarios; not measured venue data'}
    report={'versions':{k:importlib.metadata.version(k) for k in ['pythermalcomfort','psychrolib','numpy','matplotlib']},
      'checks':checks,'max_reference_solver_error':max_reference_error,'source_hashes':before,
      'assumptions':assumptions,'accepted_cases':[a for a in audits if a['default_guard_accepted']],
      'accepted_results':accepted,'figure':str(figure.relative_to(PROJECT)),
      'guard_note':'Official SET docstring prints 10<tdb,tr<40; installed4.8.1 _valid_range uses inclusive [10,40]. 39C is strict interior; 40C is only a default-guard-accepted boundary, not additional empirical validation.',
      'diagnostic_files':['extreme_heat_diagnostic_results.csv','extreme_heat_diagnostic_local.csv','extreme_heat_diagnostic.json']}
    (ROOT/'extreme_heat_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'extreme_heat_diagnostic.json').write_text(json.dumps({'status':'Diagnostic extrapolation only; excluded from paper figure and accepted results',
       'method':'Default guard evaluated and rejected first; limit_inputs=False then explicitly enabled for a labelled computational extension',
       'cases':[a for a in audits if not a['default_guard_accepted']],'results':diagnostic},indent=2)+'\n')
    print(json.dumps({'checks':checks,'accepted_results':accepted},indent=2))


if __name__=='__main__':main()
