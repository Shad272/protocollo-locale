import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import avvio

class Process:
    def __init__(self,code):self.code=code
    def poll(self):return self.code

class StartupTests(unittest.TestCase):
    def test_exit_zero_without_window_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'prima di avviarsi'):
                avvio.wait_for_interface(Process(0),Path(d)/'ready',stream=io.StringIO())
    def test_marker_does_not_hide_immediate_gui_crash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ready';p.touch()
            with self.assertRaisesRegex(RuntimeError,'chiusa subito'):
                avvio.wait_for_interface(Process(1),p,grace=.05,stream=io.StringIO())
    def test_live_gui_with_marker_is_confirmed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ready';p.touch();stream=io.StringIO()
            avvio.wait_for_interface(Process(None),p,grace=.01,stream=stream)
            self.assertIn('[OK]',stream.getvalue())
    def test_missing_marker_times_out(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'confermato'):
                avvio.wait_for_interface(Process(None),Path(d)/'ready',timeout=0,stream=io.StringIO())
    def test_complete_traceback_is_logged_and_no_success_marker(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);marker=root/'status';stream=io.StringIO()
            with patch.object(avvio,'ROOT',root),patch.object(avvio,'main',side_effect=RuntimeError('errore di prova')):
                with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):code=avvio.entrypoint(['--startup-status',str(marker)])
            self.assertEqual(code,1);self.assertFalse(marker.exists())
            log=(root/'diagnostica_avvio.log').read_text()
            self.assertIn('Traceback',log);self.assertIn('errore di prova',log);self.assertIn('errore di prova',stream.getvalue())
    def test_success_marker_only_after_completed_startup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);marker=root/'status'
            def ready():self.assertFalse(marker.exists())
            with patch.object(avvio,'ROOT',root),patch.object(avvio,'main',side_effect=ready),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(avvio.entrypoint(['--startup-status',str(marker)]),0)
            self.assertEqual(marker.read_text(),'interfaccia pronta')
    def test_missing_tk_is_reported_without_futile_pip_install(self):
        with patch.object(avvio.subprocess,'run',return_value=ProcessResult(1)) as run:
            with self.assertRaisesRegex(RuntimeError,'Tcl/Tk'):avvio.ensure_base(Path('python.exe'))
            self.assertEqual(run.call_count,1)
    def test_tee_keeps_diagnostics_on_screen_and_in_log(self):
        screen=io.StringIO();log=io.StringIO();tee=avvio.Tee(screen,log)
        tee.write('Configurazione: €\n');tee.flush();self.assertEqual(screen.getvalue(),log.getvalue())

class ProcessResult:
    def __init__(self,returncode):self.returncode=returncode

if __name__=='__main__':unittest.main()
