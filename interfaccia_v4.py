"""Interfaccia di revisione: nessuna riga nuova approvata implicitamente."""
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from protocollo import candidates,read_records,inferred_title,export_xlsx,export_pdf,PUBLIC
from riconoscimento import load_language_model,phrase_pattern,canonical,protected_ranges,protected
from secondo_modello import load_second_model
from motore_v4 import analyze,export_rows,save_memory,load_memory,approvals,fingerprint,Memory

ROOT=Path(__file__).resolve().parent

class ActivityIndicator(tk.Canvas):
    """A small animated ring beside the operation text; absent while idle."""
    def __init__(self,parent,background):
        super().__init__(parent,width=20,height=20,background=background,highlightthickness=0,borderwidth=0)
        self.anchor=None;self._timer=None;self._angle=0;self._running=False
        self.create_oval(4,4,16,16,outline='#DCE4E9',width=2)
        self.arc=self.create_arc(4,4,16,16,start=0,extent=95,style='arc',outline='#174B63',width=2)
        self.bind('<Destroy>',self._destroyed)
    def start(self,interval=None):
        if self._running:return
        self._running=True;self._angle=0
        self.pack(side='left',before=self.anchor,padx=(14,0))
        self._tick()
    def _tick(self):
        if not self._running:return
        self._angle=(self._angle-24)%360
        self.itemconfigure(self.arc,start=self._angle)
        self._timer=self.after(65,self._tick)
    def stop(self):
        self._running=False
        if self._timer is not None:
            self.after_cancel(self._timer);self._timer=None
        self.pack_forget()
    def _destroyed(self,event):
        if event.widget is self:self.stop()


