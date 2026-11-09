"""Reproducible publication figures from frozen CP-SET outputs.

Run with numpy, scipy, matplotlib, psychrolib and pythermalcomfort installed.
The spatial reconstruction is a visualization surrogate, not a new PDE/CFD
solution or an input to the reported efficiencies/MILPs. See README.md.
"""
from pathlib import Path
import csv, hashlib, json, math, os, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / 'data'
FIG = ROOT / 'figures'
os.environ.setdefault('MPLCONFIGDIR', str(HERE / '.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME', str(HERE / '.cache'))
os.environ.setdefault('NUMBA_CACHE_DIR', str(HERE / '.numba'))
import numpy as np
from scipy.interpolate import PchipInterpolator, griddata
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, Normalize
from matplotlib.patches import Polygon, Rectangle, ConnectionPatch, FancyBboxPatch
from matplotlib.path import Path as MplPath
from matplotlib.lines import Line2D
from pythermalcomfort.models import set_tmp
import psychrolib
sys.path.insert(0, str(ROOT / 'model'))
from thermal_backend import air_state, direct_evaporative, wet_bulb_c

INK='#182c3d'; MUTED='#566b7c'; GRID='#dce4ea'
COLORS={'A':'#287b9b','B':'#db9834','C':'#8e6aa9','Mixed':'#ca4c52'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
 'axes.labelsize':11,'axes.titlesize':12,'xtick.labelsize':10,'ytick.labelsize':10,
 'axes.edgecolor':GRID,'text.color':INK,'axes.labelcolor':INK,
 'xtick.color':MUTED,'ytick.color':MUTED,'axes.spines.top':False,
 'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,
 'savefig.facecolor':'white','figure.facecolor':'white'})

def read_csv(path):
    return list(csv.DictReader((ROOT/path).open(newline='')))

def number(row,key): return float(row[key])

def write_csv(path,rows):
    with path.open('w',newline='') as f:
        out=csv.DictWriter(f,fieldnames=list(rows[0]));out.writeheader();out.writerows(rows)

def save(fig,stem):
    # Fixed canvas: both formats have the same physical bounds, with no crop drift.
    fig.savefig(FIG/(stem+'.pdf'),dpi=300)
    fig.savefig(FIG/(stem+'.png'),dpi=300)
    plt.close(fig)

def header(fig,title,subtitle):
    fig.text(.055,.975,title,fontsize=17,weight='bold',va='top')
    fig.text(.055,.975-.30/fig.get_figheight(),subtitle,fontsize=10.5,color=MUTED,va='top')

def interpolate_zone(values,x):
    centers=np.array([0,220/6,110,220*5/6,220])
    return PchipInterpolator(centers,[values[0],*values,values[-1]])(x)

def device_positions(counts):
    """Assumed alternating rows; original counts retained exactly in each zone."""
    positions=[]
    for zone,row in enumerate(counts):
        total=sum(row)
        # Interleave types by evenly distributed cumulative slots.
        kinds=['B' if int((i+1)*row[1]/total)>int(i*row[1]/total) else 'A'
               for i in range(total)] if total else []
        assert kinds.count('A')==row[0] and kinds.count('B')==row[1] and row[2]==0
        for i,kind in enumerate(kinds):
            positions.append(dict(zone=zone,device=kind,
                x=(zone+(i+.5)/total)*220/3,y=1.0 if i%2==0 else 3.8))
    return positions

