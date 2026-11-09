"""Regenerate Figure 9 from frozen CSV results; no solver is run."""
from pathlib import Path
import ast,csv,os
P=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(P/'figure_sources'/'.mplconfig'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

tree=ast.parse((P/'model/extreme_heat_test.py').read_text())
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='make_figure')
code=compile(ast.Module(body=[function],type_ignores=[]),'<frozen-results-figure>','exec')
ns={'np':np,'plt':plt,'PROJECT':P,'COL':{'A':'#2379A5','B':'#D18C32','C':'#76559A'}}
exec(code,ns)
with (P/'model/extreme_heat_valid_results.csv').open() as f:
 rows=list(csv.DictReader(f))
for row in rows:
 for key,value in list(row.items()):
  if value in ('True','False'):row[key]=value=='True'
  else:
   try:row[key]=float(value)
   except ValueError:pass
print(ns['make_figure'](rows))
