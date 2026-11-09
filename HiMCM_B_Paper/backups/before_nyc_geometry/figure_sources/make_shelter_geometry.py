"""Place the supplied image in a PDF with a publication viewport.
Pixels are not redrawn or retouched. The original title is retained; the baked-in caption
is outside the viewport; the paper provides its own number and attribution.
"""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'bus_shelter_original.png'
OUT = ROOT.parent / 'figures' / '07_bus_shelter_geometry.pdf'
WIDTH_PX, HEIGHT_PX = 1536, 1024
TOP_PX, BOTTOM_PX = 0, 910
SCALE = 0.4
OUT.parent.mkdir(exist_ok=True)
c = canvas.Canvas(str(OUT), pagesize=(WIDTH_PX*SCALE,(BOTTOM_PX-TOP_PX)*SCALE))
c.setTitle('Bus shelter reference geometry - supplied schematic')
c.setSubject('Regular-size NYC shelter dimensions; original raster image preserved')
c.drawImage(ImageReader(str(SOURCE)),0,-(HEIGHT_PX-BOTTOM_PX)*SCALE,
            width=WIDTH_PX*SCALE,height=HEIGHT_PX*SCALE)
c.showPage();c.save()
print(OUT)
