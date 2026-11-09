"""Canberra occupied-area planning scenario; mixed integer counts and disjoint coverage.
Not a calibrated whole-station design. Run this file to regenerate CSVs and PDFs.
"""
from pathlib import Path
import os,sys,json,csv,copy,importlib.metadata
ROOT=Path(__file__).resolve().parent; PROJECT=ROOT.parent
for key,leaf in [('MPLCONFIGDIR','.mplconfig'),('XDG_CACHE_HOME','.cache'),('NUMBA_CACHE_DIR','.numba_cache')]:os.environ.setdefault(key,str(ROOT/leaf))
sys.path.insert(0,str(PROJECT/'station_model'))
import simulate_station as station
import numpy as np
from pythermalcomfort.models import set_tmp
import matplotlib.pyplot as plt
CFG=json.loads((ROOT/'scenario.json').read_text())
ZERO=np.zeros((3,3),dtype=int)
TYPES=['A','B','C']; COL={'A':'#2379A5','B':'#D18C32','C':'#76559A','Mixed':'#268467'}

def validate(x,cfg=CFG,coverage_scale=1.):
    x=np.asarray(x)
    if x.shape!=(3,3) or np.any(x<0) or np.any(x!=np.floor(x)):raise ValueError('Counts must be a nonnegative integer 3x3 matrix')
    fractions=x*np.array(cfg['coverage_m2_per_unit'])*coverage_scale/cfg['zone_area_m2']
    if np.any(fractions.sum(axis=1)>1+1e-12):raise ValueError('Disjoint service footprints exceed occupied zone area')
    return np.column_stack((1-fractions.sum(axis=1),fractions))

def rhs(y,n,ach,ctx,x,cfg=CFG):
    dy,budget=station.rhs(y,n,ach,ctx,'Baseline',cfg)
    air=station.states(y,cfg);extra_h=np.zeros(3);extra_w=np.zeros(3)
    for k,name in enumerate(TYPES):
        d=cfg['devices'][name]
        extra_h+=x[:,k]*d['unit_power_kw']*1000*cfg['motor_heat_fraction']
        if not d['recirculation_kg_da_s_per_unit']:continue
        for z,a in enumerate(air):
            if x[z,k]==0:continue
            out=station.direct_evaporative(a.t_c,a.rh,d['epsilon'],a.p_pa,d['outlet_drop_cap_c'])
            flow=x[z,k]*d['recirculation_kg_da_s_per_unit']
            extra_h[z]+=flow*(out.h_j_kg_da-a.h_j_kg_da)
            extra_w[z]+=flow*(out.w-a.w)
    dy[:,0]+=extra_h/ctx['mass'];dy[:,1]+=extra_w/ctx['mass']
    budget+=np.array([extra_h.sum(),extra_w.sum()])
    return dy,budget

def integrate(x,cfg=CFG,initial=None,observe=True,duration=None):
    validate(x,cfg);ctx=station.context(cfg['relative_humidity'],cfg);out=ctx['outside'];dt=cfg['dt_s'];duration=cfg['duration_s'] if duration is None else duration
    for edge in [duration,cfg['train_period_s'],cfg['arrival_pulse_duration_s']]:assert abs(edge/dt-round(edge/dt))<1e-12
    y=np.tile([out.h_j_kg_da,out.w,out.t_c],(3,1)) if initial is None else initial.copy()
    first=y.copy();budget=np.zeros(2);samples=[];people=[];times=[]
    for i in range(round(duration/dt)):
        t=(i+.5)*dt;n,ach=station.forcing(t,cfg)
        k1,b1=rhs(y,n,ach,ctx,x,cfg);k2,b2=rhs(y+k1*dt/2,n,ach,ctx,x,cfg)
        k3,b3=rhs(y+k2*dt/2,n,ach,ctx,x,cfg);k4,b4=rhs(y+k3*dt,n,ach,ctx,x,cfg)
        yn=y+dt*(k1+2*k2+2*k3+k4)/6;budget+=dt*(b1+2*b2+2*b3+b4)/6
        if observe:samples.append((y+yn)/2);people.append(n);times.append(t/60)
        y=yn
    storage=np.array([np.sum(ctx['mass']*(y[:,0]-first[:,0]))+cfg['surface_capacity_j_k']*sum(y[:,2]-first[:,2]),np.sum(ctx['mass']*(y[:,1]-first[:,1]))])
    result={'final':y,'initial':first,'budget':budget,'storage':storage,'residual':storage-budget,'dt':dt}
    if observe:
        yy=np.array(samples);ta=[];rh=[]
        for state in yy:
            aa=station.states(state,cfg);ta.append([a.t_c for a in aa]);rh.append([a.rh for a in aa])
        ta=np.array(ta);rh=np.array(rh);tr=station.radiation(yy[:,:,2],cfg)
        # All four subpopulations share bulk thermal states; only prescribed local speed differs.
        v=np.column_stack((np.full(3,cfg['baseline_air_speed_m_s']),*[cfg['devices'][k]['air_speed_m_s'] for k in TYPES]))
        theta=np.asarray(set_tmp(tdb=ta[:,:,None],tr=tr[:,:,None],rh=100*rh[:,:,None],v=v[None,:,:],met=cfg['met'],clo=cfg['clo'],p_atm=cfg['pressure_pa'],position='standing',limit_inputs=True,round_output=False).set)
        if not np.all(np.isfinite(theta)):raise ValueError('SET domain invalid')
        result.update(time=np.array(times),people=np.array(people),temperature=ta,rh=rh,mrt=tr,surface=yy[:,:,2],discomfort=np.maximum(theta-cfg['set_threshold_c'],0),theta=theta)
    return result

