import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from motore_v4 import (analyze,ReviewRow,Proposal,export_rows,fingerprint,save_memory,load_memory,approvals,Memory)
from protocollo import PUBLIC,candidates,read_records,export_xlsx,export_pdf

def record(subject,parties=(),number='1',date='01/10/2026'):
    return dict(numero=number,tipo='Arrivo',data=date,oggetto=subject,parties=list(parties))

def scan(subject,parties=(),**kwargs):return analyze([record(subject,parties)],PUBLIC,**kwargs)[0]

class FakeSecond:
    def __init__(self,names):self.names=names
    def entities_many(self,texts,progress=None):
        return [[{'start':s.index(n),'end':s.index(n)+len(n),'label':label} for n,label in self.names if n in s] for s in texts]

class RecognitionTests(unittest.TestCase):
    def test_reverse_party_name(self):
        row=scan('Domanda di Elisa Fontanelli',['FONTANELLI ELISA'])
        self.assertEqual(row.render(),'Domanda di E.F.');self.assertFalse(row.approved)
    def test_apostrophe_and_compound_surname(self):
        self.assertEqual(scan('Domanda di Elisa D’Angelo',["D'ANGELO ELISA"]).render(),'Domanda di E.D.A.')
    def test_person_after_road(self):
        row=scan('Via Roma 12 - sig. Paolo Verdi',['VERDI PAOLO'])
        self.assertEqual(row.render(),'Via Roma 12 - sig. P.V.')
    def test_road_not_changed_when_same_person_known(self):
        row=scan('Via Paolo Verdi 12 - sig. Paolo Verdi',['VERDI PAOLO'])
        self.assertEqual(row.render(),'Via Paolo Verdi 12 - sig. P.V.')
    def test_initial_and_surname(self):
        self.assertEqual(scan('Webinar a cura di C. Fontanelli').render(),'Webinar a cura di C.F.')
    def test_slash_two_people(self):
        row=scan('SIG.RI GIALDI ELIO/FERRANTE ELISA')
        self.assertEqual(row.render(),'SIG.RI G.E./F.E.')
    def test_multiple_names_cremation(self):
        row=scan('Autorizzazione al trasporto di salma e cremazione GIALDI ELIO GIOVANNI')
        self.assertEqual(row.render(),'Autorizzazione al trasporto di salma e cremazione G.E.G.')
    def test_conjunction_between_people_is_kept(self):
        row=scan('a carico di Gialdi Elio e Ferrante Elisa')
        self.assertEqual(row.render(),'a carico di G.E. e F.E.')
    def test_webinar_name_before_pipe(self):
        row=scan('Webinar a cura di C. Fontanelli | 13 Ottobre ore 11.30')
        self.assertEqual(row.render(),'Webinar a cura di C.F. | 13 Ottobre ore 11.30')
    def test_verified_name_can_be_reused_on_new_subject(self):
        memory=Memory(names={'Elisa Fontanelli':'E.F.'})
        row=scan('Un nuovo documento di Elisa Fontanelli',memory=memory)
        self.assertEqual(row.render(),'Un nuovo documento di E.F.');self.assertFalse(row.approved)
    def test_honorifics_are_never_part_of_name(self):
        for text,expected in [('Sigg.ri Elio Gialdi','Sigg.ri E.G.'),('DOTT.SSA ELISA FONTANELLI','DOTT.SSA E.F.')]:
            row=scan(text,['ELIO GIALDI','ELISA FONTANELLI']);self.assertEqual(row.render(),expected)
    def test_preposition_after_cremation_is_preserved(self):
        row=scan('Decreto cremazione di Elio Gialdi')
        self.assertEqual(row.render(),'Decreto cremazione di E.G.')
    def test_verified_company_wins_over_wider_legal_span(self):
        row=scan('Provvedimento del . di ALFA VERDE Srl',memory=Memory(names={'ALFA VERDE Srl':'A.V. SRL'}))
        self.assertEqual(row.render(),'Provvedimento del . di A.V. SRL')
    def test_verified_single_company_and_numeric_brand(self):
        row=scan('Stabilimento QUINVERDE e carta Q8',['QUINVERDE'],memory=Memory(names={'QUINVERDE':'Q.','Q8':'Q.'}))
        self.assertEqual(row.render(),'Stabilimento Q. e carta Q.')
    def test_organization_without_company_form_is_a_review_case(self):
        row=scan('a carico di ASD NUOVA SCUOLA',['ASD NUOVA SCUOLA'])
        self.assertEqual(row.render(),'a carico di ASD NUOVA SCUOLA');self.assertTrue(row.unresolved())
    def test_company_brand_is_shortened(self):
        row=scan('SCIA QUINVERDE',['QUINVERDE SRL']);self.assertEqual(row.render(),'SCIA Q.')
    def test_company_compact_variant(self):
        row=scan('Nota LagoVerdeSpA',['Lago Verde S.p.A.']);self.assertNotIn('LagoVerde',row.render())
    def test_company_suffix_keeps_surrounding_prose(self):
        row=scan('Convenzione "ALFA VERDE SRL" del 20/12/2026')
        self.assertEqual(row.render(),'Convenzione "A.V. SRL" del 20/12/2026')
    def test_codes_and_numbers_not_reduced(self):
        row=scan('Fattura 26/91/CDDPA del 30-09-2026 tot. 755,83')
        self.assertEqual(row.render(),row.record['oggetto'])
    def test_common_phrases_never_auto_redacted_by_model(self):
        for phrase in ['REVISIONE VEICOLO','LATO SINISTRO','AFFISSIONE STRISCIONE PUBBLICITARIO','CLASSE DI LEVA','QUINZANO AL KM','PARLIAMO OVUNQUE DELLA VIOLENZA SULLE DONNE']:
            row=scan(phrase,second=FakeSecond([(phrase,'person')]))
            self.assertEqual(row.render(),phrase)
    def test_single_model_guess_requires_explicit_decision(self):
        row=scan('Elisa Fontanelli',second=FakeSecond([('Elisa Fontanelli','person')]))
        self.assertEqual(row.render(),'Elisa Fontanelli');self.assertEqual(row.unresolved(),1)
        row.choose(0,'apply');self.assertEqual(row.render(),'E.F.');row.approve();self.assertTrue(row.approved)
    def test_no_global_propagation_from_model(self):
        texts=[record('Evento FIERA VERDE',number='1'),record('Oggetto FIERA VERDE',number='2')]
        class Model:
            def entities_many(self,texts,progress=None):return [[{'start':7,'end':18,'label':'company'}],[]]
        rows=analyze(texts,PUBLIC,second=Model());self.assertEqual(rows[1].render(),'Oggetto FIERA VERDE');self.assertFalse(rows[1].proposals)
    def test_model_span_does_not_swallow_convention(self):
        phrase='Convenzione ALFA VERDE SRL'
        row=scan(phrase,['ALFA VERDE SRL'],second=FakeSecond([(phrase,'company')]))
        self.assertEqual(row.render(),'Convenzione A.V. SRL')
    def test_models_only_analyze_original_not_initials(self):
        seen=[]
        class Model:
            def entities_many(self,texts,progress=None):seen.extend(texts);return [[] for s in texts]
        row=scan('sig. Paolo Verdi',second=Model());self.assertEqual(seen,['sig. Paolo Verdi']);self.assertEqual(row.render(),'sig. P.V.')
    def test_unicode_offsets_with_model(self):
        s='😀 Messaggio per Elisa Fontanelli'
        row=scan(s,second=FakeSecond([('Elisa Fontanelli','person')]))
        row.choose(0,'apply');self.assertEqual(row.render(),'😀 Messaggio per E.F.')
    def test_common_word_surname_is_not_discarded(self):
        row=scan('sig. Carlo Marzo');self.assertTrue(any('Carlo Marzo'==p.name for p in row.proposals))
    def test_common_entity_is_preserved(self):
        row=scan('Conferenza NAZIONALE AMIANTO');self.assertEqual(row.render(),'Conferenza NAZIONALE AMIANTO')

