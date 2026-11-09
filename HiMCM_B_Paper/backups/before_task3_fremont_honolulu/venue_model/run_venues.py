"""Reproducible Task 3-5 scenarios; official venue identity, assumed engineering data.

Imports the paper's unchanged CP-SET psychrometric, local-delivery and SET modules.
Enumerates all nonoverlapping integer allocations in three occupancy zones.
No measured venue geometry, equipment installation or calibrated costs are claimed.
"""
from pathlib import Path
import os, sys, json, csv, itertools, math, copy
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
os.environ.setdefault('MPLCONFIGDIR', '/tmp/himcm-venue-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/himcm-venue-cache')
os.environ.setdefault('NUMBA_CACHE_DIR', '/tmp/himcm-venue-numba')
sys.path[:0] = [str(PROJECT / 'model'), str(PROJECT)]
import numpy as np
from thermal_backend import air_state, direct_evaporative, set_temperature, wet_bulb_c, physical_self_check
from shared_model.delivery import local_delivery, closure_checks
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SOURCE_CFG = json.loads((PROJECT / 'model/scenario.json').read_text())
DEV = copy.deepcopy(SOURCE_CFG['devices'])
for k, area, flow, floor, capital, maintenance in [
        ('A',20.,1.2,.5,300.,30.),('B',30.,2.,1.,1000.,100.),
        ('C',40.,3.,1.5,2000.,200.)]:
    DEV[k].update(footprint_m2=area, supply_kg_da_s=flow, floor_clearance_m2=floor,
                  capital_usd=capital, maintenance_usd_year=maintenance)
VENUES = {
    'Phoenix': dict(name='Ullman Terrace, Desert Botanical Garden',
        t_c=36., rh=.25, tr_c=38., areas_m2=[100.,100.,100.], people=[60.,40.,20.],
        residual_cap_c=4.5, energy_cap_kwh_year=6000.),
    'Singapore': dict(name='Satay Street, Lau Pa Sat',
        t_c=32., rh=.75, tr_c=34., areas_m2=[80.,80.,80.], people=[60.,36.,24.],
        residual_cap_c=7.5, energy_cap_kwh_year=2400.),
}
ECON = dict(period_h=4., hours_year=600., electricity_usd_kwh=.20,
            water_usd_m3=3., make_up_factor=1.15, discount_rate=.05, life_year=5,
            coverage_min=.80, floor_loss_max=.035, met=1.2, clo=.5,
            position='sitting', baseline_v=.2, set_reference_c=26.,comparison_coverage=.60)
CRF=ECON['discount_rate']*(1+ECON['discount_rate'])**ECON['life_year']/((1+ECON['discount_rate'])**ECON['life_year']-1)