def spatial_figure(station,checks):
    cfg=json.loads((ROOT/'deployment_model/scenario.json').read_text())
    series=read_csv('deployment_model/time_series.csv')
    time=min({float(r['time_min']) for r in series},key=lambda t:abs(t-117.83333333333333))
    xx=np.linspace(0,220,300);yy=np.linspace(0,4.8,100);X,Y=np.meshgrid(xx,yy)
    fields=[]; placement=[]; records=[]
    for plan in ['Baseline','AB30','AB30-R']:
        rows=[next(r for r in series if r['plan']==plan and r['zone']==zone
                   and float(r['time_min'])==time) for zone in cfg['geometry']['zones']]
        bg=[air_state(number(r,'temperature_c'),number(r,'rh')) for r in rows]
        h=np.broadcast_to(interpolate_zone([b.h_j_kg_da for b in bg],xx),X.shape).copy()
        w=np.broadcast_to(interpolate_zone([b.w for b in bg],xx),X.shape).copy()
        tr=np.broadcast_to(interpolate_zone([number(r,'mrt_c') for r in rows],xx),X.shape)
        hb,wb=h.copy(),w.copy()
        u=np.full(X.shape,.2);v=np.zeros(X.shape)
        counts=[[0,0,0]]*3 if plan=='Baseline' else json.loads(station[plan]['counts_by_zone'])
        positions=device_positions(counts)
        kernels=[]; dh=[];dw=[];du=[];dv=[]
        for p in positions:
            typ=p['device'];z=p['zone'];d=cfg['devices'][typ]
            footprint=20 if typ=='A' else 30
            # 2*pi*sigma_x*sigma_y = unit footprint; aspect 4 makes elongated jets.
            sx=np.sqrt(4*footprint/(2*np.pi));sy=sx/4
            k=np.exp(-.5*((X-(p['x']+1.0))/sx)**2-.5*((Y-p['y'])/sy)**2)
            # Reconstruct the same supply state used by the frozen model in each zone.
            outlet=direct_evaporative(bg[z].t_c,bg[z].rh,d['epsilon'],max_drop_c=d['outlet_drop_cap_c'])
            hs=outlet.h_j_kg_da+1000*d['unit_power_kw']/d['recirculation_kg_da_s_per_unit']
            angle=.12 if p['y']<2.4 else -.12
            kernels.append(k)
            dh.append(hs-hb);dw.append(outlet.w-wb)
            du.append(d['air_speed_m_s'][z]*np.cos(angle)-.2)
            dv.append(d['air_speed_m_s'][z]*np.sin(angle))
            placement.append(dict(plan=plan,**p,sigma_x_m=sx,sigma_y_m=sy))
        if kernels:
            K=np.array(kernels)
            weights=K/np.maximum(1,K.sum(axis=0))[None,:,:]
            h+=.5*np.sum(weights*np.array(dh),axis=0)
            w+=.5*np.sum(weights*np.array(dw),axis=0)
            u+=np.sum(weights*np.array(du)[:,None,None],axis=0)
            v+=np.sum(weights*np.array(dv)[:,None,None],axis=0)
            beta=.5*weights.sum(axis=0)
            assert np.max(beta)<=.5+1e-12
        else: beta=np.zeros_like(X)
        t=(h-2501000*w)/(1006+1860*w)
        pv=101325*w/(.621945+w)
        rh=pv/psychrolib.GetSatVapPres(t)
        speed=np.sqrt(u*u+v*v)
        theta=np.array(set_tmp(tdb=t.ravel(),tr=tr.ravel(),v=speed.ravel(),
            rh=100*rh.ravel(),met=1.2,clo=.5,p_atm=101325,position='standing',
            limit_inputs=True,round_output=False).set).reshape(X.shape)
        assert np.isfinite(theta).all() and (rh>=0).all() and (rh<=1).all()
        np.savez_compressed(DATA/('spatial_'+plan+'.npz'),x=xx,y=yy,temperature_c=t,
              set_c=theta,rh=rh,mrt_c=tr,u_m_s=u,v_m_s=v,beta=beta,time_min=time,
              background_enthalpy=hb,background_humidity_ratio=wb)
        fields.append((t,theta,u,v,positions,rows))
        records.append(dict(plan=plan,time_min=time,grid='300 x 100',
              min_t=float(t.min()),max_t=float(t.max()),min_set=float(theta.min()),
              max_set=float(theta.max()),devices=len(positions)))
    write_csv(DATA/'spatial_positions_assumed.csv',placement)
    write_csv(DATA/'spatial_ranges.csv',records)
    fig=plt.figure(figsize=(10.6,7.4))
    header(fig,'Where cooling meets the crowd','Canberra MRT | 220 m occupied strip | high-demand snapshot at t = 117.83 min')
    titles=['(a) Uncooled baseline','(b) Uniform deployment | AB30','(c) Demand-aware redistribution | AB30-R']
    rng=np.random.default_rng(18588)
    crowd=[]
    for z,r in enumerate(fields[0][-1]):
        for x,y in zip(rng.uniform(z*220/3,(z+1)*220/3,round(number(r,'people'))),
                       rng.uniform(.2,4.6,round(number(r,'people')))):
            crowd.append(dict(zone=z,x_m=x,y_m=y))
    write_csv(DATA/'spatial_crowd_positions_assumed.csv',crowd)
    for i,(t,theta,u,v,pos,rows) in enumerate(fields):
        top=.835-i*.225
        ax=fig.add_axes([.065,top-.145,.635,.145])
        at=fig.add_axes([.755,top-.145,.19,.145])
        cs=ax.contourf(X,Y,theta,levels=np.linspace(33,38,51),cmap='RdYlBu_r',extend='both')
        ct=at.contourf(X,Y,t,levels=np.linspace(32,36,51),cmap='RdYlBu_r',extend='both')
        # Rasterize only filled layers to suppress PDF polygon seam artifacts;
        # axes, labels, devices and streamlines remain vector.
        cs.set_rasterized(True);ct.set_rasterized(True)
        for a in [ax,at]:
            a.set_xlim(0,220);a.set_ylim(0,4.8)
            a.set_yticks([0,2.4,4.8] if a==ax else [])
            a.set_xticks([0,73.3,146.7,220]);a.set_xticklabels(['0','73','147','220'] if i==2 else [])
            a.tick_params(length=2,pad=3)
            for boundary in [220/3,440/3]:a.axvline(boundary,color=INK,lw=.75,ls='--',alpha=.4)
        # Uniform visual streamline density; vector components remain physical m/s.
        ax.streamplot(xx,yy,u,v,color=(1,1,1,.58),density=(1.8,.55),
                      linewidth=.7,arrowsize=.65,broken_streamlines=False)
        ax.scatter([p['x_m'] for p in crowd],[p['y_m'] for p in crowd],s=4,
                   c=INK,alpha=.17,lw=0,zorder=3)
        for typ,marker in [('A','o'),('B','s')]:
            loc=[p for p in pos if p['device']==typ]
            if loc:ax.scatter([p['x'] for p in loc],[p['y'] for p in loc],s=19,
                marker=marker,c='white',edgecolors=INK,lw=.65,zorder=4)
        ax.set_ylabel('y (m)')
        fig.text(.065,top+.013,titles[i],weight='bold',fontsize=12)
        at.set_title('Air temperature' if i==0 else '',fontsize=11,pad=8)
        if i==0:
            for z,zone in enumerate(['Access','Crowd core','Edge']):
                ax.text((z+.5)*220/3,2.4,f'{zone}\n{number(rows[z],"people"):.0f} people',
                    ha='center',va='center',fontsize=10.5,color=INK,
                    bbox=dict(boxstyle='round,pad=.25',fc='white',ec='none',alpha=.8))
        else:
            r=station['AB30' if i==1 else 'AB30-R']
            fig.text(.065,top-.183,
                 f'2 h model totals: q = {number(r,"person_time_coverage_fraction"):.1%}    '
                 f'U = {number(r,"service_person_c_h"):.2f}    '
                 f'E = {number(r,"energy_kwh"):.1f} kWh    η = {number(r,"efficiency"):.2f}',
                 fontsize=10.3,color=MUTED)
        if i==2:
            fig.text(.3825,.164,'Distance along occupied strip, x (m)',ha='center',fontsize=10.5)
            fig.text(.85,.164,'x (m)',ha='center',fontsize=10.5)
    c1=fig.add_axes([.13,.113,.48,.017]);cb=fig.colorbar(cs,cax=c1,orientation='horizontal',ticks=np.arange(33,39));cb.set_label('SET (°C) | cooler feeling  →  hotter feeling',fontsize=10,labelpad=2)
    c2=fig.add_axes([.755,.113,.19,.017]);cb=fig.colorbar(ct,cax=c2,orientation='horizontal',ticks=[32,34,36]);cb.set_label('Air temperature (°C)',fontsize=10,labelpad=2)
    fig.text(.065,.014,'Faint dots: illustrative crowd. ○ fan A  □ evaporative B. Transverse scale expanded.\n'
        'Assumed layouts and Gaussian h–w mixing; no CFD claim. U and η remain the original zonal results.',
        fontsize=9.5,color=MUTED,va='bottom')
    save(fig,'34_continuous_thermal_fields')
    checks['spatial']=records