class ReviewTests(unittest.TestCase):
    def test_no_finding_is_not_an_approval(self):
        row=scan('Nessuna proposta');self.assertFalse(row.approved)
        with self.assertRaises(ValueError):export_rows([row])
    def test_pending_prevents_approval(self):
        row=scan('Elisa Fontanelli',second=FakeSecond([('Elisa Fontanelli','person')]))
        with self.assertRaises(ValueError):row.approve()
    def test_explicit_keep_resolves_uncertainty(self):
        row=scan('CONCERTO AL BUIO',second=FakeSecond([('CONCERTO AL BUIO','company')]))
        for i,p in enumerate(row.proposals):row.choose(i,'keep')
        row.approve();self.assertEqual(export_rows([row])[0][3],'CONCERTO AL BUIO')
    def test_manual_span_and_unaffected_text(self):
        row=scan('Pratica Fontanelli, via Roma 12');start=row.record['oggetto'].index('Fontanelli')
        row.manual_span(start,start+10);row.approve()
        self.assertEqual(row.render(),'Pratica F., via Roma 12')
    def test_manual_change_revokes_approval(self):
        row=scan('Pratica Fontanelli');row.approve();row.manual_span(8,18);self.assertFalse(row.approved)
    def test_overlap_blocked(self):
        row=ReviewRow(record('Paolo Verdi'),[Proposal(0,11,'Paolo Verdi','test','apply'),Proposal(6,11,'Verdi','test')])
        with self.assertRaises(ValueError):row.choose(1,'apply')
    def test_mutated_span_fails_closed(self):
        row=ReviewRow(record('Paolo Verdi'),[Proposal(0,11,'Paolo Berti','test','apply')])
        with self.assertRaises(ValueError):row.render()
    def test_approval_scoped_to_exact_record(self):
        row=scan('sig. Paolo Verdi');row.approve();memory=approvals([row])
        r=analyze([record('sig. Paolo Verdi')],PUBLIC,memory=memory)[0];self.assertTrue(r.approved);self.assertEqual(r.render(),'sig. P.V.')
        for r in [record('sig. Paolo Verdi!'),record('sig. Paolo Verdi',number='2'),record('sig. Paolo Verdi',date='02/10/2026')]:
            self.assertFalse(analyze([r],PUBLIC,memory=memory)[0].approved)
    def test_normalized_date_reuses_same_approval(self):
        self.assertEqual(fingerprint(record('Test')),fingerprint(record('Test',date='01-10-2026')))
    def test_persistence_only_contains_approved_rows(self):
        a=scan('sig. Paolo Verdi');a.approve();b=scan('Nuovo oggetto')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'approvazioni.json';save_memory(p,[a,b]);memory=load_memory(p)
            self.assertEqual(len(memory),1);self.assertNotIn(fingerprint(b.record),memory)
    def test_corrupted_memory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text('{"versione":4,"righe":{"bad":{}}}')
            with self.assertRaises(ValueError):load_memory(p)
    def test_duplicate_numbers_rejected(self):
        with self.assertRaises(ValueError):analyze([record('A'),record('B')],PUBLIC)
    def test_reviewed_names_persist_and_memory_copy_keeps_them(self):
        row=scan('sig. Paolo Verdi');row.approve()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ok.json';save_memory(p,[row]);m=Memory(load_memory(p));self.assertEqual(m.names['Paolo Verdi'],'P.V.')
    def test_incomplete_detector_results_block_analysis(self):
        class Bad:
            def entities_many(self,texts,progress=None):return []
        with self.assertRaises(ValueError):scan('Test',second=Bad())
    def test_manual_numbers_rejected(self):
        row=scan('Fontanelli 123')
        with self.assertRaises(ValueError):row.manual_span(0,14)

