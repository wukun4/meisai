"""Postprocess existing trajectories: no new spatial resolution or thermal simulation."""
from pathlib import Path
import os,csv,json,hashlib
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent;INPUT=PROJECT/'deployment_model'
for key,name in [('MPLCONFIGDIR','.mplconfig'),('NUMBA_CACHE_DIR','.numba_cache'),('XDG_CACHE_HOME','.cache')]:os.environ.setdefault(key,str(ROOT/name))
import numpy as np
from pythermalcomfort.models import set_tmp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
cfg=json.loads((INPUT/'scenario.json').read_text());zones=cfg['geometry']['zones'];plans=['A36','B24','C18','AB30','AC27','ABC24','AB30-R']
raw=list(csv.DictReader((INPUT/'time_series.csv').open()));results={r['plan']:r for r in csv.DictReader((INPUT/'candidate_results.csv').open())}
index={}
for name in ['Baseline']+plans:
 for z in zones:
  index[name,z]=sorted([r for r in raw if r['plan']==name and r['zone']==z],key=lambda r:float(r['time_min']))
get=lambda rows,k:np.array([float(r[k]) for r in rows])
out=[];checks=[]
for name in plans:
 counts=np.array(json.loads(results[name]['counts_by_zone']))
 for zi,z in enumerate(zones):
  r=index[name,z];b=index['Baseline',z];t=get(r,'time_min');n=get(r,'people')
  assert np.allclose(t,get(b,'time_min')) and np.allclose(n,get(b,'people'))
  ta=get(r,'temperature_c');rh=get(r,'rh');tr=get(r,'mrt_c');assert np.all((rh>=0)&(rh<=1))
  f=counts[zi]*np.array(cfg['coverage_m2_per_unit'])/cfg['zone_area_m2'];f=np.r_[1-f.sum(),f];assert min(f)>=-1e-12
  speeds=np.array([cfg['baseline_air_speed_m_s']]+[cfg['devices'][k]['air_speed_m_s'][zi] for k in 'ABC'])
  args=dict(met=cfg['met'],clo=cfg['clo'],p_atm=cfg['pressure_pa'],position='standing',limit_inputs=True,round_output=False)
  theta=np.asarray(set_tmp(tdb=ta[:,None],tr=tr[:,None],rh=100*rh[:,None],v=speeds[None,:],**args).set)
  base=np.asarray(set_tmp(tdb=get(b,'temperature_c'),tr=get(b,'mrt_c'),rh=100*get(b,'rh'),v=cfg['baseline_air_speed_m_s'],**args).set)
  assert np.all(np.isfinite(theta)) and np.all(np.isfinite(base))
  weighted=theta@f;discomfort=np.maximum(theta-cfg['set_threshold_c'],0)@f
  assert np.max(np.abs(discomfort-get(r,'mean_discomfort_c')))<1e-8
  d0=np.maximum(base-cfg['set_threshold_c'],0)
  w=lambda x:float(n@x/n.sum())
  row=dict(plan=name,zone=z,zone_area_m2=cfg['zone_area_m2'],mean_people=float(n.mean()),person_hours=float(n.sum()*cfg['dt_s']/3600),airflow_coverage_fraction=float(1-f[0]),A=int(counts[zi,0]),B=int(counts[zi,1]),C=int(counts[zi,2]),baseline_air_c=w(get(b,'temperature_c')),plan_air_c=w(ta),air_temperature_reduction_c=w(get(b,'temperature_c')-ta),baseline_set_c=w(base),plan_set_c=w(weighted),set_reduction_c=w(base-weighted),discomfort_relief_c=w(d0-discomfort),remaining_discomfort_c=w(discomfort),service_person_c_h=float(n@(d0-discomfort)*cfg['dt_s']/3600))
  out.append(row)
 for key,target in [('service_person_c_h','service_person_c_h'),('person_hours','person_hours')]:
  assert abs(sum(r[key] for r in out if r['plan']==name)-float(results[name][target]))<1e-7
