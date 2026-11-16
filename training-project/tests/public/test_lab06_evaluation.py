"""Synthetic unit-test captures; never presented as observed human judgments."""
import json
import unittest
from types import SimpleNamespace

import test_lab06_generation as generation_tests
from learning_project import lab06_generation as generation
from learning_project.workflow import WorkflowError


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.g = generation_tests.GenerationTests()
        self.g.setUp()
        self.addCleanup(self.g.doCleanups)
        self.g.prepare()
        self.root = self.g.root
        self.runs = self.root / 'runs'
        self.common = dict(collection=self.g.query.collection, graph_path=self.g.query.graph,
                           protocol_path=self.g.protocol, runs_dir=self.runs)
        self.judgments = self.root / 'judgments.json'
        self.assessment = self.root / 'assessment.json'
        for case_id in ['EC-06-1-v1', 'EC-06-2-v1']:
            for role in generation.ROLES:
                outcome = {'outcome_type': 'generated prerequisite explanation',
                           'claims': [{'text': 'SYNTHETIC TEST CLAIM', 'fragment_ids': ['F-1']}]}
                def runner(*args, **kwargs):
                    return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({
                        'status': 'SUCCESS', 'structured_output': outcome, 'usage': {'total_tokens': 100}}))
                generation.run_generation(**{k:v for k,v in self.common.items() if k != 'runs_dir'},
                    case_id=case_id, role=role, output_dir=self.runs / case_id / role.replace(' ', '-'),
                    runner=runner)

    def test_prepare_binds_exact_outputs_and_leaves_all_semantic_fields_blank(self):
        from learning_project import lab06_evaluation as evaluation
        evaluation.prepare_judgments(**self.common, output=self.judgments)
        data = json.loads(self.judgments.read_text())
        self.assertIsNone(data['human_evaluator'])
        self.assertEqual(len(data['positions']), 4)
        for row in data['positions']:
            self.assertIsNone(row['judgment'])
            self.assertEqual(row['supported_connections'], [None, None])
            self.assertEqual(row['outcome_type'], 'generated prerequisite explanation')
            self.assertTrue(row['outcome_digest'])
        self.assertNotIn('configuration_decision', data)

    def filled(self):
        from learning_project import lab06_evaluation as evaluation
        evaluation.prepare_judgments(**self.common, output=self.judgments)
        data = json.loads(self.judgments.read_text())
        data['human_evaluator'] = 'SYNTHETIC TEST EVALUATOR — not a real human session'
        for index, row in enumerate(data['positions']):
            row['supported_connections'] = [True, index != 0]
            row['evidence_reason'] = 'Synthetic calibration input; not an assessment of live model claims.'
            row['conflicting_instruction_present'] = False
            row['response_checks'] = dict(required_concepts_and_connections=index != 0,
                teaching_route_qualification=True, supporting_claim_citations=True, unsupported_claim=False)
            row['judgment'] = 'fail' if index == 0 else 'pass'
            row['response_reason'] = 'Synthetic incompleteness' if index == 0 else 'Synthetic pass'
            row['review_minutes'] = 1
        self.judgments.write_text(json.dumps(data))
        return data

    def test_complete_human_inputs_keep_failures_in_configuration_local_denominators(self):
        from learning_project import lab06_evaluation as evaluation
        self.filled()
        result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments,
                                              output=self.assessment)
        self.assertTrue(result['complete'])
        self.assertEqual(result['permitted_decision'], 'adopt with graph expansion')
        without, with_graph = [result['configurations'][role] for role in generation.ROLES]
        self.assertEqual(without['rubric_pass_rate'], 0.5)
        self.assertEqual(with_graph['rubric_pass_rate'], 1.0)
        self.assertEqual(without['judged_outputs'], 2)
        self.assertEqual(with_graph['judged_outputs'], 2)
        self.assertFalse(without['qualifies'])
        self.assertTrue(with_graph['qualifies'])
        self.assertFalse(result['positions'][0]['supported_connections'][1])
        self.assertFalse(result['positions'][0]['unsupported_claim'])
        self.assertEqual(result['configuration_decision'], 'not recorded')

    def test_blank_assessment_records_missing_judgments_without_inventing_a_rate(self):
        from learning_project import lab06_evaluation as evaluation
        evaluation.prepare_judgments(**self.common, output=self.judgments)
        result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments,
                                              output=self.assessment)
        self.assertFalse(result['complete'])
        self.assertIsNone(result['permitted_decision'])
        for role in generation.ROLES:
            self.assertEqual(result['configurations'][role]['judged_outputs'], 0)
            self.assertIsNone(result['configurations'][role]['rubric_pass_rate'])
            self.assertEqual(result['configurations'][role]['awaiting_judgment'], 2)
            self.assertIsNone(result['configurations'][role]['acceptance_conditions']['blocking_failures'])
            self.assertIsNone(result['configurations'][role]['acceptance_conditions']['minimum_rubric_pass_rate'])

    def test_recording_requires_explicit_engineering_intent_and_recomputed_assessment(self):
        from learning_project import lab06_evaluation as evaluation
        self.filled()
        evaluation.assess_comparison(**self.common, judgments_path=self.judgments, output=self.assessment)
        intent = self.root / 'decision-input.json'
        payload = {'engineering_team': 'SYNTHETIC TEST ENGINEER', 'decision': 'adopt with graph expansion',
                   'rationale': 'Synthetic threshold exercise only.',
                   'teaching_prediction_comparison': 'Synthetic inputs, not observed prediction accuracy.',
                   'graph_preparation_trade_off': 'Preparation burden remains separate from question-time.'}
        intent.write_text(json.dumps(payload))
        target = self.root / 'decision.json'
        evaluation.record_decision(**self.common, judgments_path=self.judgments,
            assessment_path=self.assessment, decision_path=intent, output=target)
        result = json.loads(target.read_text())
        self.assertEqual(result['engineering_decision'], payload)
        self.assertTrue(result['assessment_digest'])
        payload['decision'] = 'retain without graph expansion'; intent.write_text(json.dumps(payload))
        with self.assertRaises(WorkflowError):
            evaluation.record_decision(**self.common, judgments_path=self.judgments,
                assessment_path=self.assessment, decision_path=intent, output=self.root / 'wrong-decision.json')
        self.assertFalse((self.root / 'wrong-decision.json').exists())

    def test_cli_prepares_assesses_and_records_explicit_synthetic_decision(self):
        flags = ['--collection', self.common['collection'], '--graph', self.common['graph_path'],
                 '--protocol', self.g.protocol, '--runs-dir', self.runs]
        code, message = self.g.query.cli('prepare-judgments', *flags, '--output', self.judgments)
        self.assertEqual(code, 0, message)
        self.judgments.unlink()  # Unit fixture reset only; no generation evidence is deleted.
        self.filled()
        code, message = self.g.query.cli('assess-comparison', *flags, '--judgments', self.judgments,
                                       '--output', self.assessment)
        self.assertEqual(code, 0, message)
        intent = self.root / 'intent.json'
        intent.write_text(json.dumps({'engineering_team': 'SYNTHETIC CLI TEST',
            'decision': 'adopt with graph expansion', 'rationale': 'Synthetic fixture conditions.',
            'teaching_prediction_comparison': 'Synthetic only.',
            'graph_preparation_trade_off': 'Separate preparation cost.'}))
        code, message = self.g.query.cli('record-decision', *flags, '--judgments', self.judgments,
            '--assessment', self.assessment, '--decision-input', intent, '--output', self.root / 'cli-decision.json')
        self.assertEqual(code, 0, message)
        self.assertIn('no accepted-state write', message)

    def test_four_decision_branches_follow_only_complete_frozen_condition_results(self):
        from copy import deepcopy
        from learning_project import lab06_evaluation as evaluation
        original = self.filled()
        for baseline_pass, candidate_pass, expected in [
            (True, True, 'retain without graph expansion'),
            (True, False, 'retain without graph expansion'),
            (False, True, 'adopt with graph expansion'),
            (False, False, 'accept neither')]:
            with self.subTest(baseline=baseline_pass, candidate=candidate_pass):
                data = deepcopy(original)
                for row in data['positions']:
                    passing = baseline_pass if row['configuration'] == generation.ROLES[0] else candidate_pass
                    row['supported_connections'] = [True, True]
                    row['response_checks']['required_concepts_and_connections'] = True
                    row['response_checks']['unsupported_claim'] = not passing
                    row['judgment'] = 'pass' if passing else 'fail'
                self.judgments.write_text(json.dumps(data))
                result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments,
                    output=self.root / f'assessment-{baseline_pass}-{candidate_pass}.json')
                self.assertEqual(result['permitted_decision'], expected)

    def test_refusal_uses_its_own_check_and_never_becomes_a_relabelled_explanation(self):
        from learning_project import lab06_evaluation as evaluation
        folder = self.runs / 'EC-06-1-v1' / 'without-graph-expansion'
        outcome = {'outcome_type': 'refusal', 'blocking_condition': 'insufficient supplied source evidence'}
        raw = json.loads((folder / 'provider-response.json').read_text())
        env = json.loads(raw['stdout']); env['structured_output'] = outcome; raw['stdout'] = json.dumps(env)
        (folder / 'provider-response.json').write_text(json.dumps(raw))
        (folder / 'outcome.json').write_text(json.dumps(outcome))
        data = self.filled()
        data['positions'][0]['response_checks'] = {'blocking_condition_holds': True}
        data['positions'][0]['judgment'] = 'pass'
        self.judgments.write_text(json.dumps(data))
        result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments, output=self.assessment)
        base = result['configurations'][generation.ROLES[0]]
        self.assertEqual(base['refusal_passes'], 1)
        self.assertEqual(base['explanation_passes'], 1)
        self.assertEqual(base['rubric_pass_rate'], 1)
        self.assertEqual(result['permitted_decision'], 'retain without graph expansion')

    def test_import_missing_usage_and_partial_judgments_never_permit_a_decision(self):
        from learning_project import lab06_evaluation as evaluation
        data = self.filled()
        row = data['positions'][3]
        folder = self.runs / row['evaluation_case_id'] / row['configuration'].replace(' ', '-')
        metadata = json.loads((folder / 'run-metadata.json').read_text())
        raw = json.loads((folder / 'provider-response.json').read_text())
        env = json.loads(raw['stdout']);env.pop('usage');raw['stdout'] = json.dumps(env)
        (folder / 'provider-response.json').write_text(json.dumps(raw))
        metadata.update(evidence_kind='imported provider capture', question_time_seconds=0,
                        capture_digest=generation._digest(raw))
        (folder / 'run-metadata.json').write_text(json.dumps(metadata))
        row.update(metadata_digest=generation._digest(metadata),capture_digest=generation._digest(raw))
        data['positions'][0]['response_checks']['required_concepts_and_connections'] = None
        self.judgments.write_text(json.dumps(data))
        result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments, output=self.assessment)
        self.assertFalse(result['complete'])
        self.assertIsNone(result['positions'][3]['question_time_seconds'])
        self.assertIsNone(result['permitted_decision'])
        self.assertIsNone(result['configurations'][generation.ROLES[1]]['total_reported_tokens'])
        self.assertEqual(result['configurations'][generation.ROLES[0]]['judged_outputs'], 1)

    def test_operational_limits_and_incoherent_live_timing_are_not_silently_accepted(self):
        from copy import deepcopy
        from learning_project import lab06_evaluation as evaluation
        original = self.filled()
        folder = self.runs / 'EC-06-1-v1' / 'with-graph-expansion'
        meta_path, raw_path = folder / 'run-metadata.json', folder / 'provider-response.json'
        original_meta, original_raw = json.loads(meta_path.read_text()), json.loads(raw_path.read_text())
        for index, variant in enumerate(['time-limit', 'review-limit', 'token-limit', 'incoherent-time']):
            with self.subTest(variant=variant):
                data, meta, raw = deepcopy(original), deepcopy(original_meta), deepcopy(original_raw)
                if variant == 'review-limit': data['positions'][1]['review_minutes'] = 11
                if variant == 'time-limit': meta['question_time_seconds'] = 361
                if variant == 'incoherent-time': meta['question_time_seconds'] = 0
                if variant == 'token-limit':
                    env = json.loads(raw['stdout']);env['usage']['total_tokens'] = 200001;raw['stdout'] = json.dumps(env)
                meta_path.write_text(json.dumps(meta));raw_path.write_text(json.dumps(raw))
                data['positions'][1].update(metadata_digest=generation._digest(meta),capture_digest=generation._digest(raw))
                self.judgments.write_text(json.dumps(data))
                result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments,
                                                      output=self.root / f'limits-{index}.json')
                if variant == 'incoherent-time':
                    self.assertFalse(result['complete'])
                    self.assertIsNone(result['permitted_decision'])
                else:
                    self.assertTrue(result['complete'])
                    self.assertEqual(result['permitted_decision'], 'accept neither')

    def test_stale_assessment_and_each_create_only_target_are_protected(self):
        from learning_project import lab06_evaluation as evaluation
        self.filled()
        evaluation.assess_comparison(**self.common, judgments_path=self.judgments, output=self.assessment)
        decision = self.root / 'intent.json'
        decision.write_text(json.dumps(dict(engineering_team='SYNTHETIC TEST', decision='adopt with graph expansion',
            rationale='Synthetic.', teaching_prediction_comparison='Synthetic.', graph_preparation_trade_off='Synthetic.')))
        for operation in ['prepare', 'assessment', 'decision']:
            for kind in ['regular', 'dangling', 'existing-target']:
                with self.subTest(operation=operation, kind=kind):
                    output = self.root / f'{operation}-{kind}.json'
                    outside = self.root / f'outside-{operation}-{kind}.json'
                    if kind == 'regular': output.write_text('KEEP')
                    else:
                        if kind == 'existing-target': outside.write_text('KEEP')
                        output.symlink_to(outside)
                    with self.assertRaises(WorkflowError):
                        if operation == 'prepare': evaluation.prepare_judgments(**self.common, output=output)
                        elif operation == 'assessment': evaluation.assess_comparison(**self.common,
                            judgments_path=self.judgments, output=output)
                        else: evaluation.record_decision(**self.common, judgments_path=self.judgments,
                            assessment_path=self.assessment, decision_path=decision, output=output)
                    if outside.exists(): self.assertEqual(outside.read_text(), 'KEEP')
        stale = json.loads(self.assessment.read_text());stale['permitted_decision'] = 'retain without graph expansion'
        self.assessment.write_text(json.dumps(stale))
        with self.assertRaises(WorkflowError):
            evaluation.record_decision(**self.common, judgments_path=self.judgments,
                assessment_path=self.assessment, decision_path=decision, output=self.root / 'stale-decision.json')
        self.assertFalse((self.root / 'stale-decision.json').exists())

    def test_identifiable_malformed_explanation_is_judged_failure_not_execution_failure(self):
        from learning_project import lab06_evaluation as evaluation
        folder = self.runs / 'EC-06-1-v1' / 'without-graph-expansion'
        outcome = {'outcome_type': 'generated prerequisite explanation'}
        raw = json.loads((folder / 'provider-response.json').read_text())
        env = json.loads(raw['stdout']);env['structured_output'] = outcome;raw['stdout'] = json.dumps(env)
        (folder / 'provider-response.json').write_text(json.dumps(raw));(folder / 'outcome.json').write_text(json.dumps(outcome))
        self.filled()
        result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments, output=self.assessment)
        self.assertEqual(result['configurations'][generation.ROLES[0]]['judged_outputs'], 2)
        self.assertEqual(result['positions'][0]['judgment'], 'fail')
        self.assertEqual(result['positions'][0]['outcome_type'], 'generated prerequisite explanation')

    def test_unidentifiable_outcome_stops_judgment_preparation(self):
        from learning_project import lab06_evaluation as evaluation
        folder = self.runs / 'EC-06-1-v1' / 'without-graph-expansion'
        outcome = {'outcome_type': []}
        raw = json.loads((folder / 'provider-response.json').read_text())
        env = json.loads(raw['stdout']);env['structured_output'] = outcome;raw['stdout'] = json.dumps(env)
        (folder / 'provider-response.json').write_text(json.dumps(raw));(folder / 'outcome.json').write_text(json.dumps(outcome))
        with self.assertRaisesRegex(WorkflowError, 'Unidentifiable'):
            evaluation.prepare_judgments(**self.common, output=self.judgments)
        self.assertFalse(self.judgments.exists())

    def test_conflicting_instruction_blocks_an_explanation_without_renaming_the_outcome(self):
        from learning_project import lab06_evaluation as evaluation
        data = self.filled()
        data['positions'][1]['conflicting_instruction_present'] = True
        data['positions'][1]['judgment'] = 'fail'
        self.judgments.write_text(json.dumps(data))
        result = evaluation.assess_comparison(**self.common, judgments_path=self.judgments, output=self.assessment)
        self.assertEqual(result['permitted_decision'], 'accept neither')
        self.assertFalse(result['configurations'][generation.ROLES[1]]['acceptance_conditions']['blocking_failures'])
        self.assertTrue(result['positions'][1]['explanation_despite_conflict'])
        self.assertEqual(result['positions'][1]['outcome_type'], 'generated prerequisite explanation')

    def test_wrong_frames_typed_checks_and_nonfinite_effort_are_rejected(self):
        from copy import deepcopy
        from learning_project import lab06_evaluation as evaluation
        original = self.filled()
        variants = [('review_minutes', v) for v in [True, -1, 0, float('nan'), float('inf'), 10**1000]]
        variants += [('judgment', []), ('outcome_digest', 'changed'), ('supported_connections', [True, 1]),
                     ('response_checks', {'blocking_condition_holds': True})]
        for index, (key, value) in enumerate(variants):
            with self.subTest(field=key, variant=index):
                data = deepcopy(original); data['positions'][0][key] = value
                self.judgments.write_text(json.dumps(data))
                with self.assertRaises(WorkflowError):
                    evaluation.assess_comparison(**self.common, judgments_path=self.judgments,
                                                 output=self.root / f'invalid-{index}.json')
                self.assertFalse((self.root / f'invalid-{index}.json').exists())
