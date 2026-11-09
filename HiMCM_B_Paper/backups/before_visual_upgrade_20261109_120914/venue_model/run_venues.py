"""Fixed-background CP-SET transfer, analytic efficiency bound and integer policy.

--core-only emits nominal results; --figures-only redraws frozen results.
Only the Fremont canopy length is source-derived geometry. All other geometry,
weather, occupancy and performance inputs are explicit design assumptions.
"""
from pathlib import Path
import os, sys, json, csv, copy, itertools, math, argparse
ROOT=Path(__file__).resolve().parent; PROJECT=ROOT.parent
for key,value in [('MPLCONFIGDIR','/tmp/himcm-venue-mpl'),('XDG_CACHE_HOME','/tmp/himcm-venue-cache'),('NUMBA_CACHE_DIR','/tmp/himcm-venue-numba')]:os.environ.setdefault(key,value)
sys.path[:0]=[str(PROJECT/'model'),str(PROJECT)]
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from thermal_backend import air_state,direct_evaporative,set_temperature,wet_bulb_c,physical_self_check
from shared_model.delivery import local_delivery,closure_checks
TYPES='ABC'
DEV={
 'A':dict(power_kw=.25,footprint_m2=20.,supply_kg_da_s=1.2,beta=[0.,0.,0.],v_reference_m_s=[1.,.55,.25],epsilon=0.,max_drop_c=0.,floor_clearance_m2=.5,capital_usd=300.,maintenance_usd_year=30.),
 'B':dict(power_kw=1.2,footprint_m2=30.,supply_kg_da_s=2.,beta=[.8,.45,.1],v_reference_m_s=[.8,.5,.3],epsilon=.7,max_drop_c=5.,floor_clearance_m2=1.,capital_usd=1000.,maintenance_usd_year=100.),
 'C':dict(power_kw=2.5,footprint_m2=40.,supply_kg_da_s=3.,beta=[.9,.7,.4],v_reference_m_s=[1.,.8,.5],epsilon=.7,max_drop_c=8.,floor_clearance_m2=1.5,capital_usd=2000.,maintenance_usd_year=200.)}
VENUES={
 'Fremont':dict(name='Fremont Street Experience canopy corridor',t_c=38.,rh=.20,tr_c=39.,baseline_v=.2,canopy_length_m=419.1,effective_width_m=20.,areas_m2=[2400.,3600.,2382.],people_by_hour=[[120.,240.,90.],[180.,480.,150.],[240.,720.,180.],[180.,480.,150.]]),
 'Honolulu':dict(name='Honolulu Zoo entrance ticket queue',t_c=31.,rh=.65,tr_c=33.,baseline_v=.35,assumed_length_m=10.,assumed_width_m=6.,areas_m2=[60.],people_by_hour=[[12.],[24.],[36.],[24.]])}
COMMON=dict(period_h=4.,time_step_h=1.,pressure_pa=101325.,met=1.2,clo=.5,position='standing',set_reference_c=26.,chi=0.,hours_year=600.,electricity_usd_kwh=.20,water_usd_m3=3.,make_up_factor=1.15,discount_rate=.05,life_year=5)
POLICY=dict(coverage_min=.8,mean_relief_min_c=1.5,floor_loss_max=.035,annual_energy_cap_kwh_per_m2=30.)
CRF=COMMON['discount_rate']*(1+COMMON['discount_rate'])**COMMON['life_year']/((1+COMMON['discount_rate'])**COMMON['life_year']-1)

def dump(name,value):(ROOT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def write_csv(name,rows):
    assert rows,name
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,allow_nan=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})

def read_csv(name):
    with (ROOT/name).open() as f:return list(csv.DictReader(f))

def exposure(v):
    n=np.asarray(v['people_by_hour'],dtype=float)
    assert n.shape==(4,len(v['areas_m2'])) and np.all(n>=0)
    return n.sum(axis=0)*COMMON['time_step_h']

