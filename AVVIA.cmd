@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Protocollo Locale 4.3 - Python 3.12 e avvio
set "PROTO_MODE="
if /I "%~1"=="--modelli" set "PROTO_MODE=--modelli"
if /I "%~2"=="--modelli" set "PROTO_MODE=--modelli"
if /I "%~1"=="--console" goto console
start "Protocollo Locale 4.3 - Avvio" "%ComSpec%" /d /k call "%~f0" --console %PROTO_MODE%
if not errorlevel 1 exit /b 0
:console
cd /d "%~dp0"
if errorlevel 1 goto foldererror
echo ============================================================
echo Protocollo Locale 4.3 - REQUISITO: Python 3.12 a 64 bit.
echo Se manca, verra scaricato e installato automaticamente.
echo Serve Internet per la prima configurazione.
echo ============================================================
if not exist "avvio.py" goto filesmissing
> "ultimo_avvio_cmd.log" echo Protocollo Locale 4.3 - %date% %time%
>> "ultimo_avvio_cmd.log" echo Cartella: "%CD%"
>> "ultimo_avvio_cmd.log" ver
set "PROTO_STATUS=%TEMP%\ProtocolloLocale_%RANDOM%_%RANDOM%.ok"
call :discover
if not errorlevel 1 goto launch

echo Python 3.12 non e disponibile: inizio installazione automatica.
echo Le altre versioni di Python e i vecchi ambienti vengono conservati.
>> "ultimo_avvio_cmd.log" echo Installazione automatica Python 3.12 richiesta.
where pymanager >nul 2>&1
if errorlevel 1 goto try_py_manager
echo Download e installazione con Python Install Manager...
call pymanager install 3.12
>> "ultimo_avvio_cmd.log" echo Codice installazione pymanager: %errorlevel%
call :discover
if not errorlevel 1 goto launch
:try_py_manager
where py >nul 2>&1
if errorlevel 1 goto try_winget
call py help install >nul 2>&1
if errorlevel 1 goto try_winget
echo Download e installazione di Python 3.12 con il gestore Python...
call py install 3.12
>> "ultimo_avvio_cmd.log" echo Codice installazione py: %errorlevel%
call :discover
if not errorlevel 1 goto launch
:try_winget
where winget >nul 2>&1
if errorlevel 1 goto installfailed
echo Download e installazione di Python 3.12 per questo utente...
call winget install --exact --id Python.Python.3.12 --source winget --scope user --architecture x64 --accept-package-agreements --accept-source-agreements --disable-interactivity
>> "ultimo_avvio_cmd.log" echo Codice installazione winget: %errorlevel%
call :discover
if errorlevel 1 goto installfailed
:launch
echo Python 3.12 trovato. Configurazione e avvio del programma...
if "%PROTO_LAUNCHER%"=="1" goto launch_py
call "%PROTO_EXE%" -u avvio.py %PROTO_MODE% --startup-status "%PROTO_STATUS%"
goto checked
:launch_py
call py -3.12 -u avvio.py %PROTO_MODE% --startup-status "%PROTO_STATUS%"
:checked
>> "ultimo_avvio_cmd.log" echo Codice avvio: %errorlevel%
if exist "%PROTO_STATUS%" goto success
echo AVVIO NON CONFERMATO. Leggi i dettagli sopra.
echo Registri: diagnostica_avvio.log, avvio.log e ultimo_avvio_cmd.log.
pause
exit /b 1
:installfailed
echo INSTALLAZIONE AUTOMATICA NON RIUSCITA.
echo Il gestore Python o winget potrebbero mancare, oppure la rete impedisce il download.
echo Il programma richiede Python 3.12 a 64 bit, con Tcl/Tk.
echo Dettagli: ultimo_avvio_cmd.log e messaggi sopra. Non serve riavviare il PC.
echo Installazione manuale ufficiale: https://www.python.org/downloads/windows/
>> "ultimo_avvio_cmd.log" echo ESITO: Python 3.12 non disponibile dopo i tentativi automatici.
pause
exit /b 1
:filesmissing
echo Mancano i file del programma. Estrai TUTTO lo ZIP prima di avviare.
pause
exit /b 1
:foldererror
echo Impossibile aprire la cartella. Estrai lo ZIP in una cartella locale.
pause
exit /b 1
:success
echo OPERAZIONE COMPLETATA E CONFERMATA. Per chiudere la console scrivi exit.
>> "ultimo_avvio_cmd.log" echo ESITO: operazione completata e confermata.
exit /b 0
:discover
set "PROTO_EXE="
set "PROTO_LAUNCHER=0"
call :probe_file ".venv312\Scripts\python.exe"
if not errorlevel 1 exit /b 0
call :probe_file ".venv_v4\Scripts\python.exe"
if not errorlevel 1 exit /b 0
call :probe_file ".venv\Scripts\python.exe"
if not errorlevel 1 exit /b 0
where py >nul 2>&1
if errorlevel 1 goto discover_local
call py -3.12 -c "import sys,struct,tkinter; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8" >> "ultimo_avvio_cmd.log" 2>&1
if errorlevel 1 goto discover_local
set "PROTO_LAUNCHER=1"
exit /b 0
:discover_local
call :probe_file "%LocalAppData%\Programs\Python\Python312\python.exe"
if not errorlevel 1 exit /b 0
call :probe_file "%ProgramFiles%\Python312\python.exe"
if not errorlevel 1 exit /b 0
call :probe_file "%LocalAppData%\Python\bin\python3.12.exe"
if not errorlevel 1 exit /b 0
exit /b 1
:probe_file
if not exist "%~1" exit /b 1
call "%~1" -c "import sys,struct,tkinter; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8" >> "ultimo_avvio_cmd.log" 2>&1
if errorlevel 1 exit /b 1
set "PROTO_EXE=%~1"
>> "ultimo_avvio_cmd.log" echo Python 3.12 valido: "%~1"
exit /b 0
