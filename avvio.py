"""Bootstrap Windows: ambiente compatibile, rotellina, errori leggibili."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import contextlib
import datetime
import traceback
from attivita import run_command

ROOT=Path(__file__).resolve().parent

class Tee:
    """Keep diagnostics both on screen and in a UTF-8 local file."""
    def __init__(self,console,log):self.console=console;self.log=log
    def write(self,value):
        self.log.write(value);self.log.flush()
        if self.console is not None:
            try:self.console.write(value);self.console.flush()
            except UnicodeEncodeError:
                self.console.write(value.encode(self.console.encoding or 'utf-8',errors='replace').decode(self.console.encoding or 'utf-8'))
        return len(value)
    def flush(self):
        self.log.flush()
        if self.console is not None:self.console.flush()

def wait_for_interface(process,ready,timeout=90,grace=.8,stream=None):
    import time,itertools
    stream=stream or sys.stdout;started=time.monotonic();frames=itertools.cycle('|/-\\')
    while not ready.exists():
        if process.poll() is not None:raise RuntimeError('Interfaccia terminata prima di avviarsi.')
        elapsed=time.monotonic()-started
        if elapsed>=timeout:raise RuntimeError('La finestra non ha confermato il caricamento. Consulta avvio.log prima di riprovare.')
        stream.write(f'\r[{next(frames)}] Caricamento interfaccia {int(elapsed):02d}s   ');stream.flush();time.sleep(.12)
    # A ready file alone does not prove the Tk process survived initialization.
    deadline=time.monotonic()+grace
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('La finestra si e chiusa subito dopo il caricamento.')
        time.sleep(.05)
    if process.poll() is not None:raise RuntimeError('La finestra si e chiusa subito dopo il caricamento.')
    stream.write('\r[OK] Interfaccia pronta.                       \n');stream.flush()

def compatible(exe):
    try:
        return subprocess.run([str(exe),'-c','import sys,struct; assert sys.version_info[:2] in ((3,12),) and struct.calcsize("P")==8'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    except OSError:return False

def environment():
    for name in ('.venv312','.venv_v4','.venv'):
        exe=ROOT/name/'Scripts/python.exe'
        if exe.exists() and compatible(exe):return exe
    if sys.version_info[:2] not in ((3,12),) or struct.calcsize('P')!=8:
        raise RuntimeError('Serve Python 3.12 a 64 bit, con Tcl/Tk. Riapri AVVIA.cmd: il launcher installa automaticamente il requisito mancante. Gli ambienti precedenti non vengono cancellati.')
    folder=ROOT/'.venv312'
    if folder.exists():raise RuntimeError('La cartella .venv312 non contiene un ambiente Python 3.12 compatibile. Rinominala in .venv312_precedente e riapri AVVIA.cmd.')
    if run_command([sys.executable,'-m','venv',str(folder)],'Preparazione ambiente locale'):raise RuntimeError('Creazione ambiente non riuscita. Dettagli in installazione.log.')
    return folder/'Scripts/python.exe'

def ensure_base(exe):
    if subprocess.run([str(exe),'-c','import tkinter'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        raise RuntimeError('A questa installazione Python manca Tcl/Tk. Apri il programma di installazione di Python 3.12, scegli Modify e includi Tcl/Tk and IDLE.')
    code=subprocess.run([str(exe),'-c','import openpyxl,reportlab,xlrd'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
    if code:
        if run_command([str(exe),'-m','pip','install','--only-binary=:all:','-r',str(ROOT/'requirements.txt')],'Installazione componenti di base'):
            raise RuntimeError('Installazione non riuscita. Controlla connessione e installazione.log. Nessun documento e stato inviato.')

def models(exe):
    tasks=[
        ('Aggiornamento installatore',['-m','pip','install','--upgrade','pip']),
        ('Installazione riconoscitore italiano',['-m','pip','install','--only-binary=:all:','spacy==3.8.16']),
        ('Download modello italiano',['-m','spacy','download','it_core_news_lg']),
        ('Installazione motore CPU',['-m','pip','install','--only-binary=:all:','torch','--index-url','https://download.pytorch.org/whl/cpu']),
        ('Installazione secondo riconoscitore',['-m','pip','install','gliner==0.2.24','transformers>=4.49,<5']),
        ('Download secondo modello e tokenizer',[str(ROOT/'prepara_modelli.py'),'--secondo']),
        ('Verifica offline dei due modelli',[str(ROOT/'prepara_modelli.py'),'--verifica']),
    ]
    print('Download iniziale di software e modelli. Servono alcuni GB liberi. Nessun documento viene letto o inviato.')
    for label,args in tasks:
        if run_command([str(exe),*args],label):raise RuntimeError('Riconoscimento non installato completamente. Dettagli in installazione.log. Per riprovare riapri ATTIVA_RICONOSCIMENTO.cmd.')
    print('[OK] Entrambi i modelli installati. Riapri la tabella nel programma.')

def main():
    os.chdir(ROOT)
    exe=environment();ensure_base(exe)
    if '--modelli' in sys.argv:models(exe);return
    print('[OK] Avvio Protocollo Locale 4.3. I modelli sono facoltativi per le righe identiche al riferimento approvato.')
    import tempfile
    fd,path=tempfile.mkstemp(prefix='.interfaccia_v4_',suffix='.ready',dir=ROOT);os.close(fd)
    ready=Path(path);ready.unlink()
    log=(ROOT/'avvio.log').open('ab')
    # python.exe + redirected handles keeps tracebacks available even on Windows.
    # CREATE_NO_WINDOW prevents an extra console for the GUI subprocess.
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0
    try:process=subprocess.Popen([str(exe),'-u',str(ROOT/'interfaccia_v4.py'),'--ready-file',str(ready)],stdout=log,stderr=log,creationflags=flags)
    finally:log.close()
    try:wait_for_interface(process,ready)
    except Exception:
        app_log=ROOT/'avvio.log'
        if app_log.exists():print('\nUltimi dettagli della finestra:\n'+app_log.read_text(encoding='utf-8',errors='replace')[-5000:])
        raise
    finally:ready.unlink(missing_ok=True)

def entrypoint(args=None):
    args=list(sys.argv[1:] if args is None else args)
    marker=None
    if '--startup-status' in args:
        index=args.index('--startup-status')
        if index+1>=len(args):print('Manca il percorso di conferma avvio.');return 1
        marker=Path(args[index+1])
    try:
        with (ROOT/'diagnostica_avvio.log').open('a',encoding='utf-8',buffering=1) as log:
            with contextlib.redirect_stdout(Tee(sys.stdout,log)),contextlib.redirect_stderr(Tee(sys.stderr,log)):
                print('\n=== Protocollo Locale 4.3 - '+datetime.datetime.now().isoformat(timespec='seconds')+' ===')
                print('Python: '+sys.executable);print('Versione: '+sys.version.replace('\n',' '));print('Cartella: '+str(ROOT))
                try:
                    main()
                    if marker is not None:marker.write_text('modelli pronti' if '--modelli' in args else 'interfaccia pronta',encoding='utf-8')
                    return 0
                except Exception:
                    traceback.print_exc()
                    print('\nAvvio non completato. I dettagli restano in diagnostica_avvio.log e avvio.log. Non serve riavviare il PC.')
                    return 1
    except OSError as e:
        print('Impossibile scrivere il registro nella cartella del programma: '+str(e));return 1

if __name__=='__main__':
    raise SystemExit(entrypoint())
