"""Dynamic three-zone rail waiting area: conserved h/w and envelope storage.
Run from any directory. SI integration in seconds; service/energy in hours.
"""
from pathlib import Path
import os, sys, json, csv, copy, argparse, importlib.metadata
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'.cache'))
os.environ.setdefault('NUMBA_CACHE_DIR',str(ROOT/'.numba_cache'))
sys.path.insert(0,str(ROOT.parent/'model'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from thermal_backend import (air_state, air_state_from_hw, direct_evaporative,
                             set_temperature, saturation_vapor_pressure_pa)
CFG=json.loads((ROOT/'scenario.json').read_text())
FIG=ROOT.parent/'figures'
COL={'Baseline':'#666666','A':'#2379A5','B':'#D18C32','C':'#76559A'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.labelsize':11,'axes.titlesize':12,
                     'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42})

def forcing(t,cfg=CFG,ventilation=1.0):
    phase=t%cfg['train_period_s']
    f=phase/cfg['train_period_s']
    n=np.array(cfg['occupancy_min'])+(np.array(cfg['occupancy_peak'])-cfg['occupancy_min'])*f
    pulse=phase>=cfg['train_period_s']-cfg['arrival_pulse_duration_s']
    ach=ventilation*(np.array(cfg['base_ach_h_inverse'])+pulse*np.array(cfg['pulse_ach_increment_h_inverse']))
    return n,ach

def context(rh,cfg=CFG):
    out=air_state(cfg['outdoor_temperature_c'],rh,cfg['pressure_pa'])
    g=cfg['geometry']; volume=g['length_m']*g['width_m']*g['height_m']/3
    rho=(cfg['pressure_pa']-rh*saturation_vapor_pressure_pa(out.t_c))/(287.055*(out.t_c+273.15))
    return {'outside':out,'mass':np.full(3,rho*volume),'volume_m3':volume}

def states(y,cfg=CFG):
    return [air_state_from_hw(y[z,0],y[z,1],cfg['pressure_pa']) for z in range(3)]

def radiation(tm,cfg=CFG):
    f=np.array(cfg['surface_view_fractions']); outside=cfg['outdoor_radiant_temperature_c']+273.15
    return (f*(tm+273.15)**4+(1-f)*outside**4)**.25-273.15

def rhs(y,n,ach,ctx,strategy='Baseline',cfg=CFG):
    """Return derivative and external net energy [W]/moisture [kg/s].
    Interzone transfer and air-surface transfer cancel in global budgets.
    Constant dry-air storage and balanced exchange are explicit approximations.
    """
    air=states(y,cfg); T=np.array([a.t_c for a in air]); h=y[:,0]; w=y[:,1]; tm=y[:,2]
    M=ctx['mass']; out=ctx['outside']; md=M*ach/3600
    eh=md*(out.h_j_kg_da-h); ew=md*(out.w-w)
    # Equal and opposite dry-air exchanges on the adjacent-zone edges.
    for i,j in [(0,1),(1,2)]:
        mh=cfg['adjacent_exchange_kg_da_s']*(h[j]-h[i]); mw=cfg['adjacent_exchange_kg_da_s']*(w[j]-w[i])
        eh[i]+=mh; eh[j]-=mh; ew[i]+=mw; ew[j]-=mw
    human_water=n*cfg['person_vapor_kg_s']
    human_air_heat=n*cfg['person_convective_w']+human_water*(2501000+1860*T)
    conv=cfg['surface_to_air_w_k']*(tm-T)
    wall_external=cfg['surface_to_outdoor_w_k']*(out.t_c-tm)+cfg['effective_solar_load_w_per_zone']+n*cfg['person_radiant_w']
    power=0.0; devh=np.zeros(3); devw=np.zeros(3)
    if strategy!='Baseline':
        d=cfg['devices'][strategy]; units=cfg['device_count_per_zone']
        power=units*d['unit_power_kw']*1000*cfg['motor_heat_fraction']
        if d['recirculation_kg_da_s_per_unit']>0:
            mrec=units*d['recirculation_kg_da_s_per_unit']
            for z,a in enumerate(air):
                outlet=direct_evaporative(a.t_c,a.rh,d['epsilon'],a.p_pa,d['outlet_drop_cap_c'])
                devh[z]=mrec*(outlet.h_j_kg_da-a.h_j_kg_da)
                devw[z]=mrec*(outlet.w-a.w)
    fh=eh+conv+human_air_heat+power+devh
    fw=ew+human_water+devw
    fm=wall_external-conv
    dy=np.column_stack((fh/M,fw/M,fm/cfg['surface_capacity_j_k']))
    return dy,np.array([np.sum(eh+human_air_heat+power+devh+wall_external),np.sum(ew+human_water+devw)])

def rk_step(y,t,dt,ctx,strategy,cfg,ventilation):
    # Freeze scheduled inputs at the step midpoint. dt divides pulse/headway edges.
    n,ach=forcing(t+dt/2,cfg,ventilation)
    k1,b1=rhs(y,n,ach,ctx,strategy,cfg)
    k2,b2=rhs(y+dt*k1/2,n,ach,ctx,strategy,cfg)
    k3,b3=rhs(y+dt*k2/2,n,ach,ctx,strategy,cfg)
    k4,b4=rhs(y+dt*k3,n,ach,ctx,strategy,cfg)
    return y+dt*(k1+2*k2+2*k3+k4)/6,dt*(b1+2*b2+2*b3+b4)/6

def integrate(rh,strategy='Baseline',cfg=CFG,ventilation=1.,initial=None,duration=None,observe=True):
    ctx=context(rh,cfg); out=ctx['outside']; dt=cfg['dt_s']; duration=cfg['duration_s'] if duration is None else duration
    for boundary in [duration,cfg['train_period_s'],cfg['arrival_pulse_duration_s']]:
        assert abs(boundary/dt-round(boundary/dt))<1e-10,'dt must align with schedule boundaries'
    y=np.tile([out.h_j_kg_da,out.w,out.t_c],(3,1)) if initial is None else np.array(initial,copy=True)
    start=y.copy(); budget=np.zeros(2); rows=[]
    for i in range(round(duration/dt)):
        t=i*dt; yn,flux=rk_step(y,t,dt,ctx,strategy,cfg,ventilation)
        mid=(y+yn)/2; budget+=flux
        if observe:
            n,ach=forcing(t+dt/2,cfg,ventilation); tr=radiation(mid[:,2],cfg)
            air=states(mid,cfg)
            v=np.full(3,cfg['baseline_air_speed_m_s']) if strategy=='Baseline' else np.array(cfg['devices'][strategy]['air_speed_m_s'])
            for z,a in enumerate(air):
                theta=set_temperature(a.t_c,float(tr[z]),float(v[z]),a.rh,cfg['met'],cfg['clo'],cfg['pressure_pa'])
                outlet_drop=0.
                if strategy in ('B','C'):
                    d=cfg['devices'][strategy]; outlet_drop=a.t_c-direct_evaporative(a.t_c,a.rh,d['epsilon'],a.p_pa,d['outlet_drop_cap_c']).t_c
                rows.append(dict(rh_out=rh,ventilation_multiplier=ventilation,strategy=strategy,time_min=(t+dt/2)/60,zone=cfg['geometry']['zones'][z],people=float(n[z]),ach_h_inverse=float(ach[z]),air_temperature_c=a.t_c,rh=a.rh,humidity_ratio=a.w,surface_temperature_c=float(mid[z,2]),radiant_temperature_c=float(tr[z]),air_speed_m_s=float(v[z]),set_c=theta,discomfort_c=max(theta-cfg['set_threshold_c'],0),outlet_drop_c=outlet_drop))
        y=yn
    stored=np.array([np.sum(ctx['mass']*(y[:,0]-start[:,0]))+cfg['surface_capacity_j_k']*np.sum(y[:,2]-start[:,2]),np.sum(ctx['mass']*(y[:,1]-start[:,1]))])
    return {'rows':rows,'final_state':y,'initial_state':start,'budget_input':budget,'storage_change':stored,'budget_residual':stored-budget,'dry_air_mass_kg':ctx['mass'],'dt_s':dt}

def run_case(rh,cfg=CFG,ventilation=1.,strategies=('A','B','C')):
    warm=integrate(rh,cfg=cfg,ventilation=ventilation,duration=cfg['warmup_s'],observe=False)
    baseline=integrate(rh,cfg=cfg,ventilation=ventilation,initial=warm['final_state'])
    all_runs={'Baseline':baseline}; summary=[]; base=np.array([r['discomfort_c'] for r in baseline['rows']]); n=np.array([r['people'] for r in baseline['rows']]); dh=cfg['dt_s']/3600
    H=float(n.sum()*dh); r0=float(n@base*dh)
    for name in strategies:
        run=integrate(rh,name,cfg,ventilation,initial=warm['final_state']); all_runs[name]=run
        discomfort=np.array([r['discomfort_c'] for r in run['rows']]); u=float(n@(base-discomfort)*dh); residual=float(n@discomfort*dh)
        energy=3*cfg['device_count_per_zone']*cfg['devices'][name]['unit_power_kw']*cfg['duration_s']/3600
        for r,db in zip(run['rows'],base):r['baseline_discomfort_c']=float(db);r['signed_benefit_c']=float(db-r['discomfort_c'])
        summary.append(dict(rh_out=rh,ventilation_multiplier=ventilation,strategy=name,person_hours=H,energy_kwh=energy,service_person_c_h=u,efficiency=u/energy,remaining_person_c_h=residual,mean_remaining_c=residual/H if H else 0,mean_relief_c=u/H if H else 0,baseline_remaining_person_c_h=r0,peak_core_rh=max(r['rh'] for r in run['rows'] if r['zone']=='Core'),peak_core_air_temperature_c=max(r['air_temperature_c'] for r in run['rows'] if r['zone']=='Core')))
    return all_runs,summary,warm

def write_csv(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def export(name,fig):
    fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight',facecolor='white')
    plt.close(fig)

def figures(nominal,summary,sweep):
    runs=nominal['Humid']; fig,axs=plt.subplots(2,2,figsize=(10.2,6.1),layout='constrained')
    for z in CFG['geometry']['zones']:
        r=[x for x in runs['Baseline']['rows'] if x['zone']==z];t=[x['time_min'] for x in r]
        axs[0,0].plot(t,[x['people'] for x in r],label=z,lw=1.6)
        axs[0,1].plot(t,[x['ach_h_inverse'] for x in r],label=z,lw=1.6)
    for s,run in runs.items():
        r=[x for x in run['rows'] if x['zone']=='Core'];t=[x['time_min'] for x in r]
        axs[1,0].plot(t,[x['air_temperature_c'] for x in r],color=COL[s],label=s,lw=1.7)
        axs[1,1].plot(t,[100*x['rh'] for x in r],color=COL[s],label=s,lw=1.7)
    for ax,title,y in zip(axs.ravel(),['Prescribed passenger cycles','Assumed exchange pulses','Core air temperature: humid case','Core humidity: humid case'],['Mean simultaneous people','Outdoor air exchange (1/h)','Air temperature (°C)','Relative humidity (%)']):
        ax.set(title=title,xlabel='Time after switch-on (min)',ylabel=y,xlim=(0,120));ax.grid(alpha=.2)
    axs[0,0].set_ylim(0,max(CFG['occupancy_peak'])*1.25)
    axs[0,0].legend(ncol=3,fontsize=8,loc='upper right');axs[1,0].legend(ncol=2,fontsize=9)
    export('10_rail_dynamics',fig)
    fig,axs=plt.subplots(1,2,figsize=(10,3.7),layout='constrained');x=np.arange(2)
    for j,s in enumerate('ABC'):
        rows=[next(t for t in summary if t['strategy']==s and t['rh_out']==rh) for rh in [.3,.7]]
        for ax,key in zip(axs,['efficiency','mean_remaining_c']):
            bars=ax.bar(x+(j-1)*.23,[t[key] for t in rows],.23,color=COL[s],label=s);ax.bar_label(bars,fmt='%.1f',padding=3,fontsize=10)
    for ax in axs:ax.set_xticks(x,['Dry: RH 30%','Humid: RH 70%']);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.margins(y=.3)
    axs[0].set(title='Three units; all electricity counted',ylabel='Service efficiency (person·°C·h/kWh)');axs[0].legend(ncol=3)
    axs[1].set(title='Relief adequacy remains separate',ylabel='Mean remaining SET excess (°C)')
    export('11_rail_efficiency',fig)
    fig,axs=plt.subplots(2,2,figsize=(10,6),layout='constrained')
    for ci,(climate,rh) in enumerate(CFG['relative_humidity_cases'].items()):
        for s in 'BC':
            rows=[r for r in sweep if r['rh_out']==rh and r['strategy']==s]
            xs=[r['ventilation_multiplier'] for r in rows]
            axs[0,ci].plot(xs,[r['efficiency'] for r in rows],'-o',color=COL[s],label=s,lw=1.8,ms=4)
            axs[1,ci].plot(xs,[100*r['peak_core_rh'] for r in rows],'-o',color=COL[s],label=s,lw=1.8,ms=4)
        axs[0,ci].set(title=f'{climate}: evaporative service efficiency',ylabel='Service efficiency (person·°C·h/kWh)');axs[0,ci].legend()
        axs[1,ci].set(title=f'{climate}: peak core humidity',ylabel='Relative humidity (%)')
        for ax in axs[:,ci]:ax.set(xlabel='Outdoor-exchange multiplier');ax.grid(alpha=.2);ax.axvline(1,color='#999',ls=':',lw=1)
    export('12_rail_ventilation',fig)

def main(quick=False):
    nominal={};summary=[];warmstarts={};allrows=[];budgetrows=[]
    for climate,rh in CFG['relative_humidity_cases'].items():
        runs,rows,warm=run_case(rh);nominal[climate]=runs;summary+=rows
        warmstarts[climate]=[dict(zone=z,air_temperature_c=a.t_c,rh=a.rh,surface_temperature_c=float(warm['final_state'][i,2]),dry_air_mass_kg=float(warm['dry_air_mass_kg'][i])) for i,(z,a) in enumerate(zip(CFG['geometry']['zones'],states(warm['final_state'])))]
        for s,run in runs.items():
            allrows+=run['rows'];budgetrows.append(dict(climate=climate,strategy=s,energy_input_j=float(run['budget_input'][0]),stored_energy_change_j=float(run['storage_change'][0]),energy_residual_j=float(run['budget_residual'][0]),moisture_input_kg=float(run['budget_input'][1]),stored_moisture_change_kg=float(run['storage_change'][1]),moisture_residual_kg=float(run['budget_residual'][1])))
    write_csv('time_series.csv',allrows);write_csv('scenario_results.csv',summary);write_csv('conservation_budgets.csv',budgetrows)
    (ROOT/'warmup_states.json').write_text(json.dumps(warmstarts,indent=2))
    print(json.dumps({'nominal':summary,'warmup_states':warmstarts},indent=2),flush=True)
    if quick:return
    sweep=[]
    for rh in CFG['relative_humidity_cases'].values():
        for mult in CFG['ventilation_multipliers']:
            if mult==1:sweep += [t for t in summary if t['rh_out']==rh and t['strategy'] in 'BC']
            else:
                _,rows,_=run_case(rh,ventilation=mult,strategies=('B','C'));sweep+=rows
    write_csv('ventilation_sweep.csv',sweep)
    checks={}
    checks['service_plus_remaining_equals_baseline']=all(abs(r['service_person_c_h']+r['remaining_person_c_h']-r['baseline_remaining_person_c_h'])<1e-8 for r in summary+sweep)
    checks['all_electricity_counted']=all(abs(r['energy_kwh']-{'A':1.5,'B':7.2,'C':15}[r['strategy']])<1e-10 for r in summary)
    checks['global_energy_and_moisture_conserved']=all(abs(b['energy_residual_j'])<1e-4 and abs(b['moisture_residual_kg'])<1e-10 for b in budgetrows)
    checks['gas_phase_and_set_domain_valid']=all(0<=r['rh']<=1 and np.isfinite(r['set_c']) for r in allrows)
    c=copy.deepcopy(CFG);c.update(occupancy_min=[0,0,0],occupancy_peak=[0,0,0],effective_solar_load_w_per_zone=0)
    ctx=context(.3,c);o=ctx['outside'];y=np.tile([o.h_j_kg_da,o.w,o.t_c],(3,1));n,ach=forcing(0,c)
    derivative,_=rhs(y,n,ach,ctx,cfg=c);checks['uniform_unloaded_state_is_equilibrium']=bool(np.max(np.abs(derivative))<1e-10)
    # Unequal air states, no external exchange/sources: internal transfers conserve globally.
    y[0,0]+=1000;y[2,0]-=500;y[0,1]+=.001;y[1,2]+=2
    c.update(surface_to_outdoor_w_k=0)
    derivative,external=rhs(y,np.zeros(3),np.zeros(3),ctx,cfg=c)
    total_e=float(ctx['mass']@derivative[:,0]+c['surface_capacity_j_k']*sum(derivative[:,2]));total_w=float(ctx['mass']@derivative[:,1])
    checks['interzone_and_air_surface_exchanges_cancel']=abs(total_e)<1e-8 and abs(total_w)<1e-12 and np.max(np.abs(external))<1e-10
    # Empty occupancy still consumes operating electricity; source loads removed only by n=0.
    _,zero,_=run_case(.3,cfg=c,strategies=('A',));checks['empty_station_zero_service_positive_energy']=zero[0]['service_person_c_h']==0 and zero[0]['energy_kwh']>0
    # Midpoint schedules and RK4 repeat with half the timestep; no field data are fitted.
    finer=copy.deepcopy(CFG);finer['dt_s']=CFG['dt_s']/2;convergence=[]
    for climate,rh in CFG['relative_humidity_cases'].items():
        _,fine,_=run_case(rh,cfg=finer)
        for coarse,ref in zip([r for r in summary if r['rh_out']==rh],fine):
            convergence.append(dict(climate=climate,strategy=coarse['strategy'],efficiency_relative_difference=abs(coarse['efficiency']-ref['efficiency'])/max(1,abs(ref['efficiency'])),remaining_absolute_difference_c=abs(coarse['mean_remaining_c']-ref['mean_remaining_c']),peak_core_rh_absolute_difference=abs(coarse['peak_core_rh']-ref['peak_core_rh'])))
    checks['half_step_efficiency_change_below_0_5_percent']=all(r['efficiency_relative_difference']<.005 for r in convergence)
    checks['half_step_mean_remaining_change_below_0_02_c']=all(r['remaining_absolute_difference_c']<.02 for r in convergence)
    checks['half_step_peak_core_rh_change_below_0_001']=all(r['peak_core_rh_absolute_difference']<.001 for r in convergence)
    write_csv('timestep_convergence.csv',convergence)
    adverse_cfg=copy.deepcopy(CFG)
    adverse_cfg['devices']['A']['air_speed_m_s']=[CFG['baseline_air_speed_m_s']]*3
    _,adverse,_=run_case(.3,cfg=adverse_cfg,strategies=('A',))
    checks['unhelpful_fan_heat_retains_negative_service']=adverse[0]['service_person_c_h']<0
    checks={k:bool(v) for k,v in checks.items()}
    assert all(checks.values()),checks
    report={'status':'Assumption-driven simulation; internal verification, not empirical validation','versions':{k:importlib.metadata.version(k) for k in ['numpy','matplotlib','pythermalcomfort','psychrolib']},'checks':checks,'nominal':summary,'warmup_states':warmstarts,'convergence':convergence,'max_energy_budget_residual_j':max(abs(r['energy_residual_j']) for r in budgetrows),'max_moisture_budget_residual_kg':max(abs(r['moisture_residual_kg']) for r in budgetrows),'ventilation_multipliers':CFG['ventilation_multipliers']}
    (ROOT/'results_summary.json').write_text(json.dumps(report,indent=2));figures(nominal,summary,sweep)
    print(json.dumps({'checks':checks,'convergence':convergence},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');args=p.parse_args();main(args.quick)
