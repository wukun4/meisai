"""Place supplied raster drawings in standalone PDFs without altering pixels."""
from pathlib import Path
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
import shutil

P=Path(__file__).resolve().parents[1]
items=[
 ('开放式冷柜.png','09_open_display_case.pdf','open_display_case_original.png'),
 ('公交车站模型.jpg','07_bus_shelter_geometry.pdf','bus_shelter_original.jpg'),
 ('半开放式交通站.png','13_canberra_station.pdf','canberra_station_original.png'),
 ('拉斯维加斯Fremont.png','32_fremont_context.pdf','fremont_context_original.png'),
 ('火奴鲁鲁动物园售票处.png','33_honolulu_context.pdf','honolulu_context_original.png'),
]
for name,out,archived in items:
 source=P/name
 shutil.copy2(source,P/'figure_sources'/archived)
 with Image.open(source) as im:
  w=720;h=w*im.height/im.width
  c=Canvas(str(P/'figures'/out),pagesize=(w,h))
  c.setTitle(out.removesuffix('.pdf').replace('_',' '))
  c.setSubject('User-supplied architectural context; original raster pixels retained')
  c.drawImage(ImageReader(im),0,0,width=w,height=h)
  c.showPage();c.save()
 print(out)
