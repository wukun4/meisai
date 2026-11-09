"""Four independent scientific PDFs from frozen Task 3/4 outputs."""
import json, os
os.environ.setdefault('MPLCONFIGDIR','/tmp/himcm-venue-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/himcm-venue-cache')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from run_venues import ROOT,PROJECT,TYPES,DEV,VENUES,read_csv

COLORS={'A':'#246E9E','B':'#C58A2B','C':'#866097','Mixed':'#487F69',
        'Fremont':'#B27132','Honolulu':'#246E9E'}

def save(fig,name):
    fig.savefig(PROJECT/'figures'/name,facecolor='white');plt.close(fig)

def make_figures(results):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,
        'axes.spines.right':False,'pdf.fonttype':42,'axes.labelsize':12,'axes.titlesize':13,
        'xtick.labelsize':11,'ytick.labelsize':11,'legend.fontsize':11})
    comparison(results);policy(results);scaling();layouts()

def comparison(results):
    fig,axs=plt.subplots(1,2,figsize=(10.4,4.7))
    fig.subplots_adjust(left=.09,right=.98,top=.86,bottom=.27,wspace=.32)
    pos=np.arange(2);width=.23
    for j,k in enumerate(TYPES):
        rows=[r['pure_largest_fit'][k] for r in results.values()]
        for ax,field in zip(axs,['efficiency','mean_benefit_c']):
            bars=ax.bar(pos+(j-1)*width,[r[field] for r in rows],width,color=COLORS[k],label=k)
            for b,r in zip(bars,rows):
                ax.text(b.get_x()+b.get_width()/2,b.get_height()+.025*max(x[field] for x in rows),
                        f'{r[field]:.2f}',ha='center',va='bottom',fontsize=11)
    for ax in axs:
        ax.set_xticks(pos,['Fremont','Honolulu']);ax.set_ylim(0,ax.get_ylim()[1]*1.18)
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    axs[0].set(ylabel='Service efficiency\n(person·°C·h/kWh)',title='(a) Pure strategies: efficiency')
    axs[1].set(ylabel='Mean SET-excess relief (°C)',title='(b) Service per person-hour')
    axs[0].legend(ncol=3,frameon=False,loc='upper left')
    captions=[]
    for key,r in results.items():
        captions.append(key+': '+', '.join(f'{r["pure_largest_fit"][k]["plan"]}  q={100*r["pure_largest_fit"][k]["coverage"]:.2f}%' for k in TYPES))
    fig.text(.5,.145,'\n'.join(captions),ha='center',va='center',fontsize=11)
    fig.text(.5,.045,'Largest-fit footprints have different coverage. Panel (b) explains the efficiency numerator.',ha='center',fontsize=11)
    save(fig,'27_venue_comparison.pdf')

def policy(results):
    fig,axs=plt.subplots(1,2,figsize=(10.4,4.9))
    fig.subplots_adjust(left=.09,right=.98,top=.88,bottom=.30,wspace=.40)
    pos=np.arange(2);totals=[r['policy']['selected']['annual_cost_usd'] for r in results.values()]
    bottom=np.zeros(2)
    for comp,color in zip(['ownership','maintenance','electricity','water'],['#456A82','#91ABB9','#D5A257','#5CA493']):
        val=np.array([r['policy']['selected']['components'][comp]/total for r,total in zip(results.values(),totals)])
        axs[0].bar(pos,100*val,bottom=bottom,width=.55,label=comp.title(),color=color);bottom+=100*val
    for i,r in enumerate(results.values()):
        rr=r['policy']['selected'];axs[0].text(i,104,f'${rr["annual_cost_usd"]:,.0f}/year\n{rr["plan"]}',ha='center',va='bottom',fontsize=11)
    axs[0].set(xticks=pos,xticklabels=list(results),ylabel='Share of annual cost (%)',ylim=(0,129),title='(a) Minimum-cost policy plans')
    axs[0].legend(frameon=False,ncol=2,loc='upper center',bbox_to_anchor=(.5,-.12),fontsize=11)
    curves=read_csv('policy_curves.csv')
    for key,r in results.items():
        data=sorted([x for x in curves if x['venue']==key and x['status']=='0'],key=lambda x:float(x['required_relief_c']))
        axs[1].plot([float(x['required_relief_c']) for x in data],[float(x['annual_cost_usd']) for x in data],
                    marker='.',ms=4,lw=1.4,color=COLORS[key],label=key)
        axs[1].scatter([1.5],[r['policy']['selected']['annual_cost_usd']],s=100,marker='*',color=COLORS[key],zorder=5)
    axs[1].set(xlabel='Required mean SET-excess relief (°C)',ylabel='Minimum annual cost (USD/year)',yscale='log',title='(b) Sampled policy requirements')
    axs[1].legend(frameon=False);axs[1].grid(alpha=.18,which='both')
    fig.text(.5,.055,'Coverage ≥80%; floor clearance ≤3.5%; annual energy ≤30 kWh/m². Stars: 1.5°C requirement.',ha='center',fontsize=11)
    save(fig,'28_effectiveness.pdf')