def state_polygons():
    geo=json.loads((DATA/'us-states.json').read_text())
    for feature in geo['features']:
        name=feature['properties']['name']; geom=feature['geometry']
        polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
        for poly in polys:
            yield name,np.array(poly[0])

def climate_figure(venues,bus,checks):
    climate=json.loads((DATA/'climate_samples.json').read_text())
    rows=[]
    for p in climate['points']:
        wb=wet_bulb_c(p['T2M'],p['RH2M']/100,p['PS']*1000)
        rows.append(dict(name=p['name'],latitude=p['latitude'],longitude=p['longitude'],
             mean_t_c=p['T2M'],mean_rh_percent=p['RH2M'],pressure_kpa=p['PS'],
             wet_bulb_at_mean_state_c=wb,depression_c=p['T2M']-wb))
    write_csv(DATA/'climate_wet_bulb.csv',rows)
    assert all(r['depression_c']>=0 for r in rows)
    cmap=LinearSegmentedColormap.from_list('water_to_desert',['#17658c','#67b2c3','#e1ede7','#f5df9b','#df9c35','#b9671d'])
    norm=Normalize(0,18)
    fig=plt.figure(figsize=(10.6,7.8))
    header(fig,'The geography of evaporative opportunity','NASA POWER | July climatological-state wet-bulb depression | 2001–2025')
    ax=fig.add_axes([.055,.39,.89,.51]);ax.set_facecolor('#f3f7fa')
    polygons=list(state_polygons())
    def map_panel(a,extent,hawaii=False):
        xs=np.linspace(extent[0],extent[1],500);ys=np.linspace(extent[2],extent[3],280)
        X,Y=np.meshgrid(xs,ys);points=np.c_[X.ravel(),Y.ravel()]
        subset=[r for r in rows if (r['longitude']<-150)==hawaii]
        coords=np.array([[r['longitude'],r['latitude']] for r in subset]);values=np.array([r['depression_c'] for r in subset])
        zz=griddata(coords,values,points,method='linear')
        missing=~np.isfinite(zz)
        zz[missing]=griddata(coords,values,points[missing],method='nearest')
        land=np.zeros(len(points),dtype=bool)
        for name,p in polygons:
            if (name=='Hawaii')!=hawaii or name=='Alaska':continue
            land|=MplPath(p).contains_points(points)
        z=np.ma.array(zz.reshape(X.shape),mask=~land.reshape(X.shape))
        a.pcolormesh(X,Y,z,cmap=cmap,norm=norm,shading='auto',rasterized=True)
        for name,p in polygons:
            if (name=='Hawaii')!=hawaii or name=='Alaska':continue
            a.add_patch(Polygon(p,fill=False,ec='white',lw=.55,zorder=3))
        a.scatter(coords[:,0],coords[:,1],s=4,c=INK,alpha=.38,zorder=4)
        a.set(xlim=extent[:2],ylim=extent[2:],xticks=[],yticks=[])
        a.set_aspect(1/np.cos(np.deg2rad(21 if hawaii else 38)))
        for sp in a.spines.values():sp.set_visible(False)
    map_panel(ax,[-125,-66,24,50])
    hi=fig.add_axes([.075,.407,.19,.135]);hi.set_facecolor('#e8f1f6');map_panel(hi,[-160.4,-154.6,18.7,22.5],True)
    hi.set_title('Hawaii',loc='left',pad=0,fontsize=10,weight='bold')
    cbax=fig.add_axes([.905,.46,.014,.40]);cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cbax,ticks=[0,3,6,9,12,15,18]);cb.set_label('July mean-state ΔTwb (°C)',fontsize=10,labelpad=5)
    fig.text(.055,.352,'VENUE DESIGN SCENARIOS  |  separate from the climate background',weight='bold',fontsize=10.5,zorder=10,bbox=dict(fc='white',ec='none',pad=1))
    # Cards: common efficiency scale, with exact source model values.
    configs=[('Fremont','2  Las Vegas / Fremont',-115.142,36.170,'38°C • RH 20% | dry desert',.055),
             ('Honolulu','3  Honolulu Zoo',-157.819,21.272,'31°C • RH 65% | coastal',.36),
             ('NYC','1  New York City',-73.986,40.758,'34°C • RH 30% / 70%',.665)]
    for key,title,lon,lat,weather,left in configs:
        card=fig.add_axes([left,.065,.28,.26]);card.set_axis_off()
        card.add_patch(FancyBboxPatch((0,0),1,1,transform=card.transAxes,boxstyle='round,pad=.012',
                      fc='#f5f8fa',ec=GRID,lw=.8,clip_on=False))
        card.text(.045,.91,title,fontsize=11.5,weight='bold')
        card.text(.045,.795,weather,fontsize=10)
        marker_ax=hi if key=='Honolulu' else ax
        marker_ax.scatter([lon],[lat],s=80,c=INK,ec='white',lw=1.4,zorder=6)
        marker_ax.annotate(title.split()[0],(lon,lat),color='white',ha='center',va='center',fontsize=8,weight='bold',zorder=7)
        fig.add_artist(ConnectionPatch(xyA=(lon,lat),coordsA=marker_ax.transData,xyB=(.5,1.03),
                coordsB=card.transAxes,color=MUTED,lw=.9,alpha=.7,zorder=1))
        if key!='NYC':
            venue=venues[key];plans=[venue['pure_largest_fit'][k] for k in 'ABC']+[venue['policy']['selected']]
            v=venue['venue'];dep=v['t_c']-venue['thermal']['wet_bulb_c']
            card.text(.045,.69,f'Scenario ΔTwb = {dep:.2f}°C',fontsize=10,color=MUTED)
            bax=card.inset_axes([.29,.19,.59,.39]);ys=np.arange(4)
            vals=[p['efficiency'] for p in plans]
            bax.barh(ys,vals,color=[COLORS[k] for k in ['A','B','C','Mixed']],height=.62)
            bax.set(xlim=(0,100),ylim=(3.65,-.65),yticks=ys,yticklabels=[p['plan'] for p in plans],xticks=[])
            bax.tick_params(axis='y',length=0,labelsize=10)
            for i,val in enumerate(vals):bax.text(val+2,i,f'{val:.2f}',va='center',fontsize=10)
            for sp in bax.spines.values():sp.set_visible(False)
            card.text(.045,.055,f'Policy: {plans[-1]["plan"]} | q = {plans[-1]["coverage"]:.1%}',fontsize=10,weight='bold')
        else:
            selected=[r for r in bus if r['occupancy']=='Uniform']
            card.text(.045,.69,'Task 2a | 6.50 m² | 12 people',fontsize=10,color=MUTED)
            bax=card.inset_axes([.29,.19,.59,.39]);ys=np.arange(3)
            paired=[]
            for offset,rh,alpha in [(-.15,.3,1),(.15,.7,.45)]:
                vals=[number(next(r for r in selected if r['device']==k and number(r,'climate_rh')==rh),'efficiency') for k in 'ABC']
                paired.append(vals)
                bax.barh(ys+offset,vals,height=.27,color=[COLORS[k] for k in 'ABC'],alpha=alpha)
            for i,(dry,humid) in enumerate(zip(*paired)):
                bax.text(63,i,f'{dry:.1f} / {humid:.1f}',ha='center',va='center',fontsize=9.5,
                         bbox=dict(fc='white',ec='none',pad=.5,alpha=.88))
            bax.set(xlim=(0,100),ylim=(2.65,-.65),yticks=ys,yticklabels=list('ABC'),xticks=[])
            bax.tick_params(axis='y',length=0,labelsize=10)
            for sp in bax.spines.values():sp.set_visible(False)
            card.text(.045,.055,'Efficiency leader: A at both RH levels',fontsize=9.7,weight='bold')
    fig.text(.055,.014,'η bars share a 0–100 scale (person·°C·h/kWh); NYC: solid 30% RH, pale 70% RH.\n'
        '77 geographic samples; interpolation is regional context, not design weather or a station-observed field.',fontsize=9.3,color=MUTED)
    save(fig,'35_us_climate_potential')
    checks['climate']={'samples':len(rows),'period':climate['points'][0]['period'],
                        'min_depression':min(r['depression_c'] for r in rows),'max_depression':max(r['depression_c'] for r in rows)}

