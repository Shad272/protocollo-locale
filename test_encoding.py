import unittest,tempfile
from pathlib import Path
from protocollo import repair_encoding,export_xlsx,export_pdf
from motore_v4 import ReviewRow,Proposal,load_memory
class EncodingTests(unittest.TestCase):
 def test_sequences_and_unchanged_text(self):
  for good in ['attività','società','è già così: € 100,00','L’apostrofo – prova','Ã isolata, A. B. S.r.l., via Roma 12']:
   self.assertEqual(repair_encoding(good),good)
  for good in ['attività','società','è già così: € 100,00','L’apostrofo – prova']:
   bad=good.encode().decode('cp1252')
   self.assertEqual(repair_encoding(bad),good)
   self.assertEqual(repair_encoding(bad.encode().decode('cp1252')),good)
 def test_cached_reference(self):
  memory=load_memory(Path(__file__).parent/'riferimento_approvato.json')
  bad=[v['oggetto'] for v in memory.values() if 'attivitÃ' in v['oggetto']]
  self.assertEqual(len(bad),1)
  row=ReviewRow({},approved=True,approved_text=bad[0])
  self.assertIn('attività',row.render());self.assertNotIn('Ã',row.render())
 def test_spans_preserved(self):
  s='attivitÃ\xa0 Mario Rossi';start=s.index('Mario')
  row=ReviewRow({'oggetto':s},[Proposal(start,len(s),'Mario Rossi','test','apply')])
  self.assertEqual(row.render(),'attività M.R.')
  self.assertEqual(row.record['oggetto'],s)
 def test_both_exports(self):
  import openpyxl,pdfplumber
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);rows=[['15224','Arrivo','16/10/2026','Bando attivitÃ\xa0 di redazione']]
   export_xlsx(p/'a.xlsx',rows,'Protocollo');export_pdf(p/'a.pdf',rows,'Protocollo')
   self.assertEqual(openpyxl.load_workbook(p/'a.xlsx').active['D3'].value,'Bando attività di redazione')
   with pdfplumber.open(p/'a.pdf') as pdf:self.assertIn('attività',pdf.pages[0].extract_text())
