"""Preserve one traced source-grounding failure after assessments are frozen."""
import json
from pathlib import Path
import yaml

comparison = Path('reports/lab03/comparisons/cmp-d5d3bf609779')
join = json.loads((comparison / 'scoring/_join-map.json').read_text())
entry = next(e for e in join['entries'] if e['blind_id'] == 'blind-002')
assert entry['position_id'] == 'pos-criterion-metric-chain-distractor-a-1'
assessment = yaml.safe_load((comparison / 'scoring/assessments/blind-002.yaml').read_text())
assert assessment['category'] == 'U'
structural = json.loads((comparison / 'attempts' / entry['position_id'] / 'structural-result.json').read_text())
assert structural['valid']
record = {
 'regression_id': 'criterion-metric-unsupported-examples',
 'source_kind': 'observed-failure',
 'position_id': entry['position_id'],
 'blind_id': 'blind-002',
 'comparison_id': comparison.name,
 'source_pointer': entry['supplied_source'],
 'diagnosis': 'Завдання просило пояснити зв’язок критерію та метрики за наданим джерелом. Джерело підтримує властивість, вимірювання та напрям порівняння; відповідь A структурно чинна, але додає reliability, usability, security, response time та average latency in milliseconds, яких джерело не надає. Рубрика U вимагає джерельної підтримки кожного змістовного твердження, тому правильна основна частина не усуває відмови. Простежено запит, вихід, структурний результат і blind-002; дефект стосується джерельної обмеженості спостереженого виходу конфігурації A, без твердження про причинний ефект інструкції окремо від моделі маршруту.',
 'expected_behavior_review': 'Затверджена до генерування очікувана поведінка вимагає зберегти зв’язок критерію, метрики й порівняння та не переносити відволікальну примітку про резервні копії до пояснення. Вона узгоджується з двома першими реченнями джерела та загальним правилом підкріплення кожного твердження; додаткові технічні приклади не мають підтримки. Очікувана поведінка не переписувалася після відповіді; виправлена поведінка має зберегти три підтримані ланки без зовнішніх прикладів.',
 'reviewed_by': 'anton-hritsai'
}
path = Path('student/lab03/regression.yaml')
with path.open('x') as stream:
    stream.write(yaml.safe_dump(record, allow_unicode=True, sort_keys=False))
print(path)