def service_radar_figure(station,venues,checks):
    fig=plt.figure(figsize=(10.6,10.2))
    header(fig,'From electrical input to useful service','Separate energy and discomfort accounts; compare operational trade-offs without mixing units')
    fig.text(.055,.878,'(a) Canberra | same passengers, different delivery',weight='bold',fontsize=12)
    ae=fig.add_axes([.12,.63,.21,.205]);ar=fig.add_axes([.45,.63,.48,.205])
    plans=['A36','B24','AB30','AB30-R'];ys=np.arange(4)
    vals=[station[p] for p in plans];es=[number(r,'energy_kwh') for r in vals]
    us=np.array([number(r,'service_person_c_h') for r in vals]);rs=np.array([number(r,'remaining_person_c_h') for r in vals])
    total=number(vals[0],'baseline_remaining_person_c_h')
    assert np.max(np.abs(us+rs-total))<1e-8
    ae.barh(ys,es,color=[COLORS['A'],COLORS['B'],'#97a8b3',COLORS['Mixed']],height=.56)
    ae.set(xlim=(0,70),ylim=(3.65,-.65),yticks=ys,yticklabels=plans,xticks=[0,30,60],xlabel='Electricity, E (kWh)')
    ae.tick_params(axis='y',length=0)
    for y,e in zip(ys,es):ae.text(e+1,y,f'{e:.1f}',va='center',fontsize=11.5)
    ar.barh(ys,us,color='#2c9b9b',height=.56,label='Removed excess U')
    ar.barh(ys,rs,left=us,color='#efb7a6',height=.56,label='Remaining excess R')
    ar.set(xlim=(0,5100),ylim=(3.65,-.65),yticks=[],xticks=[0,1000,2000,3000,4000],xlabel='SET-excess account (person·°C·h)')
    ar.axvline(total,color=INK,lw=1,ls=':')
    ar.text(total,.99,f'R₀ = {total:,.2f}',transform=ar.get_xaxis_transform(),ha='right',fontsize=10,va='bottom')
    for y,(u,r,row) in enumerate(zip(us,rs,vals)):
        ar.text(u/2,y,f'{u:.0f}',ha='center',va='center',fontsize=11,color='white',weight='bold')
        ar.text(u+r/2,y,f'R = {r:,.0f}',ha='center',va='center',fontsize=11.5)
        ae.text(1.12,y,f'η {number(row,"efficiency"):.2f}',transform=ae.get_yaxis_transform(),fontsize=10.5,va='center')
    ar.legend(ncol=2,loc='lower left',bbox_to_anchor=(.03,1.03),frameon=False,fontsize=10.5,handlelength=1.2)
    fig.text(.055,.553,'At 37.8 kWh, redistribution delivers '
             f'+{100*(us[3]/us[2]-1):.1f}% useful service.  U + R = R₀.',fontsize=12,weight='bold')
    fig.text(.055,.511,'(b) Venue trade-offs | larger radius is better on each stated scale',weight='bold',fontsize=12)
    angles=np.linspace(0,2*np.pi,5,endpoint=False);closed=np.r_[angles,angles[0]]
    export=[]
    for i,(key,left) in enumerate([('Fremont',.11),('Honolulu',.59)]):
        ax=fig.add_axes([left,.145,.29,.285],projection='polar')
        ax.set_theta_offset(np.pi/2);ax.set_theta_direction(-1)
        source=venues[key];rows=[source['pure_largest_fit'][k] for k in 'ABC']+[source['policy']['selected']]
        maxrel=max(r['mean_benefit_c'] for r in rows);maxeta=max(r['efficiency'] for r in rows);mincost=min(r['annual_cost_usd'] for r in rows)
        for j,(r,kind) in enumerate(zip(rows,['A','B','C','Mixed'])):
            raw=[r['coverage'],r['mean_benefit_c'],r['efficiency'],1-r['floor_loss'],r['annual_cost_usd']]
            normed=[raw[0],raw[1]/maxrel,raw[2]/maxeta,raw[3],mincost/raw[4]]
            ax.plot(closed,np.r_[normed,normed[0]],color=COLORS[kind],lw=2.5 if kind=='Mixed' else 1.4,
                    ls='-' if kind=='Mixed' else ['--',':','-.'][j],marker='o',markersize=3,label=r['plan'])
            if kind=='Mixed':ax.fill(closed,np.r_[normed,normed[0]],color=COLORS[kind],alpha=.12)
            export.append(dict(venue=key,plan=r['plan'],q=raw[0],mean_relief_c=raw[1],eta=raw[2],
                 spatial_access=raw[3],annual_cost_usd=raw[4],normalized_q=normed[0],normalized_relief=normed[1],
                 normalized_eta=normed[2],normalized_access=normed[3],normalized_economy=normed[4],
                 relief_denominator=maxrel,eta_denominator=maxeta,economy_numerator=mincost))
        ax.set_xticks(angles);ax.set_xticklabels(['Coverage\nq','SET relief','Efficiency\nη','Spatial access\n1 − X','Cost\neconomy'],fontsize=11)
        ax.tick_params(pad=5)
        ax.set_ylim(0,1);ax.set_yticks([.25,.5,.75,1]);ax.set_yticklabels(['','0.5','','1.0'],fontsize=7,color=MUTED)
        ax.grid(color=GRID);ax.spines['polar'].set_color(GRID);ax.set_rlabel_position(0)
        fig.text(left-.04,.463,key,ha='left',weight='bold',fontsize=12)
        ax.legend(loc='lower center',bbox_to_anchor=(.5,-.28),ncol=2,frameon=False,fontsize=10.5,handlelength=2,columnspacing=1.2)
    fig.text(.055,.017,'q and 1 − X use their absolute 0–1 scale. Relief and η: fraction of the maximum shown within each venue.\n'
             'Cost economy: minimum shown annual cost / plan cost. This diagnostic adds no optimization objective.',fontsize=10.5,color=MUTED)
    save(fig,'36_energy_service_radar')
    write_csv(DATA/'radar_values.csv',export)
    checks['service_identity_max_abs']=float(np.max(np.abs(us+rs-total)))
    checks['radar_rows']=len(export)

