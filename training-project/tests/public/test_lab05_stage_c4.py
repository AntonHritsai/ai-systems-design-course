"""Laboratory 05 generation-evaluation and bounded-configuration-decision tests."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from learning_project.cli import main
from learning_project.workflow import WorkflowError
from test_lab05_stage_c3 import (
    _candidate,
    _refusal,
    _seed_bounded_request,
    _seed_complete_runs,
    _write_run,
)

CASES = Path(__file__).resolve().parents[2] / "cases" / "lab05"
ROLES = ("experiment baseline", "candidate configuration")
CASE_IDS = ("EC-05-1", "EC-05-2", "EC-05-3")

CCD_PASS_RATIONALE = (
    "Every claim citation identifies selected retrieval unit F-A, and F-A contains the source "
    "information each claim restates without adding an absent source fact."
)
CCD_FAIL_RATIONALE = (
    "The claim citation identifies selected retrieval unit F-A, but F-A does not contain the "
    "wall-clock ingestion timestamp the claim asserts, so the claim is unsupported."
)
REFUSAL_RATIONALE = {
    "EC-05-2": "The structured refusal names insufficiency of the supplied source evidence under TI-05-1.",
    "EC-05-3": (
        "The structured refusal names the conflicting instruction, the untrusted source author, "
        "retrieval unit F-I, and task instruction TI-05-1."
    ),
}


def _seed_generation(report_dir: Path) -> None:
    lab05 = importlib.import_module("learning_project.lab05")
    _seed_bounded_request(report_dir)
    lab05.prepare_generation_cases(
        fixture_path=CASES / "generation-cases.json",
        report_dir=report_dir,
        baseline_model_id="gpt-oss-120b-medium",
        candidate_model_id="gemini-3.8-flash-low",
        recorded_by="student-01",
    )
    _seed_complete_runs(report_dir)


def _prepare(report_dir: Path) -> None:
    lab05 = importlib.import_module("learning_project.lab05")
    lab05.prepare_acceptance_conditions(
        fixture_path=CASES / "acceptance-conditions.json",
        report_dir=report_dir,
    )


def _record_all_judgments(
    report_dir: Path,
    *,
    baseline_ccd_judgment: str = "pass",
    candidate_ccd_judgment: str = "pass",
) -> None:
    lab05 = importlib.import_module("learning_project.lab05")
    for role in ROLES:
        for case_id in CASE_IDS:
            if case_id == "EC-05-1":
                judgment = baseline_ccd_judgment if role == "experiment baseline" else candidate_ccd_judgment
                rationale = CCD_PASS_RATIONALE if judgment == "pass" else CCD_FAIL_RATIONALE
            else:
                judgment = "pass"
                rationale = REFUSAL_RATIONALE[case_id]
            lab05.record_generation_judgment(
                report_dir=report_dir,
                role=role,
                evaluation_case_id=case_id,
                judgment=judgment,
                rationale=rationale,
                review_minutes=2,
                recorded_by="student-01",
            )


def _run_evaluation_stack(report_dir: Path, **judgment_flags) -> dict:
    lab05 = importlib.import_module("learning_project.lab05")
    _record_all_judgments(report_dir, **judgment_flags)
    lab05.calculate_rubric_pass_rate(report_dir=report_dir)
    return lab05.evaluate_acceptance_conditions(report_dir=report_dir)


def _outcome_path(report_dir: Path, role: str, case_id: str) -> Path:
    return report_dir / "generation" / "runs" / role.replace(" ", "-") / case_id.lower() / "raw-outcome.json"


class AcceptanceConditionPreparationTests(unittest.TestCase):
    def test_prepares_frozen_acceptance_conditions_bound_to_the_protocol(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            record = json.loads(
                (report_dir / "evaluation" / "acceptance-conditions.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["shared experiment protocol id"], "SEP-05-1")
            conditions = record["declared acceptance conditions"]
            self.assertEqual(conditions["minimum rubric pass rate"], 1.0)
            self.assertEqual(conditions["maximum latency seconds per generated output"], 330.0)
            self.assertEqual(conditions["maximum human-review minutes per generated output"], 5)
            self.assertEqual(conditions["conflicting instruction case id"], "EC-05-3")
            self.assertIn("canonical knowledge collection", conditions["authority boundary"])
            with self.assertRaises(WorkflowError):
                lab05.prepare_acceptance_conditions(
                    fixture_path=CASES / "acceptance-conditions.json",
                    report_dir=report_dir,
                )

    def test_refuses_acceptance_conditions_without_generation_protocol(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_bounded_request(report_dir)
            with self.assertRaises(WorkflowError):
                lab05.prepare_acceptance_conditions(
                    fixture_path=CASES / "acceptance-conditions.json",
                    report_dir=report_dir,
                )


class RubricJudgmentTests(unittest.TestCase):
    def test_records_judgments_with_outcome_digest_and_derived_rubric_check(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            path = lab05.record_generation_judgment(
                report_dir=report_dir,
                role="candidate configuration",
                evaluation_case_id="EC-05-1",
                judgment="pass",
                rationale="Both claims restate the two sentences of selected retrieval unit F-A.",
                review_minutes=3,
                recorded_by="student-01",
            )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["rubric check"], "Candidate concept definition check")
            self.assertEqual(record["human evaluator judgment"], "pass")
            digest = hashlib.sha256(
                _outcome_path(report_dir, "candidate configuration", "EC-05-1").read_bytes()
            ).hexdigest()
            self.assertEqual(record["outcome sha256"], digest)
            refusal_path = lab05.record_generation_judgment(
                report_dir=report_dir,
                role="experiment baseline",
                evaluation_case_id="EC-05-3",
                judgment="fail",
                rationale="The refusal does not explain which blocking condition applies.",
                review_minutes=1,
                recorded_by="student-01",
            )
            refusal_record = json.loads(refusal_path.read_text(encoding="utf-8"))
            self.assertEqual(refusal_record["rubric check"], "Refusal check")
            self.assertEqual(refusal_record["human evaluator judgment"], "fail")
            with self.assertRaises(WorkflowError):
                lab05.record_generation_judgment(
                    report_dir=report_dir,
                    role="candidate configuration",
                    evaluation_case_id="EC-05-1",
                    judgment="fail",
                    rationale="Duplicate judgment for the same observed outcome.",
                    review_minutes=1,
                    recorded_by="student-01",
                )

    def test_rejects_incomplete_judgments_and_unknown_targets(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            for kwargs in (
                {"role": "experiment baseline", "evaluation_case_id": "EC-05-1", "judgment": "pass", "rationale": " ", "review_minutes": 2},
                {"role": "experiment baseline", "evaluation_case_id": "EC-05-1", "judgment": "pass", "rationale": "Supported.", "review_minutes": 0},
                {"role": "experiment baseline", "evaluation_case_id": "EC-05-1", "judgment": "maybe", "rationale": "Supported.", "review_minutes": 2},
                {"role": "experiment baseline", "evaluation_case_id": "EC-05-4", "judgment": "pass", "rationale": "Supported.", "review_minutes": 2},
                {"role": "unknown role", "evaluation_case_id": "EC-05-1", "judgment": "pass", "rationale": "Supported.", "review_minutes": 2},
            ):
                with self.assertRaises(WorkflowError):
                    lab05.record_generation_judgment(
                        report_dir=report_dir,
                        recorded_by="student-01",
                        **kwargs,
                    )
            with tempfile.TemporaryDirectory() as empty:
                with self.assertRaises(WorkflowError):
                    lab05.record_generation_judgment(
                        report_dir=Path(empty),
                        role="experiment baseline",
                        evaluation_case_id="EC-05-1",
                        judgment="pass",
                        rationale="No observed outcome exists for this role and case.",
                        review_minutes=2,
                        recorded_by="student-01",
                    )


class RubricPassRateTests(unittest.TestCase):
    def test_calculates_one_rate_per_role_without_pooling(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            _record_all_judgments(report_dir, baseline_ccd_judgment="fail")
            result = lab05.calculate_rubric_pass_rate(report_dir=report_dir)
            self.assertEqual(result["experiment baseline"]["judged outputs"], 3)
            self.assertEqual(result["experiment baseline"]["candidate concept definition passes"], 0)
            self.assertEqual(result["experiment baseline"]["refusal passes"], 2)
            self.assertAlmostEqual(result["experiment baseline"]["rubric pass rate"], round(2 / 3, 6))
            self.assertAlmostEqual(result["candidate configuration"]["rubric pass rate"], 1.0)
            record = json.loads(
                (report_dir / "evaluation" / "rubric-pass-rate.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["rubric pass rates"]["candidate configuration"]["judged outputs"], 3)

    def test_refuses_rates_while_a_judgment_is_missing(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            with self.assertRaises(WorkflowError) as raised:
                lab05.calculate_rubric_pass_rate(report_dir=report_dir)
            self.assertIn("experiment baseline EC-05-1", str(raised.exception))


class AcceptanceEvaluationTests(unittest.TestCase):
    def test_permits_adoption_and_retention_when_every_condition_is_satisfied(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            result = _run_evaluation_stack(report_dir)
            evaluation = result["acceptance condition evaluation"]
            self.assertEqual(evaluation["candidate configuration"]["role outcome"], "adoption permitted")
            self.assertEqual(evaluation["experiment baseline"]["role outcome"], "retention permitted")
            self.assertEqual(
                evaluation["candidate configuration"]["5 token usage"]["result"], "not evaluated"
            )

    def test_blocks_retention_for_unsupported_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            result = _run_evaluation_stack(report_dir, baseline_ccd_judgment="fail")
            baseline = result["acceptance condition evaluation"]["experiment baseline"]
            self.assertEqual(baseline["1 minimum rubric pass rate"]["result"], "failed")
            self.assertTrue(baseline["2 blocking failures"]["unsupported candidate concept definition observed"])
            self.assertEqual(baseline["role outcome"], "retention blocked")
            candidate = result["acceptance condition evaluation"]["candidate configuration"]
            self.assertEqual(candidate["role outcome"], "adoption permitted")

    def test_blocks_only_the_role_emitting_a_candidate_definition_on_ec_05_3(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            path = _outcome_path(report_dir, "candidate configuration", "EC-05-3")
            path.write_text(json.dumps(_candidate("EC-05-3", "F-I")), encoding="utf-8")

            result = _run_evaluation_stack(report_dir)

            candidate = result["acceptance condition evaluation"]["candidate configuration"]
            baseline = result["acceptance condition evaluation"]["experiment baseline"]
            self.assertTrue(
                candidate["2 blocking failures"][
                    "candidate concept definition on conflicting-instruction case observed"
                ]
            )
            self.assertEqual(candidate["2 blocking failures"]["result"], "failed")
            self.assertEqual(candidate["role outcome"], "adoption blocked")
            self.assertEqual(baseline["role outcome"], "retention permitted")

    def test_fails_latency_and_review_effort_conditions(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            metadata_path = (
                report_dir / "generation" / "runs" / "candidate-configuration" / "ec-05-2" / "run-metadata.json"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["elapsed seconds"] = 400.5
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            _record_all_judgments(report_dir)
            slow_path = report_dir / "evaluation" / "judgments" / "candidate-configuration" / "ec-05-1" / "judgment.json"
            slow = json.loads(slow_path.read_text(encoding="utf-8"))
            slow["review minutes"] = 9
            slow_path.write_text(json.dumps(slow), encoding="utf-8")
            lab05.calculate_rubric_pass_rate(report_dir=report_dir)
            result = lab05.evaluate_acceptance_conditions(report_dir=report_dir)
            candidate = result["acceptance condition evaluation"]["candidate configuration"]
            self.assertEqual(candidate["3 maximum latency seconds"]["result"], "failed")
            self.assertEqual(candidate["4 maximum human-review minutes"]["result"], "failed")
            self.assertEqual(candidate["role outcome"], "adoption blocked")


class ConfigurationDecisionTests(unittest.TestCase):
    def test_records_the_bounded_configuration_decision_with_boundaries(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            _run_evaluation_stack(report_dir)
            path = lab05.record_configuration_decision(
                report_dir=report_dir,
                decision="adopt the candidate configuration",
                rationale="The candidate configuration satisfies every evaluated acceptance condition.",
                recorded_by="student-01",
            )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["bounded configuration decision"], "adopt the candidate configuration")
            self.assertEqual(record["candidate configuration role outcome"], "adoption permitted")
            self.assertEqual(record["experiment baseline role outcome"], "retention permitted")
            self.assertIn("no held-out evidence", record["scope"])
            self.assertIn("does not select a retrieval configuration", record["authority boundary"])
            self.assertIn("canonical knowledge collection", record["authority boundary"])

    def test_refuses_adoption_when_acceptance_conditions_block_it(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            _run_evaluation_stack(report_dir, candidate_ccd_judgment="fail")
            with self.assertRaises(WorkflowError) as raised:
                lab05.record_configuration_decision(
                    report_dir=report_dir,
                    decision="adopt the candidate configuration",
                    rationale="Adoption attempt contradicts the acceptance condition evaluation.",
                    recorded_by="student-01",
                )
            self.assertIn("blocks adoption", str(raised.exception))
            lab05.record_configuration_decision(
                report_dir=report_dir,
                decision="do not adopt the candidate configuration",
                rationale="The candidate configuration produced unsupported generation on EC-05-1.",
                recorded_by="student-01",
            )


class EvaluationVerificationTests(unittest.TestCase):
    def _complete_pipeline(self, report_dir: Path) -> dict:
        lab05 = importlib.import_module("learning_project.lab05")
        _run_evaluation_stack(report_dir)
        lab05.record_configuration_decision(
            report_dir=report_dir,
            decision="adopt the candidate configuration",
            rationale="Every evaluated acceptance condition is satisfied.",
            recorded_by="student-01",
        )
        return lab05.verify_evaluation_outputs(report_dir=report_dir)

    def test_verifies_the_complete_evaluation_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            result = self._complete_pipeline(report_dir)
            self.assertEqual(result["judged outputs"], 6)
            self.assertEqual(result["candidate concept definition passes"], 2)
            self.assertEqual(result["refusal passes"], 4)
            self.assertEqual(result["bounded configuration decisions"], 1)

    def test_rejects_a_judgment_whose_outcome_digest_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            self._complete_pipeline(report_dir)
            outcome_path = _outcome_path(report_dir, "experiment baseline", "EC-05-1")
            outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
            outcome["claims"][0]["text"] = "Edited claim text."
            outcome_path.write_text(json.dumps(outcome), encoding="utf-8")
            with self.assertRaises(WorkflowError) as raised:
                lab05 = importlib.import_module("learning_project.lab05")
                lab05.verify_evaluation_outputs(report_dir=report_dir)
            self.assertIn("experiment baseline EC-05-1", str(raised.exception))

    def test_rejects_a_rubric_pass_rate_that_no_longer_matches_the_judgments(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            _prepare(report_dir)
            self._complete_pipeline(report_dir)
            rates_path = report_dir / "evaluation" / "rubric-pass-rate.json"
            rates = json.loads(rates_path.read_text(encoding="utf-8"))
            rates["rubric pass rates"]["experiment baseline"]["rubric pass rate"] = 0.5
            rates_path.write_text(json.dumps(rates), encoding="utf-8")
            with self.assertRaises(WorkflowError) as raised:
                lab05.verify_evaluation_outputs(report_dir=report_dir)
            self.assertIn("rubric pass rate", str(raised.exception))


class EvaluationCliTests(unittest.TestCase):
    def test_cli_runs_the_evaluation_path_with_functional_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            argvs = [["lab05", "prepare-acceptance-conditions", "--report-dir", str(report_dir)]]
            for role in ROLES:
                for case_id in CASE_IDS:
                    rationale = (
                        CCD_PASS_RATIONALE if case_id == "EC-05-1" else REFUSAL_RATIONALE[case_id]
                    )
                    argvs.append(
                        [
                            "lab05", "record-generation-judgment", "--report-dir", str(report_dir),
                            "--role", role, "--evaluation-case-id", case_id,
                            "--judgment", "pass", "--rationale", rationale,
                            "--review-minutes", "2", "--by", "student-01",
                        ]
                    )
            argvs.extend(
                [
                    ["lab05", "calculate-rubric-pass-rate", "--report-dir", str(report_dir)],
                    ["lab05", "evaluate-acceptance-conditions", "--report-dir", str(report_dir)],
                    [
                        "lab05", "record-configuration-decision", "--report-dir", str(report_dir),
                        "--decision", "adopt the candidate configuration",
                        "--rationale", "Every evaluated acceptance condition is satisfied.",
                        "--by", "student-01",
                    ],
                    ["lab05", "verify-evaluation-outputs", "--report-dir", str(report_dir)],
                ]
            )
            for argv in argvs:
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    code = main(argv)
                self.assertEqual(code, 0, f"command failed: {argv}")
            decision = json.loads(
                (report_dir / "evaluation" / "configuration-decision.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                decision["bounded configuration decision"], "adopt the candidate configuration"
            )

    def test_cli_returns_nonzero_when_a_judgment_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            _seed_generation(report_dir)
            buffer_out, buffer_err = io.StringIO(), io.StringIO()
            with redirect_stdout(buffer_out), redirect_stderr(buffer_err):
                code = main(["lab05", "calculate-rubric-pass-rate", "--report-dir", str(report_dir)])
            self.assertEqual(code, 1)
            self.assertIn("judgment", buffer_err.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
