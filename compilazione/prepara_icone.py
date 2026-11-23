"""Derive Windows and Tk icons from assets/logo_icona.svg."""
from pathlib import Path
import io,re
from PIL import Image
import cairosvg

ROOT=Path(__file__).resolve().parent.parent

def main():
    assets=ROOT/'assets'
    icon=(assets/'logo_icona.svg').read_text()
    raw=cairosvg.svg2png(bytestring=icon.encode(),output_width=512,output_height=512)
    im=Image.open(io.BytesIO(raw)).convert('RGBA')
    im.save(assets/'app.ico',sizes=[(n,n) for n in [16,20,24,32,40,48,64,96,128,256]])
    for n in [16,32,48,64,128,256]:im.resize((n,n),Image.Resampling.LANCZOS).save(assets/f'icona-{n}.png')
    for name,canvas_size,mark_size in [('setup-laterale.bmp',(164,314),(142,180)),('setup-intestazione.bmp',(150,57),(48,48))]:
        canvas=Image.new('RGB',canvas_size,'white')
        mark=im.copy();mark.thumbnail(mark_size,Image.Resampling.LANCZOS)
        pos=((canvas.width-mark.width)//2,(canvas.height-mark.height)//2)
        canvas.paste(mark,pos,mark);canvas.save(assets/name)

if __name__=='__main__':main()