def accounting(name,x,run,baseline,cfg=CFG,coverage_scale=1.):
    fractions=validate(x,cfg,coverage_scale);n=run['people'];dh=run['dt']/3600
    weighted=(run['discomfort']*fractions[None,:,:]).sum(axis=2)
    b=baseline['discomfort'][:,:,0];H=float(n.sum()*dh);R=float((n*weighted).sum()*dh);R0=float((n*b).sum()*dh);U=R0-R
    powers=np.array([cfg['devices'][k]['unit_power_kw'] for k in TYPES]);E=float((x*powers).sum()*cfg['duration_s']/3600)
    covered_people=float((n*(1-fractions[:,0])[None,:]).sum()*dh)
    return dict(plan=name,family=(next(k for j,k in enumerate(TYPES) if x[:,j].sum()>0) if np.count_nonzero(x.sum(axis=0))==1 else 'Mixed'),total_devices=int(x.sum()),A=int(x[:,0].sum()),B=int(x[:,1].sum()),C=int(x[:,2].sum()),counts_by_zone=json.dumps(x.tolist()),area_coverage_fraction=float((1-fractions[:,0]).mean()),person_time_coverage_fraction=covered_people/H if H else 0,energy_kwh=E,person_hours=H,service_person_c_h=U,efficiency=U/E if E else None,remaining_person_c_h=R,mean_remaining_c=R/H if H else 0,mean_relief_c=U/H if H else 0,baseline_remaining_person_c_h=R0,peak_core_rh=float(run['rh'][:,1].max()),energy_budget_residual_j=float(run['residual'][0]),moisture_budget_residual_kg=float(run['residual'][1]))

def candidates():
    d={}
    for k,levels in [('A',[1,3,6,9,12,15,17]),('B',[1,2,4,6,8,10,11]),('C',[1,2,3,4,6,8])]:
        for n in levels:
            x=ZERO.copy();x[:,TYPES.index(k)]=n;d[f'{k}{3*n}']=x
    for name,row in [('AB30',[6,4,0]),('AC27',[6,0,3]),('ABC24',[3,2,3])]:d[name]=np.tile(row,(3,1))
    d['AB30-R']=np.array([[3,4,0],[12,3,0],[3,5,0]])
    return d
BENCH=['A36','B24','C18','AB30','AC27','ABC24']