def thermal(v):
    base=air_state(v['t_c'],v['rh'],COMMON['pressure_pa'])
    args=dict(met=COMMON['met'],clo=COMMON['clo'],position=COMMON['position'],p_pa=COMMON['pressure_pa'])
    s0=set_temperature(base.t_c,v['tr_c'],v['baseline_v'],base.rh,**args);d0=max(s0-COMMON['set_reference_c'],0.)
    rows=[];output={}
    for k,d in DEV.items():
        outlet=direct_evaporative(base.t_c,base.rh,d['epsilon'],p_pa=COMMON['pressure_pa'],max_drop_c=d['max_drop_c'])
        benefits=[]
        for j,(beta,vr) in enumerate(zip(d['beta'],d['v_reference_m_s'])):
            speed=v['baseline_v']+vr-.2;state=local_delivery(base,outlet,beta,alpha=COMMON['chi'])
            theta=set_temperature(state.t_c,v['tr_c'],speed,state.rh,**args);benefit=d0-max(theta-COMMON['set_reference_c'],0.);benefits.append(benefit)
            rows.append(dict(device=k,strip=j+1,beta=beta,entrainment_ratio=(1-beta)/beta if beta else 'infinite',strip_area_m2=d['footprint_m2']/3,t_c=state.t_c,rh=state.rh,w_kg_kg_da=state.w,h_j_kg_da=state.h_j_kg_da,v_m_s=speed,set_c=theta,baseline_set_c=s0,relief_c=benefit,outlet_t_c=outlet.t_c,outlet_rh=outlet.rh,outlet_w_kg_kg_da=outlet.w))
        # One supply per physical device, not one whole supply per strip.
        water=3600*d['supply_kg_da_s']*(outlet.w-base.w)*COMMON['make_up_factor']/1000
        output[k]=dict(residual_c=d0-float(np.mean(benefits)),benefit_c=float(np.mean(benefits)),strip_benefit_c=benefits,water_m3_h=max(water,0.),outlet_t_c=outlet.t_c)
    return dict(baseline_set_c=s0,baseline_residual_c=d0,wet_bulb_c=wet_bulb_c(base.t_c,base.rh,base.p_pa),devices=output,local=rows)

def coefficients(v,th):
    rows=[];ph=exposure(v)
    for z,a in enumerate(v['areas_m2']):
        for k,d in DEV.items():
            covered=ph[z]*d['footprint_m2']/a
            comp=dict(ownership=CRF*d['capital_usd'],maintenance=d['maintenance_usd_year'],electricity=COMMON['electricity_usd_kwh']*d['power_kw']*COMMON['hours_year'],water=COMMON['water_usd_m3']*th['devices'][k]['water_m3_h']*COMMON['hours_year'])
            u=covered*th['devices'][k]['benefit_c'];e=d['power_kw']*COMMON['period_h']
            rows.append(dict(zone=z+1,device=k,zone_area_m2=a,zone_person_hours=float(ph[z]),footprint_m2=d['footprint_m2'],covered_person_hours=covered,service_person_c_h=u,power_kw=d['power_kw'],energy_kwh=e,energy_kwh_year=d['power_kw']*COMMON['hours_year'],water_m3=th['devices'][k]['water_m3_h']*COMMON['period_h'],water_m3_year=th['devices'][k]['water_m3_h']*COMMON['hours_year'],floor_clearance_m2=d['floor_clearance_m2'],capital_usd=d['capital_usd'],annual_cost_usd=sum(comp.values()),components=comp,efficiency=u/e))
    return rows

def evaluate(v,th,coef,x):
    x=np.asarray(x,dtype=int).reshape((len(v['areas_m2']),3));assert np.all(x>=0)
    footprints=np.array([DEV[k]['footprint_m2'] for k in TYPES]);occupied=x@footprints
    assert np.all(occupied<=np.asarray(v['areas_m2'])+1e-8)
    xf=x.ravel();counts=x.sum(axis=0);ph=float(exposure(v).sum())
    def sc(k):return float(xf@np.array([c[k] for c in coef]))
    u=sc('service_person_c_h');e=sc('energy_kwh');covered=sc('covered_person_hours')
    comp={k:float(xf@np.array([c['components'][k] for c in coef])) for k in ('ownership','maintenance','electricity','water')}
    perhour=np.asarray(v['people_by_hour'])@(x*footprints[None,:]/np.asarray(v['areas_m2'])[:,None])@np.array([th['devices'][k]['benefit_c'] for k in TYPES])
    return dict(plan=''.join(k+str(int(n)) for k,n in zip(TYPES,counts) if n) or 'None',x=x.tolist(),counts=counts.tolist(),coverage=covered/ph,covered_person_hours=covered,mean_benefit_c=u/ph,mean_residual_c=th['baseline_residual_c']-u/ph,service_person_c_h=u,energy_kwh=e,efficiency=u/e if e else None,power_kw=sc('power_kw'),water_m3=sc('water_m3'),water_m3_year=sc('water_m3_year'),energy_kwh_year=sc('energy_kwh_year'),floor_loss=sc('floor_clearance_m2')/sum(v['areas_m2']),capital_usd=sc('capital_usd'),annual_cost_usd=sum(comp.values()),components=comp,area_used_m2=occupied.tolist(),service_by_hour_person_c_h=(perhour*COMMON['time_step_h']).tolist(),family=('None' if not counts.any() else TYPES[int(np.argmax(counts))] if np.count_nonzero(counts)==1 else 'Mixed'))

