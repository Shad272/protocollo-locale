"""Reproducible Windows cross-build on Linux: native launcher + NSIS + private CPython."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile

SOURCE=Path(__file__).resolve().parent.parent
BUILD=Path(os.environ.get('PROTOCOLLO_BUILD_DIR',SOURCE/'build')).resolve()
TOOLS=Path(os.environ.get('PROTOCOLLO_TOOL_ROOT','/usr')).resolve()
MANIFEST=json.loads((SOURCE/'compilazione/componenti.json').read_text())

def tool(name):
    override=os.environ.get('PROTOCOLLO_'+name.upper().replace('-','_'))
    found=override or shutil.which(name) or str(TOOLS/'bin'/name)
    if not Path(found).exists():raise RuntimeError('Strumento mancante: '+name)
    return found

def run(args,**kw):
    print('> '+' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,**kw)

def main():
    BUILD.mkdir(parents=True,exist_ok=True)
    downloads=BUILD/'downloads';downloads.mkdir(exist_ok=True)
    env=dict(os.environ);env['PATH']=str(TOOLS/'bin')+os.pathsep+env.get('PATH','')
    env['NSISDIR']=str(TOOLS/'share/nsis') if (TOOLS/'share/nsis').exists() else env.get('NSISDIR','')
    env['LD_LIBRARY_PATH']=str(TOOLS/'lib/x86_64-linux-gnu')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    # Package names and hashes are locked to this release.
    wheelitems=[f for f in MANIFEST['files'] if f['name'].startswith('wheels/')]
    wheel_dir=downloads/'wheels';wheel_dir.mkdir(exist_ok=True)
    versions=[]
    for f in wheelitems:
        parts=Path(f['name']).name.split('-');versions.append(parts[0]+'=='+parts[1])
    if any(not (downloads/f['name']).exists() for f in wheelitems):
        run([sys.executable,'-m','pip','download','--no-deps','--only-binary=:all:','--platform','win_amd64','--python-version','312','--implementation','cp','--abi','cp312','--dest',wheel_dir,*versions])
    for item in MANIFEST['files']:
        p=downloads/item['name'];p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            if 'url' not in item:raise RuntimeError('Wheel mancante: '+str(p))
            urllib.request.urlretrieve(item['url'],p)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('SHA-256 non corrispondente: '+str(p))
    stage=BUILD/'staging'
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir();runtime=stage/'runtime';runtime.mkdir()
    for msi in sorted((downloads/'msi').glob('*.msi')):
        run([tool('msiextract'),'-C',runtime,msi],env=env,stdout=subprocess.DEVNULL)
    packages=runtime/'Lib/site-packages';packages.mkdir(exist_ok=True)
    wheels=list(wheel_dir.glob('*.whl'))+list((runtime/'Lib/ensurepip/_bundled').glob('pip-*.whl'))
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as z:
            for info in z.infolist():
                if info.is_dir():continue
                parts=Path(info.filename).parts
                if any(p in ('..','') for p in parts):raise RuntimeError('Percorso wheel non valido')
                if parts[0].endswith('.data'):
                    if len(parts)<3 or parts[1] not in ('purelib','platlib'):continue
                    parts=parts[2:]
                dest=packages.joinpath(*parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
    files=['app_installata.py','installa_modelli.py','avvio.py','attivita.py','protocollo.py','riconoscimento.py','secondo_modello.py','motore_v4.py','interfaccia_v4.py','prepara_modelli.py','riferimento_approvato.json','requirements.txt','VERSIONE.txt','LEGGIMI_INSTALLER.txt']
    for name in files:shutil.copy2(SOURCE/name,stage/name)
    shutil.copy2(SOURCE/'compilazione/componenti.json',stage/'componenti-inclusi.json')
    if (SOURCE/'assets').exists():shutil.copytree(SOURCE/'assets',stage/'assets')
    rc=(SOURCE/'compilazione/versione.rc').read_text()
    if (SOURCE/'assets/app.ico').exists():rc+='\n101 ICON "'+str(SOURCE/'assets/app.ico')+'"\n'
    (BUILD/'versione.rc').write_text(rc)
    run([tool('x86_64-w64-mingw32-windres'),BUILD/'versione.rc','-o',BUILD/'versione.o'],env=env)
    run([tool('x86_64-w64-mingw32-gcc'),'-municode','-mwindows','-O2','-Wall','-Wextra',SOURCE/'compilazione/launcher.c',BUILD/'versione.o','-o',stage/'ProtocolloLocale.exe','-lshell32'],env=env)
    output=BUILD/'ProtocolloLocale_Setup.exe'
    run([tool('makensis'),'-V2','-DSTAGING='+str(stage),'-DOUTPUT='+str(output),SOURCE/'compilazione/setup.nsi'],env=env)
    print('Creato:',output)
    print('Compilazione completata. Il collaudo reale su Windows deve essere eseguito separatamente.')

if __name__=='__main__':main()
