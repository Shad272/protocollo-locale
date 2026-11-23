"""Revisioni per riga, intervalli nel testo originale e riuso di approvazioni.

Nessuna sostituzione viene propagata ad altre righe. Un risultato non viene
considerato verificato soltanto perché i riconoscitori non trovano nomi.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
import datetime as dt
import json
from pathlib import Path
import re
from protocollo import repair_encoding
from riconoscimento import (WORD, SUFFIX, COMMON, COMPANY_WORDS, ROLE, canonical,
    initials, is_redacted, phrase_pattern, protected_ranges, protected)

VERSION = 4

class Memory(dict):
    def __init__(self,rows=(),names=None):
        super().__init__(rows);self.names=dict(getattr(rows,'names',{}));self.names.update(names or {})
    def update(self,other):
        super().update(other);self.names.update(getattr(other,'names',{}))

STOP = COMMON | set("accesso aggiornato aggiornata complementare allerta rischio idro meteo revisione veicolo lato sinistro destro ubicata foglio massima rateizzazione trascrizione organizzazione organizza domenica striscione pubblicitario affissione contabile eventuali arretrati notificato violazione classe leva parlamento europeo variazione forestale pianura concerto buio convenzione certificato malattia laurea magistrale documento documento contabili elezione camera senato repubblica significato disposizioni patriocinio patrocinio oneroso bandiera lilla indirizzo sinac sinistro spettacolo viaggiante".split())
CONNECTORS = {'di','de','del','della','dello','lo','la','el','al','van','von','da','e','e.','&'}
STOP.update({'salma','cremazione','sana','presentata','presentato'})
LEGAL = re.compile(r'\s+('+SUFFIX+r')\s*$', re.I)
CONTEXT = re.compile(r"\b(?:sigg?\.?\s*ri\.?|sig(?:\s*\.\s*(?:ra|ri|na))?\.?|signor[ae]?|avv\.|arch\.|ing\.|geom\.|dott(?:\.\s*ssa)?\.?|defunt[oa]|alunn[oa]|propr\.|intestato\s+a|a\s+carico\s+(?:di|del|della)|a\s+cura\s+di|webinar\s+gratuito\s+di|avo\s+italiano|verifica\s+anagrafica|cremazione|salma|richiedenti|professionista\s+incaricato|ditta\s+cedente)(?!\w)\s*[:.]?\s*", re.I)
END = re.compile(r"[,;:\n()|]|\s+-\s+|\s+(?:via|viale|nato|nata|nati|nate|prot\.?|oggetto|documenti|n\.|e\s+altri|domiciliat[oa]|residente|per|con|del)\b", re.I)

def date_key(value):
    for fmt in ('%d/%m/%Y','%d-%m-%Y','%Y-%m-%d','%Y-%m-%d %H:%M:%S'):
        try:return dt.datetime.strptime(str(value),fmt).date().isoformat()
        except ValueError:pass
    return str(value)

def fingerprint(record):
    # Party metadata is not part of the exported text or of its approval.
    fields=[str(record['numero']),str(record['tipo']),date_key(record['data']),record['oggetto']]
    return sha256(json.dumps(fields,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def replacement(value):
    legal=LEGAL.search(value)
    return initials(value[:legal.start()])+' '+legal.group(1) if legal else initials(value)

@dataclass
class Proposal:
    start:int
    end:int
    name:str
    reason:str
    choice:str='pending'  # apply / keep / pending
    value:str=''
    def __post_init__(self):
        if not self.value:self.value=replacement(self.name)

@dataclass
class ReviewRow:
    record:dict
    proposals:list[Proposal]=field(default_factory=list)
    approved:bool=False
    approved_text:str|None=None
    origin:str=''
    def render(self):
        if self.approved_text is not None:return repair_encoding(self.approved_text)
        s=self.record['oggetto'];last=len(s);pieces=[]
        for p in sorted((p for p in self.proposals if p.choice=='apply'),key=lambda p:p.start,reverse=True):
            if not (0<=p.start<p.end<=last) or s[p.start:p.end]!=p.name:
                raise ValueError('Intervalli sovrapposti o modificati: rivedi la riga '+str(self.record['numero']))
            pieces.extend([s[p.end:last],p.value]);last=p.start
        pieces.append(s[:last]);return repair_encoding(''.join(reversed(pieces)))
    def unresolved(self):return sum(p.choice=='pending' for p in self.proposals)
    def approve(self):
        if self.unresolved():raise ValueError('Decidi prima tutti i casi dubbi della riga.')
        self.render();self.approved=True;self.origin='Revisione manuale'
    def choose(self,index,choice):
        if self.approved_text is not None:raise ValueError('Riapri prima la riga approvata.')
        p=self.proposals[index]
        if choice not in ('apply','keep'):raise ValueError('Decisione non valida')
        if choice=='apply':
            for other in self.proposals:
                if other is not p and other.choice=='apply' and p.start<other.end and p.end>other.start:
                    raise ValueError('La selezione si sovrappone a un oscuramento: conserva prima quello da sostituire.')
        p.choice=choice;self.approved=False;self.origin='';self.render()
    def manual_span(self,start,end):
        s=self.record['oggetto'];name=s[start:end]
        if not (0<=start<end<=len(s)) or not re.search(WORD,name):raise ValueError('Seleziona il nome nel testo originale.')
        if re.search(r'\d',name):raise ValueError('La selezione contiene numeri: seleziona soltanto il nome.')
        for i,p in enumerate(self.proposals):
            if p.start==start and p.end==end:self.choose(i,'apply');return
        if any(p.choice=='apply' and start<p.end and end>p.start for p in self.proposals):
            raise ValueError('Selezione sovrapposta: conserva prima la proposta esistente.')
        self.proposals.append(Proposal(start,end,name,'Selezione manuale','apply'))
        self.approved=False;self.render()

def _names(records,public,verified=None):
    names={k:'dizionario verificato' for k in (verified or {})}
    for r in records:
        for field in r.get('parties',[]):
            for p in re.sub(r'^\(\d+\)\s*','',field).split(';'):
                p=ROLE.sub('',p.strip());p=re.split(r'\s+-\s+|\s+RESP\.',p,flags=re.I)[0].strip()
                if not p or public.search(p) or '@' in p or len(p)>180:continue
                words=re.findall(WORD,p)
                if not words or is_redacted(p) or all(canonical(w) in STOP|COMPANY_WORDS for w in words):continue
                legal=LEGAL.search(p)
                names[p]='società' if legal else 'anagrafica'
                if legal:
                    base=p[:legal.start()].strip()
                    if len(base)>2:
                        names[base]='società'
                        # Compact exports: Alfa Beta Esempio S.p.A. -> AlfaBetaEsempioSpA.
                        compact=re.sub(r'\W+','',p)
                        if len(compact)>3:names[compact]='società'
                elif 2<=len(words)<=6 and not any(canonical(w) in COMPANY_WORDS for w in words):
                    for k in range(1,len(words)):names[' '.join(words[k:]+words[:k])]='anagrafica'
                    # Initial + full surname is still personal data.
                    for k,w in enumerate(words):
                        if len(w)>2 and canonical(w) not in STOP|CONNECTORS:
                            for other in words[:k]+words[k+1:]:
                                if len(other)>2:names[other[0]+'. '+w]='anagrafica'
    return names

def analyze(records,public,nlp=None,second=None,progress=None,memory=None):
    numbers=[str(r['numero']) for r in records]
    if len(numbers)!=len(set(numbers)):raise ValueError('Numeri di protocollo duplicati: controlla la tabella originale.')
    if memory is None:memory={}
    verified=getattr(memory,'names',{})
    names=_names(records,public,verified);pattern=phrase_pattern(names) if names else None
    lookup={canonical(k):v for k,v in names.items()};verified_values={canonical(k):v for k,v in verified.items()}
    output=[];active=[]
    for r in records:
        row=ReviewRow(r)
        entry=memory.get(fingerprint(r))
        if entry is not None:
            if not isinstance(entry,dict) or not isinstance(entry.get('oggetto'),str):raise ValueError('Archivio approvazioni non valido.')
            row.approved=True;row.approved_text=entry['oggetto'];row.origin=entry.get('origine','Riferimento approvato')
        else:active.append(len(output))
        output.append(row)
    texts=[records[i]['oggetto'] for i in active]
    first=[[] for _ in texts]
    if nlp is not None:
        # Only analyze original texts. Repeated NER on initials creates false positives.
        variants=[]
        for s in texts:
            variants.append(s)
            if sum(c.isupper() for c in s)>sum(c.islower() for c in s) and len(s.title())==len(s):variants.append(s.title())
        docs=iter(nlp.pipe(variants,batch_size=32))
        for i,s in enumerate(texts):
            for _ in range(2 if sum(c.isupper() for c in s)>sum(c.islower() for c in s) and len(s.title())==len(s) else 1):
                doc=next(docs)
                for e in doc.ents:
                    if e.label_ in ('PER','PERSON','ORG'):first[i].append((e.start_char,e.end_char,'person' if e.label_ in ('PER','PERSON') else 'company'))
    second_results=second.entities_many(texts,progress) if second is not None else [[] for _ in texts]
    if len(second_results)!=len(texts):raise ValueError('Analisi incompleta: numero di risultati non valido.')
    for position,i in enumerate(active):
        row=output[i];s=row.record['oggetto'];ranges=protected_ranges(s);proposals=[]
        def add(start,end,reason,auto=False,value=None):
            while start<end and s[start] in ' \t\n\"':start+=1
            while end>start and s[end-1] in ' \t\n\",;:':end-=1
            name=s[start:end]
            if not name or is_redacted(name) or protected(start,end,ranges) or public.search(name):return
            words=[canonical(w) for w in re.findall(WORD,name)]
            if not words or all(w in STOP|COMPANY_WORDS for w in words):return
            if re.search(r'\d',name) and value is None:return  # Only an explicitly verified brand may include digits.
            for p in proposals:
                if (p.start,p.end)==(start,end):
                    if reason not in p.reason:p.reason+='; '+reason
                    if auto:p.choice='apply'
                    return
            proposals.append(Proposal(start,end,name,reason,'apply' if auto else 'pending',value or ''))
        if pattern:
            for m in pattern.finditer(s):
                # Same literal, local span. Never touch a road because of another row.
                kind=lookup[canonical(m.group())];words=re.findall(WORD,m.group())
                auto=(canonical(m.group()) in verified_values or not (kind=='anagrafica' and len(words)==1)) and not re.match(r'^(?:ASD|APS|PARROCCHIA)\b',m.group(),re.I)
                add(m.start(),m.end(),'Corrispondenza con '+kind,auto,verified_values.get(canonical(m.group())))
        for m in CONTEXT.finditer(s):
            tail=s[m.end():];end=END.search(tail);tail=tail[:end.start()] if end else tail
            origin=m.end()
            if re.search(r'\b(?:cremazione|salma)\s*$',m.group(),re.I) and tail.startswith('di '):tail=tail[3:];origin+=3
            # Separators between people are prose, not part of either name.
            boundaries=[];previous=0
            for separator in re.finditer(r'[/|]|\s+(?:e|ed)\s+',tail,re.I):
                boundaries.append((previous,separator.start()));previous=separator.end()
            boundaries.append((previous,len(tail)))
            for a,b in boundaries:
                start=origin+a;stop=origin+b
                value=s[start:stop].strip();words=[canonical(w) for w in re.findall(WORD,value)]
                if 0<len(words)<=7 and not re.search(r'\d',value):
                    # Strong context, but an administrative word makes it a review case.
                    auto=not any(w in STOP and w not in CONNECTORS for w in words) and not re.match(r'^(?:ASD|APS|PARROCCHIA)\b',value,re.I)
                    add(start,stop,'Contesto personale esplicito',auto)
        for m in re.finditer(r'(?<!\w)'+SUFFIX+r'(?!\w)',s,re.I):
            tokens=list(re.finditer(WORD+r'|&',s[:m.start()]));start=m.start()
            for tok in reversed(tokens):
                gap=s[tok.end():start]
                if re.search(r'[:;,/\n()\"]|\s+-\s+',gap) and start!=m.start():break
                low=canonical(tok.group())
                if low in STOP and low not in CONNECTORS|{'servizi','servizio'}:break
                start=tok.start()
                if len(s[start:m.start()].split())>=8:break
            if start<m.start():add(start,m.end(),'Denominazione con forma giuridica',True)
        for start,end,label in first[position]:add(start,end,'Modello italiano: '+label)
        for e in second_results[position]:add(int(e['start']),int(e['end']),'Modello multilingue: '+e.get('label','entità'))
        # An anchored span wins over a wider model phrase. Do not include prose in a name.
        priority=lambda p:0 if p.reason.startswith('Corrispondenza') else 1 if p.reason.startswith('Contesto') else 2
        anchors=[]
        for p in sorted((p for p in proposals if p.choice=='apply'),key=lambda p:(priority(p),-(p.end-p.start),p.start)):
            if not any(p.start<a.end and p.end>a.start for a in anchors):anchors.append(p)
        filtered=list(anchors)
        for p in (p for p in proposals if p.choice!='apply'):
            if any(p.start<a.end and p.end>a.start for a in anchors):
                # Preserve an uncovered extra proper token as a separate review candidate.
                for a,b in [(p.start,min((x.start for x in anchors if p.start<x.end and p.end>x.start),default=p.end)),
                            (max((x.end for x in anchors if p.start<x.end and p.end>x.start),default=p.start),p.end)]:
                    value=s[a:b].strip(' .-/,;:')
                    if value and any(canonical(w) not in STOP|COMPANY_WORDS|CONNECTORS for w in re.findall(WORD,value)):
                        offset=s.find(value,a,b);filtered.append(Proposal(offset,offset+len(value),value,'Parte residua di una proposta: verifica'))
                continue
            filtered.append(p)
        unique={}
        for p in filtered:
            key=(p.start,p.end)
            if key not in unique or p.choice=='apply':unique[key]=p
        row.proposals=sorted(unique.values(),key=lambda p:(p.start,p.end))
        row.render()
        if progress and position%50==0:progress(f'Analisi delle righe nuove: {position+1}/{len(active)}')
    return output

def export_rows(rows):
    if not rows:raise ValueError('Carica prima una tabella.')
    if any(not row.approved or row.unresolved() for row in rows):
        raise ValueError('Esportazione bloccata: ogni riga nuova deve essere controllata e ogni proposta deve avere una decisione.')
    return [[r.record['numero'],r.record['tipo'],r.record['data'],r.render()] for r in rows]

def approvals(rows):
    return {fingerprint(r.record):{'oggetto':r.render(),'origine':r.origin or 'Revisione manuale'} for r in rows if r.approved and not r.unresolved()}

def save_memory(path,rows,verified=None):
    names=dict(verified or {})
    for row in rows:
        if row.approved and not row.unresolved():
            for p in row.proposals:
                if p.choice=='apply':names[p.name]=p.value
    data={'versione':VERSION,'descrizione':'Solo righe esplicitamente approvate. Riutilizzo soltanto su originali identici.','righe':approvals(rows),'nomi_verificati':names}
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)

def load_memory(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('versione')!=VERSION or not isinstance(data.get('righe'),dict):raise ValueError('Formato archivio approvazioni non riconosciuto.')
    for key,entry in data['righe'].items():
        if not re.fullmatch('[0-9a-f]{64}',key) or not isinstance(entry,dict) or not isinstance(entry.get('oggetto'),str):raise ValueError('Archivio approvazioni danneggiato.')
    names=data.get('nomi_verificati',{})
    if not isinstance(names,dict) or not all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in names.items()):raise ValueError('Dizionario verificato non valido.')
    return Memory(data['righe'],names)
