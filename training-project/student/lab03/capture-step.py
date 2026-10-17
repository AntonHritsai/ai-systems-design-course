"""Capture an actual Terminal window showing saved evidence, with account and date."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

step = int(sys.argv[1])
names = {0: '00-initial-state.png', 1: '08-step01-admission.png', 2: '01-calibration.png',
         3: '09-step03-variant-a.png', 4: '02-development.png', 5: '03-freeze.png',
         6: '04-held-out-execution.png', 7: '10-step07-blind-scoring.png',
         8: '05-scoring-recommendation.png', 9: '06-regression.png',
         10: '11-step10-completion.png', 11: '07-final-verification.png'}
project = Path(__file__).resolve().parents[2]
destination = project / 'reports/lab03/screenshots' / names[step]
if destination.exists() and '--replace' not in sys.argv[2:]:
    raise SystemExit(f'Existing screenshot will not be overwritten: {destination}')
with tempfile.TemporaryDirectory(prefix='lab03-screen-') as temporary:
    ready = Path(temporary) / 'ready'
    title = f'Lab03 step {step} - {Path(temporary).name}'
    command = f"set +m; clear; cd {shlex.quote(str(project))} && bash student/lab03/show-step.sh {step}; touch {shlex.quote(str(ready))}"
    applescript = f'''tell application "Terminal"
activate
do script ""
set evidenceTab to selected tab of front window
set custom title of evidenceTab to {json.dumps(title)}
set bounds of front window to {{30, 40, 1450, 1100}}
do script {json.dumps(command)} in evidenceTab
return id of front window
end tell'''
    window_id = subprocess.check_output(['osascript', '-e', applescript], text=True).strip()
    deadline = time.monotonic() + 30
    while not ready.exists():
        if time.monotonic() > deadline:
            raise SystemExit('Timed out waiting for Terminal evidence display.')
        time.sleep(0.1)
    time.sleep(1)
    find_window = f'''tell application "Terminal"
repeat with candidateWindow in windows
repeat with candidateTab in tabs of candidateWindow
if custom title of candidateTab is {json.dumps(title)} then
set selected tab of candidateWindow to candidateTab
set index of candidateWindow to 1
return id of candidateWindow
end if
end repeat
end repeat
error "Evidence tab is no longer available"
end tell'''
    subprocess.check_output(['osascript', '-e', find_window], text=True)
    time.sleep(0.5)
    cg_query = ('ObjC.import("CoreGraphics"); '
                'var windows = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(0, 0))); '
                f'var matches = windows.filter(w => /terminal/i.test(w.kCGWindowOwnerName || "") && (w.kCGWindowName || "").includes({json.dumps(title)})); '
                'if (!matches.length) throw Error("Evidence window not found in CoreGraphics"); '
                'String(matches[0].kCGWindowNumber);')
    window_id = subprocess.check_output(['osascript', '-l', 'JavaScript', '-e', cg_query], text=True).strip()
    captured = Path(temporary) / 'capture.png'
    subprocess.run(['screencapture', '-x', '-o', '-l', window_id, str(captured)], check=True)
    captured.replace(destination)
print(destination)
