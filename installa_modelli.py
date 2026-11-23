"""Optional recognition installer for the private Python runtime; no input files read."""
from pathlib import Path
import sys
from avvio import models

if __name__=='__main__':
    try:models(Path(sys.executable))
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
