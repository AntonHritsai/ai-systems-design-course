"""Read saved evidence for a screenshot without repeating a model call or judgment."""
import json
from pathlib import Path
import sys
import textwrap
import yaml

root = Path(__file__).resolve().parents[2]
report = root / 'reports/lab03'
step = int(sys.argv[1])

def load(path):
    return json.loads(path.read_text())

def paragraph(value):
    print(textwrap.fill(str(value), width=110))

def comparison():
    directories = sorted((report / 'comparisons').glob('cmp-*'))
    if len(directories) != 1:
        raise SystemExit('Expected exactly one recorded comparison.')
    return directories[0]

print(f'STEP {step} | Saved evidence, read-only display')
if step in (3, 4):
    schedule = load(report / 'development/schedule.json')
    by_id = {p['position_id']: p for p in schedule['positions']}
    for pid in schedule['order']:
        position = by_id[pid]
        if step == 3 and position['variant'] != 'a':
            continue
        directory = report / 'development/attempts' / pid
        structural = directory / 'structural-result.json'
        valid = load(structural)['valid'] if structural.exists() else 'n/a'
        print(f"{pid}: {position['state']}; structurally_valid={valid}")
        if (directory / 'raw-response.txt').exists():
            paragraph((directory / 'raw-response.txt').read_text())
        elif (directory / 'error.json').exists():
            paragraph(load(directory / 'error.json'))
    if step == 4:
        print('Single instruction factor: source-grounding policy')
elif step == 5:
    manifest = load(comparison() / 'freeze-manifest.json')
    print('Freeze:', manifest['freeze_id'])
    print('Frozen at:', manifest['frozen_at'])
    print('Route:', manifest['route'])
    print('A SHA256:', manifest['variant_a_sha256'])
    print('B SHA256:', manifest['variant_b_sha256'])
    for key in ('engineering_decision', 'hypothesis', 'semantic_acceptance', 'blocking_failures',
                'operational_acceptance', 'tradeoff_rule', 'attempt_budget', 'timing_boundary', 'resume_window'):
        paragraph(f"{key}: {manifest['protocol'].get(key, manifest.get(key))}")
elif step == 6:
    directory = comparison()
    schedule = load(directory / 'schedule.json')
    print('Freeze:', directory.name, '| Family:', schedule['family_id'])
    by_id = {p['position_id']: p for p in schedule['positions']}
    for index, pid in enumerate(schedule['order'], 1):
        position = by_id[pid]
        structural = directory / 'attempts' / pid / 'structural-result.json'
        valid = load(structural)['valid'] if structural.exists() else 'n/a'
        print(f"{index:02d}. {pid}: {position['state']}; valid={valid}")
elif step == 7:
    directory = comparison()
    print('Freeze:', directory.name)
    for path in sorted((directory / 'scoring/assessments').glob('*')):
        item = yaml.safe_load(path.read_text())
        print(item.get('blind_id', path.stem), '|', item.get('category'))
        paragraph('Source: ' + str(item.get('source_pointer', '')))
    print('Judgments prepared with assistant support; independent student review required.')
elif step == 8:
    directory = comparison()
    print('Freeze:', directory.name)
    aggregate = load(directory / 'scoring/aggregate.json')
    columns = ('attempted', 'returned', 'structurally_valid', 'assessable', 'rubric_acceptable')
    print('Variant | ' + ' | '.join(columns))
    for variant, counts in aggregate['nested_counts'].items():
        print(variant.upper() + ' | ' + ' | '.join(str(counts[c]) for c in columns))
    for key in ('failure_counts', 'unstarted_counts', 'critical_unsupported_counts', 'observed_models', 'unknown_values'):
        paragraph(f'{key}: {aggregate[key]}')
    for variant, entries in aggregate['observed_latency'].items():
        times = [e['seconds'] for e in entries if e['seconds'] is not None]
        paragraph(f'{variant.upper()} latency, seconds: count={len(times)}, mean={sum(times)/len(times):.3f}, max={max(times):.3f}' if times else 'Latency unknown')
    recommendation = yaml.safe_load((directory / 'recommendation.yaml').read_text())
    print('Outcome:', recommendation['outcome'])
    paragraph(recommendation['rationale'])
    paragraph(recommendation['limitations'])
elif step == 9:
    for path in sorted((report / 'regression').glob('*.yaml')):
        print(path.name)
        print(path.read_text())
elif step == 10:
    print((report / 'completion-status.yaml').read_text())
    print('Report sections:')
    for line in (report / 'REPORT.md').read_text().splitlines():
        if line.startswith('## '):
            print(line)
elif step == 11:
    verification = load(report / 'verification-report.json')
    print('Final commit:', verification['final_commit'])
    print('Result:', verification['outcome'])
    for check in verification['checks']:
        paragraph(f"{check['check_id']}: {check['status']} | {check['message']}")
else:
    raise SystemExit('Use a step between 3 and 11.')