def bus_composite(bus):
    fig=plt.figure(figsize=(10.6,3.8));header(fig,'Humidity and delivery jointly determine efficiency','Bus shelter | same 12 people and nominal device power | η in person·°C·h/kWh')
    ax=fig.add_axes([.075,.18,.40,.62]);ad=fig.add_axes([.59,.18,.35,.62])
    for i,kind in enumerate('ABC'):
        v=[number(next(r for r in bus if r['occupancy']=='Uniform' and r['device']==kind and number(r,'climate_rh')==rh),'efficiency') for rh in [.3,.7]]
        b=ax.bar(np.arange(2)+(i-1)*.24,v,.22,color=COLORS[kind],label=kind)
        ax.bar_label(b,fmt='%.1f',fontsize=9,padding=3)
    ax.set(xticks=[0,1],xticklabels=['RH 30%','RH 70%'],ylim=(0,116),ylabel='Service efficiency η',title='(a) Nominal comparison')
    ax.legend(ncol=3,frameon=False,fontsize=9,loc='upper right',handlelength=1)
    rows=read_csv('model/delivery_decision_map.csv');rhv=sorted({number(r,'rh') for r in rows});qs=sorted({number(r,'fan_delivery') for r in rows})
    zz=np.array([[{'A':0,'B':1,'C':2}[next(r['winner'] for r in rows if number(r,'rh')==rh and number(r,'fan_delivery')==q)] for q in qs] for rh in rhv])
    ad.pcolormesh(qs,np.array(rhv)*100,zz,shading='nearest',cmap=ListedColormap([COLORS['A'],COLORS['B'],COLORS['C']]),vmin=0,vmax=2,rasterized=True)
    ad.set(xlim=(0,1),ylim=(20,80),xlabel='Delivered-speed factor q',ylabel='Relative humidity (%)',title='(b) Efficiency winner')
    ad.text(.57,51,'A',ha='center',fontsize=25,color='white',weight='bold');ad.text(.07,51,'B',ha='center',fontsize=20,color=INK,weight='bold')
    fig.text(.59,.02,'C wins no cell of the sampled grid.',fontsize=10,color=MUTED)
    save(fig,'37_bus_efficiency_delivery')

