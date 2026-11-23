"""Install/cache models only. No user files are opened by this script."""
import os
import sys
os.environ.pop('HF_HUB_OFFLINE',None)
os.environ.pop('TRANSFORMERS_OFFLINE',None)
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
if __name__=='__main__':
    if '--secondo' in sys.argv:
        from gliner import GLiNER
        GLiNER.from_pretrained('urchade/gliner_multi-v2.1')
    elif '--verifica' in sys.argv:
        from riconoscimento import load_language_model
        from secondo_modello import load_second_model
        first,one=load_language_model();second,two=load_second_model()
        print(one);print(two)
        if first is None or second is None:raise SystemExit(1)
        print('Entrambi i modelli sono disponibili senza Internet.')