with (ROOT/'zone_comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
lookup={(r['plan'],r['zone']):r for r in out}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(2,1,figsize=(12,7.3),layout='constrained')
fig.suptitle('Where do air cooling and comfort improvement occur?',fontsize=17,fontweight='bold')
for ax,key,title,unit in zip(axs,['air_temperature_reduction_c','set_reduction_c'],['A. Air-temperature reduction','B. Passenger-weighted SET reduction'],['Air-temperature reduction (°C)','SET reduction (°C)']):
 a=np.array([[lookup[p,z][key] for p in plans] for z in zones]);lim=np.ceil(np.max(np.abs(a))*2)/2;norm=TwoSlopeNorm(vmin=-lim,vcenter=0,vmax=lim)
 im=ax.imshow(a,cmap='RdBu',norm=norm,aspect='auto',interpolation='nearest')
 ax.set_title(title,loc='left');ax.set_xticks(range(len(plans)),plans)
 ax.set_yticks(range(3),[f'{z}\n{lookup[plans[0],z]["mean_people"]:.1f} people on average' for z in zones]);ax.tick_params(length=0)
 for zi in range(3):
  for pi in range(len(plans)):
   ax.text(pi,zi,f'{a[zi,pi]:+.2f}',ha='center',va='center',fontsize=13,color='white' if abs(a[zi,pi])>.65*lim else '#15202b')
 fig.colorbar(im,ax=ax,shrink=.88,label=unit)
 ax.set_xticks(np.arange(-.5,len(plans),1),minor=True);ax.set_yticks(np.arange(-.5,3,1),minor=True);ax.grid(which='minor',color='white',lw=2);ax.tick_params(which='minor',length=0)
fig.supxlabel('A: fan; B/C: evaporative devices. Numbers = total units; -R = redistributed installation.\nTwo-hour passenger-time-weighted means vs matched no-device baseline. Blue = reduction; red = increase.\nThree aggregate functional zones only; no interpolation or track-temperature prediction.',fontsize=10)
fig.savefig(PROJECT/'figures/17_zone_thermal_maps.pdf',bbox_inches='tight');fig.savefig(ROOT/'17_zone_thermal_maps.png',dpi=150,bbox_inches='tight');plt.close(fig)
selected=['A36','AB30','AB30-R'];allset=[lookup[p,z]['set_reduction_c'] for p in selected for z in zones];lim=np.ceil(max(abs(v) for v in allset)*2)/2;norm=TwoSlopeNorm(vmin=-lim,vcenter=0,vmax=lim);cmap=plt.get_cmap('RdBu')
fig=plt.figure(figsize=(13,8.6),layout='constrained');gs=fig.add_gridspec(3,2,width_ratios=[2.8,1]);axs=[];baraxs=[]
fig.suptitle('Place equipment where it serves passengers',fontsize=17,fontweight='bold')
service_max=max(lookup[p,z]['service_person_c_h'] for p in selected for z in zones)*1.18
for i,p in enumerate(selected):
 ax=fig.add_subplot(gs[i,0]);bar=fig.add_subplot(gs[i,1]);axs.append(ax);baraxs.append(bar)
 rtotal=results[p];personcov=float(rtotal['person_time_coverage_fraction']);ax.set_title(f'{p}: {float(rtotal["energy_kwh"]):.1f} kWh  |  person-time coverage {personcov:.1%}',loc='left',fontsize=12)
 ax.set_xlim(0,3);ax.set_ylim(0,1.55);ax.axis('off')
 for zi,z in enumerate(zones):
  r=lookup[p,z];v=r['set_reduction_c'];color=cmap(norm(v));ax.add_patch(Rectangle((zi+.025,.42),.95,1.05,facecolor=color,edgecolor='white',lw=1.5))
  counts=' + '.join(str(r[k])+k for k in 'ABC' if r[k])
  label=f'{z} | {r["mean_people"]:.1f} people\nSET reduction {v:+.2f} °C\nDirect coverage {r["airflow_coverage_fraction"]:.1%}\n{counts}'
  ax.text(zi+.5,.96,label,ha='center',va='center',linespacing=1.65,fontsize=10,color='white' if abs(v)>.65*lim else '#15202b')
 ax.add_patch(Rectangle((.025,.025),2.95,.27,facecolor='#eeeeee',edgecolor='#999999',hatch='///',lw=.7))
 ax.text(1.5,.16,'Tracks / non-waiting space: no service credit; temperature not solved',ha='center',va='center',fontsize=9,bbox=dict(facecolor='#eeeeee',edgecolor='none',pad=2))
 vals=[lookup[p,z]['service_person_c_h'] for z in zones];bars=bar.barh(zones,vals,color=['#77a9bd','#296884','#a5c7ce']);bar.invert_yaxis();bar.set_xlim(0,service_max);bar.bar_label(bars,fmt='%.1f',padding=3,fontsize=10);bar.grid(axis='x',alpha=.2);bar.set_axisbelow(True)
 if i==0:bar.set_title('Useful service by zone',fontsize=12)
 if i==2:bar.set_xlabel('Discomfort relief (person·°C·h)')
fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),ax=axs,orientation='horizontal',fraction=.035,pad=.02,label='Passenger-weighted SET reduction (°C); common color scale')
fig.supxlabel('A: fan; B: evaporative device. Numbers in tiles = local counts; plan numbers = total units; -R = redistributed.\nFunctional-zone schematic, not a surveyed floor plan. Equal tiles denote 352 m² zones; track-band size is symbolic.\nGrey hatching marks an excluded domain, not zero cooling. Occupancy and delivery footprints are assumed.',fontsize=10)
fig.savefig(PROJECT/'figures/18_occupancy_service_maps.pdf',bbox_inches='tight');fig.savefig(ROOT/'18_occupancy_service_maps.png',dpi=150,bbox_inches='tight');plt.close(fig)
report=dict(status='Postprocessed existing trajectories; no new thermal simulation or spatial interpolation',plans=plans,checks={'common_time_and_occupancy':True,'valid_set_inputs':True,'reproduces_zone_discomfort':True,'zone_service_sums_to_original_total':True,'person_hours_sum_to_original_total':True},source_hashes={n:hashlib.sha256((INPUT/n).read_bytes()).hexdigest() for n in ['scenario.json','time_series.csv','candidate_results.csv']},max_set_vs_discomfort_difference=max(abs(r['set_reduction_c']-r['discomfort_relief_c']) for r in out))
(ROOT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