def scaling():
    fig,axs=plt.subplots(1,3,figsize=(10.5,4.6))
    fig.subplots_adjust(left=.08,right=.98,top=.85,bottom=.28,wspace=.48)
    data=read_csv('scale_checks.csv')
    for case,color,marker in [('Fixed A3',COLORS['A'],'o'),('Replicated devices',COLORS['Mixed'],'s')]:
        rows=[r for r in data if r['case']==case]
        for ax,field in zip(axs[:2],['coverage','efficiency']):
            ax.plot([float(r['area_multiplier']) for r in rows],
                    [float(r[field])*(100 if field=='coverage' else 1) for r in rows],color=color,
                    marker=marker,linestyle='-' if case=='Fixed A3' else '--',label=case,ms=6,
                    mfc='none' if case=='Fixed A3' else color)
    axs[0].set(title='(a) Coverage',ylabel='Person-time coverage (%)',xlabel='Area / demand multiplier',xticks=[1,2,4,8],ylim=(0,110))
    axs[1].set(title='(b) Efficiency',ylabel='Service efficiency',xlabel='Area / demand multiplier',xticks=[1,2,4,8],ylim=(0,float(data[0]['efficiency'])*1.2))
    clipping=read_csv('boundary_clipping.csv')
    for k in TYPES:
        rows=[r for r in clipping if r['device']==k]
        axs[2].plot([float(r['available_area_m2']) for r in rows],[float(r['efficiency']) for r in rows],label=k,color=COLORS[k])
        at=next(r for r in rows if float(r['available_area_m2'])==DEV[k]['footprint_m2'])
        axs[2].scatter([DEV[k]['footprint_m2']],[float(at['efficiency'])],s=30,color=COLORS[k])
    axs[2].set(title='(c) Boundary clipping',xlabel='Available service area (m²)',ylabel='Service efficiency')
    axs[2].legend(frameon=False,ncol=3,loc='lower right',columnspacing=.7)
    for ax in axs:ax.grid(alpha=.15)
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,ncol=2,loc='upper center',bbox_to_anchor=(.5,.20))
    fig.text(.5,.08,'Honolulu climate and fixed density. Efficiency unit: person·°C·h/kWh.',ha='center',fontsize=11)
    fig.text(.5,.025,'Clipping removes far, then middle strips; full power is charged. Markers: complete device footprint.',ha='center',fontsize=11)
    save(fig,'30_scale_transfer.pdf')

def layouts():
    fig=plt.figure(figsize=(10.4,6.1));gs=fig.add_gridspec(2,2,height_ratios=[1,1.2],hspace=.68,wspace=.27)
    fig.subplots_adjust(left=.08,right=.98,top=.91,bottom=.13)
    axf=fig.add_subplot(gs[0,0]);axh=fig.add_subplot(gs[0,1]);axt=fig.add_subplot(gs[1,:])
    left=0
    for z,(a,c) in enumerate(zip(VENUES['Fremont']['areas_m2'],['#CCE0EB','#7FA9C0','#D9E6EC'])):
        w=a/20.;axf.add_patch(Rectangle((left,0),w,20,fc=c,ec='white',lw=2))
        axf.text(left+w/2,10,f'Zone {z+1}\n{a:,.0f} m²',ha='center',va='center',fontsize=12);left+=w
    axf.set(xlim=(0,419.1),ylim=(-4,24));axf.axis('off');axf.set_title('(a) Fremont conceptual corridor',pad=9)
    axf.text(.5,-.12,'419.1 m × assumed 20 m effective width',transform=axf.transAxes,ha='center',fontsize=11)
    axh.add_patch(Rectangle((0,0),10,6,fc='#DCEAE4',ec='#487F69',lw=1.5))
    axh.plot([2.7,7.3],[6,6],color='#415C66',lw=7,solid_capstyle='butt')
    axh.text(5,6.45,'Ticket windows',ha='center',fontsize=11)
    axh.text(5,3.3,'One customer demand zone\n60 m²',ha='center',va='center',fontsize=12)
    axh.annotate('Open approach',xy=(5,.2),xytext=(5,-1.4),ha='center',fontsize=11,arrowprops=dict(arrowstyle='->',color='#487F69',lw=1.5))
    axh.set(xlim=(-1,11),ylim=(-1.8,7.1));axh.axis('off');axh.set_title('(b) Honolulu conceptual queue',pad=9)
    axh.text(.5,-.12,'Assumed customer area: 10 m × 6 m',transform=axh.transAxes,ha='center',fontsize=11)
    for key,v in VENUES.items():
        total=np.asarray(v['people_by_hour']).sum(axis=1);normalized=total/total.mean()
        axt.stairs(normalized,np.arange(5),label=key,color=COLORS[key],lw=2.2)
        for i,n in enumerate(total):axt.text(i+.5,normalized[i]+(.10 if key=='Fremont' else -.16),f'{n:g}',ha='center',color=COLORS[key],fontsize=11)
    axt.set(xlim=(0,4),ylim=(.25,1.85),xticks=np.arange(5),xlabel='Time from scenario start (h)',ylabel='Population / venue mean',title='(c) Prescribed hourly populations (labels give people)')
    axt.legend(frameon=False,ncol=2,loc='upper left');axt.grid(alpha=.15)
    fig.text(.5,.025,'Conceptual domains, not to scale; window geometry, zone boundaries and populations are assumptions.',ha='center',fontsize=11)
    save(fig,'31_venue_layouts.pdf')

if __name__=='__main__':make_figures(json.loads((ROOT/'results.json').read_text()))
