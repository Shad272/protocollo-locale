import io
from pathlib import Path
import sys
import tempfile
import unittest
from attivita import run_command
from secondo_modello import SecondRecognizer

class ActivityTests(unittest.TestCase):
    def test_spinner_runs_and_logs_output(self):
        with tempfile.TemporaryDirectory() as d:
            stream=io.StringIO();log=Path(d)/'run.log'
            code=run_command([sys.executable,'-c','import time; print("ready"); time.sleep(.1)'],'Caricamento',log,stream,.01)
            self.assertEqual(code,0);self.assertIn('\r[',stream.getvalue());self.assertIn('[OK]',stream.getvalue());self.assertIn('ready',log.read_text())
    def test_failed_command_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as d:
            stream=io.StringIO();code=run_command([sys.executable,'-c','raise SystemExit(7)'],'Test',Path(d)/'log',stream,.01)
            self.assertEqual(code,7);self.assertIn('[ERRORE]',stream.getvalue())
    def test_long_cells_are_not_silently_truncated(self):
        class Model:
            def batch_predict_entities(self,texts,labels,threshold):
                return [[{'start':s.index('Elisa Rossi'),'end':s.index('Elisa Rossi')+11,'label':'person'}] if 'Elisa Rossi' in s else [] for s in texts]
        recognizer=SecondRecognizer(Model());s='testo '*320+'Elisa Rossi'
        entities=recognizer.entities_many([s])[0]
        self.assertTrue(any(s[e['start']:e['end']]=='Elisa Rossi' for e in entities))
    def test_model_failure_does_not_poison_cache(self):
        class Model:
            def batch_predict_entities(self,texts,labels,threshold):raise RuntimeError('inference failed')
        r=SecondRecognizer(Model())
        with self.assertRaises(RuntimeError):r.entities_many(['Una persona'])
        self.assertFalse(r.cache)

if __name__=='__main__':unittest.main()
