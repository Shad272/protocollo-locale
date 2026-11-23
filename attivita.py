"""Run a local command with a live terminal spinner and a private local log."""
import itertools
import os
from pathlib import Path
import subprocess
import sys
import time

def run_command(command, label='Operazione in corso', log_path=None, stream=None, delay=.12):
    stream=stream or sys.stdout
    log_path=Path(log_path or Path(__file__).with_name('installazione.log'))
    log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open('ab',buffering=0) as log:
        log.write(('\n--- '+label+' ---\n').encode('utf-8'))
        try:process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        except OSError as e:
            stream.write('\nAvvio non riuscito: '+str(e)+'\n');return 1
        started=time.monotonic();frames=itertools.cycle('|/-\\')
        try:
            while process.poll() is None:
                elapsed=int(time.monotonic()-started)
                stream.write(f'\r[{next(frames)}] {label}  {elapsed//60:02d}:{elapsed%60:02d}   ');stream.flush();time.sleep(delay)
        except KeyboardInterrupt:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            stream.write('\nOperazione interrotta.\n');return 130
        code=process.wait()
        stream.write(f'\r[{"OK" if code==0 else "ERRORE"}] {label}'+ ' '*24+'\n');stream.flush()
    if code:
        stream.write('Dettagli in '+str(log_path)+'\n')
        try:stream.write(log_path.read_text(encoding='utf-8',errors='replace')[-2200:]+'\n')
        except OSError:pass
    return code

if __name__=='__main__':
    if len(sys.argv)<4 or '--' not in sys.argv:
        raise SystemExit('Uso: attivita.py "Etichetta" -- comando argomenti')
    index=sys.argv.index('--')
    raise SystemExit(run_command(sys.argv[index+1:],sys.argv[1]))