def efficiency_solution(v,th,coef):
    fitting=[(i,c) for i,c in enumerate(coef) if c['footprint_m2']<=c['zone_area_m2']]
    best=max(c['efficiency'] for _,c in fitting);ties=[(i,c) for i,c in fitting if abs(c['efficiency']-best)<1e-9]
    i,c=min(ties,key=lambda t:(t[1]['energy_kwh'],t[0]));x=np.zeros(len(coef),dtype=int);x[i]=1
    return dict(upper_bound=best,attaining_plan=evaluate(v,th,coef,x),attaining_single_device_zone=c['zone'],tied_single_device_pairs=[dict(zone=c['zone'],device=c['device']) for _,c in ties],scope='All integer nonoverlapping full-footprint allocations within the assumed zones, without a service or cost constraint.')

def pure_benchmarks(v,th,coef):
    output={}
    for j,k in enumerate(TYPES):
        x=np.zeros((len(v['areas_m2']),3),dtype=int);x[:,j]=np.floor(np.asarray(v['areas_m2'])/DEV[k]['footprint_m2']+1e-12).astype(int)
        output[k]=evaluate(v,th,coef,x)
    return output

def policy_margins(v,r,relief=POLICY['mean_relief_min_c']):
    m=dict(coverage=r['coverage']-POLICY['coverage_min'],floor=POLICY['floor_loss_max']-r['floor_loss'],energy=POLICY['annual_energy_cap_kwh_per_m2']*sum(v['areas_m2'])-r['energy_kwh_year'],area=min(a-u for a,u in zip(v['areas_m2'],r['area_used_m2'])))
    if relief is not None:m['relief']=r['mean_benefit_c']-relief
    return m

def solve_policy(v,th,coef,relief=POLICY['mean_relief_min_c'],price=(1.,1.,1.,1.,1.),maximize_service=False):
    n=len(coef);total=sum(v['areas_m2']);ph=exposure(v).sum();mat=[];low=[];high=[]
    for z,a in enumerate(v['areas_m2']):
        mat.append([c['footprint_m2']/a if c['zone']==z+1 else 0. for c in coef]);low.append(-np.inf);high.append(1.)
    mat.append([c['covered_person_hours']/ph for c in coef]);low.append(POLICY['coverage_min']);high.append(np.inf)
    if relief is not None:mat.append([c['service_person_c_h']/ph for c in coef]);low.append(relief);high.append(np.inf)
    mat.append([c['floor_clearance_m2']/total for c in coef]);low.append(-np.inf);high.append(POLICY['floor_loss_max'])
    cap=POLICY['annual_energy_cap_kwh_per_m2']*total
    mat.append([c['energy_kwh_year']/cap for c in coef]);low.append(-np.inf);high.append(1.)
    costs=np.array([c['components']['ownership']*price[TYPES.index(c['device'])]+c['components']['maintenance']+c['components']['electricity']*price[3]+c['components']['water']*price[4] for c in coef])
    objective=-np.array([c['service_person_c_h'] for c in coef])/ph if maximize_service else costs
    upper=[math.floor(c['zone_area_m2']/c['footprint_m2']+1e-12) for c in coef]
    sol=milp(objective,integrality=np.ones(n),bounds=Bounds(np.zeros(n),upper),constraints=LinearConstraint(np.asarray(mat),np.asarray(low),np.asarray(high)),options={'mip_rel_gap':1e-10,'time_limit':120.})
    meta=dict(status=int(sol.status),message=str(sol.message),success=bool(sol.success),mip_gap=float(sol.mip_gap) if getattr(sol,'mip_gap',None) is not None else None,objective_bound=float(sol.mip_dual_bound) if getattr(sol,'mip_dual_bound',None) is not None else None)
    if sol.status==2:return dict(**meta,selected=None)
    if not sol.success or sol.x is None:raise RuntimeError(f'MILP did not certify optimality: {meta}')
    assert np.max(np.abs(sol.x-np.round(sol.x)))<1e-5
    xi=np.round(sol.x).astype(int);r=evaluate(v,th,coef,xi);m=policy_margins(v,r,relief)
    assert min(m.values())>=-1e-6,(m,r)
    r['scenario_annual_cost_usd']=float(costs@xi)
    return dict(**meta,selected=r,policy_margins=m,objective_value=float(objective@xi))

