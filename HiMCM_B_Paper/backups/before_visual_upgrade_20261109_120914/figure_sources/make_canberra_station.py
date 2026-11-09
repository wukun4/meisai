from pathlib import Path
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
r=Path(__file__).resolve().parent
p=r/'canberra_station_original.png'
im=Image.open(p)
w=720; h=w*im.height/im.width
c=Canvas(str(r.parent/'figures/13_canberra_station.pdf'),pagesize=(w,h))
c.drawImage(ImageReader(im),0,0,width=w,height=h)
c.save()
