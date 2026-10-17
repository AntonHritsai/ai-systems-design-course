"""Run exactly one laboratory CLI invocation with credentials kept out of arguments."""
import os
from pathlib import Path
import subprocess
import sys

if len(sys.argv) < 2 or sys.argv[1] not in {'dev-run', 'run'}:
    raise SystemExit('Use: python3 student/lab03/run-live.py dev-run|run [CLI arguments]')
project = Path(__file__).resolve().parents[2]
environment = os.environ.copy()
environment['OPENROUTER_API_KEY'] = Path('/Users/antonygritsai/Desktop/Sobol/.lab03-openrouter-key').read_text().strip()
environment['SSL_CERT_FILE'] = '/etc/ssl/cert.pem'
result = subprocess.run(['uv', 'run', 'learning-project', 'lab03', *sys.argv[1:]], cwd=project, env=environment)
raise SystemExit(result.returncode)
