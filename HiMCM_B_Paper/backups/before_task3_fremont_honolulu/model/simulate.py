"""Illustrative three-zone HiMCM bus-stop model; run from any directory.
NYC geometry is sourced; all local delivery profiles and occupancy are illustrative.
All scenario parameters are explicit in scenario.json. No experimental data.
"""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).parent / '.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME', str(Path(__file__).parent / '.cache'))
os.environ.setdefault('NUMBA_CACHE_DIR', str(Path(__file__).parent / '.numba_cache'))
import csv, json, copy, argparse, importlib.metadata, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from thermal_backend import air_state, direct_evaporative, set_temperature
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_model.delivery import local_delivery, entrainment_ratio
from geometry import shelter_zones, occupancy_counts, occupancy_rows

ROOT = Path(__file__).parent
CFG = json.loads((ROOT/'scenario.json').read_text())
FIG = ROOT.parent/'figures'; FIG.mkdir(exist_ok=True)
EXPORT_FIGURES = True
COL = {'A':'#2379A5', 'B':'#D18C32', 'C':'#76559A'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelsize':12,'axes.titlesize':13,'figure.dpi':120,'savefig.dpi':240,'pdf.fonttype':42,'ps.fonttype':42})

def evaluate(rh, cfg=CFG, occupancy='Uniform', fan_delivery=1.0):
    base = air_state(cfg['temperature_c'], float(rh))
    n = np.array(occupancy_counts(cfg, occupancy), dtype=float)
    theta0 = set_temperature(base.t_c, cfg['radiant_temperature_c'],cfg['baseline_air_speed_m_s'],base.rh,met=cfg['met'],clo=cfg['clo'])
    d0 = max(theta0-cfg['discomfort_threshold_set_c'],0)
    rows=[]; totals=[]
    for s,p in cfg['devices'].items():
        outlet = base if s=='A' else direct_evaporative(base.t_c,base.rh,p['epsilon'],max_drop_c=p['max_drop_c'])
        benefits=[]; discomfort=[]
        for z in range(3):
            beta = p['cooled_mass_fractions'][z]  # Legacy config key: dry-air delivery fraction beta.
            state = local_delivery(base, outlet, beta)
            v = p['v_m_s'][z]
            if s=='A': v = cfg['baseline_air_speed_m_s']+fan_delivery*(v-cfg['baseline_air_speed_m_s'])
            theta = set_temperature(state.t_c,cfg['radiant_temperature_c'],v,state.rh,met=cfg['met'],clo=cfg['clo'])
            d=max(theta-cfg['discomfort_threshold_set_c'],0)
            b=d0-d
            benefits.append(b); discomfort.append(d)
            rows.append(dict(climate_rh=rh,occupancy=occupancy,device=s,zone=cfg['zone_names'][z],
                             people=n[z],t_c=state.t_c,rh=state.rh,v_m_s=v,set_c=theta,
                             baseline_set_c=theta0,benefit_set_c=b,residual_set_c=d,
                             outlet_drop_c=base.t_c-outlet.t_c,delivery_beta=beta,
                             entrainment_ratio_r=entrainment_ratio(beta)))
        u=float(n@np.array(benefits))*cfg['period_h']; e=p['power_kw']*cfg['period_h']
        residual=float(n@np.array(discomfort))*cfg['period_h']
        totals.append(dict(climate_rh=rh,occupancy=occupancy,device=s,people=float(n.sum()),
                           service_person_c_h=u,energy_kwh=e,efficiency=u/e,
                           residual_person_c_h=residual,mean_residual_c=residual/n.sum()/cfg['period_h'] if n.sum() else 0,
                           mean_benefit_c=u/n.sum()/cfg['period_h'] if n.sum() else 0,
                           baseline_set_c=theta0))
    return rows, totals

def write_csv(name, rows):
    with (ROOT/name).open('w', newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

def save(name, fig):
    if not EXPORT_FIGURES:
        plt.close(fig)
        return
    # Export vector PDF directly; never wrap a PNG in a PDF.
    for ax in fig.axes:
        for collection in ax.collections:
            collection.set_rasterized(False)
            if isinstance(collection, matplotlib.collections.QuadMesh):
                # Avoid viewer anti-alias seams between adjacent vector cells.
                collection.set_edgecolor('face')
                collection.set_linewidth(0.1)
                collection.set_antialiased(False)
    fig.savefig(FIG/f'{name}.pdf',format='pdf',bbox_inches='tight',facecolor='white')
    plt.close(fig)

def check_geometry():
    """Check spatial accounting while holding prescribed local fields fixed.

    Counterfactual geometry tests verify the accounting interface, not physical
    airflow invariance or a shelter's allowable passenger capacity.
    """
    zones = shelter_zones(CFG)
    g = CFG['geometry']
    source = g['source_dimensions']
    expected = (source['length_ft'] * 0.3048,
                source['width_ft'] * 0.3048,
                (source['height_ft'] * 12 + source['height_in']) * 0.0254)
    area = sum(z['gross_area_m2'] for z in zones)
    checks = {
        'metric_dimensions_match_documented_imperial_values': all(abs(g[k]-v) < 1e-12 for k, v in zip(('length_m','width_m','height_m'), expected)),
        'zone_areas_partition_gross_footprint': abs(area-g['length_m']*g['width_m']) < 1e-12,
        'zone_bounds_contiguous_and_equal_area': zones[0]['x_min_m'] == 0 and abs(zones[-1]['x_max_m']-g['length_m']) < 1e-12 and all(abs(a['x_max_m']-b['x_min_m']) < 1e-12 for a,b in zip(zones,zones[1:])) and all(abs(z['gross_area_m2']-area/3) < 1e-12 for z in zones),
    }
    _, nominal = evaluate(.3)
    c = copy.deepcopy(CFG)
    c['geometry']['width_m'] *= 2
    _, fixed_counts = evaluate(.3, c)
    checks['fixed_counts_and_prescribed_fields_geometry_change_preserves_service'] = all(abs(a[k]-b[k]) < 1e-10 for a,b in zip(nominal,fixed_counts) for k in ('people','service_person_c_h','energy_kwh','efficiency','residual_person_c_h','mean_benefit_c'))
    density_cfg = copy.deepcopy(CFG)
    density_cfg['occupancies']['Uniform'] = {'gross_density_people_m2': [n/z['gross_area_m2'] for n,z in zip(occupancy_counts(CFG,'Uniform'),zones)]}
    _, density_result = evaluate(.3, density_cfg)
    checks['equivalent_density_and_counts_produce_same_service'] = all(abs(a[k]-b[k]) < 1e-10 for a,b in zip(nominal,density_result) for k in ('people','service_person_c_h','energy_kwh','efficiency','residual_person_c_h'))
    density_cfg['geometry']['width_m'] *= 2
    _, density_doubled = evaluate(.3, density_cfg)
    checks['fixed_density_and_prescribed_fields_double_area_doubles_service'] = all(abs(b[k]-2*a[k]) < 1e-10 for a,b in zip(nominal,density_doubled) for k in ('people','service_person_c_h','efficiency','residual_person_c_h'))
    checks['fixed_density_area_change_does_not_rescale_power_or_local_benefit'] = all(abs(a[k]-b[k]) < 1e-10 for a,b in zip(nominal,density_doubled) for k in ('energy_kwh','mean_benefit_c','mean_residual_c'))
    invalid_occupancies = [[1,-1,1], [1,2], [1,float('nan'),1], {'gross_density_people_m2':[1,-1,1]}, {'gross_density_people_m2':[1,float('inf'),1]}, {'people':[1,1,1], 'gross_density_people_m2':[1,1,1]}]
    rejected = []
    for spec in invalid_occupancies:
        c = copy.deepcopy(CFG); c['occupancies']['Uniform'] = spec
        try:
            occupancy_counts(c, 'Uniform')
        except ValueError:
            rejected.append(True)
        else:
            rejected.append(False)
    checks['invalid_or_ambiguous_occupancy_inputs_rejected'] = all(rejected)
    rejected = []
    for value in (0, -1, float('nan'), float('inf')):
        c = copy.deepcopy(CFG); c['geometry']['width_m'] = value
        try:
            shelter_zones(c)
        except ValueError:
            rejected.append(True)
        else:
            rejected.append(False)
    checks['nonpositive_or_nonfinite_dimensions_rejected'] = all(rejected)
    assert all(checks.values()), checks
    return {'checks': checks,
            'source': {k:g[k] for k in ('source_title','source_url','source_accessed','source_dimensions')},
            'dimensions_m': {k:g[k] for k in ('length_m','width_m','height_m')},
            'gross_plan_area_m2': area,
            'zones': zones,
            'occupancies': occupancy_rows(CFG),
            'interpretation': 'Gross geometry defines positions and density-to-count accounting. Local air-speed and treated-air fractions remain prescribed; geometry does not predict these fields. Fixed-count result invariance and fixed-density scaling apply only under that assumption. These are not capacity or net standing-area tests.'}


def main(export_figures=True):
    global EXPORT_FIGURES
    EXPORT_FIGURES = export_figures
    write_csv('geometry_zones.csv', shelter_zones(CFG))
    write_csv('geometry_occupancy.csv', occupancy_rows(CFG))
    (ROOT/'geometry_checks.json').write_text(json.dumps(check_geometry(), indent=2)+'\n')
    local=[]; totals=[]
    for label,rh in CFG['relative_humidity_cases'].items():
        for occ in CFG['occupancies']:
            r,t=evaluate(rh,occupancy=occ)
            local+=r; totals+=t
    write_csv('local_conditions.csv',local); write_csv('scenario_results.csv',totals)
    # Figure 1: expose the environmental mechanisms and spatial variation.
    fig,axes=plt.subplots(2,3,figsize=(10.2,5.5),layout='constrained')
    fields=[('t_c','Air temperature (°C)','coolwarm'),('rh','Relative humidity (%)','YlGnBu'),('set_c','SET (°C)','YlOrRd')]
    for ri,(label,rh) in enumerate(CFG['relative_humidity_cases'].items()):
        r,t=evaluate(rh)
        for ci,(key,title,cmap) in enumerate(fields):
            vals=np.array([[next(x[key] for x in r if x['device']==s and x['zone']==z) for z in CFG['zone_names']] for s in 'ABC'])
            if key=='rh': vals*=100
            lo,hi={'t_c':(25,34),'rh':(20,100),'set_c':(24,38)}[key]
            # Mesh cells remain vector rectangles in the exported PDF.
            im=axes[ri,ci].pcolormesh(np.arange(4)-.5,np.arange(4)-.5,vals,cmap=cmap,vmin=lo,vmax=hi,shading='flat',rasterized=False)
            axes[ri,ci].set_xlim(-.5,2.5); axes[ri,ci].set_ylim(2.5,-.5)
            for iy in range(3):
                for ix in range(3): axes[ri,ci].text(ix,iy,f'{vals[iy,ix]:.1f}',ha='center',va='center',color=('white' if sum(a*b for a,b in zip(im.cmap(im.norm(vals[iy,ix]))[:3],[.2126,.7152,.0722]))<.5 else 'black'),fontsize=12)
            axes[ri,ci].set(xticks=range(3),xticklabels=CFG['zone_names'],yticks=range(3),yticklabels=list('ABC'),title=f'{label}: {title}')
            fig.colorbar(im,ax=axes[ri,ci],shrink=.8)
    save('01_local_conditions',fig)
    # Figure 2: efficiency and quality are separate outcomes.
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    x=np.arange(2); width=.22
    for j,s in enumerate('ABC'):
        st=[next(t for t in totals if t['device']==s and t['occupancy']=='Uniform' and t['climate_rh']==rh) for rh in [.3,.7]]
        for ax,key in zip(axes,['efficiency','mean_residual_c']):
            bars=ax.bar(x+(j-1)*width,[v[key] for v in st],width,label=s,color=COL[s])
            ax.bar_label(bars,fmt='%.1f',padding=3,fontsize=11)
    axes[0].set(ylabel='Service efficiency (person·°C·h/kWh)',title='Useful relief per unit electricity')
    axes[1].set(ylabel='Mean remaining SET excess (°C)',title='Remaining discomfort above assumed 26°C')
    for ax in axes: ax.set_xticks(x,['Dry: RH 30%','Humid: RH 70%']); ax.margins(y=.2); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    axes[0].legend(title='Device',ncol=3,loc='upper right')
    axes[0].set_ylim(0,max(t['efficiency'] for t in totals if t['occupancy']=='Uniform')*1.45)
    save('02_efficiency_and_quality',fig)
    # Figure 3: climate sweep, with all other assumptions fixed.
    rhs=np.linspace(.2,.8,61); sweep=[]
    for rh in rhs:
        r,t=evaluate(float(rh)); sweep+=t
    write_csv('humidity_sweep.csv',sweep)
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    for s in 'BC':
        p=CFG['devices'][s]
        drops=[CFG['temperature_c']-direct_evaporative(CFG['temperature_c'],float(r),p['epsilon'],max_drop_c=p['max_drop_c']).t_c for r in rhs]
        axes[0].plot(rhs*100,drops,label=s,color=COL[s],lw=2,ls='--' if s=='C' else '-')
    axes[0].set(xlabel='Ambient relative humidity (%)',ylabel='Modeled outlet air-temperature drop (°C)',title='Wet-bulb limit reduces evaporative cooling'); axes[0].legend()
    for s in 'ABC': axes[1].plot(rhs*100,[x['efficiency'] for x in sweep if x['device']==s],label=s,color=COL[s],lw=2)
    axes[1].set(xlabel='Ambient relative humidity (%)',ylabel='Service efficiency (person·°C·h/kWh)',title='Climate-dependent service efficiency'); axes[1].legend()
    for ax in axes: ax.grid(alpha=.2)
    save('03_humidity_sweep',fig)
    # Figure 4: keep total number fixed; move passengers between zones.
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    occs=list(CFG['occupancies']); x=np.arange(len(occs))
    counts_by_occ=[occupancy_counts(CFG,o) for o in occs]
    occupancy_labels=[o+'\n'+' / '.join(f'{n:g}' for n in counts) for o,counts in zip(occs,counts_by_occ)]
    populations=[sum(counts) for counts in counts_by_occ]
    occupancy_title=(f'same {populations[0]:g} people, different positions' if np.allclose(populations,populations[0]) else 'assumed occupancy scenarios')
    for ax,(label,rh) in zip(axes,CFG['relative_humidity_cases'].items()):
        for j,s in enumerate('ABC'):
            vals=[next(t['efficiency'] for t in totals if t['climate_rh']==rh and t['occupancy']==o and t['device']==s) for o in occs]
            ax.bar(x+(j-1)*.22,vals,.22,label=s,color=COL[s])
        ax.set(xticks=x,xticklabels=occupancy_labels,ylabel='Service efficiency (person·°C·h/kWh)',title=f'{label}: {occupancy_title}')
        ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    axes[0].legend(ncol=3)
    for ax in axes: ax.set_ylim(0,max(t['efficiency'] for t in totals)*1.3)
    save('04_occupancy',fig)
    # Figure 5: loss of fan delivery, with unchanged electrical power.
    qs=np.linspace(0,1,51); winners=np.zeros((len(qs),len(rhs)),int); regimes=[]
    thresholds=[]
    for ix,rh in enumerate(rhs):
        for iy,q in enumerate(qs):
            _,t=evaluate(float(rh),fan_delivery=float(q)); es=[x['efficiency'] for x in t]; win=int(np.argmax(es)); winners[iy,ix]=win
            regimes.append(dict(rh=float(rh),fan_delivery=float(q),winner='ABC'[win],eta_A=es[0],eta_B=es[1],eta_C=es[2]))
        wins_a=(winners[:,ix]==0)
        assert np.all(np.diff(wins_a.astype(int))>=0), 'Non-contiguous A-winner region; cannot draw a single threshold.'
        winning_q=[qs[i] for i in range(len(qs)) if winners[i,ix]==0]
        thresholds.append(dict(rh=float(rh),minimum_grid_q_for_A=float(min(winning_q)) if winning_q else None))
    write_csv('delivery_decision_map.csv',regimes); write_csv('fan_delivery_thresholds.csv',thresholds)
    fig,ax=plt.subplots(figsize=(7.8,3.9),layout='constrained')
    cmap=ListedColormap([COL[s] for s in 'ABC']); norm=BoundaryNorm([-.5,.5,1.5,2.5],3)
    # Merge this two-region grid into contiguous vector fills to avoid PDF
    # viewer seams between thousands of same-colored cells. Grid values stay exact.
    if set(np.unique(winners)).issubset({0,1}) and all(t['minimum_grid_q_for_A'] is not None for t in thresholds):
        dx=(rhs[1]-rhs[0])*100; dy=qs[1]-qs[0]
        edges=np.r_[rhs*100-dx/2, rhs[-1]*100+dx/2]
        xp=np.column_stack((edges[:-1],edges[1:])).reshape(-1)
        boundary=np.repeat([t['minimum_grid_q_for_A']-dy/2 for t in thresholds],2)
        ax.set_facecolor(COL['A'])
        ax.fill_between(xp,qs[0]-dy/2,boundary,color=COL['B'],linewidth=0,antialiased=False)
        ax.set_xlim(edges[0],edges[-1]); ax.set_ylim(qs[0]-dy/2,qs[-1]+dy/2)
        im=matplotlib.cm.ScalarMappable(norm=norm,cmap=cmap)
    else:
        im=ax.pcolormesh(rhs*100,qs,winners,cmap=cmap,norm=norm,shading='nearest')
    ax.plot(rhs*100,[t['minimum_grid_q_for_A'] for t in thresholds],color='white',lw=1.5)
    cb=fig.colorbar(im,ax=ax,ticks=[0,1,2]); cb.ax.set_yticklabels(['A: fan','B: evaporative','C: no winning cells'])
    ax.set(xlabel='Ambient relative humidity (%)',ylabel='Fan air-speed delivery fraction q',title='Highest service efficiency under a fan-delivery stress test')
    ax.text(.98,.94,'q=1: nominal fan profile\nq=0: no added air speed at occupied positions',transform=ax.transAxes,ha='right',va='top',color='white',fontsize=11)
    save('05_delivery_decision',fig)
    # Figure 6: one-at-a-time sensitivity, predeclared parameter ranges.
    sensitivities=[]; variants=[]
    def add(label, configs): variants.append((label,configs))
    for label,vals,mutator in [
      ('Evap. effectiveness: 0.5–0.9',[.5,.9],lambda c,v:[c['devices'][s].update(epsilon=v) for s in 'BC']),
      ('Delivery beta: ×0.75–1.25',[.75,1.25],lambda c,v:[c['devices'][s].update(cooled_mass_fractions=[min(1,f*v) for f in CFG['devices'][s]['cooled_mass_fractions']]) for s in 'BC']),
      ('Fan added speed: x0.5–1.5',[.5,1.5],lambda c,v:c['devices']['A'].update(v_m_s=[.2+v*(x-.2) for x in CFG['devices']['A']['v_m_s']])),
      ('Evap. added speed: x0.5–1.5',[.5,1.5],lambda c,v:[c['devices'][s].update(v_m_s=[.2+v*(x-.2) for x in CFG['devices'][s]['v_m_s']]) for s in 'BC']),
      ('Rating cap: applied / removed',[True,False],lambda c,v:[c['devices'][s].update(max_drop_c=CFG['devices'][s]['max_drop_c'] if v else None) for s in 'BC']),
      ('SET threshold: 24–28°C',[24,28],lambda c,v:c.update(discomfort_threshold_set_c=v)),
      ('Mean radiant temperature: 34–38°C',[34,38],lambda c,v:c.update(radiant_temperature_c=v)),
      ('Activity: 1.1–1.6 met',[1.1,1.6],lambda c,v:c.update(met=v)),
      ('Clothing: 0.3–0.7 clo',[.3,.7],lambda c,v:c.update(clo=v))]:
        configs=[]
        for val in vals:
            c=copy.deepcopy(CFG); mutator(c,val); configs.append(c)
        add(label,configs)
    fig,axes=plt.subplots(1,2,figsize=(10,5.0),layout='constrained')
    labels=[x[0] for x in variants]
    for ax,(label,rh) in zip(axes,CFG['relative_humidity_cases'].items()):
        _,base=evaluate(rh); ratios={s:base['ABC'.index(s)]['efficiency']/base[0]['efficiency'] for s in 'BC'}
        for j,s in enumerate('BC'):
            for i,(factor,configs) in enumerate(variants):
                rs=[]
                for ci,c in enumerate(configs):
                    _,tt=evaluate(rh,cfg=c); ratio=tt['ABC'.index(s)]['efficiency']/tt[0]['efficiency']; rs.append(ratio)
                    sensitivities.append(dict(climate=label,factor=factor,endpoint=ci,device=s,ratio_to_A=ratio))
                y=i+(j-.5)*.22; ax.plot([min(rs),max(rs)],[y,y],color=COL[s],lw=3); ax.plot(ratios[s],y,'o',color=COL[s],ms=4)
            ax.plot([],[],color=COL[s],lw=3,label=f'{s}/A')
        ax.axvline(1,color='#555555',ls='--',lw=1)
        ax.set(yticks=range(len(labels)),yticklabels=labels if ax is axes[0] else [],xlabel='Efficiency ratio to A (above 1 beats A)',title=label,xlim=(min(0,min(t['ratio_to_A'] for t in sensitivities if t['climate']==label)*1.1),max(1.12,max(t['ratio_to_A'] for t in sensitivities if t['climate']==label)*1.1))); ax.invert_yaxis(); ax.grid(axis='x',alpha=.2); ax.legend(loc='lower right')
    write_csv('sensitivity.csv',sensitivities); save('06_sensitivity',fig)
    # Accounting and limiting-case checks; no fitted data are asserted.
    _,nom=evaluate(.3)
    checks={}
    checks['benefit_plus_residual_equals_baseline']=all(abs(t['service_person_c_h']+t['residual_person_c_h']-t['people']*CFG['period_h']*max(t['baseline_set_c']-26,0))<1e-8 for t in totals)
    c=copy.deepcopy(CFG); c['occupancies']['Uniform']=[0,0,0]; _,zero=evaluate(.3,c)
    checks['empty_shelter_zero_service_positive_energy']=all(t['service_person_c_h']==0 and t['energy_kwh']>0 for t in zero)
    c=copy.deepcopy(CFG); c['occupancies']['Uniform']=[8,8,8]; _,twice=evaluate(.3,c)
    checks['doubling_population_doubles_efficiency_preserves_rank']=all(abs(b['efficiency']-2*a['efficiency'])<1e-8 for a,b in zip(nom,twice))
    c=copy.deepcopy(CFG)
    for p in c['devices'].values(): p.update(v_m_s=[.2]*3,cooled_mass_fractions=[0]*3)
    _,off=evaluate(.3,c); checks['zero_delivered_effect_zero_service']=all(abs(t['service_person_c_h'])<1e-8 for t in off)
    checks['all_local_states_unsaturated']=all(0<x['rh']<=1 for x in local)
    c=copy.deepcopy(CFG); c['baseline_air_speed_m_s']=1.0; c['devices']['A']['v_m_s']=[.2]*3
    _,adverse=evaluate(.3,c); checks['negative_benefit_retained']=adverse[0]['service_person_c_h']<0 and adverse[0]['efficiency']<0
    c=copy.deepcopy(CFG); c.update(temperature_c=20,radiant_temperature_c=20)
    _,mild=evaluate(.3,c); checks['no_credit_for_cooling_already_comfortable']=all(abs(t['service_person_c_h'])<1e-8 for t in mild)
    reference=json.loads((ROOT.parent/'shared_model/reference_bus_results.json').read_text())
    checks['unified_map_recovers_original_bus_results']=all(abs(float(a[k])-b[k])<1e-10 for a,b in zip(reference,totals) for k in ('service_person_c_h','energy_kwh','efficiency','mean_residual_c'))
    assert all(checks.values()),checks
    report={'checks':checks,'versions':{x:importlib.metadata.version(x) for x in ['numpy','scipy','pythermalcomfort','psychrolib','matplotlib']},'nominal_uniform':[t for t in totals if t['occupancy']=='Uniform'],
            'decision_grid_winner_counts':{s:int((winners==i).sum()) for i,s in enumerate('ABC')},
            'decision_grid_note':'Counts describe an artificial uniform grid, not probabilities.',
            'fan_thresholds':[t for t in thresholds if abs(t['rh']-.3)<1e-8 or abs(t['rh']-.7)<1e-8],
            'maximum_sensitivity_ratios':{s:max(t['ratio_to_A'] for t in sensitivities if t['device']==s) for s in 'BC'}}
    (ROOT/'results_summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-figures', action='store_true', help='Recalculate CSV/JSON results without replacing the six figure PDFs')
    args = parser.parse_args()
    main(export_figures=not args.no_figures)
