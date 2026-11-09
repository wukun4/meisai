"""Full CP-SET workflow as a standalone, replaceable vector PDF."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/cp-set-framework-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
ROOT=Path(__file__).resolve().parent.parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'pdf.fonttype':42})
fig,ax=plt.subplots(figsize=(10.1,3.65));fig.subplots_adjust(left=.01,right=.99,top=.98,bottom=.02)
ax.set(xlim=(0,10),ylim=(0,3.5));ax.axis('off')
def box(x,y,w,h,title,body,fc='#edf4f7',ec='#32647a'):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.025,rounding_size=.08',lw=1.2,edgecolor=ec,facecolor=fc))
 ax.text(x+w/2,y+h-.16,title,ha='center',va='top',fontsize=12.5,weight='bold',color=ec)
 ax.text(x+w/2,y+.27,body,ha='center',va='center',fontsize=11.5,color='#233944',linespacing=1.25)
def arrow(x1,y1,x2,y2):
 ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=14,lw=1.3,color='#526f7a'))
box(.05,2.25,2.15,1.12,'1  SERVICE','Freezer: useful storage\nPublic space: useful relief')
box(2.55,2.25,2.15,1.12,'2  PHYSICS','Psychrometric balances\nLocal mixing: β and χ')
box(5.05,2.25,2.15,1.12,'3  RESPONSE','Local T, RH, speed, MRT\nSET → person-time relief U')
box(7.55,2.25,2.4,1.12,'4  EFFICIENCY','All-device energy E\nη = U / E  |  Tasks 1–3')
for x in (2.2,4.7,7.2):arrow(x,2.8,x+.35,2.8)
box(.05,.08,4.65,1.27,'CONTROLLED MODEL EXTENSION','Bus: fixed background → Rail: dynamic background\nTransfer: Phoenix terrace + Singapore dining street',fc='#edf5ee',ec='#39785c')
box(5.05,.08,4.9,1.27,'5  EFFECTIVENESS & ACTION  |  Tasks 4–5','Performance • visitor experience • energy • cost\nTradeoff analysis → operating plan → memo + public blog',fc='#fff4e5',ec='#956521')
arrow(3.62,2.25,3.62,1.35)
arrow(8.74,2.25,8.74,1.35)
arrow(4.7,.72,5.05,.72)
fig.savefig(ROOT/'figures/29_cp_set_framework.pdf',bbox_inches='tight',facecolor='white')
plt.close(fig)
