"""Student report structure; semantic judgments remain human-owned."""
from __future__ import annotations

import re
from pathlib import Path

from . import report_contract

HEADINGS = ('Ідентифікація', 'Мета роботи', 'Хід виконання', 'Висновки')
SCREENSHOTS = ('01-reviewed-graph.png', '02-bounded-paths.png', '03-evidence-preparation.png',
               '04-observed-outcomes.png', '05-comparison-decision.png',
               '06-transfer-review.png', '07-final-verification.png')
REQUIRED_EVIDENCE = ('graph-preparation/review.json', 'graph-preparation/graph.json',
    'graph-query/paths-1.json', 'graph-query/paths-2.json', 'graph-query/direct-edge.json',
    'evidence-preparation/evidence-preparation.json', 'evidence-preparation/policy-probes.json',
    'generation/protocol.json', 'judgments.json', 'comparison.json', 'decision-input.json', 'decision.json',
    *(f'generation/runs/{case}/{role}/{name}' for case in ('EC-06-1-v1', 'EC-06-2-v1')
      for role in ('without-graph-expansion', 'with-graph-expansion')
      for name in ('provider-response.json', 'outcome.json', 'run-metadata.json')))
INTERNAL = r'(?<![\w-])(?:Authoring\s+Stage\b|Stage\s+(?:A|B|C1|C2|C3|C4|D|E)\b)'


def _report_scope(report_dir: Path, text: str) -> tuple[str, tuple[str, ...]]:
    # Keep identity/completion syntax aligned with report_contract flexible bullets/spacing.
    partial = re.search(r'^\s*[-*]?\s*Статус завершення:\s*`?honest-partial`?\s*$', text, re.M)
    if not partial:
        return 'complete', SCREENSHOTS
    groups = (('graph-preparation',), ('graph-query',), ('evidence-preparation',),
              ('generation',), ('judgments.json', 'comparison.json', 'decision.json'))
    reached = []
    for index, group in enumerate(groups):
        if any((report_dir / name).is_file() or
               any(p.is_file() for p in (report_dir / name).rglob('*')) for name in group):
            reached.append(SCREENSHOTS[index])
    if ('screenshots/' + SCREENSHOTS[-2]) in text or (report_dir / 'screenshots' / SCREENSHOTS[-2]).is_file():
        reached.append(SCREENSHOTS[-2])
    return 'honest-partial', (*reached, SCREENSHOTS[-1])


def validate_report(*, report_dir: Path) -> dict:
    """Check the source report, not human support or goal attainment."""
    path = report_dir / 'REPORT.md'
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    state, screenshots = _report_scope(report_dir, text)
    result = report_contract.validate_report_contract(
        report_dir=report_dir, lab_id='lab06', lab_label='Laboratory 06', headings=HEADINGS,
        screenshots=screenshots, required_evidence=REQUIRED_EVIDENCE if state == 'complete' else (),
        internal_stage_pattern=INTERNAL, evidence_present_message='required reporting evidence is present',
        personal_branch_pattern=r'lab06/[A-Za-z0-9._-]+', personal_branch_example='lab06/<student-id>')
    path = report_dir / 'REPORT.md'
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    prompts = re.search(r'\[(?:Дія:|Сформулювати|Стисло|Указати)[^\n]*\]', text)
    passed = prompts is None and 'Заповнити кожен розділ' not in text
    result['checks'].append({'check_id':'report-prompts', 'status':'passed' if passed else 'failed',
                             'message':'replace all fixture prompts and introductory instructions'})
    if state == 'honest-partial':
        stop = re.search(r'^### Межа зупинки\s*\n(.+?)(?=^## |\Z)', text, re.M | re.S)
        recorded = stop is not None and bool(stop[1].strip())
        result['checks'].append({'check_id':'partial-stop', 'status':'passed' if recorded else 'failed',
                                 'message':'a partial report must record the stopping boundary and missing result'})
    result['completion_state'] = state
    result['screenshots'] = list(screenshots)
    result['status'] = 'passed' if all(c['status']=='passed' for c in result['checks']) else 'failed'
    return result


