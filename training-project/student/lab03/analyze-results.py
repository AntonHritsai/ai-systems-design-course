"""Derive transparent supplementary summaries without changing course evidence."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import yaml

comparison = Path('reports/lab03/comparisons/cmp-d5d3bf609779')
schedule = json.loads((comparison / 'schedule.json').read_text())
join_path = comparison / 'scoring/_join-map.json'
if not join_path.exists():
    raise SystemExit('Inspect the course join-map filename after assessment before running this analysis.')
join = json.loads(join_path.read_text())
joined = {e['position_id']: e['blind_id'] for e in join['entries']}
summary = {'comparison_id': comparison.name, 'category_counts': {}, 'latency': {}, 'repeated_attempts': []}
by_case = {}
for variant in ('a', 'b'):
    counts = Counter()
    times = []
    unknown_latency = 0
    for p in schedule['positions']:
        if p['variant'] != variant:
            continue
        directory = comparison / 'attempts' / p['position_id']
        if p['position_id'] in joined:
            bid = joined[p['position_id']]
            judgment = yaml.safe_load((comparison / 'scoring/assessments' / f'{bid}.yaml').read_text())
            counts[judgment['category']] += 1
            category = judgment['category']
        else:
            category = None
        if (directory / 'raw-response.txt').exists():
            raw = (directory / 'raw-response.txt').read_bytes()
            by_case.setdefault((p['case_id'], variant), []).append({'position_id': p['position_id'], 'category': category, 'raw_sha256': hashlib.sha256(raw).hexdigest()})
        if (directory / 'run-metadata.json').exists():
            meta = json.loads((directory / 'run-metadata.json').read_text())
            if isinstance(meta.get('started_at'), str) and isinstance(meta.get('finished_at'), str):
                times.append((datetime.fromisoformat(meta['finished_at']) - datetime.fromisoformat(meta['started_at'])).total_seconds())
            else:
                unknown_latency += 1
    summary['category_counts'][variant] = dict(counts)
    summary['latency'][variant] = {'count': len(times), 'unknown_count': unknown_latency, 'mean_seconds': statistics.mean(times) if times else None, 'median_seconds': statistics.median(times) if times else None, 'max_seconds': max(times) if times else None}
for (case, variant), entries in by_case.items():
    summary['repeated_attempts'].append({'case_id': case, 'variant': variant, 'responses': entries,
        'raw_differs': len({e['raw_sha256'] for e in entries}) > 1 if len(entries) == 2 else None,
        'category_differs': len({e['category'] for e in entries}) > 1 if len(entries) == 2 and all(e['category'] is not None for e in entries) else None})
summary['course_repeat_flag_limitation'] = 'Course aggregate repeated_attempt_differences compares blind-id:category strings, so distinct blind IDs can set the flag even when categories match. Use the separately recomputed raw_differs and category_differs fields.'
path = Path('reports/lab03/analysis-summary.json')
with path.open('x') as stream:
    stream.write(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
