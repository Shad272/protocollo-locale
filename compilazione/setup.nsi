Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!ifndef STAGING
 !error "Indicare /DSTAGING=cartella-preparata e /DOUTPUT=file.exe"
!endif
Name "Protocollo Locale"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\ProtocolloLocale"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "4.3.0.0"
VIAddVersionKey /LANG=1040 "ProductName" "Protocollo Locale"
VIAddVersionKey /LANG=1040 "FileDescription" "Installazione Protocollo Locale"
VIAddVersionKey /LANG=1040 "FileVersion" "4.3.0"
VIAddVersionKey /LANG=1040 "LegalCopyright" "Protocollo Locale - componenti con licenze incluse"
!if /FileExists "${STAGING}\assets\app.ico"
 !define MUI_ICON "${STAGING}\assets\app.ico"
 !define MUI_UNICON "${STAGING}\assets\app.ico"
!endif
!define MUI_WELCOMEFINISHPAGE_BITMAP "${STAGING}\assets\setup-laterale.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${STAGING}\assets\setup-laterale.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "${STAGING}\assets\setup-intestazione.bmp"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Questo Setup installa Protocollo Locale e il runtime privato Python 3.12 a 64 bit con Excel e PDF. Non serve installare Python manualmente.$\r$\n$\r$\nI riconoscitori locali sono selezionati nella pagina successiva: il loro download richiede Internet, alcuni GB liberi e diversi minuti. I documenti restano sul PC.$\r$\n$\r$\nVersione 4.3."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ProtocolloLocale.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Apri Protocollo Locale"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Italian"

Function .onInit
 ${IfNot} ${AtLeastWin10}
  MessageBox MB_ICONSTOP "Serve Windows 10/11 a 64 bit."
  Abort
 ${EndIf}
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "Serve Windows 10/11 a 64 bit."
  Abort
 ${EndIf}
 System::Call 'kernel32::OpenMutexW(i 1048576, i 0, w "Local\ProtocolloLocale") p.r0'
 ${If} $0 != 0
  System::Call 'kernel32::CloseHandle(p r0)'
  MessageBox MB_ICONSTOP "Chiudi Protocollo Locale prima di installare o aggiornare."
  Abort
 ${EndIf}
FunctionEnd

Section "Programma, Python 3.12, Excel e PDF (obbligatorio)" secBase
 SectionIn RO
 SetShellVarContext current
 SetOutPath "$INSTDIR"
 File /r "${STAGING}\*"
 DetailPrint "Verifica del runtime, della finestra e dei componenti..."
 Delete "$INSTDIR\autotest.ok"
 ClearErrors
 ExecWait '"$INSTDIR\ProtocolloLocale.exe" --autotest' $0
 ${If} ${Errors}
  MessageBox MB_ICONSTOP "Impossibile avviare la verifica. Consulta avvio.log nella cartella del programma."
  SetErrorLevel 1
  Abort
 ${EndIf}
 ${If} $0 != 0
  MessageBox MB_ICONSTOP "Verifica non riuscita: il Setup non considera pronta questa installazione. Consulta avvio.log."
  SetErrorLevel 1
  Abort
 ${EndIf}
 IfFileExists "$INSTDIR\autotest.ok" +4
  MessageBox MB_ICONSTOP "Manca la conferma del runtime. Installazione interrotta: controlla avvio.log."
  SetErrorLevel 1
  Abort
 Delete "$INSTDIR\autotest.ok"
 WriteUninstaller "$INSTDIR\Disinstalla.exe"
 CreateDirectory "$SMPROGRAMS\Protocollo Locale"
 CreateShortcut "$SMPROGRAMS\Protocollo Locale\Protocollo Locale.lnk" "$INSTDIR\ProtocolloLocale.exe"
 CreateShortcut "$DESKTOP\Protocollo Locale.lnk" "$INSTDIR\ProtocolloLocale.exe"
 CreateShortcut "$SMPROGRAMS\Protocollo Locale\Attiva riconoscitori locali.lnk" "$INSTDIR\runtime\python.exe" '-u "$INSTDIR\installa_modelli.py"' "$INSTDIR\ProtocolloLocale.exe" 0
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale" "DisplayName" "Protocollo Locale"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale" "DisplayVersion" "4.3.0"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale" "UninstallString" '$\"$INSTDIR\Disinstalla.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale" "DisplayIcon" "$INSTDIR\ProtocolloLocale.exe"
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale" "NoRepair" 1
SectionEnd

Section "Riconoscitori italiani e multilingue (download Internet)" secModelli
 retry:
 ClearErrors
 ExecWait '"$INSTDIR\runtime\python.exe" -u "$INSTDIR\installa_modelli.py"' $0
 ${If} ${Errors}
  StrCpy $0 1
 ${EndIf}
 ${If} $0 != 0
  MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Download o verifica dei modelli non completati. Riprova oppure scegli Annulla per tenere il programma con revisione manuale. Potrai riprovare dal menu Start: Attiva riconoscitori locali." IDRETRY retry
 ${EndIf}
SectionEnd

Section "Uninstall"
 SetShellVarContext current
 System::Call 'kernel32::OpenMutexW(i 1048576, i 0, w "Local\ProtocolloLocale") p.r0'
 ${If} $0 != 0
  System::Call 'kernel32::CloseHandle(p r0)'
  MessageBox MB_ICONSTOP "Chiudi Protocollo Locale prima di disinstallare."
  Abort
 ${EndIf}
 RMDir /r "$INSTDIR\runtime"
 RMDir /r "$INSTDIR\assets"
 Delete "$INSTDIR\ProtocolloLocale.exe"
 Delete "$INSTDIR\app_installata.py"
 Delete "$INSTDIR\installa_modelli.py"
 Delete "$INSTDIR\avvio.py"
 Delete "$INSTDIR\attivita.py"
 Delete "$INSTDIR\protocollo.py"
 Delete "$INSTDIR\riconoscimento.py"
 Delete "$INSTDIR\secondo_modello.py"
 Delete "$INSTDIR\motore_v4.py"
 Delete "$INSTDIR\interfaccia_v4.py"
 Delete "$INSTDIR\prepara_modelli.py"
 Delete "$INSTDIR\riferimento_approvato.json"
 Delete "$INSTDIR\requirements.txt"
 Delete "$INSTDIR\VERSIONE.txt"
 Delete "$INSTDIR\LEGGIMI_INSTALLER.txt"
 Delete "$INSTDIR\componenti-inclusi.json"
 Delete "$INSTDIR\Disinstalla.exe"
 Delete "$DESKTOP\Protocollo Locale.lnk"
 Delete "$SMPROGRAMS\Protocollo Locale\Protocollo Locale.lnk"
 Delete "$SMPROGRAMS\Protocollo Locale\Attiva riconoscitori locali.lnk"
 RMDir "$SMPROGRAMS\Protocollo Locale"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtocolloLocale"
 RMDir "$INSTDIR"
SectionEnd