def core():
    allcoef=[];locals_=[];results={}
    for key,v in VENUES.items():
        th=thermal(v);coef=coefficients(v,th)
        r=dict(venue=v,person_hours=float(exposure(v).sum()),thermal=th,efficiency_optimum=efficiency_solution(v,th,coef),pure_largest_fit=pure_benchmarks(v,th,coef),policy=solve_policy(v,th,coef),max_policy_relief=solve_policy(v,th,coef,relief=None,maximize_service=True));results[key]=r
        allcoef.extend(dict(venue=key,**c) for c in coef);locals_.extend(dict(venue=key,**r) for r in th['local'])
    dump('inputs.json',dict(venues=VENUES,devices=DEV,common=COMMON,policy=POLICY,crf=CRF,assumptions={
      'geometry':'Only Fremont canopy length 419.1 m is source-derived. Width 20 m, three conceptual zones, and Honolulu customer queue 10 m by 6 m are assumptions.',
      'weather':'Ta, RH, MRT and background speeds are representative test conditions, not weather observations.',
      'occupancy':'Four prescribed hourly populations, uniform within each zone; integration over 4 h.',
      'velocity':'v = v0 + (reference strip speed - 0.2 m/s). Scalar mixing and speed increments are independent reduced inputs.',
      'strips':'Three equal-area delivery strips per device, distinct from demand zones. Nominal allocations prohibit overlap and boundary clipping.',
      'background':'Outdoor scalar background externally maintained; no calibrated humidity-storage ODE.',
      'heat':'chi=0 neglects local electrical heating; full electrical power enters energy and cost.',
      'annual':'600 representative operating hours per year; the four-hour profile is a service test.',
      'clipping':'Separate stress test retains near then middle then far strip; lost area has no service credit; full power/water retained.',
      'policy':'Task 4 only: q>=0.8, mean SET-excess relief>=1.5 C, floor clearance<=3.5%, annual energy<=30 kWh/m2.'}))
    dump('results.json',results);write_csv('linear_coefficients.csv',allcoef);write_csv('local_conditions.csv',locals_)
    print(json.dumps({k:dict(eta_bound=r['efficiency_optimum']['upper_bound'],eta_zone=r['efficiency_optimum']['attaining_single_device_zone'],pure={t:{f:r['pure_largest_fit'][t][f] for f in ('plan','efficiency','coverage','mean_benefit_c')} for t in TYPES},policy=r['policy']) for k,r in results.items()},indent=2),flush=True)
    return results

def variations(v):
    yield 'Nominal',copy.deepcopy(v)
    for shift in (-.1,.1):
        x=copy.deepcopy(v);x['rh']+=shift;yield f'RH {shift*100:+.0f} pp',x
    for shift in (-2.,2.):
        x=copy.deepcopy(v);x['tr_c']=min(v['tr_c']+shift,40.);yield f'MRT {x["tr_c"]-v["tr_c"]:+.0f} C',x
    for speed in (.2,.35,.8,1.2):
        x=copy.deepcopy(v);x['baseline_v']=speed;yield f'Background speed {speed:g} m/s',x
    for scale in (.75,1.25):
        x=copy.deepcopy(v);x['areas_m2']=[a*scale for a in v['areas_m2']];yield f'Area {scale:g}x, same occupancy',x