def csvwrite(path,rows):
    with (ROOT/path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def graphs(rows,sensitivity):
    fig,ax=plt.subplots(figsize=(9,5.1),layout='constrained')
    for family in ['A','B','C','Mixed']:
        rr=[r for r in rows if r['family']==family];ax.scatter([r['energy_kwh'] for r in rr],[r['mean_remaining_c'] for r in rr],c=COL[family],marker='D' if family=='Mixed' else 'o',s=48,label=family,zorder=3)
    nd=sorted([r for r in rows if r['nondominated']],key=lambda r:r['energy_kwh'])
    ax.plot([r['energy_kwh'] for r in nd],[r['mean_remaining_c'] for r in nd],ls='--',c='#555',lw=1,label='Nondominated sampled plans')
    for r in rows:
        if r['plan'] in BENCH or r['plan']=='AB30-R':ax.annotate(r['plan'],(r['energy_kwh'],r['mean_remaining_c']),xytext=(4,7 if r['plan']!='AB30-R' else -13),textcoords='offset points',fontsize=9)
    ax.set(xlabel='All-device electricity over two hours (kWh)',ylabel='Mean remaining SET excess (°C)',title='Canberra planning scenario: finite candidate comparison')
    ax.grid(alpha=.2);ax.legend(ncol=2,fontsize=9)
    fig.savefig(PROJECT/'figures/14_deployment_tradeoff.pdf',bbox_inches='tight');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10.2,4.7),layout='constrained');labels=BENCH;rr=[next(r for r in rows if r['plan']==n) for n in labels];y=np.arange(6);left=np.zeros(6)
    for k in TYPES:
        vals=np.array([r[k] for r in rr]);bar=axs[0].barh(y,vals,left=left,color=COL[k],label=k)
        axs[0].bar_label(bar,labels=[str(int(v)) if v else '' for v in vals],label_type='center',fontsize=10,color='white');left+=vals
    axs[0].set(yticks=y,yticklabels=labels,xlabel='Total units across three zones',title='Equal assumed coverage: 68.2%');axs[0].set_ylim(6,-.6);axs[0].legend(ncol=3,loc='lower right',fontsize=9)
    bars=axs[1].barh(y,[r['mean_remaining_c'] for r in rr],color=[COL[r['family']] for r in rr]);axs[1].bar_label(bars,fmt='%.2f',padding=3,fontsize=10)
    axs[1].set(yticks=y,yticklabels=labels,xlabel='Mean remaining SET excess (°C)',title='Same weather, occupancy and covered area');axs[1].invert_yaxis();axs[1].set_xlim(0,max(r['mean_remaining_c'] for r in rr)*1.2)
    for ax in axs:ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    fig.savefig(PROJECT/'figures/15_deployment_mix.pdf',bbox_inches='tight');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10.2,4.6),layout='constrained')
    for k in TYPES:
        rr=sorted([r for r in rows if r['family']==k],key=lambda r:r['total_devices']);axs[0].plot([r['total_devices'] for r in rr],[100*r['person_time_coverage_fraction'] for r in rr],'-o',color=COL[k],label=k,ms=4)
    axs[0].set(xlabel='Total units',ylabel='Person-time in direct-airflow footprints (%)',title='Coverage expands with device count');axs[0].legend()
    palette=['#2379A5','#D18C32','#76559A','#268467','#b35e7c','#8c564b']
    for i,name in enumerate(BENCH):
        rr=[r for r in sensitivity if r['plan']==name];axs[1].plot([r['coverage_scale'] for r in rr],[r['mean_remaining_c'] for r in rr],'-o',label=name,ms=4,color=palette[i])
    axs[1].set(xlabel='Assumed footprint multiplier',ylabel='Mean remaining SET excess (°C)',title='Unmeasured coverage: ±25% sensitivity',xticks=[.75,1,1.25]);axs[1].legend(ncol=2,fontsize=8)
    for ax in axs:ax.grid(alpha=.2)
    fig.savefig(PROJECT/'figures/16_deployment_coverage.pdf',bbox_inches='tight');plt.close(fig)

