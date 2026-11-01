"""Write-once Laboratory 05 outputs must not follow symbolic links."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from learning_project import lab05
from learning_project.workflow import WorkflowError
from test_lab05_stage_c3 import _seed_bounded_request
from test_lab05_stage_c4 import (
    _prepare, _record_all_judgments, _seed_generation,
    CCD_PASS_RATIONALE,
)

CASES = Path(__file__).resolve().parents[2] / "cases" / "lab05"


def _prepare_cases(report):
    lab05.prepare_generation_cases(
        fixture_path=CASES / "generation-cases.json", report_dir=report,
        baseline_model_id="gemini-3.8-flash-medium",
        candidate_model_id="gemini-3.8-flash-medium", recorded_by="test-evaluator",
    )


class OutputSafetyTests(unittest.TestCase):
    def test_initial_operations_refuse_dangling_and_existing_target_symlinks(self):
        steps = (
            (lab05.apply_query_rewriting, "query-rewriting-cases.json", "query-rewriting/query-rewriting-results.json"),
            (lab05.apply_retrieval_unit_selection, "retrieval-unit-selection-cases.json", "retrieval-unit-selection/selection-record.json"),
            (lab05.apply_context_construction, "context-construction-cases.json", "context-construction/bounded-model-request.json"),
        )
        for index, (operation, fixture, relative) in enumerate(steps):
            for existing in (False, True):
                with self.subTest(operation=operation.__name__, existing=existing), tempfile.TemporaryDirectory() as temp:
                    report = Path(temp) / "report"
                    for prerequisite, prerequisite_fixture, _ in steps[:index]:
                        prerequisite(fixture_path=CASES / prerequisite_fixture, report_dir=report)
                    output = report / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    target = Path(temp) / "outside.json"
                    if existing:
                        target.write_text("original", encoding="utf-8")
                    output.symlink_to(target)
                    with self.assertRaises(WorkflowError):
                        operation(fixture_path=CASES / fixture, report_dir=report)
                    self.assertEqual(target.read_text(encoding="utf-8") if target.exists() else None,
                                     "original" if existing else None)

    def test_generation_preparation_refuses_symlinks_before_writing_any_output(self):
        for relative in (
            "generation/shared-experiment-protocol.json",
            "generation/cases/ec-05-1/bounded-model-request.json",
            "generation/cases/ec-05-2/bounded-model-request.json",
            "generation/cases/ec-05-3/bounded-model-request.json",
        ):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as temp:
                report = Path(temp) / "report"
                _seed_bounded_request(report)
                output = report / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                target = Path(temp) / "outside.json"
                output.symlink_to(target)
                with self.assertRaises(WorkflowError):
                    _prepare_cases(report)
                self.assertFalse(target.exists())
                protocol = report / "generation/shared-experiment-protocol.json"
                self.assertFalse(protocol.exists())

    def test_generation_refuses_dangling_output_links_before_calling_provider(self):
        for filename in ("raw-response.txt", "raw-outcome.json", "run-metadata.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temp:
                report = Path(temp) / "report"
                _seed_bounded_request(report)
                _prepare_cases(report)
                output = report / "generation/runs/experiment-baseline/ec-05-1" / filename
                output.parent.mkdir(parents=True)
                target = Path(temp) / "outside.json"
                output.symlink_to(target)
                runner = Mock(return_value=SimpleNamespace(returncode=1))
                with self.assertRaisesRegex(WorkflowError, "already exists"):
                    lab05.run_generation_agy(
                        report_dir=report, role="experiment baseline", evaluation_case_id="EC-05-1",
                        schema_path=lab05.DEFAULT_GENERATION_SCHEMA, recorded_by="test-evaluator", runner=runner,
                    )
                runner.assert_not_called()
                self.assertFalse(target.exists())

    def test_evaluation_operations_refuse_dangling_output_links(self):
        outputs = (
            "evaluation/acceptance-conditions.json",
            "evaluation/judgments/experiment-baseline/ec-05-1/judgment.json",
            "evaluation/rubric-pass-rate.json",
            "evaluation/acceptance-evaluation.json",
            "evaluation/configuration-decision.json",
        )
        for index, relative in enumerate(outputs):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as temp:
                report = Path(temp) / "report"
                _seed_generation(report)
                if index >= 1:
                    _prepare(report)
                if index >= 2:
                    _record_all_judgments(report)
                if index >= 3:
                    lab05.calculate_rubric_pass_rate(report_dir=report)
                if index >= 4:
                    lab05.evaluate_acceptance_conditions(report_dir=report)
                output = report / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                target = Path(temp) / "outside.json"
                output.symlink_to(target)
                with self.assertRaises(WorkflowError):
                    if index == 0:
                        _prepare(report)
                    elif index == 1:
                        lab05.record_generation_judgment(
                            report_dir=report, role="experiment baseline", evaluation_case_id="EC-05-1",
                            judgment="pass", rationale=CCD_PASS_RATIONALE,
                            review_minutes=2, recorded_by="test-evaluator",
                        )
                    elif index == 2:
                        lab05.calculate_rubric_pass_rate(report_dir=report)
                    elif index == 3:
                        lab05.evaluate_acceptance_conditions(report_dir=report)
                    else:
                        lab05.record_configuration_decision(
                            report_dir=report, decision="adopt the candidate configuration",
                            rationale="Every evaluated acceptance condition is satisfied.", recorded_by="test-evaluator",
                        )
                self.assertFalse(target.exists())
