"""Entry point hosted inside ProtocolloLocale.exe; no separate Python GUI process."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
# Isolated mode deliberately omits the working directory from sys.path.
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1')

def main():
    import contextlib,traceback,datetime
    with (ROOT/'avvio.log').open('a',encoding='utf-8',buffering=1) as log:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            print('\n=== Protocollo Locale 4.3 '+datetime.datetime.now().isoformat()+' ===')
            try:
                if '--autotest' in sys.argv:
                    import openpyxl,reportlab,xlrd,tkinter
                    import interfaccia_v4,motore_v4
                    root=tkinter.Tk();root.withdraw();root.update();root.destroy()
                    (ROOT/'autotest.ok').write_text('Python 3.12, Tk e componenti pronti',encoding='utf-8')
                    return 0
                from interfaccia_v4 import App
                app=App()
                if '--verifica-gui' in sys.argv:
                    app.root.after(1500,app.root.destroy)
                app.root.mainloop()
                return 0
            except Exception:
                traceback.print_exc()
                try:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(None,'Avvio non riuscito. Consulta avvio.log nella cartella del programma oppure riesegui il Setup.','Protocollo Locale',16)
                except Exception:pass
                return 1

if __name__=='__main__':raise SystemExit(main())
