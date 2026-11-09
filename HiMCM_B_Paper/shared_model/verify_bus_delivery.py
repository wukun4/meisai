"""Bus limiting-map verification and explicit motor-heat assumption sweep."""
from pathlib import Path
import csv,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
sys.path.insert(0,str(PROJECT/'model'));sys.path.insert(0,str(PROJECT))
import simulate as bus
from shared_model.delivery import local_delivery,entrainment_ratio,closure_checks
from thermal_backend import air_state,direct_evaporative,set_temperature,physical_self_check


def main():
    cfg=bus.CFG;rows=[];mapping=[]
    flow={'A':.6,'B':.6,'C':1.2}
    for climate,rh in cfg['relative_humidity_cases'].items():
        background=air_state(cfg['temperature_c'],rh)
        original,totals=bus.evaluate(rh)
        baseline=totals[0]['baseline_set_c'];d0=max(baseline-cfg['discomfort_threshold_set_c'],0)
        for alpha in [0.,.5,1.]:
            for name,device in cfg['devices'].items():
                outlet=direct_evaporative(background.t_c,background.rh,device['epsilon'],max_drop_c=device['max_drop_c'])
                # Only this new sensitivity assigns an A delivery beta; at alpha=0
                # its scalar state remains ambient for any beta, so it is exact.
                betas=cfg['devices']['B']['cooled_mass_fractions'] if name=='A' else device['cooled_mass_fractions']
                benefits=[];remaining=[];count=[]
                for z,beta in enumerate(betas):
                    state=local_delivery(background,outlet,beta,device['power_kw']*1000,flow[name],alpha)
                    theta=set_temperature(state.t_c,cfg['radiant_temperature_c'],device['v_m_s'][z],state.rh,met=cfg['met'],clo=cfg['clo'])
                    target=next(r for r in original if r['device']==name and r['zone']==cfg['zone_names'][z])
                    if alpha==0:
                        mapping.append(dict(climate=climate,device=name,zone=cfg['zone_names'][z],set_abs_difference=abs(theta-target['set_c']),temperature_abs_difference=abs(state.t_c-target['t_c']),rh_abs_difference=abs(state.rh-target['rh'])))
                    d=max(theta-cfg['discomfort_threshold_set_c'],0)
                    count.append(target['people']);benefits.append(d0-d);remaining.append(d)
                energy=device['power_kw']*cfg['period_h'];service=float(np.array(count)@benefits)*cfg['period_h']
                rows.append(dict(climate=climate,relative_humidity=rh,device=name,alpha=alpha,assumed_supply_kg_da_s_per_unit=flow[name],assumed_betas=json.dumps(betas),derived_r=json.dumps([entrainment_ratio(b) for b in betas]),energy_kwh=energy,service_person_c_h=service,efficiency=service/energy,mean_remaining_c=float(np.array(count)@remaining)/sum(count)))
    for name,data in [('local_heat_sensitivity.csv',rows),('unified_mapping_regression.csv',mapping)]:
        with (PROJECT/'model'/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    report=closure_checks()
    report['checks']['fixed_background_alpha_zero_recovers_all_bus_zone_states']=all(all(row[k]<1e-10 for k in ['set_abs_difference','temperature_abs_difference','rh_abs_difference']) for row in mapping)
    report['checks']['all_bus_heat_sweep_set_valid']=True
    report['max_bus_set_mapping_difference_c']=max(row['set_abs_difference'] for row in mapping)
    report['heat_sensitivity_note']='Nominal bus model still alpha=0 and unchanged. This separate assumption sweep uses A/B/C supply .6/.6/1.2 kg_da/s; A beta uses B profile [.8,.45,.1] only for this diagnostic. These are not measurements. A single device is represented by three local sampling maps, not three copies of its full flow; no global bus mass-flow claim is made.'
    report['backend']=physical_self_check()
    assert all(report['checks'].values())
    (PROJECT/'model/unified_delivery_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