def _verify_domain(report_dir: Path, collection: Path) -> None:
    """Replay existing deterministic checks; do not call a model or rejudge."""
    import tempfile
    from . import lab06, lab06_evaluation as evaluation
    from .workflow import WorkflowError
    graph = report_dir / 'graph-preparation/graph.json'
    lab06.verify_graph(collection=collection, graph_path=graph)
    if lab06._read(report_dir / 'graph-preparation/review.json') != lab06._read(collection / 'accepted.json')['review']:
        raise WorkflowError('Report review differs from accepted storage.')
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'expected.json'
        for depth in (1, 2):
            lab06.query_paths(collection=collection, graph_path=graph, start='C-RET', max_edges=depth, output=target)
            if lab06._read(target) != lab06._read(report_dir / f'graph-query/paths-{depth}.json'):
                raise WorkflowError('Bounded query differs from the accepted graph.')
            target.unlink()
        lab06.inspect_direct_edge(collection=collection, graph_path=graph, start='C-RET', target='C-MODEL', output=target)
        if lab06._read(target) != lab06._read(report_dir / 'graph-query/direct-edge.json'):
            raise WorkflowError('Direct-edge inspection differs from the accepted graph.')
        target.unlink()
        for name, fixture in [('evidence-preparation', 'evidence-preparation'), ('policy-probes', 'evidence-policy-probes')]:
            lab06.verify_evidence(collection=collection, graph_path=graph,
                fixture_path=lab06.DEFAULT_INPUT.with_name(fixture + '.json'),
                evidence_path=report_dir / f'evidence-preparation/{name}.json')
        common = dict(collection=collection, graph_path=graph, protocol_path=report_dir / 'generation/protocol.json',
                      runs_dir=report_dir / 'generation/runs', judgments_path=report_dir / 'judgments.json')
        evaluation.record_decision(**common, assessment_path=report_dir / 'comparison.json',
            decision_path=report_dir / 'decision-input.json', output=target)
        if lab06._read(target) != lab06._read(report_dir / 'decision.json'):
            raise WorkflowError('Recorded decision differs from the current bound evidence.')


def _committed_inputs(report_dir: Path, collection: Path, final_commit: str) -> None:
    import subprocess
    from .workflow import WorkflowError
    if not re.fullmatch(r'[0-9a-f]{40}', final_commit):
        raise WorkflowError('Use the exact full final commit hash.')
    root = Path(subprocess.check_output(['git', '-C', str(report_dir), 'rev-parse', '--show-toplevel'], text=True).strip())
    branch = subprocess.check_output(['git', '-C', str(root), 'branch', '--show-current'], text=True).strip()
    recorded_branch = re.search(
        r'^\s*[-*]?\s*Особиста гілка:\s*`?([^`\s]+)`?\s*$',
        (report_dir / 'REPORT.md').read_text(encoding='utf-8'),
        re.M,
    )
    if recorded_branch is None or recorded_branch[1] != branch:
        raise WorkflowError('The report personal branch must name the current branch.')
    relative_collection = (collection / 'accepted.json').resolve().relative_to(root.resolve()).as_posix()
    drift = subprocess.run(['git', '-C', str(root), 'diff', '--quiet', final_commit, '--', relative_collection])
    if drift.returncode:
        raise WorkflowError('Accepted collection changed or was removed after the final commit.')
    post_commit = {report_dir / 'verification-report.json', report_dir / 'screenshots' / SCREENSHOTS[-1],
                   report_dir / 'submission/REPORT.md'}
    paths = [p for p in report_dir.rglob('*') if p.is_file() and p not in post_commit]
    if (collection / 'accepted.json').exists():
        paths.append(collection / 'accepted.json')
    for path in paths:
        if path.is_symlink():
            raise WorkflowError('Report evidence must not be a symbolic link: ' + str(path))
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        recorded = subprocess.run(['git', '-C', str(root), 'show', final_commit + ':' + relative], capture_output=True)
        if recorded.returncode or recorded.stdout != path.read_bytes():
            raise WorkflowError('Input is uncommitted or changed after the final commit: ' + relative)


def verify(*, report_dir: Path, collection: Path, final_commit: str) -> dict:
    """Bind a complete or explicitly partial report; never manufacture grades."""
    from .lab06 import _write
    validation = validate_report(report_dir=report_dir)
    try:
        _committed_inputs(report_dir, collection, final_commit)
    except Exception as exc:
        validation['checks'].append({'check_id':'committed-inputs', 'status':'failed', 'message':str(exc)})
    else:
        validation['checks'].append({'check_id':'committed-inputs', 'status':'passed',
                                     'message':'source report, existing machine evidence and collection match committed bytes'})
    domain_passed = False
    if validation['completion_state'] == 'complete':
        try:
            _verify_domain(report_dir, collection)
        except Exception as exc:  # collect the failing domain boundary without overwriting its input
            validation['checks'].append({'check_id':'domain-evidence', 'status':'failed', 'message':str(exc)})
        else:
            domain_passed = True
            validation['checks'].append({'check_id':'domain-evidence', 'status':'passed',
                                         'message':'existing deterministic checks match the recorded human inputs and decision'})

    def write(path, result):
        result.update(completion_state=validation['completion_state'],
                      domain_completion_claimed=domain_passed and result['outcome']=='passed')
        _write(path, result)

    return report_contract.verify_report_contract(
        report_dir=report_dir, final_commit=final_commit, lab_id='lab06', lab_label='Laboratory 06',
        screenshots=tuple(validation['screenshots']), validation=validation, write_report=write)
