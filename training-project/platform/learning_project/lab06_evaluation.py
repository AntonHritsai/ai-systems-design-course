"""Record human rubric inputs; never infer semantic support from identifiers."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .lab06 import _read, _write
from .lab06_generation import ROLES, _digest, _validated_protocol, verify_generation
from .workflow import WorkflowError

EXPLANATION_CHECKS = ('required_concepts_and_connections', 'teaching_route_qualification',
                      'supporting_claim_citations', 'unsupported_claim')
EDITABLE = {'supported_connections', 'evidence_reason', 'conflicting_instruction_present',
            'response_checks', 'judgment', 'response_reason', 'review_minutes'}


def _inputs(*, collection: Path, graph_path: Path, protocol_path: Path, runs_dir: Path):
    protocol = _validated_protocol(protocol_path, collection, graph_path)
    verified = verify_generation(collection=collection, graph_path=graph_path,
                                 protocol_path=protocol_path, runs_dir=runs_dir)
    rows, metadata = [], []
    for case in protocol['cases']:
        for role in ROLES:
            folder = runs_dir / case['evaluation_case_id'] / role.replace(' ', '-')
            outcome = _read(folder / 'outcome.json')
            kind = outcome.get('outcome_type')
            if kind not in ('generated prerequisite explanation', 'refusal'):
                raise WorkflowError('Unidentifiable outcome: execution failure; stop response judging.')
            run = _read(folder / 'run-metadata.json')
            capture = _read(folder / 'provider-response.json')
            if run.get('evidence_kind') == 'imported provider capture' and run.get('capture_digest') != _digest(capture):
                raise WorkflowError('Imported capture digest differs from preserved response.')
            keys = EXPLANATION_CHECKS if kind == 'generated prerequisite explanation' else ('blocking_condition_holds',)
            rows.append({'evaluation_case_id': case['evaluation_case_id'], 'configuration': role,
                'outcome_type': kind, 'outcome_digest': _digest(outcome),
                'metadata_digest': _digest(run), 'capture_digest': _digest(capture),
                'reference': case['reference'], 'request': case['requests'][role], 'outcome': outcome,
                'structural_issues': [i for i in verified['structural_issues']
                    if i['case'] == case['evaluation_case_id'] and i['configuration'] == role],
                'supported_connections': [None] * len(case['reference']['required_connections']),
                'evidence_reason': None, 'conflicting_instruction_present': None,
                'response_checks': dict.fromkeys(keys), 'judgment': None,
                'response_reason': None, 'review_minutes': None})
            metadata.append((run, capture))
    return protocol, rows, metadata


def prepare_judgments(*, collection: Path, graph_path: Path, protocol_path: Path,
                      runs_dir: Path, output: Path) -> Path:
    protocol, rows, _ = _inputs(collection=collection, graph_path=graph_path,
                              protocol_path=protocol_path, runs_dir=runs_dir)
    return _write(output, {'schema_version': 'lab06-judgments-v1', 'protocol_digest': _digest(protocol),
                           'human_evaluator': None, 'positions': rows})



def _number(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _human_judgment(row: dict, evaluator) -> bool:
    coverage, checks = row['supported_connections'], row['response_checks']
    if (not isinstance(coverage, list) or len(coverage) != len(row['reference']['required_connections'])
            or any(v is not None and type(v) is not bool for v in coverage)
            or not isinstance(checks, dict)
            or set(checks) != set(EXPLANATION_CHECKS if row['outcome_type'] == 'generated prerequisite explanation'
                                      else ('blocking_condition_holds',))
            or any(v is not None and type(v) is not bool for v in checks.values())
            or (row['conflicting_instruction_present'] is not None
                and type(row['conflicting_instruction_present']) is not bool)
            or row['judgment'] not in (None, 'pass', 'fail')):
        raise WorkflowError('Human judgment fields have invalid types or branch-specific checks.')
    for key in ('evidence_reason', 'response_reason'):
        if row[key] is not None and not _text(row[key]):
            raise WorkflowError('Human evidence and response reasons must be nonempty text.')
    if row['review_minutes'] is not None and (not _number(row['review_minutes']) or row['review_minutes'] <= 0):
        raise WorkflowError('Review effort must be finite positive minutes.')
    values = [*coverage, *checks.values(), row['conflicting_instruction_present'],
              row['judgment'], row['evidence_reason'], row['response_reason'], row['review_minutes']]
    if any(v is None for v in values):
        return False
    if not _text(evaluator):
        raise WorkflowError('An identified human evaluator must supply the completed judgments.')
    if row['outcome_type'] == 'generated prerequisite explanation':
        passes = (all(coverage) and not row['conflicting_instruction_present']
            and checks['required_concepts_and_connections'] and checks['teaching_route_qualification']
            and checks['supporting_claim_citations'] and not checks['unsupported_claim'])
    else:
        condition = row['outcome'].get('blocking_condition')
        holds = ((condition == 'insufficient supplied source evidence' and not all(coverage))
                 or (condition == 'conflicting instruction' and row['conflicting_instruction_present']))
        passes = checks['blocking_condition_holds'] and holds
    passes = bool(passes) and not row['structural_issues']
    if (row['judgment'] == 'pass') != passes:
        raise WorkflowError('Recorded pass/fail contradicts the supplied human checks or outcome structure.')
    return True


def _maximum(values: list, limit: float) -> bool | None:
    if any(v is not None and v > limit for v in values):
        return False
    return None if any(v is None for v in values) else True


def _assessment(*, judgments_path: Path, **common) -> dict:
    protocol, expected, metadata = _inputs(**common)
    judgments = _read(judgments_path)
    if (set(judgments) != {'schema_version', 'protocol_digest', 'human_evaluator', 'positions'}
            or judgments.get('schema_version') != 'lab06-judgments-v1'
            or judgments.get('protocol_digest') != _digest(protocol)
            or not isinstance(judgments.get('positions'), list)
            or len(judgments['positions']) != len(expected)):
        raise WorkflowError('Judgments must bind the complete frozen comparison.')
    positions = []
    for row, frame, (run, capture) in zip(judgments['positions'], expected, metadata):
        if (not isinstance(row, dict) or set(row) != set(frame)
                or {k:v for k,v in row.items() if k not in EDITABLE}
                   != {k:v for k,v in frame.items() if k not in EDITABLE}):
            raise WorkflowError('A judgment frame differs from the actual frozen position.')
        judged = _human_judgment(row, judgments['human_evaluator'])
        try:
            envelope = json.loads(capture['stdout'])
            usage = envelope.get('usage')
            tokens = usage.get('total_tokens') if isinstance(usage, dict) else None
        except (ValueError, KeyError, TypeError, AttributeError):
            tokens = None
        if type(tokens) is not int or tokens < 0:
            tokens = None
        # An offline extraction import cannot supply a measured complete live path.
        duration = run.get('question_time_seconds') if run.get('evidence_kind') == 'live' else None
        elapsed = run.get('elapsed_seconds')
        if not _number(duration) or not _number(elapsed) or duration < elapsed:
            duration = None
        positions.append({'evaluation_case_id': row['evaluation_case_id'], 'configuration': row['configuration'],
            'outcome_type': row['outcome_type'], 'supported_connections': row['supported_connections'],
            'judgment': row['judgment'] if judged else None,
            'unsupported_claim': row['response_checks'].get('unsupported_claim') if judged else None,
            'explanation_despite_conflict': row['outcome_type'] == 'generated prerequisite explanation'
                and row['conflicting_instruction_present'] if judged else None,
            'review_minutes': row['review_minutes'] if judged else None,
            'question_time_seconds': duration, 'reported_total_tokens': tokens,
            'timing_origin': run.get('evidence_kind')})
    limits = protocol['acceptance_conditions']
    configurations, missing = {}, []
    for role in ROLES:
        selected = [r for r in positions if r['configuration'] == role]
        judged = [r for r in selected if r['judgment'] is not None]
        passes = {kind: sum(r['judgment'] == 'pass' and r['outcome_type'] == kind for r in judged)
                  for kind in ('generated prerequisite explanation', 'refusal')}
        rate = sum(passes.values()) / len(judged) if judged else None
        absent = []
        for row in selected:
            for key in ('judgment', 'review_minutes', 'question_time_seconds', 'reported_total_tokens'):
                if row[key] is None:
                    absent.append(row['evaluation_case_id'] + ': ' + key)
        all_judged = len(judged) == len(selected)
        blocking = any(r['unsupported_claim'] or r['explanation_despite_conflict'] for r in judged)
        tokens = [r['reported_total_tokens'] for r in selected]
        known_total = sum(v for v in tokens if v is not None)
        tests = {'minimum_rubric_pass_rate': rate >= limits['minimum_rubric_pass_rate'] if all_judged else None,
            'blocking_failures': False if blocking else True if all_judged else None,
            'question_time': _maximum([r['question_time_seconds'] for r in selected], limits['maximum_question_time_seconds']),
            'human_review_effort': _maximum([r['review_minutes'] for r in selected], limits['maximum_review_minutes_per_outcome']),
            'token_usage': False if known_total > limits['maximum_total_tokens_per_configuration']
                else None if any(v is None for v in tokens) else True}
        configurations[role] = {'explanation_passes': passes['generated prerequisite explanation'],
            'refusal_passes': passes['refusal'], 'judged_outputs': len(judged),
            'awaiting_judgment': len(selected) - len(judged), 'rubric_pass_rate': rate,
            'total_reported_tokens': sum(r['reported_total_tokens'] for r in selected)
                if all(r['reported_total_tokens'] is not None for r in selected) else None,
            'acceptance_conditions': tests, 'missing_evidence': absent,
            'qualifies': all(tests.values()) if not absent else None}
        missing.extend(role + ': ' + item for item in absent)
    permitted = None
    if not missing:
        baseline, candidate = (configurations[r] for r in ROLES)
        if baseline['qualifies'] and candidate['qualifies']:
            permitted = ('adopt with graph expansion' if candidate['rubric_pass_rate'] > baseline['rubric_pass_rate']
                         else 'retain without graph expansion')
        elif candidate['qualifies']:
            permitted = 'adopt with graph expansion'
        elif baseline['qualifies']:
            permitted = 'retain without graph expansion'
        else:
            permitted = 'accept neither'
    return {'schema_version': 'lab06-assessment-v1', 'protocol_digest': _digest(protocol),
            'judgments_digest': _digest(judgments), 'complete': not missing,
            'missing_evidence': missing, 'permitted_decision': permitted,
            'configuration_decision': 'not recorded', 'scope': limits['scope'],
            'positions': positions, 'configurations': configurations}


def assess_comparison(*, judgments_path: Path, output: Path, **common) -> dict:
    result = _assessment(judgments_path=judgments_path, **common)
    _write(output, result)
    return result


def record_decision(*, judgments_path: Path, assessment_path: Path, decision_path: Path,
                    output: Path, **common) -> Path:
    current = _assessment(judgments_path=judgments_path, **common)
    if _read(assessment_path) != current:
        raise WorkflowError('Assessment is stale or changed; decision must use the current bound evidence.')
    intent = _read(decision_path)
    fields = {'engineering_team', 'decision', 'rationale', 'teaching_prediction_comparison',
              'graph_preparation_trade_off'}
    if set(intent) != fields or not all(_text(intent[k]) for k in fields):
        raise WorkflowError('Record the identified engineering team, decision and all three explanations.')
    if not current['complete'] or intent['decision'] != current['permitted_decision']:
        raise WorkflowError('Incomplete evidence permits no decision; complete evidence must follow frozen conditions.')
    return _write(output, {'schema_version': 'lab06-decision-v1',
        'protocol_digest': current['protocol_digest'], 'judgments_digest': current['judgments_digest'],
        'assessment_digest': _digest(current), 'engineering_decision': intent,
        'scope': current['scope'],
        'authority_boundary': 'Records the engineering team decision for these development cases only; no deployment approval or accepted-state write.'})
