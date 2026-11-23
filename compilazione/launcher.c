#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <wchar.h>
#include <stdio.h>
#include <shellapi.h>

typedef int (__cdecl *PythonMain)(int,wchar_t **);
typedef void (__cdecl *PythonSetString)(const wchar_t *);
int WINAPI wWinMain(HINSTANCE inst,HINSTANCE prev,PWSTR command,int show) {
    (void)inst;(void)prev;(void)command;(void)show;
    HANDLE guard=CreateMutexW(NULL,TRUE,L"Local\\ProtocolloLocale");
    if(guard && GetLastError()==ERROR_ALREADY_EXISTS){MessageBoxW(NULL,L"Protocollo Locale e gia aperto. Controlla la barra delle applicazioni.",L"Protocollo Locale",MB_OK|MB_ICONINFORMATION);CloseHandle(guard);return 0;}
    wchar_t root[32768],dll[32768],python[32768],script[32768],*p;
    if(!GetModuleFileNameW(NULL,root,32768)) return 1;
    p=wcsrchr(root,L'\\');if(!p)return 1;*p=0;
    SetCurrentDirectoryW(root);
    swprintf(dll,32768,L"%ls\\runtime\\python312.dll",root);
    swprintf(python,32768,L"%ls\\runtime\\python.exe",root);
    swprintf(script,32768,L"%ls\\app_installata.py",root);
    wchar_t runtime[32768];swprintf(runtime,32768,L"%ls\\runtime",root);
    SetDllDirectoryW(runtime);
    HMODULE lib=LoadLibraryExW(dll,NULL,LOAD_WITH_ALTERED_SEARCH_PATH);
    if(!lib){MessageBoxW(NULL,L"Il runtime privato Python 3.12 non e disponibile. Riesegui ProtocolloLocale_Setup.exe per riparare l'installazione.",L"Protocollo Locale",MB_OK|MB_ICONERROR);return 1;}
    union { FARPROC raw;PythonMain main;PythonSetString set; } proc;
    proc.raw=GetProcAddress(lib,"Py_SetPythonHome");if(proc.raw)proc.set(runtime);
    proc.raw=GetProcAddress(lib,"Py_SetProgramName");if(proc.raw)proc.set(python);
    proc.raw=GetProcAddress(lib,"Py_Main");PythonMain mainfn=proc.main;
    if(!mainfn){MessageBoxW(NULL,L"Runtime Python non compatibile.",L"Protocollo Locale",MB_OK|MB_ICONERROR);return 1;}
    // The Python runtime lives in this very process, whose name stays ProtocolloLocale.exe.
    int argc=0;LPWSTR *args=CommandLineToArgvW(GetCommandLineW(),&argc);
    wchar_t *pyargs[7]={python,L"-I",L"-u",script,NULL,NULL,NULL};
    if(argc>1)pyargs[4]=args[1];
    int code=mainfn(argc>1?5:4,pyargs);
    if(args)LocalFree(args);
    FreeLibrary(lib);if(guard){ReleaseMutex(guard);CloseHandle(guard);}return code;
}
