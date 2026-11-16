"""Reporting-contract tests; synthetic records/images are not a student pilot."""
import json
import re
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures/lab06/REPORT.md'


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report = self.root / 'reports/lab06'
        self.report.mkdir(parents=True)
        self.collection = self.root / 'student/lab06-collection'

    def filled_report(self):
        from learning_project import lab06_reporting as reporting
        text = FIXTURE.read_text()
        text = text[text.index('## Ідентифікація'):]
        text = text.replace('URL форка:', 'URL форка: https://github.com/test-student/course')
        text = text.replace('Особиста гілка:', 'Особиста гілка: lab06/test-student')
        text = text.replace('`complete` або `honest-partial`', '`complete`')
        text = re.sub(r'^\[[^\n]+\]$', 'СИНТЕТИЧНИЙ ТЕСТ: не справжнє виконання студента.', text, flags=re.M)
        (self.report / 'REPORT.md').write_text(text)
        (self.report / 'screenshots').mkdir()
        for name in reporting.SCREENSHOTS[:-1]:
            (self.report / 'screenshots' / name).write_bytes(b'SYNTHETIC UNIT TEST IMAGE')
        for relative in reporting.REQUIRED_EVIDENCE:
            p = self.report / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{}')
        return text

    def test_complete_report_checks_use_seven_actual_checkpoints(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        result = reporting.validate_report(report_dir=self.report)
        self.assertEqual(result['status'], 'passed')
        message = next(c['message'] for c in result['checks'] if c['check_id']=='report-screenshots')
        self.assertIn('7 exact relative links', message)

    def test_partial_stop_preserves_only_reached_checkpoints(self):
        from learning_project import lab06_reporting as reporting
        text = self.filled_report().replace('`complete`', '`honest-partial`')
        for relative in reporting.REQUIRED_EVIDENCE:
            if relative != 'graph-preparation/review.json':
                (self.report / relative).unlink()
        for name in reporting.SCREENSHOTS[1:-1]:
            (self.report / 'screenshots' / name).unlink()
            text = re.sub(r'^!\[[^\n]+\]\(screenshots/'+re.escape(name)+r'\)\n', '', text, flags=re.M)
        (self.report / 'REPORT.md').write_text(text)
        result = reporting.validate_report(report_dir=self.report)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(result['completion_state'], 'honest-partial')
        self.assertEqual(result['screenshots'], [reporting.SCREENSHOTS[0], reporting.SCREENSHOTS[-1]])
        self.assertFalse((self.report / 'decision.json').exists())
        (self.report / 'screenshots' / reporting.SCREENSHOTS[0]).unlink()
        self.assertEqual(reporting.validate_report(report_dir=self.report)['status'], 'failed')

    def commit(self):
        import subprocess
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()
        git('init', '-q', '-b', 'lab06/test-student')
        git('add', '.')
        git('-c', 'user.name=Synthetic Test', '-c', 'user.email=test@example.invalid',
            'commit', '-q', '-m', 'Synthetic report contract fixture')
        return git('rev-parse', 'HEAD')

    def test_partial_verification_binds_commit_without_claiming_experiment_completion(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        head = self.commit()
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(result['outcome'], 'passed', result)
        self.assertEqual(result['completion_state'], 'honest-partial')
        self.assertFalse(result['domain_completion_claimed'])
        self.assertEqual(json.loads((self.report / 'verification-report.json').read_text()), result)

    def test_complete_verification_rejects_present_but_invalid_domain_files(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=self.commit())
        self.assertEqual(result['outcome'], 'failed')
        self.assertFalse(result['domain_completion_claimed'])
        self.assertTrue(any(c['check_id']=='domain-evidence' and c['status']=='failed' for c in result['checks']))

    def seed_domain(self):
        import shutil
        from learning_project import lab06, lab06_evaluation as evaluation
        from test_lab06_evaluation import EvaluationTests
        e = EvaluationTests()
        e.setUp()
        self.addCleanup(e.doCleanups)
        e.filled()
        self.collection.mkdir(parents=True)
        shutil.copyfile(e.common['collection'] / 'accepted.json', self.collection / 'accepted.json')
        shutil.copyfile(e.common['graph_path'], self.report / 'graph-preparation/graph.json')
        shutil.copyfile(e.g.query.prep.review, self.report / 'graph-preparation/review.json')
        for depth in (1, 2):
            target = self.report / f'graph-query/paths-{depth}.json'
            target.unlink()
            lab06.query_paths(collection=self.collection, graph_path=self.report / 'graph-preparation/graph.json',
                              start='C-RET', max_edges=depth, output=target)
        target = self.report / 'graph-query/direct-edge.json'
        target.unlink()
        lab06.inspect_direct_edge(collection=self.collection, graph_path=self.report / 'graph-preparation/graph.json',
                                  start='C-RET', target='C-MODEL', output=target)
        for name, fixture in [('evidence-preparation', 'evidence-preparation'), ('policy-probes', 'evidence-policy-probes')]:
            target = self.report / f'evidence-preparation/{name}.json'
            target.unlink()
            lab06.prepare_evidence(collection=self.collection, graph_path=self.report / 'graph-preparation/graph.json',
                fixture_path=lab06.DEFAULT_INPUT.with_name(fixture + '.json'), output=target)
        shutil.copyfile(e.g.protocol, self.report / 'generation/protocol.json')
        shutil.copytree(e.runs, self.report / 'generation/runs', dirs_exist_ok=True)
        shutil.copyfile(e.judgments, self.report / 'judgments.json')
        common = dict(collection=self.collection, graph_path=self.report / 'graph-preparation/graph.json',
            protocol_path=self.report / 'generation/protocol.json', runs_dir=self.report / 'generation/runs',
            judgments_path=self.report / 'judgments.json')
        assessment = self.report / 'comparison.json'
        assessment.unlink()
        evaluation.assess_comparison(**common, output=assessment)
        intent = self.report / 'decision-input.json'
        intent.write_text(json.dumps(dict(engineering_team='SYNTHETIC TEST', decision='adopt with graph expansion',
            rationale='Synthetic branch only', teaching_prediction_comparison='Not observed real quality',
            graph_preparation_trade_off='Synthetic test only')))
        output = self.report / 'decision.json'
        output.unlink()
        evaluation.record_decision(**common, assessment_path=assessment, decision_path=intent, output=output)

    def test_complete_domain_and_real_fixture_packaging(self):
        from learning_project import lab06_reporting as reporting
        from learning_project.report_submission import prepare_report
        from PIL import Image
        self.filled_report()
        self.seed_domain()
        for name in reporting.SCREENSHOTS[:-1]:
            Image.new('RGB', (16, 16), 'navy').save(self.report / 'screenshots' / name)
        head = self.commit()
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(result['outcome'], 'passed', result)
        self.assertTrue(result['domain_completion_claimed'])
        Image.new('RGB', (16, 16), 'navy').save(self.report / 'screenshots' / reporting.SCREENSHOTS[-1])
        before = (self.report / 'REPORT.md').read_bytes()
        output, count = prepare_report(self.report / 'REPORT.md')
        self.assertEqual(count, 7)
        self.assertEqual(output.read_text().count('data:image/png;base64,'), 7)
        self.assertEqual(before, (self.report / 'REPORT.md').read_bytes())

    def test_verification_rejects_collection_drift_outside_report_tree(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        self.collection.mkdir(parents=True)
        accepted = self.collection / 'accepted.json'
        accepted.write_text('{"synthetic": "original"}')
        head = self.commit()
        accepted.write_text('{"synthetic": "changed after commit"}')
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(result['outcome'], 'failed')
        self.assertTrue(any(c['check_id']=='committed-inputs' and c['status']=='failed' for c in result['checks']))

    def test_cli_reports_and_verifies_a_partial_source_report(self):
        import contextlib
        import io
        from learning_project.cli import main
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        head = self.commit()
        for command, flags in [('validate-report', []), ('verify', ['--collection', str(self.collection), '--final-commit', head])]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                try:
                    code = main(['lab06', command, '--report-dir', str(self.report), *flags])
                except SystemExit as exc:
                    code = exc.code
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn('honest-partial', out.getvalue())

    def test_existing_verification_outputs_and_links_are_not_overwritten(self):
        from learning_project import lab06_reporting as reporting
        from learning_project.workflow import WorkflowError
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        head = self.commit()
        output = self.report / 'verification-report.json'
        target = self.root / 'outside.json'
        for kind in ('regular', 'dangling', 'target'):
            with self.subTest(kind=kind):
                if kind == 'regular':
                    output.write_text('original verification')
                else:
                    if kind == 'target': target.write_text('outside sentinel')
                    output.symlink_to(target)
                with self.assertRaises(WorkflowError):
                    reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
                if kind == 'regular': self.assertEqual(output.read_text(), 'original verification')
                if kind == 'target': self.assertEqual(target.read_text(), 'outside sentinel')
                output.unlink()

    def test_verification_requires_the_report_personal_branch_to_be_current(self):
        import subprocess
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        head = self.commit()
        subprocess.run(['git', '-C', str(self.root), 'branch', '-m', 'lab06/different'], check=True)
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(result['outcome'], 'failed')

    def test_missing_previously_committed_collection_cannot_pass_partial_verification(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        self.collection.mkdir(parents=True)
        accepted = self.collection / 'accepted.json'
        accepted.write_text('{"synthetic": "original"}')
        head = self.commit()
        accepted.unlink()
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(result['outcome'], 'failed')

    def test_report_reads_use_explicit_utf8_for_windows_portability(self):
        from unittest.mock import patch
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        real = Path.read_text
        encodings = []
        def read(path, *args, **kwargs):
            encodings.append(kwargs.get('encoding'))
            return real(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read):
            reporting.validate_report(report_dir=self.report)
        self.assertTrue(encodings)
        self.assertTrue(all(value == 'utf-8' for value in encodings), encodings)

    def test_untracked_collection_is_not_bound_by_file_presence(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        head = self.commit()
        self.collection.mkdir(parents=True)
        (self.collection / 'accepted.json').write_text('{}')
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(result['outcome'], 'failed')

    def test_ignored_collection_is_not_bound_by_file_presence(self):
        from learning_project import lab06_reporting as reporting
        self.filled_report()
        path = self.report / 'REPORT.md'
        path.write_text(path.read_text().replace('`complete`', '`honest-partial`'))
        (self.root / '.gitignore').write_text('student/')
        self.collection.mkdir(parents=True)
        (self.collection / 'accepted.json').write_text('{}')
        result = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=self.commit())
        self.assertEqual(result['outcome'], 'failed')

    def test_flexible_identity_spacing_still_classifies_honest_partial(self):
        from learning_project import lab06_reporting as reporting
        text = self.filled_report()
        text = text.replace('- Статус завершення: `complete`', '*   Статус завершення: honest-partial')
        text = text.replace('- Особиста гілка: lab06/test-student', '  - Особиста гілка: `lab06/test-student`')
        (self.report / 'REPORT.md').write_text(text)
        result = reporting.validate_report(report_dir=self.report)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(result['completion_state'], 'honest-partial')
        # All machine-evidence groups exist, so every pre-final checkpoint is reached; partial still forbids domain completion.
        self.assertEqual(result['screenshots'], list(reporting.SCREENSHOTS))
        head = self.commit()
        verified = reporting.verify(report_dir=self.report, collection=self.collection, final_commit=head)
        self.assertEqual(verified['outcome'], 'passed', verified)
        self.assertEqual(verified['completion_state'], 'honest-partial')
        self.assertFalse(verified['domain_completion_claimed'])

    def test_unfilled_real_fixture_is_rejected_without_creating_judgments(self):
        from learning_project import lab06_reporting as reporting
        (self.report / 'REPORT.md').write_text(FIXTURE.read_text())
        result = reporting.validate_report(report_dir=self.report)
        self.assertEqual(result['status'], 'failed')
        failed = {r['check_id'] for r in result['checks'] if r['status']=='failed'}
        self.assertIn('report-prompts', failed)
        self.assertFalse((self.report / 'judgments.json').exists())
