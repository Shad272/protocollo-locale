"""Complementary multilingual entity recognizer, offline-only at runtime."""
import os
from pathlib import Path

MODEL_ID='urchade/gliner_multi-v2.1'
_instance=None

class SecondRecognizer:
    def __init__(self,model):self.model=model;self.cache={}
    def entities_many(self,texts,progress=None):
        unseen=list(dict.fromkeys(s for s in texts if s.strip() and s not in self.cache))
        tasks=[];pending={}
        for full in unseen:
            pending[full]=[]
            offset=0
            # Overlap prevents missing a name straddling a long-cell boundary.
            while offset<len(full):
                end=min(offset+900,len(full))
                if end<len(full):
                    space=full.rfind(' ',offset+700,end)
                    if space>offset:end=space
                tasks.append((full,offset,full[offset:end]))
                if end==len(full):break
                offset=max(offset+1,end-150)
                while offset<len(full) and offset>0 and full[offset-1].isalnum():offset+=1
        for offset in range(0,len(tasks),4):
            work=tasks[offset:offset+4];batch=[part for _,_,part in work]
            results=self.model.batch_predict_entities(batch,['person','company'],threshold=.30)
            if len(results)!=len(work):raise RuntimeError('Il secondo modello ha restituito un numero incompleto di risultati.')
            for (full,start,part),entities in zip(work,results):
                for e in entities:
                    candidate={**e,'start':int(e['start'])+start,'end':int(e['end'])+start}
                    if not any(x['start']==candidate['start'] and x['end']==candidate['end'] for x in pending[full]):pending[full].append(candidate)
            if progress:progress(f'Secondo riconoscitore: {min(offset+4,len(tasks))}/{len(tasks)} blocchi')
        self.cache.update(pending)
        return [self.cache.get(s,[]) for s in texts]

def load_second_model():
    global _instance
    if _instance is not None:return _instance,'Secondo modello multilingue locale attivo'
    # Installed weights and tokenizer must already exist: no runtime network.
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    try:
        import torch
        from gliner import GLiNER
        torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
        model=GLiNER.from_pretrained(MODEL_ID,local_files_only=True)
        model.eval()
        _instance=SecondRecognizer(model)
        return _instance,'Secondo modello multilingue locale attivo'
    except Exception as e:
        return None,'Secondo modello non attivo: esegui ATTIVA_RICONOSCIMENTO.cmd ('+type(e).__name__+')'