def main():
    plans=candidates();warm=integrate(ZERO,observe=False,duration=CFG['warmup_s']);base=integrate(ZERO,initial=warm['final']);runs={};rows=[]
    for name,x in plans.items():
        run=integrate(x,initial=warm['final']);runs[name]=run;rows.append(accounting(name,x,run,base));print(name,rows[-1]['efficiency'],rows[-1]['mean_remaining_c'],flush=True)
    for r in rows:r['nondominated']=not any(q['energy_kwh']<=r['energy_kwh'] and q['mean_remaining_c']<=r['mean_remaining_c'] and (q['energy_kwh']<r['energy_kwh'] or q['mean_remaining_c']<r['mean_remaining_c']) for q in rows)
    sensitivity=[]
    for name in BENCH:
        for scale in [.75,1.,1.25]:
            q=accounting(name,plans[name],runs[name],base,coverage_scale=scale);q['coverage_scale']=scale;sensitivity.append(q)
    fine=copy.deepcopy(CFG);fine['dt_s']/=2;warmf=integrate(ZERO,cfg=fine,observe=False,duration=fine['warmup_s']);basef=integrate(ZERO,cfg=fine,initial=warmf['final']);convergence=[]
    for name in ['AB30','AC27','ABC24']:
        ff=integrate(plans[name],cfg=fine,initial=warmf['final']);q=accounting(name,plans[name],ff,basef,cfg=fine);r=next(r for r in rows if r['plan']==name)
        convergence.append(dict(plan=name,relative_efficiency_difference=abs(q['efficiency']-r['efficiency'])/max(1,abs(q['efficiency'])),remaining_difference_c=abs(q['mean_remaining_c']-r['mean_remaining_c']),peak_rh_difference=abs(q['peak_core_rh']-r['peak_core_rh'])))
    checks={}
    checks['all_counts_integer_and_disjoint']=all(np.all(validate(x)>=-1e-12) for x in plans.values())
    checks['same_benchmark_coverage']=all(abs(next(r for r in rows if r['plan']==name)['area_coverage_fraction']-720/1056)<1e-12 for name in BENCH)
    checks['service_identity']=all(abs(r['service_person_c_h']+r['remaining_person_c_h']-r['baseline_remaining_person_c_h'])<1e-9 for r in rows)
    checks['all_power_counted']=all(abs(r['energy_kwh']-2*(.25*r['A']+1.2*r['B']+2.5*r['C']))<1e-9 for r in rows)
    checks['global_energy_and_moisture']=all(abs(r['energy_budget_residual_j'])<1e-3 and abs(r['moisture_budget_residual_kg'])<1e-10 for r in rows)
    checks['half_step_convergence']=all(r['relative_efficiency_difference']<.005 and r['remaining_difference_c']<.02 and r['peak_rh_difference']<.001 for r in convergence)
    checks['valid_humidity_and_set']=all(np.all(np.isfinite(run['theta'])) and np.all((run['rh']>=0)&(run['rh']<=1)) for run in runs.values())
    # Exact pure-limit check: same dynamic sources when all entries are zero except one type.
    n,ach=station.forcing(155,CFG);ctx=station.context(CFG['relative_humidity'],CFG)
    limit=True
    for j,k in enumerate(TYPES):
        x=ZERO.copy();x[:,j]=2;c=copy.deepcopy(CFG);c['device_count_per_zone']=2
        a,b=rhs(warm['final'],n,ach,ctx,x,CFG);aa,bb=station.rhs(warm['final'],n,ach,ctx,k,c)
        limit=limit and np.allclose(a,aa,rtol=0,atol=1e-10) and np.allclose(b,bb,rtol=0,atol=1e-7)
    checks['mixed_sources_reduce_to_pure_model']=bool(limit)
    # No occupancy earns no service, irrespective of electrical input.
    no=copy.deepcopy(CFG);no['occupancy_min']=[0,0,0];no['occupancy_peak']=[0,0,0]
    nb=integrate(ZERO,cfg=no,initial=warm['final']);nr=integrate(plans['A3'],cfg=no,initial=warm['final']);nq=accounting('empty',plans['A3'],nr,nb,cfg=no)
    checks['empty_zero_service_positive_energy']=nq['service_person_c_h']==0 and nq['energy_kwh']>0
    bad=copy.deepcopy(CFG);bad['devices']['A']['air_speed_m_s']=[bad['baseline_air_speed_m_s']]*3
    br=integrate(plans['A3'],cfg=bad,initial=warm['final']);bq=accounting('adverse',plans['A3'],br,base,cfg=bad)
    checks['adverse_heat_remains_signed']=bq['service_person_c_h']<0
    checks['footprint_weights_sum_one']=all(np.allclose(validate(x).sum(axis=1),1) for x in plans.values())
    checks={k:bool(v) for k,v in checks.items()};assert all(checks.values()),checks
    csvwrite('candidate_results.csv',rows);csvwrite('coverage_sensitivity.csv',sensitivity);csvwrite('timestep_convergence.csv',convergence)
    trajectory=[]
    for name in ['Baseline']+BENCH+['AB30-R']:
        run=base if name=='Baseline' else runs[name];x=ZERO if name=='Baseline' else plans[name];f=validate(x);d=(run['discomfort']*f[None,:,:]).sum(axis=2)
        for i,t in enumerate(run['time']):
            for z in range(3):trajectory.append(dict(plan=name,time_min=t,zone=CFG['geometry']['zones'][z],people=run['people'][i,z],temperature_c=run['temperature'][i,z],rh=run['rh'][i,z],surface_c=run['surface'][i,z],mrt_c=run['mrt'][i,z],mean_discomfort_c=d[i,z],airflow_coverage_fraction=1-f[z,0]))
    csvwrite('time_series.csv',trajectory)
    report={'versions':{k:importlib.metadata.version(k) for k in ['numpy','matplotlib','pythermalcomfort','psychrolib']},'status':'Hypothetical occupied-area deployment scenario; no measured station validation; nondominance only among sampled plans','checks':checks,'baseline_remaining_c':float((base['people']*base['discomfort'][:,:,0]).sum()/base['people'].sum()),'person_hours':rows[0]['person_hours'],'warmup_state':warm['final'].tolist(),'benchmarks':[r for r in rows if r['plan'] in BENCH+['AB30-R']],'nondominated':[r['plan'] for r in rows if r['nondominated']],'convergence':convergence,'candidate_count':len(rows),'max_energy_residual_j':max(abs(r['energy_budget_residual_j']) for r in rows),'max_moisture_residual_kg':max(abs(r['moisture_budget_residual_kg']) for r in rows)}
    (ROOT/'results_summary.json').write_text(json.dumps(report,indent=2));graphs(rows,sensitivity)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
