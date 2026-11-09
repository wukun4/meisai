"""Place the supplied diagram in a separate PDF, retaining original image pixels.

The PDF viewport omits the baked-in source and figure number below pixel 906;
the paper supplies a verified source and consistent numbering in its caption.
This is a raster figure in a PDF container, not a vector reconstruction.
"""
from pathlib import Path
from reportlab.pdfgen import canvas
from PIL import Image
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'open_display_case_original.png'
OUT = ROOT.parent / 'figures' / '09_open_display_case.pdf'
with Image.open(SOURCE) as im:
    width, height = im.size
assert (width, height) == (1536, 1024), 'Review viewport when replacing source size.'
visible_bottom = 906
scale = 0.4
c = canvas.Canvas(str(OUT), pagesize=(width*scale, visible_bottom*scale))
c.setTitle('Open refrigerated display case - user-supplied schematic')
c.setAuthor('User-supplied illustration; PDF placement prepared for HiMCM draft')
c.drawImage(str(SOURCE), 0, -(height-visible_bottom)*scale, width=width*scale, height=height*scale)
c.showPage()
c.save()
print(OUT)
