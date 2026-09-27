"""Vector manipulator pictogram based on the supplied brand reference."""
from pathlib import Path
from math import cos, sin, radians
from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parents[1] / 'public'
DARK, GREEN, LIME = '#193137', '#06b998', '#8bda46'
SHAPES = [
 ('arc',((5,5,61,61),20,90),GREEN,3),
 ('arc',((5,5,61,61),277,335),GREEN,3),
 ('rect',(28,42,33,53),'#087565',1),('rect',(35,37,40,54),GREEN,1),('rect',(42,31,48,51),LIME,1),
 ('polygon',[(10,33),(16,30),(25,45),(24,48),(14,48)],DARK,0),
 ('polygon',[(12,23),(28,10),(33,18),(20,31)],DARK,0),
 ('polygon',[(30,11),(35,9),(42,21),(38,25),(29,17)],DARK,0),
 ('line',[(39,22),(37,28),(39,31)],DARK,3),('line',[(40,22),(45,26),(44,30)],DARK,3),
 ('circle',(5,22,21,38),DARK,0),('circle',(8,25,18,35),GREEN,0),('circle',(11,28,15,32),DARK,0),
 ('circle',(25,4,38,17),DARK,0),('circle',(28,7,35,14),GREEN,0),('circle',(30,9,33,12),DARK,0),
 ('circle',(37,19,43,25),GREEN,0),('circle',(39,21,41,23),DARK,0),
 ('rect',(8,49,26,58),DARK,4),('rect',(4,54,30,62),DARK,3),('line',[(11,57),(23,57)],GREEN,2),
 ('circle',(48,27,64,43),DARK,0),('line',[(52,35),(55,38),(60,32)],LIME,3),
]

def main():
 nodes=[]
 canvas=Image.new('RGBA',(1024,1024)); draw=ImageDraw.Draw(canvas)
 for kind,coords,color,size in SHAPES:
  if kind == 'arc':
   box,start,end=coords
   x,y,x2,y2=box; cx,cy=(x+x2)/2,(y+y2)/2; rx,ry=(x2-x)/2,(y2-y)/2
   points=[(cx+rx*cos(radians(angle)),cy+ry*sin(radians(angle))) for angle in (start,end)]
   (ax,ay),(bx,by)=points
   nodes.append(f'<path d="M{ax:.3f},{ay:.3f} A{rx},{ry} 0 0 1 {bx:.3f},{by:.3f}" fill="none" stroke="{color}" stroke-width="{size}"/>')
   draw.arc(tuple(v*16 for v in box),start,end,fill=color,width=size*16)
  elif kind in {'line','polygon'}:
   points=' '.join(f'{x},{y}' for x,y in coords)
   scaled=[(x*16,y*16) for x,y in coords]
   if kind=='line':
    nodes.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{size}" stroke-linecap="round" stroke-linejoin="round"/>')
    draw.line(scaled,fill=color,width=size*16,joint='curve')
    for x,y in scaled:
     r=size*8; draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
   else:
    nodes.append(f'<polygon points="{points}" fill="{color}"/>'); draw.polygon(scaled,fill=color)
  else:
   x,y,x2,y2=coords; box=tuple(v*16 for v in coords)
   if kind=='circle':
    nodes.append(f'<ellipse cx="{(x+x2)/2}" cy="{(y+y2)/2}" rx="{(x2-x)/2}" ry="{(y2-y)/2}" fill="{color}"/>'); draw.ellipse(box,fill=color)
   else:
    nodes.append(f'<rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" rx="{size}" fill="{color}"/>'); draw.rounded_rectangle(box,radius=size*16,fill=color)
 (PUBLIC/'favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 68 68" role="img"><title>РОБОДОВОД — манипулятор</title><g transform="translate(2 1)">'+''.join(nodes)+'</g></svg>\n',encoding='utf-8')
 padded=Image.new('RGBA',(1088,1088)); padded.paste(canvas,(32,16))
 for size in (16,32,64,180,192,512):
  name='apple-touch-icon.png' if size==180 else f'favicon-{size}.png' if size<=64 else f'icon-{size}.png'
  padded.resize((size,size),Image.Resampling.LANCZOS).save(PUBLIC/name)
 padded.save(PUBLIC/'favicon.ico',sizes=[(16,16),(32,32),(64,64)])

if __name__=='__main__':
 main()