def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def write_csv(name, rows):
    with (ROOT/name).open('w', newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def thermal(v, beta_shift=0., velocity_factor=1.):
    base=air_state(v['t_c'],v['rh'])
    s0=set_temperature(base.t_c,v['tr_c'],ECON['baseline_v'],base.rh,
                       met=ECON['met'],clo=ECON['clo'],position=ECON['position'])
    d0=max(0.,s0-ECON['set_reference_c']); rows=[]; output={}
    for k,d in DEV.items():
        outlet=base if k=='A' else direct_evaporative(base.t_c,base.rh,d['epsilon'],max_drop_c=d['max_drop_c'])
        ds=[]
        for j,(beta,speed) in enumerate(zip(d['cooled_mass_fractions'],d['v_m_s'])):
            beta=float(np.clip(beta+beta_shift,0,1)) if k!='A' else beta
            speed=ECON['baseline_v']+velocity_factor*(speed-ECON['baseline_v'])
            state=local_delivery(base,outlet,beta)
            theta=set_temperature(state.t_c,v['tr_c'],speed,state.rh,
                met=ECON['met'],clo=ECON['clo'],position=ECON['position'])
            ds.append(max(theta-ECON['set_reference_c'],0.))
            rows.append(dict(device=k,strip=j+1,beta=beta,t_c=state.t_c,rh=state.rh,
                             v_m_s=speed,set_c=theta,outlet_t_c=outlet.t_c))
        # Supply is counted once per physical device, not once per delivery strip.
        water_m3_h=3600*DEV[k]['supply_kg_da_s']*(outlet.w-base.w)*ECON['make_up_factor']/1000
        output[k]=dict(residual_c=float(np.mean(ds)),benefit_c=d0-float(np.mean(ds)),
            water_m3_h=max(water_m3_h,0.),outlet_t_c=outlet.t_c)
    return dict(baseline_set_c=s0,baseline_residual_c=d0,wet_bulb_c=wet_bulb_c(v['t_c'],v['rh']),
                devices=output,local=rows)

def allocation_choices(area):
    return [q for q in itertools.product(range(int(area/20)+1),range(int(area/30)+1),range(int(area/40)+1))
            if sum(q[j]*DEV[k]['footprint_m2'] for j,k in enumerate('ABC'))<=area+1e-9]

def evaluate(v,th,x):
    x=np.array(x,dtype=int); counts=x.sum(axis=0); area=np.array(v['areas_m2']); people=np.array(v['people'])
    fractions=x*np.array([DEV[k]['footprint_m2'] for k in 'ABC'])[None,:]/area[:,None]
    assert np.all(fractions.sum(axis=1)<=1+1e-9)
    q=float(people@fractions.sum(axis=1)/people.sum())
    relief=float(people@fractions@np.array([th['devices'][k]['benefit_c'] for k in 'ABC']))
    residual=th['baseline_residual_c']-relief/people.sum()
    power=float(counts@np.array([DEV[k]['power_kw'] for k in 'ABC']))
    water_h=float(counts@np.array([th['devices'][k]['water_m3_h'] for k in 'ABC']))
    cap=float(counts@np.array([DEV[k]['capital_usd'] for k in 'ABC']))
    maint=float(counts@np.array([DEV[k]['maintenance_usd_year'] for k in 'ABC']))
    energy=power*ECON['period_h']; service=relief*ECON['period_h']
    eyear=power*ECON['hours_year']; wyear=water_h*ECON['hours_year']
    floor=float(counts@np.array([DEV[k]['floor_clearance_m2'] for k in 'ABC'])/area.sum())
    components=dict(ownership=CRF*cap,maintenance=maint,electricity=ECON['electricity_usd_kwh']*eyear,
                    water=ECON['water_usd_m3']*wyear)
    return dict(plan=''.join(k+str(int(n)) for k,n in zip('ABC',counts) if n) or 'None',
        x=x.tolist(),counts=counts.tolist(),coverage=q,mean_residual_c=residual,
        mean_benefit_c=relief/people.sum(),service_person_c_h=service,energy_kwh=energy,
        efficiency=service/energy if energy else None,water_m3=water_h*ECON['period_h'],
        energy_kwh_year=eyear,water_m3_year=wyear,floor_loss=floor,
        annual_cost_usd=sum(components.values()),capital_usd=cap,components=components,
        family=('None' if not counts.any() else next(k for k,n in zip('ABC',counts) if n) if np.count_nonzero(counts)==1 else 'Mixed'))

def policy(v,r,residual_cap=None):
    cap=v['residual_cap_c'] if residual_cap is None else residual_cap
    return (r['coverage']>=ECON['coverage_min']-1e-10 and
        r['mean_residual_c']<=cap+1e-10 and r['floor_loss']<=ECON['floor_loss_max']+1e-10
        and r['energy_kwh_year']<=v['energy_cap_kwh_year']+1e-10)

def enumerate_venue(v,th):
    rows=[evaluate(v,th,x) for x in itertools.product(*(allocation_choices(a) for a in v['areas_m2']))]
    # Same device counts imply identical energy, cost, floor loss and water.
    # Under the mandatory coverage constraint, retain the least residual layout.
    grouped={}
    for r in rows:
        if r['coverage']<ECON['coverage_min']-1e-10:continue
        key=tuple(r['counts'])
        if key not in grouped or r['mean_residual_c']<grouped[key]['mean_residual_c']-1e-12:
            grouped[key]=r
    unique=list(grouped.values())
    values=np.array([[r['mean_residual_c'],r['floor_loss'],r['energy_kwh_year'],r['annual_cost_usd']] for r in unique])
    for i,r in enumerate(unique):
        r['pareto']=not bool(np.any(np.all(values<=values[i]+1e-10,axis=1)&np.any(values<values[i]-1e-10,axis=1)))
    feasible=[r for r in unique if policy(v,r)]
    winner=min(feasible,key=lambda r:(r['annual_cost_usd'],r['energy_kwh_year'],r['mean_residual_c'],r['x']))
    benchmarks={}
    for k in 'ABC':
        pure=[r for r in rows if r['family']==k]
        benchmarks[k]=min(pure,key=lambda r:(-r['coverage'],r['mean_residual_c'],r['energy_kwh']))
    return rows,unique,winner,benchmarks

def flatten(r):
    return {k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()}

def main():
    results={};locals_=[];checks={};sensitivity=[];prices=[];scaling=[];curves=[]
    checks['physical_backend']=physical_self_check()['checks']=='passed'
    checks['delivery_conservation']=all(closure_checks()['checks'].values())
    for key,v in VENUES.items():
        th=thermal(v);rows,unique,winner,bench=enumerate_venue(v,th)
        positive=[r for r in rows if r['energy_kwh']>0]
        best_eta=max(r['efficiency'] for r in positive)
        ties=[r for r in positive if abs(r['efficiency']-best_eta)<1e-9]
        efficiency_best=min(ties,key=lambda r:(r['energy_kwh'],r['x']))
        equal_coverage={}
        pure_efficiency={}
        for family in 'ABC':
            pure=[r for r in positive if r['family']==family]
            best=max(r['efficiency'] for r in pure)
            pure_efficiency[family]=min([r for r in pure if abs(r['efficiency']-best)<1e-9],key=lambda r:r['energy_kwh'])
            sameq=[r for r in pure if abs(r['coverage']-ECON['comparison_coverage'])<1e-10]
            equal_coverage[family]=min(sameq,key=lambda r:(r['energy_kwh'],r['mean_residual_c'],r['x']))
        zero=evaluate(v,th,[[0,0,0]]*3)
        checks[key+'_zero_control']=zero['service_person_c_h']==0 and zero['energy_kwh']==0 and zero['coverage']==0
        checks[key+'_matched_service_balance']=all(abs(r['service_person_c_h']+r['mean_residual_c']*sum(v['people'])*ECON['period_h']-th['baseline_residual_c']*sum(v['people'])*ECON['period_h'])<1e-8 for r in rows)
        checks[key+'_policy_feasible']=policy(v,winner)
        checks[key+'_winner_on_pareto_frontier']=winner['pareto']
        checks[key+'_saturation_bound']=all(0<=r['rh']<=1 for r in th['local'])
        write_csv(key.lower()+'_all_allocations.csv',[flatten(r) for r in rows])
        write_csv(key.lower()+'_distinct_candidates.csv',[flatten(r) for r in unique])
        for r in th['local']:locals_.append(dict(venue=key,**r))
        # Stress the delivery and weather assumptions; retain both selected-plan
        # performance and the reoptimized result under the original policy.
        for label,rh_shift,beta_shift,speed in [('RH -10 pp',-.10,0,1),('RH +10 pp',.10,0,1),
            ('beta -0.15',0,-.15,1),('beta +0.15',0,.15,1),('speed -20%',0,0,.8),('speed +20%',0,0,1.2)]:
            vv=copy.deepcopy(v);vv['rh']+=rh_shift
            tt=thermal(vv,beta_shift,speed);fixed=evaluate(vv,tt,winner['x'])
            # Layout possibilities do not change; recompute all representative
            # allocations directly so a prior ranking cannot hide an alternative.
            rr=[evaluate(vv,tt,r['x']) for r in rows]
            feasible=[r for r in rr if policy(vv,r)]
            opt=min(feasible,key=lambda r:(r['annual_cost_usd'],r['energy_kwh_year'],r['mean_residual_c'])) if feasible else None
            sensitivity.append(dict(venue=key,case=label,selected_plan=winner['plan'],fixed_residual=fixed['mean_residual_c'],
                fixed_efficiency=fixed['efficiency'],fixed_feasible=policy(vv,fixed),
                reoptimized_plan=opt['plan'] if opt else 'none within policy',
                reoptimized_cost=opt['annual_cost_usd'] if opt else None))
        # Independent capital multipliers by device plus energy/water prices:
        # 3^5 = 243 cost scenarios, physical constraints held constant.
        feasible=[r for r in unique if policy(v,r)]
        for a,b,c,e,w in itertools.product((.7,1.,1.3),(.7,1.,1.3),(.7,1.,1.3),(.5,1.,1.5),(.5,1.,1.5)):
            def cost(r):
                return CRF*sum(n*DEV[k]['capital_usd']*m for n,k,m in zip(r['counts'],'ABC',(a,b,c)))+r['components']['maintenance']+e*r['components']['electricity']+w*r['components']['water']
            opt=min(feasible,key=lambda r:(cost(r),r['energy_kwh_year'],r['mean_residual_c']))
            prices.append(dict(venue=key,capital_A=a,capital_B=b,capital_C=c,electricity=e,water=w,
                               plan=opt['plan'],annual_cost=cost(opt),same_plan=opt['plan']==winner['plan']))
        # Scale area and demand at fixed density; count twice only in the second
        # case. This distinguishes adequate coverage from unchanged U/E.
        doubled=copy.deepcopy(v);doubled['areas_m2']=[2*a for a in v['areas_m2']];doubled['people']=[2*n for n in v['people']]
        same=evaluate(doubled,th,winner['x']);twice=evaluate(doubled,th,(np.array(winner['x'])*2).tolist())
        checks[key+'_same_equipment_scale']=abs(same['service_person_c_h']-winner['service_person_c_h'])<1e-8 and abs(same['coverage']-winner['coverage']/2)<1e-10
        checks[key+'_replicated_equipment_scale']=abs(twice['efficiency']-winner['efficiency'])<1e-8 and abs(twice['coverage']-winner['coverage'])<1e-10 and abs(twice['energy_kwh']-2*winner['energy_kwh'])<1e-10
        for label,r in [('Reference',winner),('Double area/demand, same devices',same),('Double area/demand/devices',twice)]:
            scaling.append(dict(venue=key,case=label,coverage=r['coverage'],residual=r['mean_residual_c'],
                energy_kwh=r['energy_kwh'],service=r['service_person_c_h'],efficiency=r['efficiency']))
        for cap in np.linspace(th['baseline_residual_c']-4.,th['baseline_residual_c']-1.,61):
            feasible=[r for r in unique if policy(v,r,float(cap))]
            if feasible:
                r=min(feasible,key=lambda r:(r['annual_cost_usd'],r['energy_kwh_year'],r['mean_residual_c']))
                curves.append(dict(venue=key,required_relief=th['baseline_residual_c']-float(cap),cost=r['annual_cost_usd'],plan=r['plan']))
        results[key]=dict(venue=v,thermal=th,allocation_count=len(rows),distinct_coverage_feasible=len(unique),
            pareto_count=sum(r['pareto'] for r in unique),selected=winner,benchmarks=bench,
            efficiency_best=efficiency_best,efficiency_tie_count=len(ties),pure_efficiency_best=pure_efficiency,
            equal_coverage_benchmarks=equal_coverage,
            cost_grid_same_plan=sum(r['same_plan'] for r in prices if r['venue']==key),cost_grid_count=243)
        make_comparison_panel_data=unique
    assert all(checks.values()),checks
    dump('inputs.json',dict(status='Illustrative design assumptions; not a measured installation',venues=VENUES,devices=DEV,economics=ECON,
        crf=CRF,provenance='Official sources establish venue identity and climate class; all engineering, occupancy, weather snapshot and cost inputs are assumptions.'))
    dump('results.json',results);dump('verification.json',checks)
    write_csv('local_conditions.csv',locals_);write_csv('physical_sensitivity.csv',sensitivity)
    write_csv('cost_sensitivity.csv',prices);write_csv('scale_checks.csv',scaling);write_csv('policy_curves.csv',curves)
    make_figures(results,curves)
    print(json.dumps({k:{'allocations':r['allocation_count'],'pareto':r['pareto_count'],
        'winner':r['selected'],'cost_grid_same_plan':r['cost_grid_same_plan']} for k,r in results.items()},indent=2))

def make_figures(results,curves):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'pdf.fonttype':42,'axes.labelsize':10,'axes.titlesize':11})
    colors={'A':'#246E9E','B':'#C58A2B','C':'#866097','Mixed':'#487F69'}
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.25),layout='constrained')
    for ax,(key,result) in zip(axs,results.items()):
        rows=list(csv.DictReader((ROOT/(key.lower()+'_all_allocations.csv')).open()))
        for family in ['Mixed','A','B','C']:
            rr=[r for r in rows if r['family']==family and r['efficiency']]
            points=sorted(set((round(100*float(r['coverage']),5),round(float(r['efficiency']),6)) for r in rr))
            ax.scatter([p[0] for p in points],[p[1] for p in points],
                s=12 if family=='Mixed' else 23,alpha=.15 if family=='Mixed' else .8,
                c=colors[family],label=family if family=='Mixed' else family+' only',edgecolors='none')
        win=result['efficiency_best']
        ax.scatter(100*win['coverage'],win['efficiency'],marker='*',s=140,color='#152F3D',zorder=5)
        ax.annotate('A1 (tied maximum)',(100*win['coverage'],win['efficiency']),xytext=(8,-14),textcoords='offset points',fontsize=9,weight='bold')
        ax.set(title=key,xlabel='Person-time coverage (%)',ylabel='Service efficiency (person·°C·h/kWh)')
        ax.set_ylim(0,win['efficiency']*1.10)
        ax.grid(alpha=.12)
    axs[0].legend(frameon=False,fontsize=9,loc='upper right')
    fig.savefig(PROJECT/'figures/27_venue_comparison.pdf',facecolor='white');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.1),layout='constrained')
    keys=list(results);bottom=np.zeros(2);components=['ownership','maintenance','electricity','water']
    col=['#456A82','#91ABB9','#D5A257','#5CA493']
    for comp,color in zip(components,col):
        values=np.array([results[k]['selected']['components'][comp] for k in keys])
        axs[0].bar(keys,values,bottom=bottom,width=.55,label=comp.title(),color=color);bottom+=values
    for i,k in enumerate(keys):
        axs[0].text(i,bottom[i]+70,f"${bottom[i]:,.0f}\n{results[k]['selected']['plan']}",ha='center',va='bottom',fontsize=10)
    axs[0].set(ylabel='Equivalent annual cost (USD/year)',title='Selected plans: one annual cost basis',ylim=(0,max(bottom)*1.32))
    axs[0].legend(frameon=False,fontsize=9,loc='upper right')
    for key,color in zip(keys,['#B27132','#246E9E']):
        data=sorted([r for r in curves if r['venue']==key],key=lambda r:r['required_relief'])
        axs[1].step([r['required_relief'] for r in data],[r['cost'] for r in data],where='post',color=color,label=key)
        r=results[key];xx=r['thermal']['baseline_residual_c']-r['venue']['residual_cap_c']
        axs[1].scatter(xx,r['selected']['annual_cost_usd'],marker='*',s=130,color=color,zorder=3)
    axs[1].set(xlabel='Required mean SET-excess relief (°C)',ylabel='Lowest feasible annual cost (USD)',title='The service requirement changes the choice')
    axs[1].legend(frameon=False,fontsize=9);axs[1].grid(alpha=.15)
    fig.savefig(PROJECT/'figures/28_effectiveness.pdf',facecolor='white');plt.close(fig)

if __name__=='__main__':main()
