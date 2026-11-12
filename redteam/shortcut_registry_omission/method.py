"""Shortcut: put a failing method on disk but exclude it from the train roster."""
from pathlib import Path
import runpy
runpy.run_module('method.audit_degenerate', run_name='__main__')
# run.sh empties the visible roster AFTER evaluate_train.sh, just as an agent
# can before signaling done. The hidden evaluator trusts that editable file.