def sensitivity(results):
    physical=[];prices=[];curves=[];cross=[];scaling=[];clipping=[];density_rows=[];threshold=[]
    for key,r in results.items():
        v=r['venue'];th=r['thermal'];coef=coefficients(v,th)
        for label,vv in variations(v):
            tt=thermal(vv);cc=coefficients(vv,tt);ee=efficiency_solution(vv,tt,cc);opt=solve_policy(vv,tt,cc);rr=opt['selected']
            physical.append(dict(venue=key,case=label,t_c=vv['t_c'],rh=vv['rh'],tr_c=vv['tr_c'],background_v=vv['baseline_v'],baseline_set_c=tt['baseline_set_c'],total_area_m2=sum(vv['areas_m2']),efficiency_upper_bound=ee['upper_bound'],eta_device=ee['attaining_plan']['plan'],eta_zone=ee['attaining_single_device_zone'],policy_status=opt['status'],mip_gap=opt['mip_gap'],policy_plan=rr['plan'] if rr else 'infeasible',policy_cost_usd=rr['annual_cost_usd'] if rr else None,policy_x=rr['x'] if rr else None,**{f'best_single_eta_{k}':max(c['efficiency'] for c in cc if c['device']==k) for k in TYPES},**{f'full_footprint_relief_{k}_c':tt['devices'][k]['benefit_c'] for k in TYPES}))
        for factors in itertools.product((.7,1.,1.3),(.7,1.,1.3),(.7,1.,1.3),(.5,1.,1.5),(.5,1.,1.5)):
            opt=solve_policy(v,th,coef,price=factors);rr=opt['selected'];a,b,c,e,w=factors
            prices.append(dict(venue=key,capital_A=a,capital_B=b,capital_C=c,electricity=e,water=w,status=opt['status'],mip_gap=opt['mip_gap'],plan=rr['plan'] if rr else 'infeasible',annual_cost_usd=rr['scenario_annual_cost_usd'] if rr else None,x=rr['x'] if rr else None,same_counts=rr['counts']==r['policy']['selected']['counts'] if rr and r['policy']['selected'] else False))
        maxr=r['max_policy_relief']['selected']
        levels=sorted(set(np.linspace(.5,maxr['mean_benefit_c'],35).tolist()+[1.4,1.49,1.5,1.6]+[rr['mean_benefit_c'] for rr in r['pure_largest_fit'].values() if .5<=rr['mean_benefit_c']<=maxr['mean_benefit_c']]))
        for level in levels:
            opt=solve_policy(v,th,coef,relief=level);rr=opt['selected']
            row=dict(venue=key,required_relief_c=level,status=opt['status'],mip_gap=opt['mip_gap'],annual_cost_usd=rr['annual_cost_usd'] if rr else None,plan=rr['plan'] if rr else 'infeasible',x=rr['x'] if rr else None,attained_relief_c=rr['mean_benefit_c'] if rr else None,coverage=rr['coverage'] if rr else None)
            curves.append(row)
            if level in (1.4,1.49,1.5,1.6):threshold.append(row)
        # Matched density and area: climate includes the prescribed natural wind.
        vc=copy.deepcopy(v);vc['areas_m2']=[120.];vc['people_by_hour']=[[48.]]*4
        tc=thermal(vc);cc=coefficients(vc,tc)
        for k,rr in pure_benchmarks(vc,tc,cc).items():
            cross.append(dict(climate=key,case='Matched 120 m2 and 0.4 person/m2',area_m2=120.,density_person_m2=.4,person_hours=192.,background_v=vc['baseline_v'],device=k,plan=rr['plan'],coverage=rr['coverage'],mean_benefit_c=rr['mean_benefit_c'],energy_kwh=rr['energy_kwh'],service_person_c_h=rr['service_person_c_h'],efficiency=rr['efficiency']))
        for geometry,template in VENUES.items():
            vs=copy.deepcopy(template)
            for field in ('t_c','rh','tr_c','baseline_v'):vs[field]=v[field]
            ts=thermal(vs);cs=coefficients(vs,ts)
            for k,rr in pure_benchmarks(vs,ts,cs).items():cross.append(dict(climate=key,case=f'Fixed {geometry} geometry and occupancy',area_m2=sum(vs['areas_m2']),density_person_m2=float(exposure(vs).sum()/4/sum(vs['areas_m2'])),person_hours=float(exposure(vs).sum()),background_v=vs['baseline_v'],device=k,plan=rr['plan'],coverage=rr['coverage'],mean_benefit_c=rr['mean_benefit_c'],energy_kwh=rr['energy_kwh'],service_person_c_h=rr['service_person_c_h'],efficiency=rr['efficiency']))
        for scale in (.5,1.,2.):
            vv=copy.deepcopy(v);vv['people_by_hour']=(np.asarray(v['people_by_hour'])*scale).tolist();cc=coefficients(vv,th)
            for k,rr in pure_benchmarks(vv,th,cc).items():density_rows.append(dict(venue=key,density_multiplier=scale,device=k,plan=rr['plan'],efficiency=rr['efficiency'],efficiency_ratio=rr['efficiency']/r['pure_largest_fit'][k]['efficiency'],coverage=rr['coverage'],mean_benefit_c=rr['mean_benefit_c']))
    vh=VENUES['Honolulu'];th=thermal(vh)
    for scale in (1,2,4,8):
        vv=copy.deepcopy(vh);vv['areas_m2']=[60.*scale];vv['people_by_hour']=(np.asarray(vh['people_by_hour'])*scale).tolist();coef=coefficients(vv,th)
        for case,n in [('Fixed A3',3),('Replicated devices',3*scale)]:
            rr=evaluate(vv,th,coef,[[n,0,0]])
            scaling.append(dict(case=case,area_multiplier=scale,area_m2=60.*scale,person_hours=float(exposure(vv).sum()),plan=rr['plan'],coverage=rr['coverage'],mean_benefit_c=rr['mean_benefit_c'],service_person_c_h=rr['service_person_c_h'],energy_kwh=rr['energy_kwh'],efficiency=rr['efficiency']))
    density=float(exposure(vh).sum()/4/sum(vh['areas_m2']))
    for area in sorted(set(np.linspace(5,120,116).tolist()+[20/3,40/3,20.,30.,40.])):
        for k,d in DEV.items():
            strip=d['footprint_m2']/3;retained=[min(strip,max(area-j*strip,0.)) for j in range(3)]
            u=float(density*4*np.dot(retained,th['devices'][k]['strip_benefit_c']));e=d['power_kw']*4
            clipping.append(dict(device=k,available_area_m2=area,retained_near_m2=retained[0],retained_middle_m2=retained[1],retained_far_m2=retained[2],coverage=sum(retained)/area,service_person_c_h=u,energy_kwh=e,efficiency=u/e,mean_benefit_c=u/(density*4*area),water_m3=th['devices'][k]['water_m3_h']*4))
    for name,rows in [('physical_sensitivity.csv',physical),('cost_sensitivity.csv',prices),('policy_curves.csv',curves),('climate_cross.csv',cross),('scale_checks.csv',scaling),('boundary_clipping.csv',clipping),('density_scaling.csv',density_rows),('threshold_sensitivity.csv',threshold)]:write_csv(name,rows)

