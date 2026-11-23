"""Riconoscimento locale: regole strutturali, dizionario del file e NER italiano.

Nessun documento o nominativo viene inviato in rete. Il modello si installa
separatamente una volta sola. Le segnalazioni non sono una stima di accuratezza.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import unicodedata

WORD = r"[^\W\d_]+(?:['’ʼ\-][^\W\d_]+)*"
SUFFIX = r"(?:S\s*\.?\s*R\s*\.?\s*L\s*\.?\s*S?\.?|S\s*\.?\s*P\s*\.?\s*A\.?|S\s*\.?\s*N\s*\.?\s*C\.?|S\s*\.?\s*A\s*\.?\s*S\.?|S\s*\.?\s*C\s*\.?\s*A\.?|ETS|ONLUS|ODV)"
ROLE = re.compile(r'^(?:(?:arch\.|ing\.|geom\.|avv\.|dott\.ssa|dott\.|dr\.ssa|dr\.|notaio)\s*)+',re.I)
COMMON = set('posta certificata invio richiesta domanda comunicazione comunicazioni verifica conferma iscrizione attivazione servizio servizi cessazione comune provincia regione pubblico pubblica amministrazione amministrativo tramite atto atti protocollo oggetto ufficio signor signora sig sigra sigri dott dottssa arch geom avv scuola materna statale capitanio sacro cuore biblioteca centrale lombardia brescia verolanuova cadignano mensa ricevuta ricevuta fattura fatture file scia cila tari imu inizio fine lavori relativo relativa nominativo copia integrale certificato certificazione stato civile copia allegato lettera sindaco segretario pnr pnrr anci asl asst ats ansc aia id pec italiano italiana italia elenco famiglia nascita morte residenza matrimonio cittadinanza processo pagamento repertorio parte raccomandata notifica intero universita università nato nata con per della delle degli della dello dei del dal dalle dalla allo alla alle agli agli il lo la le gli un una uno e o a da di in su nel nella presso tramite autorita autorità modulo riferimento decreto occupazione spazi aree restituzione conferenza incontro ordinanza intervento impianto nuovo nuova costruzione san santa santo'.split())
COMMON.update('presentazione riscontro trasmissione manutenzione perizia proroga accordo incarico fatturazione invito sollecito preventivo domanda servizio allegati allegato protocollo prot attestazione restituzione inoltro relazione rendicontazione'.split())
COMMON.update('comuni contratto entrate reg lett euro fwd fw enti casa gelo dgr dpr dlgs art articolo legge n numero nr civici centro rete regionale nazionale comunale provinciali provinciale pratiche pratica ascolto regolamento sopralluogo provvedimento soprassuolo segnalazione fiscale accertamento tasse tributi direzione generale anno mese settembre ottobre gennaio febbraio marzo aprile maggio giugno luglio agosto novembre dicembre annuo avviso soluzioni relazione incidente giudiziario bando deliberazione istruttoria approvazione controllo controlli amministrazioni diritto studio riconoscimento assistenza idoneita idoneità alloggio idoneita alloggiativa integrazione documentale'.split())
COMMON.update('adi pdc cdu ati rti aso tso onu rgr sie sicp pa asl cgil cisl sindacale pec sap fna imu iva ccr ppc scia cila cosap osap pnrr mepa vvf ao atena cosap artt cf sd sdd pas ferpas idp permesso civile elettorali cittadini'.split())
COMMON.update('prossimità allevamento avicolo dubbi applicativi edifici pubblici uso divorzio ricovero territorio comunale consegna chiavi vendita torte ragione sociale ultimi posti disponibili aggiornamento mappatura territoriale recupero revoca misure prevenzione interventi eseguiti errata corrige ccnl funzioni locali didattica laboratorio operativo online porticato est procedura abilitativa semplificata istanza catasto terreni istruttore tecnico transito eccezionale impianti ascensori dichiarazione ospitalita ospitalità nuove modalità modalita depurazione opere urgente controcitazione piano attuativo convocazione iniziale informativa risposta rif progetto vita pergola bioclimatica parti offese asilo nido variante sostanziale bilancio assegnazione urna cineraria proventi sanzioni amministrative rilevazione organo misura non effluenti assunzioni sentenza sospensione riforme giurisprudenza loculo informazioni invalidi anziani nullaosta servoscala segnalazioni demaniali oneri materne fattpa strada familiare guida successione pediatra conto anniversario carta nazioni unite edizione anno scolastico riflessioni concessione permanente zootecnico cedente pubbliche amministrazioni fondo evasione deputati nct fg mapp'.split())
COMPANY_WORDS=set('srl spa snc sas srls società societa societa’ societa\' coop cooperativa azienda agricola ditta impresa studio fondazione associazione bar banca gruppo consorzio filiale'.split())
COMMON.update('nota anac mase agid agcom agenzia ragioneria ispettorato prefettura ministero ministeri procura tribunale questura polizia carabinieri'.split())
COMMON.update('ricezione supporto richieste'.split())
BOUNDARY = re.compile(r'\s*(?:[;\n:(),]|\s+-\s+|\b(?:nato|nata|nati|nate|oggetto|via|viale|per|con|su|atto|prot|codice|richiesta|richiedenti|professionista|indirizzo|trasmissione|trascrizione|e altri)\b)',re.I)
_model=None

def canonical(s):
    s=unicodedata.normalize('NFKC',str(s))
    return re.sub(r'\s+',' ',s.replace('’',"'").replace('ʼ',"'").replace('–','-').replace('—','-')).strip().casefold()

def initials(s):
    return ''.join(word[0].upper()+'.' for word in re.findall(r"[^\W\d_]+|\d+",s,re.UNICODE))

def is_initials(s):
    s=s.strip(' \"')
    if re.fullmatch(r'[A-ZÀ-ÖØ-Ý]{1,2}',s):return True
    return '.' in s and bool(re.fullmatch(r"(?:[A-Za-zÀ-ÖØ-öø-ÿ]{1,2}\s*\.\s*)+(?:[A-Za-zÀ-ÖØ-öø-ÿ]{1,2})?",s))

def is_redacted(s):
    s=ROLE.sub('',s).strip()
    m=re.search(r'\s+'+SUFFIX+r'$',s,re.I)
    if m:s=s[:m.start()].strip()
    if is_initials(s):return True
    words=[canonical(w) for w in re.findall(WORD,s)]
    meaningful=[w for w in words if w not in COMMON and w not in COMPANY_WORDS]
    return '.' in s and not re.search(r'\d',s) and all(len(w)<=2 for w in meaningful)

def expression(s):
    """Literal phrase with flexible whitespace/apostrophes, no regex from input."""
    chunks=[]
    for part in re.split(r"(\s+|['’ʼ]|[-–—])",s.strip()):
        if not part:continue
        if part.isspace():chunks.append(r'\s+')
        elif part in "'’ʼ":chunks.append("['’ʼ]")
        elif part in '-–—':chunks.append('[-–—]')
        else:chunks.append(re.escape(part))
    return ''.join(chunks)

def phrase_pattern(names):
    return re.compile(r'(?<!\w)(?:'+'|'.join(expression(k) for k in sorted(names,key=len,reverse=True))+r')(?!\w)',re.I)

def protected_ranges(s):
    # Only the address itself; never the name following an address delimiter.
    pat=r'\b(?:via|viale|piazza|vicolo|largo|slargo|corso|cascina|frazione)\s+[^\n,;:()]+?(?=\s+(?:n\.?\s*)?\d|\s+-\s+|\s+(?:sig\.|sig\.ra|sig\.ri|propr\.|richiedente|utente|ditta|società)\s|[,;:\n()]|$)'
    return [(m.start(),m.end()) for m in re.finditer(pat,s,re.I)]

def protected(start,end,ranges):return any(start<hi and end>lo for lo,hi in ranges)

def load_language_model():
    global _model
    if _model is not None:return _model,'Modello italiano locale attivo'
    try:
        import spacy
        for name in ('it_core_news_lg','it_core_news_md','it_core_news_sm'):
            try:
                _model=spacy.load(name,exclude=['parser','lemmatizer','attribute_ruler','tagger','morphologizer','senter'])
                return _model,f'Modello italiano locale: {name}'
            except OSError:continue
    except (ImportError,ValueError,RuntimeError) as exc:
        return None,'Modello italiano non disponibile: '+type(exc).__name__
    return None,'Modello italiano non installato: avvia ATTIVA_RICONOSCIMENTO.cmd'
