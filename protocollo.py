"""Protocollo Locale: trasformazione di registri senza servizi esterni."""
from __future__ import annotations
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
from html.parser import HTMLParser
from xml.sax.saxutils import escape

MONTHS = ['', 'GENNAIO','FEBBRAIO','MARZO','APRILE','MAGGIO','GIUGNO','LUGLIO','AGOSTO','SETTEMBRE','OTTOBRE','NOVEMBRE','DICEMBRE']
PUBLIC = re.compile(r'^(?:UFFICIO|COMUNE\b|COMANDO\b|CARABINIERI\b|LEGIONE CARABINIERI|GRUPPO CARABINIERI|GUARDIA DI FINANZA|REGIONE\b|PROVINCIA\b|PROVICIA\b|PREFETTURA\b|QUESTURA\b|TRIBUNALE\b|PROCURA\b|CONSOLATO\b|AMBASCIATA\b|AGENZIA\b|ATS\b|A\.T\.S\.|ASST\b|ARPA\b|INPS\b|INAIL\b|ISTAT\b|MEF\b|ISPETTORATO\b|ISTITUTO (?:COMPRENSIVO|SUPERIORE|BLAISE)|LICEO\b|SISTEMA BIBLIOTECARIO|SISTEMA DI INTERSCAMBIO|CENTRO PER L.IMPIEGO|CASELLARIO\b|DISTRETTO VETERINARIO|OSPEDALE\b|SANA - PREFETTURA|RAGIONERIA\b|SEGRETERIA\b|SEGRETARIO\b|DEMOGRAFICI\b|AMMINISTRAZIONE\b|ASSISTENTE SOCIALE\b|MESSI COMUNALI\b|BIBLIOTECA\b|CULTURA-IG|DESTINATARI VARI|UTENTI DEL|MEMBRI COMMISSIONE|OFFICINA LEGISLATIVA|MINISTERO\b|ORDINE DEGLI|SPORTELLO TELEMACO|AMBITO\s*9|AZIENDA TERRITORIALE|ANCI\b|ASMEL\b|UNITEL\b|CGIL\b|CISL\b|UILA\b|POLIZIA LOCALE\b|CONSORZIO DI BONIFICA\b)', re.I)
LEGAL = re.compile(r'\s+(S\.?R\.?L\.?S?\.?|S\.?P\.?A\.?|S\.?N\.?C\.?|S\.?A\.?S\.?|S\.?C\.?A\.?|ETS|ONLUS|ODV)\s*$',re.I)
TITLES = re.compile(r'^(?:(?:ARCH\.|ING\.|GEOM\.|AVV\.|DOTT\.SSA|DOTT\.|NOTAIO|DR\.SSA)\s*)+',re.I)
def norm(s): return re.sub(r'\s+',' ',str(s or '')).strip().casefold()
def repair_encoding(value):
    """Repair only complete UTF-8 sequences misread as Western single-byte text.

    Work on local sequences, never re-decode whole documents or drop characters.
    This also handles already corrupted approval archives without changing keys.
    """
    if not isinstance(value,str):return value
    def fix(match):
        part=match.group()
        for codec in ('cp1252','latin1'):
            try:return part.encode(codec).decode('utf-8')
            except (UnicodeEncodeError,UnicodeDecodeError):pass
        return part
    sequence=re.compile(r'[\u00c2-\u00df][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]|[\u00e0-\u00ef][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]{2}')
    for _ in range(3):
        repaired=sequence.sub(fix,value)
        if repaired==value:break
        value=repaired
    return value
def text(v):
    if isinstance(v,(dt.datetime,dt.date)): return v.strftime('%d/%m/%Y')
    if v is None: return ''
    if isinstance(v,float) and v.is_integer(): return str(int(v))
    return str(v).strip()

class HTMLTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.tables=[]; self.stack=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table': self.stack.append([])
        elif tag=='tr': self.row=[]
        elif tag in ('td','th'): self.cell=[]
        elif tag=='br' and self.cell is not None: self.cell.append('\n')
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            if self.row is not None: self.row.append(''.join(self.cell).replace('\xa0',' ').strip())
            self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.stack: self.stack[-1].append(self.row)
            self.row=None
        elif tag=='table' and self.stack: self.tables.append(self.stack.pop())

def raw_tables(path):
    path=Path(path); data=path.read_bytes()
    if data[:2]==b'PK':
        from openpyxl import load_workbook
        # Bytes allow HTML exports and true XLSX to be identified by content.
        import io
        wb=load_workbook(io.BytesIO(data),read_only=True,data_only=False)
        try: return [(s.title,[[text(c) for c in r] for r in s.iter_rows(values_only=True)]) for s in wb]
        finally: wb.close()
    if data.startswith(bytes.fromhex('D0CF11E0')):
        import xlrd
        wb=xlrd.open_workbook(file_contents=data)
        tables=[]
        for s in wb.sheets():
            table=[]
            for i in range(s.nrows):
                line=[]
                for c in s.row(i):
                    v=xlrd.xldate.xldate_as_datetime(c.value,wb.datemode) if c.ctype==xlrd.XL_CELL_DATE else c.value
                    line.append(text(v))
                table.append(line)
            tables.append((s.name,table))
        return tables
    try: decoded=data.decode('utf-8-sig')
    except UnicodeDecodeError: decoded=data.decode('cp1252',errors='replace')
    if re.search(r'<(?:html|table)\b',decoded,re.I):
        p=HTMLTables();p.feed(decoded);return [(f'Tabella {i+1}',t) for i,t in enumerate(p.tables)]
    if path.suffix.lower() not in ('.csv','.tsv'): raise ValueError('Formato non riconosciuto. Usa XLS, XLSX, CSV oppure un export HTML.')
    try: dialect=csv.Sniffer().sniff(decoded[:8192],delimiters=';,\t')
    except csv.Error: dialect=csv.excel
    return [(path.stem,list(csv.reader(decoded.splitlines(),dialect)))]

def candidates(path):
    result=[]
    for sheet,table in raw_tables(path):
        for index,row in enumerate(table):
            heads=[norm(x) for x in row]
            aliases=[('numero','n.','n'),('tipo',),('data',),('oggetto',)]
            if all(any(a in heads for a in group) for group in aliases):
                cols=[next(heads.index(a) for a in group if a in heads) for group in aliases]
                result.append((sheet,table,index,heads,cols));break
    if not result: raise ValueError('Non trovo le intestazioni Numero, Tipo, Data e Oggetto. Controlla il file.')
    return result

def read_records(candidate):
    sheet,table,index,heads,cols=candidate; records=[]; skipped=0
    for source_row,row in enumerate(table[index+1:],index+2):
        if not any(text(x) for x in row): continue
        get=lambda i: text(row[i]) if i<len(row) else ''
        values=[get(i) for i in cols]
        if norm(values[0]) in ('numero','totale','totali') or not values[0]:
            skipped+=1;continue
        record=dict(zip(('numero','tipo','data','oggetto'),values));record['source_row']=source_row
        record['parties']=[get(i) for i,h in enumerate(heads) if h in ('mittente','destinatario')]
        records.append(record)
    if not records: raise ValueError('La tabella non contiene registrazioni.')
    if all(re.fullmatch(r'\d+',r['numero']) for r in records):records.sort(key=lambda r:int(r['numero']))
    return records,skipped

def inferred_title(records):
    months=set()
    for r in records:
        for fmt in ('%d/%m/%Y','%d-%m-%Y','%Y-%m-%d','%Y-%m-%d %H:%M:%S'):
            try:
                d=dt.datetime.strptime(r['data'],fmt);months.add((d.year,d.month));break
            except ValueError:pass
    if len(months)==1:
        y,m=next(iter(months));return f'PROTOCOLLO MESE DI {MONTHS[m]} {y}'
    return 'REGISTRO DI PROTOCOLLO'

