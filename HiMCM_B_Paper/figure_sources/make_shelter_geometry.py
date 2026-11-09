"""Place the latest supplied drawing in a standalone PDF without cropping."""
from pathlib import Path
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT / 'bus_shelter_original.jpg'
OUT=ROOT.parent/'figures' / '07_bus_shelter_geometry.pdf'
with Image.open(SOURCE) as im:
    width=720
    height=width*im.height/im.width
    c=Canvas(str(OUT),pagesize=(width,height))
    c.drawImage(ImageReader(im),0,0,width=width,height=height)
    c.showPage(); c.save()
print(OUT)
