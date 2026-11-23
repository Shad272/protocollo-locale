"""Integration tests for explicit, row-scoped output corrections (requires a display)."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from motore_v4 import Memory,analyze,export_rows,fingerprint,load_memory
from protocollo import PUBLIC

@unittest.skipUnless(sys.platform=='win32' or os.environ.get('DISPLAY'),'Richiede interfaccia Tk o display virtuale')
class ManualOutputTests(unittest.TestCase):
    def setUp(self):
        from interfaccia_v4 import App
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.errors=[];self.patches=[patch('interfaccia_v4.messagebox.showerror',side_effect=lambda *a,**k:self.errors.append(a)),patch('interfaccia_v4.messagebox.showinfo'),patch('interfaccia_v4.messagebox.askyesno',return_value=True)]
        for p in self.patches:p.start()
        self.app=App()
        self.records=[dict(numero='1',tipo='Arrivo',data='01/10/2026',oggetto='Domanda del sig. Mario Rossi - Via Roma 12',parties=[]),dict(numero='2',tipo='Arrivo',data='01/10/2026',oggetto='Comunicazione del sig. Luca Bianchi',parties=[])]
        self.snapshot=json.dumps(self.records,sort_keys=True)
        values=['Domanda del sig. M.R. - Via Roma 12','Comunicazione del sig. L.B.']
        self.app.memory=Memory({fingerprint(r):{'oggetto':v,'origine':'Riferimento approvato'} for r,v in zip(self.records,values)})
        self.app.records=self.records;self.app.rows=analyze(self.records,PUBLIC,memory=self.app.memory)
        self.app.source=self.folder/'originale.xlsx';self.app.source.write_bytes(b'ORIGINALE')
        self.app.title.set('PROVA');self.app.populate();self.app.tree.selection_set('0');self.app.root.update();self.app.select()
    def tearDown(self):
        for timer in self.app.root.tk.call('after','info'):self.app.root.after_cancel(timer)
        self.app.root.destroy();self.temp.cleanup()
        for p in reversed(self.patches):p.stop()
    def write(self,text):
        self.app.result.delete('1.0','end');self.app.result.insert('1.0',text);self.app.root.update()
    def choose(self,index):
        self.app.tree.selection_set(str(index));self.app.select();self.app.root.update()
    def test_cached_output_accepts_paste_and_blocks_unsaved_export(self):
        self.assertEqual(self.app.result.cget('state'),'normal')
        self.app.root.clipboard_clear();self.app.root.clipboard_append('Testo incollato a mano')
        self.app.result.delete('1.0','end');self.app.result.event_generate('<<Paste>>');self.app.root.update()
        self.assertEqual(self.app.result.get('1.0','end-1c'),'Testo incollato a mano')
        with patch('interfaccia_v4.filedialog.askdirectory') as dialog:self.app.export('both');dialog.assert_not_called()
        self.assertIn('non salvate',self.errors[-1][1])
        self.assertEqual(self.app.rows[0].render(),'Domanda del sig. M.R. - Via Roma 12')
    def test_confirm_is_local_and_reusable_from_saved_json(self):
        text='Domanda corretta di M.R. - Via Roma 12'
        other=self.app.rows[1].render();self.write(text);self.assertTrue(self.app.save_output())
        self.assertEqual(export_rows(self.app.rows)[0][3],text)
        self.assertEqual(self.app.rows[1].render(),other)
        self.assertEqual(json.dumps(self.records,sort_keys=True),self.snapshot)
        dest=self.folder/'approvazioni.json'
        with patch('interfaccia_v4.filedialog.asksaveasfilename',return_value=str(dest)):self.app.save_memory()
        restored=analyze(self.records,PUBLIC,memory=load_memory(dest))
        self.assertEqual(export_rows(restored)[0][3],text)
        self.assertFalse(self.app.manual_output_changes)
    def test_drafts_survive_navigation_and_cancel_is_local(self):
        self.write('Prima bozza');self.choose(1);self.write('Seconda bozza');self.choose(0)
        self.assertEqual(self.app.result.get('1.0','end-1c'),'Prima bozza')
        self.app.discard_output();self.app.root.update()
        self.assertEqual(self.app.result.get('1.0','end-1c'),'Domanda del sig. M.R. - Via Roma 12')
        self.choose(1);self.assertEqual(self.app.result.get('1.0','end-1c'),'Seconda bozza')
    def test_empty_output_does_not_replace_a_cached_result(self):
        self.write('  ');self.assertFalse(self.app.save_output())
        self.assertEqual(self.app.rows[0].render(),'Domanda del sig. M.R. - Via Roma 12')
        self.assertTrue(self.app.output_drafts)
    def test_review_button_confirms_typed_output(self):
        self.app.rows[1].approved=False
        self.write('Correzione confermata dal pulsante di verifica');self.app.approve();self.app.root.update()
        self.assertEqual(self.app.rows[0].render(),'Correzione confermata dal pulsante di verifica')
        self.assertTrue(self.app.rows[0].approved);self.assertEqual(self.app.current,1)
    def test_excel_and_pdf_contain_the_confirmed_correction(self):
        text='Domanda rettificata - Via Roma 12'
        self.write(text);self.app.save_output()
        with patch('interfaccia_v4.filedialog.askdirectory',return_value=str(self.folder)):self.app.export('both')
        deadline=time.monotonic()+15
        while self.app.busy and time.monotonic()<deadline:self.app.root.update();time.sleep(.02)
        self.assertFalse(self.app.busy);self.assertFalse(self.errors)
        import openpyxl
        rows=list(openpyxl.load_workbook(self.folder/'PROVA.xlsx',data_only=True).active.values)
        self.assertEqual(rows[2][3],text);self.assertEqual(rows[3][3],'Comunicazione del sig. L.B.')
        import pdfplumber
        with pdfplumber.open(self.folder/'PROVA.pdf') as pdf:content='\n'.join(p.extract_text() or '' for p in pdf.pages)
        self.assertIn(text,content);self.assertEqual(self.app.source.read_bytes(),b'ORIGINALE')

if __name__=='__main__':unittest.main()