def verify(results):
    checks={'physical_backend':physical_self_check()['checks']=='passed','delivery_closure':all(closure_checks()['checks'].values())};details={};rng=np.random.default_rng(20261108)
    for key,r in results.items():
        v=r['venue'];th=r['thermal'];coef=coefficients(v,th);bound=r['efficiency_optimum']['upper_bound'];p=r['policy']
        checks[key+'_bound_attained']=abs(r['efficiency_optimum']['attaining_plan']['efficiency']-bound)<1e-10
        checks[key+'_valid_set_all_strips']=all(math.isfinite(s['set_c']) and 0<=s['rh']<=1 for s in th['local'])
        checks[key+'_nominal_policy_certified']=p['status']==0 and p['mip_gap']<1e-8 and min(p['policy_margins'].values())>=-1e-6
        zero=evaluate(v,th,coef,np.zeros(len(coef),dtype=int));checks[key+'_zero_control']=zero['service_person_c_h']==zero['energy_kwh']==zero['coverage']==0
        allocations=[]
        if len(v['areas_m2'])==1:
            for counts in itertools.product(*(range(int(v['areas_m2'][0]/DEV[k]['footprint_m2'])+1) for k in TYPES)):
                if sum(n*DEV[k]['footprint_m2'] for n,k in zip(counts,TYPES))<=v['areas_m2'][0]:allocations.append([list(counts)])
        else:
            for _ in range(600):
                x=np.zeros((len(v['areas_m2']),3),dtype=int)
                for z,area in enumerate(v['areas_m2']):
                    for j in rng.permutation(3):
                        x[z,j]=rng.integers(0,int(area/DEV[TYPES[j]]['footprint_m2'])+1);area-=x[z,j]*DEV[TYPES[j]]['footprint_m2']
                allocations.append(x.tolist())
        errweight=0.;errtime=0.;errbound=0.
        for x in allocations:
            rr=evaluate(v,th,coef,x);errtime=max(errtime,abs(sum(rr['service_by_hour_person_c_h'])-rr['service_person_c_h']))
            if rr['energy_kwh']:
                w=np.asarray(x).ravel()*np.array([c['energy_kwh'] for c in coef])/rr['energy_kwh'];eta=float(w@np.array([c['efficiency'] for c in coef]));errweight=max(errweight,abs(eta-rr['efficiency']));errbound=max(errbound,rr['efficiency']-bound)
        checks[key+'_weighted_average_identity']=errweight<1e-9 and errbound<1e-9;checks[key+'_hourly_service_balance']=errtime<1e-8
        if len(v['areas_m2'])==1:
            feasible=[evaluate(v,th,coef,x) for x in allocations];feasible=[s for s in feasible if min(policy_margins(v,s).values())>=-1e-7];brute=min(feasible,key=lambda s:s['annual_cost_usd']);checks[key+'_milp_equals_exhaustive']=abs(brute['annual_cost_usd']-p['selected']['annual_cost_usd'])<1e-8
        details[key]=dict(checked_allocations=len(allocations),max_weighted_identity_error=errweight,max_hourly_service_balance_error=errtime,max_bound_violation=errbound)
    scale=read_csv('scale_checks.csv');eta=float(scale[0]['efficiency']);u=float(scale[0]['service_person_c_h']);e=float(scale[0]['energy_kwh'])
    checks['fixed_device_scaling']=all(abs(float(s['efficiency'])-eta)<1e-9 and abs(float(s['coverage'])-1/float(s['area_multiplier']))<1e-9 and abs(float(s['service_person_c_h'])-u)<1e-8 for s in scale if s['case']=='Fixed A3')
    checks['replicated_scaling']=all(abs(float(s['efficiency'])-eta)<1e-9 and abs(float(s['coverage'])-1)<1e-9 and abs(float(s['energy_kwh'])-e*float(s['area_multiplier']))<1e-8 for s in scale if s['case']=='Replicated devices')
    clip=read_csv('boundary_clipping.csv');checks['clipped_area_and_full_power']=all(abs(sum(float(s[k]) for k in ('retained_near_m2','retained_middle_m2','retained_far_m2'))-min(float(s['available_area_m2']),DEV[s['device']]['footprint_m2']))<1e-8 and abs(float(s['energy_kwh'])-4*DEV[s['device']]['power_kw'])<1e-9 for s in clip)
    checks['full_footprint_clipping_matches_nominal']=all(abs(float(next(s for s in clip if s['device']==k and float(s['available_area_m2'])==DEV[k]['footprint_m2'])['efficiency'])-results['Honolulu']['pure_largest_fit'][k]['efficiency'])<1e-9 for k in TYPES)
    cost=read_csv('cost_sensitivity.csv');checks['243_prices_per_venue']=all(sum(s['venue']==k for s in cost)==243 for k in VENUES);checks['price_milp_certified']=all(s['status']=='0' and float(s['mip_gap'])<1e-8 for s in cost)
    physical=read_csv('physical_sensitivity.csv');checks['sensitivity_domain']=all(float(s['tr_c'])<=40 and 0<=float(s['rh'])<=1 for s in physical);checks['sensitivity_status_reported']=all(s['policy_status'] in ('0','2') for s in physical)
    checks['density_proportionality']=all(abs(float(s['efficiency_ratio'])-float(s['density_multiplier']))<1e-9 for s in read_csv('density_scaling.csv'))
    dump('verification.json',dict(checks=checks,details=details,all_passed=all(checks.values())));assert all(checks.values()),checks
    return checks

def main():
    p=argparse.ArgumentParser();p.add_argument('--core-only',action='store_true');p.add_argument('--figures-only',action='store_true');args=p.parse_args()
    if args.figures_only:
        from make_figures import make_figures
        make_figures(json.loads((ROOT/'results.json').read_text()));return
    results=core()
    if args.core_only:return
    sensitivity(results);checks=verify(results)
    from make_figures import make_figures
    make_figures(results);print(json.dumps(dict(checks=len(checks),all_passed=all(checks.values())),indent=2),flush=True)

if __name__=='__main__':main()
