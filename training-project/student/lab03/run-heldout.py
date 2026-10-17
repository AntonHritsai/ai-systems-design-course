"""Run remaining scheduled positions once, in course order; stop on route-wide failure."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--freeze-id', required=True)
parser.add_argument('--resume-probe', action='store_true')
args = parser.parse_args()
comparison = Path('reports/lab03/comparisons') / args.freeze_id
schedule = json.loads((comparison / 'schedule.json').read_text())
by_id = {p['position_id']: p for p in schedule['positions']}
probe = args.resume_probe
for pid in schedule['order']:
    state = by_id[pid]['state']
    if state in {'returned', 'failed', 'closed-unstarted'}:
        continue
    attempt = comparison / 'attempts' / pid
    if (attempt / 'request.json').exists():
        raise SystemExit(f'Interrupted attempt {pid}; use record-interrupted, do not run again.')
    command = [sys.executable, 'student/lab03/run-live.py', 'run', '--report-dir', 'reports/lab03',
               '--freeze-id', args.freeze_id, '--position-id', pid, '--adapter', 'openrouter',
               '--model-id', 'openrouter/free', '--by', 'anton-hritsai']
    if probe:
        command.append('--resume-probe')
        probe = False
    print('RUN:', ' '.join(command[1:]), flush=True)
    subprocess.run(command, check=True)
    current = json.loads((comparison / 'schedule.json').read_text())
    state = next(p['state'] for p in current['positions'] if p['position_id'] == pid)
    if state == 'returned':
        subprocess.run(['uv', 'run', 'learning-project', 'lab03', 'structural-check',
                        '--report-dir', 'reports/lab03', '--freeze-id', args.freeze_id,
                        '--position-id', pid], check=False)
    elif state == 'failed':
        error = json.loads((attempt / 'error.json').read_text())
        print(json.dumps(error, ensure_ascii=False), flush=True)
        if error['failure_class'] == 'route-wide':
            raise SystemExit('Route-wide failure preserved; stopped before dispatching next position.')
    else:
        raise SystemExit(f'Unexpected state {state}; inspect saved evidence.')
print('All sixteen scheduled positions are terminal.', flush=True)
