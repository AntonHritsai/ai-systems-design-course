#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
printf 'GitHub: AntonHritsai | OS account: %s\n' "$(id -un)"
TZ=Europe/Kyiv date '+%Y-%m-%d %H:%M:%S %Z'
printf 'Branch: %s\n' "$(git branch --show-current)"
case "${1:-}" in
  0)
    git remote -v
    git log -1 --format='%H %s'
    ;;
  1)
    printf 'Saved result from admission replay on original lab02 branch:\n'
    cat reports/lab03/admission-replay.log
    ls -ld reports/lab03/REPORT.md reports/lab03/screenshots student/lab03
    ;;
  2)
    uv run python - <<'PY'
import json
from pathlib import Path
result = json.loads(Path('reports/lab03/calibration/calibration-a/calibration-result.json').read_text())
print('Packet:', result['packet_id'])
print(f"Calibration complete: {result['agreement']}/{result['total']} labels agree with reviewed labels.")
for item in result['comparison']:
    print(f"{item['output_id']}: student={item['student_category']} reviewed={item['reviewed_category']} agrees={item['agrees']}")
print('Judgments prepared with assistant support; student review is still required.')
PY
    ;;
  3|4|5|6|7|8|9|10|11)
    uv run python student/lab03/show-step.py "$1"
    ;;
  *)
    printf 'Use: bash student/lab03/show-step.sh <0..11>\n' >&2
    exit 2
    ;;
esac
printf '\nGitHub: AntonHritsai | OS account: %s | Step: %s\n' "$(id -un)" "$1"
TZ=Europe/Kyiv date '+%Y-%m-%d %H:%M:%S %Z'