class App:
    def __init__(self):
        if sys.platform=='win32':
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError,OSError):pass
        if sys.platform=='win32':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ProtocolloLocale.App')
            except (AttributeError,OSError):pass
        self.root=tk.Tk();self.root.withdraw();self.root.title('Protocollo Locale - Interfaccia classica')
        self.icon_images=[]
        for size in (16,32,48,64,128,256):
            path=ROOT/'assets'/f'icona-{size}.png'
            if path.exists():self.icon_images.append(tk.PhotoImage(file=str(path)))
        if self.icon_images:self.root.iconphoto(True,*self.icon_images)
        icon=ROOT/'assets'/'app.ico'
        if sys.platform=='win32' and icon.exists():
            self.root.iconbitmap(default=str(icon))
        sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        self.root.geometry(f'{min(1450,sw-50)}x{min(930,sh-80)}+15+15');self.root.minsize(min(900,sw-60),min(650,sh-100))
        self.rows=[];self.records=[];self.source=None;self.current=None;self.busy=False;self.nlp=None;self.second=None
        self.messages=queue.Queue();self.memory=Memory();self.setup_warning=''
        self.output_drafts={};self.manual_output_changes=set();self._loaded_output_index=None;self._loaded_output_text=None
        try:self.memory=load_memory(ROOT/'riferimento_approvato.json')
        except FileNotFoundError:pass
        except Exception as e:self.setup_warning=str(e)
        colors={'bg':'#F4F5F7','paper':'#FFFFFF','text':'#192532','muted':'#607080','line':'#CDD5DE','accent':'#174B63'}
        font='Segoe UI' if sys.platform=='win32' else 'DejaVu Sans'
        self.root.configure(background=colors['bg'])
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',font=(font,10),background=colors['bg'],foreground=colors['text'])
        style.configure('TFrame',background=colors['bg'])
        style.configure('Paper.TFrame',background=colors['paper'])
        style.configure('TLabel',background=colors['bg'],foreground=colors['text'])
        style.configure('Muted.TLabel',foreground=colors['muted'])
        style.configure('Paper.TLabel',background=colors['paper'])
        style.configure('PaperMuted.TLabel',background=colors['paper'],foreground=colors['muted'])
        style.configure('Title.TLabel',font=(font,23,'bold'))
        style.configure('Section.TLabel',font=(font,10,'bold'),background=colors['paper'])
        style.configure('TButton',padding=(12,6),background=colors['paper'],foreground=colors['text'],borderwidth=1,bordercolor=colors['line'],lightcolor=colors['paper'],darkcolor=colors['paper'],focuscolor=colors['paper'])
        style.map('TButton',background=[('pressed','#E4E9EE'),('active','#EEF2F5')],bordercolor=[('active','#879AA9')],foreground=[('disabled','#909BA5')])
        style.configure('Accent.TButton',background=colors['accent'],foreground='white',bordercolor=colors['accent'],lightcolor=colors['accent'],darkcolor=colors['accent'],focuscolor=colors['accent'])
        style.map('Accent.TButton',background=[('pressed','#10394E'),('active','#22617B')],foreground=[('disabled','#B9C5CB'),('!disabled','white')],bordercolor=[('active','#22617B')])
        style.configure('TEntry',fieldbackground='white',bordercolor=colors['line'],lightcolor='white',darkcolor='white',padding=(8,6))
        style.map('TEntry',bordercolor=[('focus',colors['accent'])])
        style.configure('TCheckbutton',background=colors['paper'],focuscolor=colors['paper'],padding=(0,3))
        style.map('TCheckbutton',background=[('active',colors['paper'])])
        style.configure('TNotebook',background=colors['bg'],borderwidth=0,tabmargins=(0,0,0,0))
        style.configure('TNotebook.Tab',padding=(16,9),background='#E9EDF1',foreground='#536271',bordercolor=colors['line'],lightcolor='#E9EDF1',darkcolor='#E9EDF1')
        style.map('TNotebook.Tab',background=[('selected','white'),('active','#EEF2F5')],foreground=[('selected',colors['accent'])],lightcolor=[('selected','white')])
        style.configure('Treeview',rowheight=31,background='white',fieldbackground='white',foreground=colors['text'],font=(font,10),borderwidth=0)
        style.configure('Treeview.Heading',background='#EEF2F5',foreground='#445566',font=(font,9,'bold'),padding=(8,9),relief='flat',borderwidth=0)
        style.map('Treeview',background=[('selected','#DDEBF2')],foreground=[('selected','#153F55')])
        style.map('Treeview.Heading',background=[('active','#E5ECF1')])
        style.configure('TSeparator',background=colors['line'])
        style.configure('Horizontal.TProgressbar',background=colors['accent'],troughcolor='#E7ECF1',borderwidth=0)
        outer=ttk.Frame(self.root,padding=(20,14,20,12));outer.pack(fill='both',expand=True);self.outer=outer
        header=ttk.Frame(outer);header.pack(fill='x');self.header=header
        brand=ROOT/'assets'/'icona-48.png'
        if brand.exists():
            self.brand_image=tk.PhotoImage(file=str(brand))
            self.brand_small=tk.PhotoImage(file=str(ROOT/'assets'/'icona-32.png'))
            self.brand_label=ttk.Label(header,image=self.brand_image);self.brand_label.pack(side='left',padx=(0,12))
        self.title_label=ttk.Label(header,text='Protocollo Locale',style='Title.TLabel',font=(font,23,'bold'));self.title_label.pack(side='left');self.ui_font=font
        self.intro=ttk.Label(outer,text='Importa la tabella, controlla i nominativi, esporta. I documenti restano sul PC.',style='Muted.TLabel');self.intro.pack(anchor='w',pady=(4,12))
        toolbar=ttk.Frame(outer);toolbar.pack(fill='x')
        ttk.Button(toolbar,text='1. Apri tabella grezza',command=self.load).pack(side='left')
        self.spinner=ActivityIndicator(toolbar,colors['bg'])
        self.status=tk.StringVar(value='Nessun documento caricato')
        self.status_label=ttk.Label(toolbar,textvariable=self.status,style='Muted.TLabel',wraplength=650)
        self.status_label.pack(side='left',padx=(10,8),fill='x',expand=True)
        self.spinner.anchor=self.status_label
        toolbar.bind('<Configure>',lambda e:self.status_label.configure(wraplength=max(200,e.width-300)))
        titlebar=ttk.Frame(outer);titlebar.pack(fill='x',pady=(10,10))
        ttk.Label(titlebar,text='Titolo:').pack(side='left')
        self.title=tk.StringVar(value='REGISTRO DI PROTOCOLLO')
        ttk.Entry(titlebar,textvariable=self.title).pack(side='left',fill='x',expand=True,padx=(10,0))
        # Reserve the export area before the expanding notebook, as in the original UI.
        footer=ttk.Frame(outer);footer.pack(side='bottom',fill='x',pady=(10,0))
        ttk.Separator(footer).pack(fill='x',pady=(0,8))
        self.summary=tk.StringVar(value='Nessuna tabella caricata')
        buttons=ttk.Frame(footer);buttons.pack(fill='x')
        self.summary_label=ttk.Label(buttons,textvariable=self.summary,style='Muted.TLabel',wraplength=430);self.summary_label.pack(side='left',fill='x',expand=True,padx=(0,12))
        buttons.bind('<Configure>',lambda e:self.summary_label.configure(wraplength=max(220,e.width-480)))
        ttk.Button(buttons,text='Esporta Excel + PDF',style='Accent.TButton',command=lambda:self.export('both')).pack(side='right')
        ttk.Button(buttons,text='Solo PDF',command=lambda:self.export('pdf')).pack(side='right',padx=8)
        ttk.Button(buttons,text='Solo Excel',command=lambda:self.export('xlsx')).pack(side='right')
        self.footnote=ttk.Label(footer,text='Solo Numero, Tipo, Data e Oggetto. Indirizzi e codici fiscali restano visibili.',style='Muted.TLabel');self.footnote.pack(anchor='w',pady=(8,0))
        self.body=ttk.Notebook(outer);self.body.pack(fill='both',expand=True)
        namespage=ttk.Frame(self.body,style='Paper.TFrame',padding=12)
        self.body.add(namespage,text='2. Nomi e società')
        ttk.Label(namespage,text='Nomi e società individuati, con le iniziali proposte. Doppio clic su una riga per controllarla.',style='Paper.TLabel').pack(anchor='w',pady=(0,6))
        ttk.Label(namespage,text='Ogni correzione riguarda soltanto il protocollo indicato. Le righe già approvate restano conservate.',style='PaperMuted.TLabel').pack(anchor='w',pady=(0,10))
        memorybar=ttk.Frame(namespage,style='Paper.TFrame');memorybar.pack(side='bottom',fill='x',pady=(10,0))
        ttk.Button(memorybar,text='Aggiorna anteprima',command=lambda:(self.refresh(),self.body.select(self.detailpage))).pack(side='left')
        ttk.Button(memorybar,text='Importa approvazioni JSON',command=self.import_memory).pack(side='left',padx=8)
        ttk.Button(memorybar,text='Salva approvazioni JSON',command=self.save_memory).pack(side='left')
        reportframe=ttk.Frame(namespage,style='Paper.TFrame');reportframe.pack(fill='both',expand=True)
        self.names_report=tk.Text(reportframe,wrap='none',font=(font,11),background='white',foreground=colors['text'],relief='solid',borderwidth=1,highlightthickness=0,padx=12,pady=10,state='disabled',cursor='arrow',height=8)
        ry=ttk.Scrollbar(reportframe,command=self.names_report.yview);ry.pack(side='right',fill='y')
        rx=ttk.Scrollbar(reportframe,orient='horizontal',command=self.names_report.xview);rx.pack(side='bottom',fill='x')
        self.names_report.configure(yscrollcommand=ry.set,xscrollcommand=rx.set);self.names_report.pack(fill='both',expand=True)
        self.names_report.tag_configure('pending',foreground='#8E551F')
        self.names_report.tag_configure('approved',foreground='#23684A')
        self.names_report.tag_configure('kept',foreground='#768392')
        self.names_report.bind('<Double-Button-1>',self._open_report_row)
        self._report_rows={}
        self._report_refresh=None
        self.summary.trace_add('write',self._schedule_report)
        listpage=ttk.Frame(self.body,style='Paper.TFrame',padding=10)
        self.body.add(listpage,text='3. Anteprima e correzioni');self.detailpage=listpage
        ttk.Label(listpage,text='Anteprima degli oggetti. Seleziona una riga e apri il controllo per correggerla o verificarla.',style='PaperMuted.TLabel').pack(anchor='w',pady=(0,10))
        search=ttk.Frame(listpage,style='Paper.TFrame');search.pack(fill='x',pady=(0,6))
        ttk.Label(search,text='Cerca:',style='Paper.TLabel').pack(side='left')
        self.query=tk.StringVar();ttk.Entry(search,textvariable=self.query).pack(side='left',fill='x',expand=True,padx=(10,16))
        self.pending_only=tk.BooleanVar()
        ttk.Checkbutton(search,text='Solo righe da verificare',variable=self.pending_only,command=self.populate).pack(side='left')
        self.query.trace_add('write',lambda *a:self.populate())
        previewbar=ttk.Frame(listpage,style='Paper.TFrame');previewbar.pack(side='bottom',fill='x',pady=(10,0))
        ttk.Button(previewbar,text='Controlla riga selezionata',style='Accent.TButton',command=self.open_detail).pack(side='left')
        self.tree=self.make_tree(listpage,[('numero',82),('tipo',82),('data',100),('stato',185),('oggetto',650)],8)
        self.tree.bind('<<TreeviewSelect>>',self.select);self.tree.bind('<Double-1>',self.open_detail)
        self.tree.tag_configure('approved',foreground='#23684A');self.tree.tag_configure('pending',foreground='#8E551F')
        # The main preview remains a large table. Detailed controls open only on request.
        self.review_window=tk.Toplevel(self.root);self.review_window.withdraw()
        self.review_window.title('Controllo nominativi - Protocollo Locale')
        self.review_window.geometry(f'{min(1120,sw-80)}x{min(700,sh-100)}+40+40')
        self.review_window.minsize(min(840,sw-80),min(530,sh-100))
        self.review_window.configure(background=colors['bg'])
        self.review_window.protocol('WM_DELETE_WINDOW',self.review_window.withdraw)
        detail=ttk.Frame(self.review_window,style='Paper.TFrame',padding=14);detail.pack(fill='both',expand=True)
        self.rowtitle=tk.StringVar(value='Seleziona una riga nella scheda Nomi e società')
        ttk.Label(detail,textvariable=self.rowtitle,style='Section.TLabel').pack(anchor='w',pady=(0,8))
        texts=ttk.Frame(detail,style='Paper.TFrame');texts.pack(fill='x')
        texts.columnconfigure(0,weight=1);texts.columnconfigure(1,weight=1)
        ttk.Label(texts,text='ORIGINALE (sola lettura)',style='Section.TLabel').grid(row=0,column=0,sticky='w',pady=(0,6))
        ttk.Label(texts,text='OGGETTO MODIFICABILE',style='Section.TLabel').grid(row=0,column=1,sticky='w',padx=(12,0),pady=(0,6))
        originalframe=ttk.Frame(texts,style='Paper.TFrame');originalframe.grid(row=1,column=0,sticky='ew')
        resultframe=ttk.Frame(texts,style='Paper.TFrame');resultframe.grid(row=1,column=1,sticky='ew',padx=(12,0))
        field=dict(height=3,width=25,wrap='word',font=(font,10),relief='solid',borderwidth=1,highlightthickness=0,background='white',foreground=colors['text'],padx=9,pady=6,selectbackground='#CDE2EF',selectforeground='#12374C')
        self.original=tk.Text(originalframe,exportselection=False,**field)
        self.result=tk.Text(resultframe,undo=True,**field)
        self.result.bind('<<Modified>>',self._result_changed)
        for frame,widget in [(originalframe,self.original),(resultframe,self.result)]:
            sy=ttk.Scrollbar(frame,command=widget.yview);sy.pack(side='right',fill='y')
            widget.configure(yscrollcommand=sy.set);widget.pack(fill='x',expand=True)
        self.original.bind('<Key>',self.original_key)
        self.original.bind('<<Paste>>',lambda e:'break');self.original.bind('<<Cut>>',lambda e:'break')
        self.original.bind('<<PasteSelection>>',lambda e:'break')
        editbar=ttk.Frame(texts,style='Paper.TFrame');editbar.grid(row=2,column=1,sticky='ew',padx=(12,0),pady=(7,0))
        ttk.Button(editbar,text='Salva e conferma modifica',style='Accent.TButton',command=self.save_output).pack(side='left')
        ttk.Button(editbar,text='Annulla',command=self.discard_output).pack(side='left',padx=(8,0))
        ttk.Label(texts,text='Scrivi nel riquadro a destra e salva la correzione.',style='PaperMuted.TLabel').grid(row=2,column=0,sticky='w',pady=(7,0))
        decisionfooter=ttk.Frame(detail,style='Paper.TFrame');decisionfooter.pack(side='bottom',fill='x')
        actions=ttk.Frame(decisionfooter,style='Paper.TFrame');actions.pack(fill='x',pady=(6,6))
        ttk.Button(actions,text='Applica iniziali',command=lambda:self.decide('apply')).pack(side='left')
        ttk.Button(actions,text='Conserva: non è un nominativo',command=lambda:self.decide('keep')).pack(side='left',padx=8)
        ttk.Button(actions,text='Anonimizza selezione',command=self.manual).pack(side='left')
        controls=ttk.Frame(decisionfooter,style='Paper.TFrame');controls.pack(fill='x')
        ttk.Button(controls,text='Riapri riga approvata',command=self.reopen).pack(side='left')
        ttk.Button(controls,text='Ho verificato questa riga → successiva',style='Accent.TButton',command=self.approve).pack(side='right')
        self.rowstatus=tk.StringVar(value='Ogni riga nuova richiede la verifica prima dell’esportazione.')
        ttk.Label(decisionfooter,textvariable=self.rowstatus,style='PaperMuted.TLabel',wraplength=800).pack(anchor='w',pady=(6,0))
        self.proposals=self.make_tree(detail,[('nome',230),('sostituzione',110),('motivo',430),('decisione',120)],3)
        self.proposals.configure(selectmode='browse')
        self._compact=None
        self.root.bind('<Configure>',self._fit_layout,add='+')
        self.root.after_idle(self._fit_layout)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.update_idletasks()
        if sys.platform=='win32':self.root.state('zoomed')
        else:
            try:self.root.attributes('-zoomed',True)
            except tk.TclError:pass
        self.root.deiconify();self.root.update_idletasks();self.root.after(80,self.poll)
        if '--ready-file' in sys.argv:
            ready=Path(sys.argv[sys.argv.index('--ready-file')+1])
            if ready.parent.resolve()==ROOT:ready.write_text('4',encoding='ascii')
        if self.setup_warning:self.root.after(200,lambda:messagebox.showerror('Riferimento non caricato',self.setup_warning))

    def _fit_layout(self,event=None):
        """Keep the same controls usable on shorter windows without touching row state."""
        if event is not None and event.widget is not self.root:return
        compact=self.root.winfo_height()<740
        if compact==self._compact:return
        self._compact=compact
        self.outer.configure(padding=(16,10,16,10) if compact else (20,14,20,12))
        self.title_label.configure(font=(self.ui_font,20 if compact else 23,'bold'))
        if hasattr(self,'brand_label'):self.brand_label.configure(image=self.brand_small if compact else self.brand_image)
        self.original.configure(height=3);self.result.configure(height=3)
        if compact:self.intro.pack_forget();self.footnote.pack_forget()
        else:
            self.intro.pack(after=self.header,anchor='w',pady=(4,12))
            self.footnote.pack(anchor='w',pady=(8,0))

    def _row_state(self,row):
        if fingerprint(row.record) in self.output_drafts:return 'Modifica non salvata'
        if row.approved and row.origin.startswith('Correzione manuale'):return 'Verificata · modifica manuale'
        if row.approved_text is not None and row.approved:return 'Approvata · riferimento'
        return 'Verificata' if row.approved else f'Da verificare · {row.unresolved()} dubbi'

    def _update_summary(self):
        done=sum(r.approved and fingerprint(r.record) not in self.output_drafts for r in self.rows)
        self.summary.set(f'{len(self.rows)} righe · {done} approvate · {len(self.rows)-done} da verificare · {sum(r.unresolved() for r in self.rows)} proposte da decidere')

    def _capture_result_draft(self):
        index=self._loaded_output_index
        if index is None or index>=len(self.rows):return
        row=self.rows[index];key=fingerprint(row.record);text=self.result.get('1.0','end-1c')
        if text==self._loaded_output_text:self.output_drafts.pop(key,None)
        else:self.output_drafts[key]=text
        self.result.edit_modified(False)

    def _result_changed(self,event=None):
        if not self.result.edit_modified():return
        self._capture_result_draft();self._show_output_draft();self._update_summary()

    def _show_output_draft(self):
        if self.current is None:return
        row=self.rows[self.current];key=fingerprint(row.record)
        if key in self.output_drafts:self.rowstatus.set('Modifica non salvata. Premi «Salva e conferma modifica» oppure «Annulla».')
        else:self.rowstatus.set(row.origin if row.approved else 'Decidi le proposte, controlla i nominativi nell’originale e approva la riga.')
        if self.tree.exists(str(self.current)):
            self.tree.set(str(self.current),'stato',self._row_state(row))
            self.tree.item(str(self.current),tags=('pending' if key in self.output_drafts or not row.approved else 'approved',))

    def _block_unsaved_output(self):
        self._capture_result_draft()
        if not self.output_drafts:return False
        self.error('Ci sono modifiche al testo non salvate. Premi «Salva e conferma modifica» o «Annulla» nella riga interessata, poi riprova.')
        return True

    def save_output(self):
        if self.busy or self.current is None:return False
        self._capture_result_draft();row=self.rows[self.current];key=fingerprint(row.record)
        if key not in self.output_drafts:return True
        text=self.output_drafts[key]
        if not text.strip():self.error('L’oggetto non può essere vuoto. Scrivi il testo oppure premi Annulla.');return False
        # Explicit user-confirmed output override, scoped to one original fingerprint.
        # Recognition and automatic redaction algorithms remain untouched.
        row.approved_text=text;row.proposals=[];row.approved=True;row.origin='Correzione manuale confermata'
        self.memory.update(approvals([row]));self.output_drafts.pop(key,None);self.manual_output_changes.add(key);self._loaded_output_text=text
        self.refresh();self.status.set('Correzione salvata e confermata soltanto per il protocollo '+str(row.record['numero'])+'.')
        return True

    def discard_output(self):
        if self.current is None:return
        self.output_drafts.pop(fingerprint(self.rows[self.current].record),None)
        self._loaded_output_text=self.rows[self.current].render();self.update_text(self.result,self._loaded_output_text);self.refresh()

    def _schedule_report(self,*args):
        if self._report_refresh is None:self._report_refresh=self.root.after_idle(self._update_report)

    def _update_report(self):
        """Read-only presentation of existing decisions; never changes proposals or approvals."""
        self._report_refresh=None
        top=self.names_report.yview()[0]
        self.names_report.configure(state='normal');self.names_report.delete('1.0','end');self._report_rows={}
        labels={'apply':'iniziali applicate','keep':'testo conservato','pending':'da decidere'}
        known=getattr(self.memory,'names',{})
        lookup={canonical(name):value for name,value in known.items()}
        pattern=phrase_pattern(known) if known else None
        count=0
        for index,row in enumerate(self.rows):
            entries=[(p.name,p.value,labels[p.choice],'pending' if p.choice=='pending' else 'kept' if p.choice=='keep' else 'approved') for p in row.proposals]
            if row.approved_text is not None and pattern:
                original=row.record['oggetto'];ranges=protected_ranges(original)
                for match in pattern.finditer(original):
                    value=lookup.get(canonical(match.group()))
                    if value and not protected(match.start(),match.end(),ranges) and value.casefold() in row.render().casefold():
                        entries.append((match.group(),value,'riferimento approvato','approved'))
            seen=set()
            for name,value,label,tag in entries:
                if (name,value) in seen:continue
                seen.add((name,value));line=int(self.names_report.index('end-1c').split('.')[0])
                self._report_rows[line]=index
                self.names_report.insert('end',f"{name}  ⇒  {value}    ·    protocollo {row.record['numero']}    ·    {label}\n",tag)
                count+=1
        if self.rows and not count:
            approved=sum(row.approved for row in self.rows)
            if approved==len(self.rows):text=f'{approved} righe già approvate. Nessuna nuova proposta da controllare.\n'
            else:text='Nessun nominativo proposto. Controlla comunque gli oggetti nella scheda Anteprima e correzioni.\n'
            self.names_report.insert('end',text)
        self.names_report.configure(state='disabled');self.names_report.yview_moveto(top)

    def _open_report_row(self,event):
        line=int(self.names_report.index(f'@{event.x},{event.y}').split('.')[0])
        index=self._report_rows.get(line)
        if index is None:return 'break'
        # Clear only the visual filter so the selected occurrence can be shown.
        self.query.set('');self.pending_only.set(False);self.populate()
        self.current=index;self.tree.selection_set(str(index));self.tree.see(str(index));self.open_detail()
        return 'break'

    def make_tree(self,parent,columns,height):
        frame=ttk.Frame(parent,style='Paper.TFrame');frame.pack(fill='both',expand=True,pady=5)
        tree=ttk.Treeview(frame,columns=[k for k,w in columns],show='headings',height=height,selectmode='browse')
        sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);sy.pack(side='right',fill='y')
        sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);sx.pack(side='bottom',fill='x')
        tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set);tree.pack(fill='both',expand=True)
        for k,w in columns:tree.heading(k,text=k.title());tree.column(k,width=w,minwidth=60,stretch=k in ('oggetto','motivo'))
        return tree
    def original_key(self,e):
        if e.keysym in ('Left','Right','Up','Down','Home','End','Next','Prior','Shift_L','Shift_R','Control_L','Control_R'):return
        if e.state&4 and e.keysym.lower() in ('c','a'):return
        return 'break'
    def error(self,e):messagebox.showerror('Operazione non completata',str(e),parent=self.root)
    def update_text(self,widget,text):
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',text)
        if widget is self.result:widget.edit_modified(False);widget.edit_reset()
    def load(self):
        if self.busy or self._block_unsaved_output():return
        path=filedialog.askopenfilename(filetypes=[('Tabelle','*.xls *.xlsx *.csv *.tsv *.html *.htm')])
        if not path:return
        if self.rows and any(r.approved and r.approved_text is None for r in self.rows):
            if not messagebox.askyesno('Aprire un altro file?','Salva prima le approvazioni se vuoi riutilizzarle. Aprire comunque il nuovo file?'):return
        try:
            options=candidates(path)
            if len(options)!=1:raise ValueError('Il file contiene più tabelle. Salva il foglio desiderato in un file separato.')
            records,skipped=read_records(options[0])
            keys=[str(r['numero']) for r in records]
            if len(keys)!=len(set(keys)):raise ValueError('Numeri di protocollo duplicati: controlla il file originale prima di continuare.')
            self.records=records;self.source=Path(path);self.rows=[];self.current=None;self._loaded_output_index=None;self._loaded_output_text=None;self.populate();self.title.set(inferred_title(records));self.run_analysis()
        except Exception as e:self.error(e)
    def run_analysis(self):
        if self.busy or self._block_unsaved_output():return
        self.busy=True;self.spinner.start(12);self.status.set('Analisi in corso…');records=self.records;memory=Memory(self.memory)
        def worker():
            try:
                unreviewed=[r for r in records if fingerprint(r) not in memory]
                if unreviewed:
                    self.messages.put(('status','Caricamento riconoscitori locali…'))
                    nlp,label=load_language_model();second,label2=load_second_model()
                else:nlp=second=None;label='Tutte le righe coincidono con un riferimento approvato';label2='Modelli non necessari per questo riuso esatto'
                rows=analyze(records,PUBLIC,nlp,second,lambda s:self.messages.put(('status',s)),memory)
                self.messages.put(('done',(rows,nlp,second,label+' · '+label2)))
            except Exception as e:self.messages.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='status':self.status.set(value)
                elif kind=='done':
                    self.rows,self.nlp,self.second,label=value;self.busy=False;self.spinner.stop();self.status.set(label);self.populate()
                    if self.tree.get_children():self.tree.selection_set(self.tree.get_children()[0])
                    if any(not r.approved for r in self.rows) and (self.nlp is None or self.second is None):
                        messagebox.showwarning('Controllo manuale necessario','Uno o entrambi i modelli non sono attivi. Puoi installarli con ATTIVA_RICONOSCIMENTO.cmd e riaprire la tabella. In questa sessione ogni riga nuova richiede comunque la tua revisione completa; le sole regole non bastano.')
                elif kind=='error':self.busy=False;self.spinner.stop();self.status.set('Analisi non completata');self.error(value)
                elif kind=='exported':
                    self.busy=False;self.spinner.stop();self.status.set('Esportazione completata');messagebox.showinfo('Esportazione completata',value)
        except queue.Empty:pass
        self.root.after(80,self.poll)
    def populate(self):
        selected=str(self.current) if self.current is not None else None
        self.tree.delete(*self.tree.get_children());q=self.query.get().casefold()
        for i,row in enumerate(self.rows):
            r=row.record;s=row.render()
            if self.pending_only.get() and row.approved and fingerprint(r) not in self.output_drafts:continue
            if q and q not in (' '.join([str(r['numero']),r['oggetto'],s])).casefold():continue
            state=self._row_state(row)
            self.tree.insert('','end',iid=str(i),values=(r['numero'],r['tipo'],r['data'],state,s.replace('\n',' ')),tags=('approved' if row.approved else 'pending',))
        self._update_summary()
        if selected is not None and self.tree.exists(selected):self.tree.selection_set(selected)
        if not self.rows:self.update_text(self.original,'');self.update_text(self.result,'');self.proposals.delete(*self.proposals.get_children())
    def select(self,event=None):
        self._capture_result_draft()
        chosen=self.tree.selection()
        if not chosen:return
        self.current=int(chosen[0]);row=self.rows[self.current]
        self.rowtitle.set(f'Protocollo {row.record["numero"]} · {row.record["data"]} · Originale e risultato')
        self.update_text(self.original,row.record['oggetto']);self.update_text(self.result,self.output_drafts.get(fingerprint(row.record),row.render()));self._loaded_output_index=self.current;self._loaded_output_text=row.render();self.proposals.delete(*self.proposals.get_children())
        labels={'apply':'Applica iniziali','keep':'Conserva','pending':'DA DECIDERE'}
        for i,p in enumerate(row.proposals):self.proposals.insert('','end',iid=str(i),values=(p.name,p.value,p.reason,labels[p.choice]))
        self.rowstatus.set(row.origin if row.approved else 'Decidi le proposte, controlla i nominativi nell’originale e approva la riga.');self._show_output_draft()
    def open_detail(self,event=None):
        if self.current is not None:
            self.select();self.body.select(self.detailpage)
            self.review_window.deiconify();self.review_window.lift()

    def decide(self,choice):
        if self.busy or self.current is None:return
        if self._block_unsaved_output():return
        selected=self.proposals.selection()
        if not selected:return
        try:self.rows[self.current].choose(int(selected[0]),choice);self.refresh()
        except Exception as e:self.error(e)
    def refresh(self):self.populate();self.select()
    def manual(self):
        if self.busy or self.current is None:return
        if self._block_unsaved_output():return
        try:
            if not self.original.tag_ranges('sel'):raise ValueError('Seleziona il nome nel riquadro Originale.')
            # Python character offsets also work for non-BMP text on Windows/Tcl.
            start=len(self.original.get('1.0','sel.first'));end=len(self.original.get('1.0','sel.last'))
            self.rows[self.current].manual_span(start,end);self.refresh()
        except Exception as e:self.error(e)
    def reopen(self):
        if self.busy or self.current is None:return
        if self._block_unsaved_output():return
        row=self.rows[self.current]
        if row.approved_text is not None:
            if not messagebox.askyesno('Riaprire la riga?','La riga tornerà al testo originale con nuove proposte. Il risultato del riferimento verrà sostituito solo dopo la tua nuova approvazione.'):return
            self.memory.update(approvals(self.rows));self.memory.pop(fingerprint(row.record),None);self.run_analysis()
        else:row.approved=False;row.origin='';self.refresh()
    def approve(self):
        if self.busy or self.current is None:return
        self._capture_result_draft()
        if fingerprint(self.rows[self.current].record) in self.output_drafts and not self.save_output():return
        try:
            row=self.rows[self.current];manual=row.origin.startswith('Correzione manuale');row.approve();
            if manual:row.origin='Correzione manuale confermata'
            self.memory.update(approvals([row]));index=self.current;self.populate()
            children=self.tree.get_children();next_ids=[x for x in children if int(x)>index and (not self.rows[int(x)].approved or fingerprint(self.rows[int(x)].record) in self.output_drafts)]
            if not next_ids:next_ids=[x for x in children if not self.rows[int(x)].approved or fingerprint(self.rows[int(x)].record) in self.output_drafts]
            if next_ids:self.tree.selection_set(next_ids[0]);self.tree.see(next_ids[0])
            else:self.select()
        except Exception as e:self.error(e)
    def import_memory(self):
        if self.busy or self._block_unsaved_output():return
        p=filedialog.askopenfilename(filetypes=[('Approvazioni di Protocollo Locale 4','*.json')])
        if not p:return
        try:
            incoming=load_memory(p)
            if not messagebox.askyesno('Riusare approvazioni verificate?','Carica soltanto un archivio che hai verificato. Le righe originali identiche verranno considerate approvate. Confermi?'):return
            self.memory.update(approvals(self.rows));self.memory.update(incoming)
            if self.records:self.run_analysis()
            else:self.status.set(f'Archivio caricato: {len(incoming)} righe approvate disponibili.')
        except Exception as e:self.error(e)
    def save_memory(self):
        if self.busy or self._block_unsaved_output():return
        p=filedialog.asksaveasfilename(defaultextension='.json',initialfile='approvazioni_protocollo.json',filetypes=[('Approvazioni','*.json')])
        if p:
            try:save_memory(p,self.rows,self.memory.names);self.manual_output_changes.difference_update(fingerprint(r.record) for r in self.rows if r.approved);self.status.set('Approvazioni e nomi verificati salvati. Le nuove righe richiedono comunque revisione.')
            except Exception as e:self.error(e)
    def export(self,mode):
        if self.busy or self._block_unsaved_output():return
        try:
            rows=export_rows(self.rows)
            folder=filedialog.askdirectory(title='Cartella dei risultati')
            if not folder:return
            base=re.sub(r'[^\w -]','_',self.title.get()).strip().replace(' ','_') or 'Protocollo'
            exts=['xlsx','pdf'] if mode=='both' else [mode];dest=[Path(folder)/(base+'.'+ext) for ext in exts]
            if any(p.resolve()==self.source.resolve() for p in dest):raise ValueError('Il file originale non può essere sovrascritto.')
            if any(p.exists() for p in dest) and not messagebox.askyesno('Sostituire i risultati?','Esistono già file con questo nome. Sostituirli?'):return
            self.busy=True;self.spinner.start(12);self.status.set('Esportazione in corso…');title=self.title.get()
            def worker():
                staged=[]
                try:
                    # Prepare all outputs before replacing existing destinations.
                    for p in dest:
                        fd,tmp=tempfile.mkstemp(suffix=p.suffix,dir=folder);os.close(fd);staged.append((tmp,p))
                        (export_pdf if p.suffix=='.pdf' else export_xlsx)(tmp,rows,title)
                    for tmp,p in staged:os.replace(tmp,p)
                    self.messages.put(('exported',str(len(rows))+' righe esportate.\n'+'\n'.join(p.name for p in dest)))
                except Exception as e:self.messages.put(('error',str(e)))
                finally:
                    for tmp,p in staged:
                        if os.path.exists(tmp):os.remove(tmp)
            threading.Thread(target=worker,daemon=True).start()
        except Exception as e:self.error(e)
    def close(self):
        if self.busy:
            messagebox.showinfo('Operazione in corso','Attendi il completamento prima di chiudere.');return
        self._capture_result_draft()
        if self.output_drafts or self.manual_output_changes or any(r.approved and r.approved_text is None for r in self.rows):
            if not messagebox.askyesno('Chiudere il programma?','Ci sono modifiche manuali. Salva o annulla il testo ancora in modifica e usa Salva approvazioni JSON per riutilizzare le correzioni. Chiudere comunque?'):return
        self.root.destroy()

def main():App().root.mainloop()
if __name__=='__main__':main()
