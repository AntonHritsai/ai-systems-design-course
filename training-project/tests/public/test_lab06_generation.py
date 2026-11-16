"""Generation evidence is distinct from semantic judging."""
import json
import unittest

import test_lab06_graph_queries as queries
from learning_project import lab06_generation as generation


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.query = queries.GraphQueryTests()
        self.query.setUp()
        self.addCleanup(self.query.doCleanups)
        self.root = self.query.root
        self.protocol = self.root / 'protocol.json'

    def prepare(self):
        return generation.prepare_generation(collection=self.query.collection,
            graph_path=self.query.graph, model_id='gemini-3.8-flash-low', output=self.protocol)

    def test_freeze_two_development_cases_with_identical_generator_and_no_reference_leak(self):
        self.prepare()
        p = json.loads(self.protocol.read_text())
        self.assertEqual(p['generator']['model_id'], 'gemini-3.8-flash-low')
        self.assertEqual(p['attempts_per_position'], 1)
        conditions = p['acceptance_conditions']
        self.assertEqual(conditions['minimum_rubric_pass_rate'], 1.0)
        self.assertTrue(conditions['block_unsupported_claim'])
        self.assertEqual(conditions['maximum_question_time_seconds'], 360)
        self.assertEqual(conditions['maximum_review_minutes_per_outcome'], 10)
        self.assertEqual(conditions['maximum_total_tokens_per_configuration'], 200000)
        self.assertEqual(len(p['cases']), 2)
        for case in p['cases']:
            self.assertEqual(case['membership'], 'development')
            self.assertEqual(len(case['reference']['required_connections']), 2)
            requests = list(case['requests'].values())
            for request in requests:
                self.assertEqual(set(request), {'task instruction', 'supplied source evidence', 'output contract'})
                self.assertNotIn('reference', request)
            self.assertEqual(requests[0]['task instruction'], requests[1]['task instruction'])
            self.assertEqual(requests[0]['output contract'], requests[1]['output contract'])
        self.assertEqual(p['cases'][1]['requests']['without graph expansion'],
                         p['cases'][1]['requests']['with graph expansion'])
        self.assertNotEqual(p['cases'][0]['requests']['without graph expansion'],
                            p['cases'][0]['requests']['with graph expansion'])

    def test_run_preserves_full_transport_and_extracts_one_outcome(self):
        from types import SimpleNamespace
        self.prepare()
        calls = []
        outcome = {'outcome_type': 'refusal', 'blocking_condition': 'insufficient supplied source evidence'}
        stdout = json.dumps({'status': 'SUCCESS', 'response': json.dumps(outcome), 'usage': {'tokens': 123}})
        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout=stdout, stderr='diagnostic')
        paths = generation.run_generation(protocol_path=self.protocol, case_id='EC-06-1-v1',
            role='without graph expansion', output_dir=self.root / 'run', runner=runner,
            collection=self.query.collection, graph_path=self.query.graph)
        self.assertEqual(json.loads(paths['outcome'].read_text()), outcome)
        raw = json.loads(paths['response'].read_text())
        self.assertEqual(raw['stdout'], stdout)
        self.assertEqual(raw['stderr'], 'diagnostic')
        self.assertIn('--json-schema', calls[0])
        self.assertIn('--disable-slash-commands', calls[0])
        self.assertEqual(json.loads(calls[0][calls[0].index('--settings') + 1]), {'useG1Credits': False})
        prompt = calls[0][calls[0].index('--print') + 1]
        self.assertNotIn('required_connections', prompt)
        self.assertNotIn('graph_digest', prompt)
        metadata = json.loads(paths['metadata'].read_text())
        self.assertEqual(metadata['status'], 'observed')
        self.assertEqual(metadata['semantic_judgment'], 'not performed')
        self.assertGreaterEqual(metadata['question_time_seconds'], metadata['elapsed_seconds'])
        self.assertEqual(metadata['latency_boundary'], 'AGY process invocation through process completion only')

    def test_collision_on_each_sibling_including_links_stops_before_provider(self):
        from learning_project.workflow import WorkflowError
        self.prepare()
        for filename in ['attempt.json', 'provider-response.json', 'outcome.json', 'run-metadata.json']:
            for kind in ['regular', 'dangling', 'existing-target']:
                with self.subTest(filename=filename, kind=kind):
                    folder = self.root / (filename + kind)
                    folder.mkdir()
                    path = folder / filename
                    target = self.root / ('outside-' + filename + kind)
                    if kind == 'regular':
                        path.write_text('unchanged')
                    else:
                        if kind == 'existing-target':
                            target.write_text('unchanged')
                        path.symlink_to(target)
                    def forbidden(*args, **kwargs):
                        self.fail('Provider invoked after collision')
                    with self.assertRaises(WorkflowError):
                        generation.run_generation(protocol_path=self.protocol, case_id='EC-06-1-v1',
                            role='without graph expansion', output_dir=folder, runner=forbidden,
                            collection=self.query.collection, graph_path=self.query.graph)
                    if target.exists():
                        self.assertEqual(target.read_text(), 'unchanged')

    def test_failed_transport_and_malformed_content_keep_evidence_and_metadata(self):
        from types import SimpleNamespace
        from learning_project.workflow import WorkflowError
        import subprocess
        self.prepare()
        variants = [SimpleNamespace(returncode=3, stdout='failed', stderr='quota'),
                    SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'SUCCESS', 'response': '{} {}'}), stderr=''),
                    subprocess.TimeoutExpired(['agy'], 330, output=b'partial', stderr=b'timeout')]
        for index, value in enumerate(variants):
            folder = self.root / f'failed-{index}'
            def runner(*args, **kwargs):
                if isinstance(value, Exception):
                    raise value
                return value
            with self.assertRaises(WorkflowError):
                generation.run_generation(protocol_path=self.protocol, case_id='EC-06-1-v1',
                    role='without graph expansion', output_dir=folder, runner=runner,
                    collection=self.query.collection, graph_path=self.query.graph)
            self.assertTrue((folder / 'provider-response.json').exists())
            self.assertEqual(json.loads((folder / 'run-metadata.json').read_text())['status'], 'execution failure')
            self.assertFalse((folder / 'outcome.json').exists())

    def test_protocol_tampering_is_rejected_before_provider(self):
        from learning_project.workflow import WorkflowError
        self.prepare()
        protocol = json.loads(self.protocol.read_text())
        protocol['cases'][0]['requests']['without graph expansion']['task instruction'] = 'Use reference facts'
        self.protocol.write_text(json.dumps(protocol))
        def forbidden(*args, **kwargs):
            self.fail('Provider invoked for changed protocol')
        with self.assertRaises(WorkflowError):
            generation.run_generation(protocol_path=self.protocol, case_id='EC-06-1-v1',
                role='without graph expansion', output_dir=self.root / 'tampered', runner=forbidden,
                collection=self.query.collection, graph_path=self.query.graph)

    def test_cli_preparation_and_verification_detects_changed_outcome(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from learning_project.workflow import WorkflowError
        code, message = self.query.cli('prepare-generation', '--collection', self.query.collection,
            '--graph', self.query.graph, '--model', 'gemini-3.8-flash-low', '--output', self.protocol)
        self.assertEqual(code, 0, message)
        def runner(*args, **kwargs):
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'SUCCESS', 'response': json.dumps({
                'outcome_type': 'refusal', 'blocking_condition': 'insufficient supplied source evidence'})}), stderr='')
        folder = self.root / 'runs'
        for case_id in ['EC-06-1-v1', 'EC-06-2-v1']:
            for role in generation.ROLES:
                generation.run_generation(protocol_path=self.protocol, collection=self.query.collection,
                    graph_path=self.query.graph, case_id=case_id, role=role,
                    output_dir=folder / case_id / role.replace(' ', '-'), runner=runner)
        result = generation.verify_generation(protocol_path=self.protocol, collection=self.query.collection,
            graph_path=self.query.graph, runs_dir=folder)
        self.assertEqual(result['observed_outputs'], 4)
        outcome = folder / 'EC-06-1-v1' / 'without-graph-expansion' / 'outcome.json'
        outcome.write_text('{}')
        with self.assertRaises(WorkflowError):
            generation.verify_generation(protocol_path=self.protocol, collection=self.query.collection,
                graph_path=self.query.graph, runs_dir=folder)

    def test_schema_capture_uses_explicit_structured_output_without_scanning_for_favorable_json(self):
        from types import SimpleNamespace
        self.prepare()
        outcome = {'outcome_type': 'refusal', 'blocking_condition': 'insufficient supplied source evidence'}
        capture = self.root / 'capture.json'
        capture.write_text(json.dumps({'stdout': json.dumps({'status': 'SUCCESS',
            'response': 'prose {} {}', 'structured_output': outcome}), 'stderr': '', 'returncode': 0}))
        paths = generation.run_generation(protocol_path=self.protocol, collection=self.query.collection,
            graph_path=self.query.graph, case_id='EC-06-1-v1', role='without graph expansion',
            output_dir=self.root / 'imported', recorded_response=capture)
        self.assertEqual(json.loads(paths['outcome'].read_text()), outcome)
        metadata = json.loads(paths['metadata'].read_text())
        self.assertEqual(metadata['evidence_kind'], 'imported provider capture')
        self.assertIn('capture_digest', metadata)

    def test_import_single_response_with_empty_transport_placeholders_without_retry(self):
        from learning_project.workflow import WorkflowError
        self.prepare()
        outcome = {'outcome_type': 'generated prerequisite explanation',
                   'claims': [{'text': 'An attempted claim', 'fragment_ids': ['F-1']}]}
        for index, response in enumerate([json.dumps(outcome) + '\n{}\n',
                                           json.dumps(outcome) + '\n' + json.dumps(outcome)]):
            capture = self.root / f'placeholder-{index}.json'
            capture.write_text(json.dumps({'stdout': json.dumps({'status': 'SUCCESS',
                'response': response}), 'stderr': '', 'returncode': 0}))
            kwargs = dict(protocol_path=self.protocol, collection=self.query.collection,
                graph_path=self.query.graph, case_id='EC-06-1-v1', role='without graph expansion',
                output_dir=self.root / f'placeholder-run-{index}', recorded_response=capture)
            if index == 0:
                paths = generation.run_generation(**kwargs)
                self.assertEqual(json.loads(paths['outcome'].read_text()), outcome)
            else:
                with self.assertRaises(WorkflowError):
                    generation.run_generation(**kwargs)

    def test_fenced_json_with_trailing_prose_extracts_single_object(self):
        """Claude/AGY may fence the object and append finish-tool prose without structured_output."""
        self.prepare()
        outcome = {'outcome_type': 'generated prerequisite explanation',
                   'claims': [{'text': 'In this teaching route, retrieval requires a query embedding.',
                               'fragment_ids': ['F-1']}]}
        fenced = (
            '```json\n'
            + json.dumps(outcome, indent=2)
            + '\n```\nThe finish tool is misconfigured. Task complete.\n{}\n'
        )
        capture = self.root / 'fenced-claude.json'
        capture.write_text(json.dumps({'stdout': json.dumps({'status': 'SUCCESS',
            'response': fenced}), 'stderr': '', 'returncode': 0}))
        paths = generation.run_generation(
            protocol_path=self.protocol, collection=self.query.collection,
            graph_path=self.query.graph, case_id='EC-06-1-v1', role='without graph expansion',
            output_dir=self.root / 'fenced-run', recorded_response=capture)
        self.assertEqual(json.loads(paths['outcome'].read_text()), outcome)

    def test_malformed_protocols_fail_cleanly_before_provider(self):
        from learning_project.workflow import WorkflowError
        import copy
        self.prepare()
        original = json.loads(self.protocol.read_text())
        variants = [{}, {**original, 'generator': None}, {**original, 'generator': {}},
                    {**original, 'generator': {'model_id': 3}}]
        for protocol in variants:
            self.protocol.write_text(json.dumps(protocol))
            with self.assertRaises(WorkflowError):
                generation.run_generation(protocol_path=self.protocol, collection=self.query.collection,
                    graph_path=self.query.graph, case_id='EC-06-1-v1', role='without graph expansion',
                    output_dir=self.root / 'never', runner=lambda *a, **k: self.fail('Unexpected provider call'))

    def test_nonstring_refusal_conditions_are_structural_violations_not_exceptions(self):
        from types import SimpleNamespace
        self.prepare()
        for index, condition in enumerate([[], ['insufficient supplied source evidence'], {},
                                            {'reason': 'conflicting instruction'}, None, True, 1]):
            with self.subTest(condition=condition):
                outcome = {'outcome_type': 'refusal', 'blocking_condition': condition}
                def runner(*args, **kwargs):
                    return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'SUCCESS',
                        'response': json.dumps(outcome)}), stderr='')
                folder = self.root / f'malformed-condition-{index}'
                for case_id in ['EC-06-1-v1', 'EC-06-2-v1']:
                    for role in generation.ROLES:
                        paths = generation.run_generation(protocol_path=self.protocol, collection=self.query.collection,
                            graph_path=self.query.graph, case_id=case_id, role=role,
                            output_dir=folder / case_id / role.replace(' ', '-'), runner=runner)
                        self.assertEqual(json.loads(paths['outcome'].read_text()), outcome)
                result = generation.verify_generation(protocol_path=self.protocol, collection=self.query.collection,
                    graph_path=self.query.graph, runs_dir=folder)
                self.assertEqual(result['observed_outputs'], 4)
                self.assertEqual(len(result['structural_issues']), 4)
                for item in result['structural_issues']:
                    self.assertEqual(item['issues'], ['Refusal contract violation'])
                self.assertEqual(result['semantic_judgment'], 'not performed')
                self.assertEqual(result['configuration_decision'], 'not authorized')


if __name__ == '__main__':
    unittest.main()
