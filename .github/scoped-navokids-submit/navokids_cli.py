"""Only closed NavoKids entrypoint; stream scope spans validation and upload."""
import os
from pathlib import Path
from stream_zip import stream_store
from cli import main
if __name__=='__main__':
    with stream_store(Path(os.environ.get('RUNNER_TEMP','/tmp'))/'scoped-navokids-scratch'):
        raise SystemExit(main(family='navokids1'))