def station_composite(station):
    # Replace large rank list + separate sensitivity triptych by compact analytical panels.
    fig=plt.figure(figsize=(10.6,4.0));header(fig,'Station efficiency: counts and local delivery','All 24 candidate values retained in the source CSV; six equal-coverage benchmarks shown in sensitivity')
    ax=fig.add_axes([.075,.19,.36,.61]);ad=fig.add_axes([.55,.19,.39,.61])
    for kind in 'ABC':
        rows=sorted([r for r in station.values() if r['family']==kind],key=lambda r:number(r,'total_devices'))
        ax.plot([number(r,'total_devices') for r in rows],[number(r,'efficiency') for r in rows],'-o',color=COLORS[kind],label=kind,ms=4)
    for name in ['A3','A36']:
        r=station[name];x=number(r,'total_devices');y=number(r,'efficiency');ax.annotate(f'{name}: {y:.2f}',(x,y),xytext=(3,-19),textcoords='offset points',fontsize=9,weight='bold')
    ax.set(title='(a) Pure-device counts',xlabel='Number of devices',ylabel='Service efficiency η',ylim=(0,42));ax.legend(ncol=3,frameon=False,fontsize=9,loc='center right')
    rows=read_csv('deployment_model/delivery_sensitivity.csv')
    for name,color in [('A36',COLORS['A']),('B24',COLORS['B']),('C18',COLORS['C']),('AB30','#318c73'),('AC27','#aa617b'),('ABC24','#897260')]:
        xx=[0,.25,.5,.75,1];vv=[]
        for chi in [0,.5,1]:
            vv.append([number(next(r for r in rows if r['plan']==name and number(r,'delivery_beta')==b and number(r,'local_heat_fraction_alpha')==chi),'efficiency') for b in xx])
        vv=np.array(vv);ad.fill_between(xx,vv.min(axis=0),vv.max(axis=0),color=color,alpha=.13)
        ad.plot(xx,vv[-1],'-o',ms=3,lw=1.4,label=name,color=color)
    ad.set(title='(b) Mixing and heat allocation',xlabel='Supply fraction β',ylim=(0,42),xticks=[0,.25,.5,.75,1]);ad.set_xticklabels(['0','0.25','0.5','0.75','1'])
    ad.legend(ncol=2,frameon=False,fontsize=9,loc='center right',handlelength=1.5)
    for a in [ax,ad]:a.grid(alpha=.3);a.set_axisbelow(True)
    fig.text(.075,.025,'Lines: χ = 1. Bands: range over χ = 0, 0.5, 1.  Nominal β = 0.5.  η unit: person·°C·h/kWh.',fontsize=10,color=MUTED)
    save(fig,'38_station_efficiency_sensitivity')

