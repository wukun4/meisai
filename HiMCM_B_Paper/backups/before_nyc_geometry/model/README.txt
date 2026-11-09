Rebuild the six bus-stop figure PDFs

Run Python 3.12 with requirements.txt installed:
  python model/simulate.py

The script reads model/scenario.json, writes CSV and JSON calculation results to
model/, and writes six independent PDF files to figures/ one directory above.
They are directly exported vector PDFs, with embedded fonts. No PNG is wrapped
in a PDF. Replacing a PDF with the same filename updates the paper on its next
LaTeX compilation. Model equations, numerical settings and assumptions are
unchanged from the prior calculation; only the figure-export backend differs.

All scenario data are illustrative assumptions, not manufacturer or field
measurements. See source_audit.txt and the paper for interpretations and limits.