class FormatTests(unittest.TestCase):
    def test_raw_html_only_four_columns(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.xls';p.write_text('<table><tr><th>Numero</th><th>Tipo</th><th>Data</th><th>Mittente</th><th>Oggetto</th><th>Stato</th></tr><tr><td>007</td><td>Arrivo</td><td>01/10/2026</td><td>FONTANELLI ELISA</td><td>Richiesta Elisa Fontanelli</td><td>Aperto</td></tr></table>')
            records,_=read_records(candidates(p)[0]);row=analyze(records,PUBLIC)[0];row.approve();values=export_rows([row])
            self.assertEqual(values,[['007','Arrivo','01/10/2026','Richiesta E.F.']])
    def test_xlsx_literals_and_pdf(self):
        from openpyxl import load_workbook
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as d:
            row=scan('=HYPERLINK("https://example.test")');row.approve();values=export_rows([row]);x=Path(d)/'a.xlsx';p=Path(d)/'a.pdf'
            export_xlsx(x,values,'Protocollo');export_pdf(p,values,'Protocollo')
            w=load_workbook(x);self.assertEqual(w.active['D3'].data_type,'s');self.assertEqual(w.active.max_column,4)
            self.assertIn('HYPERLINK',''.join(pg.extract_text() for pg in PdfReader(p).pages))
    def test_csv_separator(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.csv';p.write_text('Numero;Tipo;Data;Oggetto\n1;Arrivo;01/10/2026;"Oggetto; altro"\n')
            records,_=read_records(candidates(p)[0]);self.assertEqual(records[0]['oggetto'],'Oggetto; altro')

if __name__=='__main__':unittest.main()