def bus_local_fields():
    rows=read_csv('model/local_conditions.csv')
    fig=plt.figure(figsize=(10.6,5.0))
    header(fig,'Local air and perceived temperature','Bus shelter | identical thermal color scales across dry and humid cases')
    for i,rh in enumerate([.3,.7]):
        for j,(key,title,cmap,lo,hi) in enumerate([
            ('t_c','Air temperature (°C)','RdYlBu_r',26,38),
            ('rh','Relative humidity (%)','Blues',20,90),
            ('set_c','SET (°C)','RdYlBu_r',26,38)]):
            ax=fig.add_axes([.12+j*.29,.53-i*.37,.235,.28])
            vals=np.array([[number(next(r for r in rows if r['occupancy']=='Uniform' and
                number(r,'climate_rh')==rh and r['device']==k and r['zone']==z),key)
                for z in ['Near','Middle','Edge']] for k in 'ABC'])
            if key=='rh':vals*=100
            im=ax.imshow(vals,cmap=cmap,vmin=lo,vmax=hi,aspect='auto',interpolation='nearest')
            for y in range(3):
                for x in range(3):
                    c=plt.get_cmap(cmap)((vals[y,x]-lo)/(hi-lo))
                    lum=.2126*c[0]+.7152*c[1]+.0722*c[2]
                    ax.text(x,y,f'{vals[y,x]:.1f}',ha='center',va='center',fontsize=11,
                            color=INK if lum>.6 else 'white')
            ax.set(xticks=[0,1,2],xticklabels=['Near','Middle','Edge'],yticks=[0,1,2],yticklabels=list('ABC'))
            ax.tick_params(length=0,labelsize=10)
            if i==0:ax.set_title(title,pad=7,fontsize=12)
            if j==0:ax.set_ylabel(('Dry' if i==0 else 'Humid')+f' | RH {rh:.0%}',fontsize=11,labelpad=12)
            cbax=fig.add_axes([.363+j*.29,.53-i*.37,.009,.28])
            fig.colorbar(im,cax=cbax,ticks=[26,30,34,38] if key!='rh' else [20,50,90]).ax.tick_params(labelsize=9,length=2)
    fig.text(.12,.025,'A: fan; B/C: evaporative devices. Values are the original local-state outputs, rounded to one decimal.',fontsize=10,color=MUTED)
    save(fig,'39_bus_local_fields')

def main():
    manifest=json.loads((HERE/'frozen_manifest.json').read_text())
    check_hash=lambda:all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest.items())
    assert check_hash(),'Frozen model files changed before drawing'
    station={r['plan']:r for r in read_csv('deployment_model/candidate_results.csv')}
    venues=json.loads((ROOT/'venue_model/results.json').read_text());bus=read_csv('model/scenario_results.csv')
    checks={'source_files_unchanged_before':True}
    spatial_figure(station,checks);print('Spatial figure complete',flush=True)
    climate_figure(venues,bus,checks);print('Climate figure complete',flush=True)
    service_radar_figure(station,venues,checks);print('Service/radar figure complete',flush=True)
    bus_composite(bus);station_composite(station);bus_local_fields()
    assert check_hash(),'Frozen model files changed during drawing'
    checks['source_files_unchanged_after']=True;checks['frozen_file_count']=len(manifest)
    (HERE/'verification.json').write_text(json.dumps(checks,indent=2))
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()
