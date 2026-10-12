import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from learning_project.lab04 import prepare_boundary_comparison, record_boundary_decision, verify_stage_b
from learning_project.cli import main
from learning_project.workflow import WorkflowError


TRAINING_PROJECT = Path(__file__).resolve().parent.parent.parent
STAGE_B_FIXTURE = TRAINING_PROJECT / "cases" / "lab04" / "stage-b-fixture.json"


class Lab04StageBPreparationTests(unittest.TestCase):
    def test_prepare_boundary_comparison_preserves_contract_roles_cases_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result_path = prepare_boundary_comparison(
                fixture_path=STAGE_B_FIXTURE,
                report_dir=Path(temp),
            )
            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["canonical_knowledge_collection_version"], "course-seed-v1")
        contract = result["retrieval_contract"]
        self.assertEqual(
            {
                "text query",
                "canonical knowledge collection version",
                "retrieval unit and its boundary rule",
                "retrieval configuration",
                "ranked candidate output",
                "evaluator-only expected result",
                "relevance judging basis",
                "designated human evaluator",
                "observation boundary",
            },
            set(contract["declared fields"]),
        )
        self.assertEqual(
            contract["retrieval configuration roles"],
            {
                "experiment-baseline retrieval configuration": "lexical retrieval",
                "candidate retrieval configuration": "embedding-based retrieval",
            },
        )
        self.assertEqual(
            [case["evaluation_case_id"] for case in result["evaluation_cases"]],
            ["Evaluation Case A", "Evaluation Case B"],
        )
        self.assertTrue(all(case["identity_source"] == "Module 04 theory Section 1.4" for case in result["evaluation_cases"]))
        self.assertTrue(all("evaluator-only expected result" not in case["operation_input"] for case in result["evaluation_cases"]))
        self.assertTrue(all("evaluator-only expected result" in case["evaluator_only_information"] for case in result["evaluation_cases"]))

        manifests = {item["chunking_configuration_id"]: item for item in result["chunking_configuration_results"]}
        self.assertEqual(
            [item["stable_retrieval_identifier"] for item in manifests["sentence-pair-v1"]["source_fragments"] if item["canonical_knowledge_record_id"] == "R-A"],
            ["F-A"],
        )
        self.assertEqual(
            [item["provenance_link"]["character_span"] for item in manifests["fixed-72-v1"]["source_fragments"] if item["canonical_knowledge_record_id"] == "R-A"],
            ["1-71", "73-140", "142-203", "205-215"],
        )
        self.assertTrue(
            all(
                fragment["collection_membership"] == "derived retrieval-side artifact; not a canonical knowledge collection member"
                for manifest in manifests.values()
                for fragment in manifest["source_fragments"]
            )
        )
        self.assertTrue(all(record["supplied_seed_record"] for record in result["canonical_knowledge_records"]))
        self.assertTrue(all(not record["student_generated"] and not record["student_approved"] for record in result["canonical_knowledge_records"]))

    def test_prepare_refuses_symlink_without_modifying_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            stage_dir = report_dir / "stage-b"
            stage_dir.mkdir()
            target = report_dir / "target.txt"
            (stage_dir / "boundary-comparison.json").symlink_to(target)
            with self.assertRaises(WorkflowError):
                prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            self.assertFalse(target.exists())

    def test_record_boundary_decision_preserves_human_selection_and_stops_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            decision_path = record_boundary_decision(
                report_dir=report_dir,
                selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary rule preserves the originating-record relationship required by both declared evaluation cases.",
                student="student-01",
            )
            decision = yaml.safe_load(decision_path.read_text(encoding="utf-8"))

            self.assertEqual(decision["selected chunking configuration"], "sentence-pair-v1")
            self.assertEqual(decision["selected retrieval-unit definition"], "source fragment under sentence-pair-v1")
            self.assertEqual(decision["decision actor"], "the student acting as the engineering team")
            self.assertIn("declared evaluation cases", decision["decision boundary"])
            with self.assertRaisesRegex(WorkflowError, "already exists"):
                record_boundary_decision(
                    report_dir=report_dir,
                    selected_chunking_configuration_id="fixed-72-v1",
                    rationale="A later replacement must not overwrite the recorded decision.",
                    student="student-01",
                )

    def test_decision_refuses_dangling_symlink_without_modifying_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            target = report_dir / "target.yaml"
            (report_dir / "stage-b" / "boundary-decision.yaml").symlink_to(target)
            with self.assertRaises(WorkflowError):
                record_boundary_decision(
                    report_dir=report_dir,
                    selected_chunking_configuration_id="sentence-pair-v1",
                    rationale="A valid human selection.",
                    student="student-01",
                )
            self.assertFalse(target.exists())

    def test_record_boundary_decision_rejects_malformed_comparison_as_workflow_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            comparison_path = prepare_boundary_comparison(
                fixture_path=STAGE_B_FIXTURE,
                report_dir=report_dir,
            )
            comparison_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "does not match the supplied fixture"):
                record_boundary_decision(
                    report_dir=report_dir,
                    selected_chunking_configuration_id="sentence-pair-v1",
                    rationale="A malformed comparison cannot support a decision.",
                    student="student-01",
                )

    def test_cli_prepares_comparison_and_records_boundary_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            output = io.StringIO()
            with redirect_stdout(output):
                prepare_status = main([
                    "lab04",
                    "prepare-boundaries",
                    "--report-dir",
                    str(report_dir),
                ])
                decision_status = main([
                    "lab04",
                    "record-boundary-decision",
                    "--report-dir",
                    str(report_dir),
                    "--chunking-configuration-id",
                    "sentence-pair-v1",
                    "--rationale",
                    "The boundary rule preserves the complete provenance relationship required by both declared evaluation cases.",
                    "--by",
                    "student-01",
                ])
                verification_status = main([
                    "lab04",
                    "verify-stage-b",
                    "--report-dir",
                    str(report_dir),
                ])

            self.assertEqual(prepare_status, 0)
            self.assertEqual(decision_status, 0)
            self.assertEqual(verification_status, 0)
            self.assertIn("Prepared the boundary comparison", output.getvalue())
            self.assertIn("Recorded the boundary decision", output.getvalue())
            self.assertIn("Laboratory 04 Stage B verification passed", output.getvalue())
            self.assertTrue((report_dir / "stage-b" / "boundary-comparison.json").is_file())
            self.assertTrue((report_dir / "stage-b" / "boundary-decision.yaml").is_file())

    def test_verify_stage_b_checks_structure_without_making_the_boundary_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            record_boundary_decision(
                report_dir=report_dir,
                selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary rule preserves every relationship named by the relevance judging basis.",
                student="student-01",
            )

            verification = verify_stage_b(report_dir=report_dir)

        self.assertEqual(verification["outcome"], "passed")
        self.assertEqual(verification["selected chunking configuration"], "sentence-pair-v1")
        self.assertEqual(verification["verification boundary"], "structural consistency; no human boundary decision")

    def test_verify_rejects_altered_fragment_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            comparison_path = prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            record_boundary_decision(
                report_dir=report_dir, selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary preserves context.", student="student-01",
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["chunking_configuration_results"][0]["source_fragments"][0]["text"] = "falsified"
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                verify_stage_b(report_dir=report_dir)

    def test_verify_rejects_altered_character_span(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            comparison_path = prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            record_boundary_decision(
                report_dir=report_dir, selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary preserves context.", student="student-01",
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["chunking_configuration_results"][0]["source_fragments"][0]["provenance_link"]["character_span"] = "1-2"
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                verify_stage_b(report_dir=report_dir)

    def test_verify_rejects_evaluator_only_input_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            comparison_path = prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            record_boundary_decision(
                report_dir=report_dir, selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary preserves context.", student="student-01",
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["evaluation_cases"][0]["operation_input"]["evaluator-only expected result"] = ["F-A"]
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                verify_stage_b(report_dir=report_dir)

    def test_verify_rejects_malformed_nested_decision_as_workflow_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            decision_path = record_boundary_decision(
                report_dir=report_dir, selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary preserves context.", student="student-01",
            )
            decision = yaml.safe_load(decision_path.read_text(encoding="utf-8"))
            decision["selected chunking configuration"] = ["sentence-pair-v1"]
            decision_path.write_text(yaml.safe_dump(decision), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                verify_stage_b(report_dir=report_dir)

    def test_verify_rejects_type_changed_record_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            comparison_path = prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            record_boundary_decision(
                report_dir=report_dir, selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The boundary preserves context.", student="student-01",
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["canonical_knowledge_records"][0]["record_version"] = True
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                verify_stage_b(report_dir=report_dir)

    def test_verify_stage_b_rejects_an_incomplete_retrieval_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            comparison_path = prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
            record_boundary_decision(
                report_dir=report_dir,
                selected_chunking_configuration_id="sentence-pair-v1",
                rationale="The complete relationship remains inside each selected source fragment.",
                student="student-01",
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["retrieval_contract"]["declared fields"].pop("observation boundary")
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "does not match the supplied fixture"):
                verify_stage_b(report_dir=report_dir)


if __name__ == "__main__":
    unittest.main()