def export_xlsx(path,rows,title):
    rows=[[repair_encoding(v) for v in row] for row in rows]
    title=repair_encoding(title)
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill,Border,Side
    from openpyxl.worksheet.page import PageMargins
    from textwrap import wrap
    wb=Workbook();s=wb.active;s.title='Protocollo'
    s.merge_cells('A1:D1');s['A1']=title;s['A1'].font=Font(name='Arial',size=14,bold=True);s['A1'].alignment=Alignment(horizontal='center');s.row_dimensions[1].height=28
    s.append(['Numero','Tipo','Data','Oggetto'])
    for row in rows:
        s.append(row)
        # Force every imported field to literal text: no executable formulas.
        for c in s[s.max_row]:c.data_type='s';c.font=Font(name='Arial',size=10);c.alignment=Alignment(vertical='top',wrap_text=True)
        lines=sum(max(1,len(wrap(line,105))) for line in row[3].split('\n'))
        s.row_dimensions[s.max_row].height=max(24,lines*14+6)
    for c in s[2]:c.font=Font(name='Arial',size=10,bold=True);c.fill=PatternFill('solid',fgColor='E8E8E8')
    for key,width in [('A',12),('B',13),('C',15),('D',112)]:s.column_dimensions[key].width=width
    s.freeze_panes='A3';s.auto_filter.ref=f'A2:D{s.max_row}';s.sheet_view.showGridLines=False
    s.print_title_rows='1:2';s.print_options.horizontalCentered=True;s.print_area=f'A1:D{s.max_row}'
    s.page_setup.orientation='landscape';s.page_setup.paperSize=s.PAPERSIZE_A4;s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;s.sheet_properties.pageSetUpPr.fitToPage=True
    s.page_margins=PageMargins(left=.25,right=.25,top=.35,bottom=.35,header=.1,footer=.1)
    s.oddFooter.right.text='Pagina &P di &N';wb.save(path)

def export_pdf(path,rows,title):
    rows=[[repair_encoding(v) for v in row] for row in rows]
    title=repair_encoding(title)
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular='Helvetica';bold='Helvetica-Bold'
    for folder,name,bname in [(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts','arial.ttf','arialbd.ttf'),(Path('/usr/share/fonts/truetype/dejavu'),'DejaVuSans.ttf','DejaVuSans-Bold.ttf')]:
        if (folder/name).exists() and (folder/bname).exists():
            pdfmetrics.registerFont(TTFont('LocalSans',str(folder/name)));pdfmetrics.registerFont(TTFont('LocalSansBold',str(folder/bname)));regular='LocalSans';bold='LocalSansBold';break
    body=ParagraphStyle('body',fontName=regular,fontSize=8,leading=10,splitLongWords=True)
    head=ParagraphStyle('head',fontName=bold,fontSize=9,leading=11)
    heading=ParagraphStyle('title',fontName=bold,fontSize=13,leading=17,alignment=1,spaceAfter=12)
    def para(v,style=body):return Paragraph(escape(str(v)).replace('\n','<br/>'),style)
    data=[[para(x,head) for x in ['Numero','Tipo','Data','Oggetto']]]+[[para(v) for v in row] for row in rows]
    table=Table(data,colWidths=[52,46,57,404],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.6,'#777777'),('LINEBELOW',(0,1),(-1,-1),.2,'#D8D8D8')]))
    def footer(c,d):c.setFont(regular,8);c.drawRightString(A4[0]-18,13,str(d.page))
    doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=18,rightMargin=18,topMargin=20,bottomMargin=24,title=title,author='')
    doc.build([para(title,heading),table],onFirstPage=footer,onLaterPages=footer)

def main():
    from interfaccia_v4 import main as launch
    launch()

if __name__=='__main__':main()
