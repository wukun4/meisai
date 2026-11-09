"""Export the Task 3 numerical LaTeX fragments from the computed result file."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'venue_model/results.json').read_text())
f,h=r['Fremont'],r['Honolulu']
values={
 'FMaxEta':f['efficiency_optimum']['upper_bound'],
 'HMaxEta':h['efficiency_optimum']['upper_bound'],
 'FTwb':f['thermal']['wet_bulb_c'],
 'HTwb':h['thermal']['wet_bulb_c'],
 'FCDrop':f['venue']['t_c']-f['thermal']['devices']['C']['outlet_t_c'],
 'HCDrop':h['venue']['t_c']-h['thermal']['devices']['C']['outlet_t_c'],
 'HWithFEta':h['person_hours']/4/sum(h['venue']['areas_m2'])*20*f['thermal']['devices']['A']['benefit_c']/.25,
}
(ROOT/'sections/task3_values.tex').write_text('% Generated from venue_model/results.json; do not hand-edit.\n'+''.join(rf'\newcommand{{\{k}}}{{{v:.2f}}}'+'\n' for k,v in values.items()))
rows=[]
for venue,result in r.items():
 for k in 'ABC':
  v=result['pure_largest_fit'][k]
  rows.append(f"{venue if k=='A' else ''} & {v['plan']} & {100*v['coverage']:.2f} & {v['service_person_c_h']:.2f} & {v['energy_kwh']:.1f} & {v['efficiency']:.2f}"+r'\\'+'\n')
tex=r'''\begin{table}[!ht]
\centering\small
\caption{Largest-fitting pure installations. Coverage $q$ is visitor-time weighted; $U$ has units person$\cdot{}^\circ$C$\cdot$h and $\eta=U/E$.}
\label{tab:venue-results}
\begin{tabular}{@{}llrrrr@{}}
\toprule
Venue & Plan & $q$ (\%) & $U$ & $E$ (kWh) & $\eta$\\
\midrule
'''+''.join(rows)+r'''\bottomrule
\end{tabular}
\end{table}
'''
(ROOT/'sections/task3_results_table.tex').write_text(tex)
print(json.dumps(values,indent=2))
