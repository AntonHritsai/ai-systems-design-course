"""Laboratory 05 Stage B query-rewriting tests."""

import importlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from learning_project.cli import main
from learning_project.workflow import WorkflowError


CASES = Path(__file__).resolve().parents[2] / "cases" / "lab05"


class QueryRewritingTests(unittest.TestCase):
    def test_applies_one_solvable_and_one_unsolvable_rewrite(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            output = lab05.apply_query_rewriting(
                fixture_path=CASES / "query-rewriting-cases.json",
                report_dir=report_dir,
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["query-rewriting rule"], "QR-05-v1")
        by_case = {item["case id"]: item for item in result["cases"]}
        self.assertEqual(set(by_case), {"solvable-rewrite", "unsolvable-rewrite"})

        solvable = by_case["solvable-rewrite"]
        self.assertEqual(solvable["outcome"], "rewritten retrieval input")
        self.assertEqual(
            solvable["rewritten retrieval input"],
            "How can an auditor trace an excerpt to its origin and revision?",
        )
        self.assertEqual(solvable["meaning preservation"]["requested concept"], "provenance link")
        self.assertEqual(solvable["meaning preservation"]["requested relation"], "trace an excerpt to its origin and revision")
        self.assertEqual(solvable["next operation"], "accepted retrieval operation")
        self.assertNotIn("ranked candidate output", solvable)

        unsolvable = by_case["unsolvable-rewrite"]
        self.assertEqual(unsolvable["outcome"], "unsolvable rewrite")
        self.assertEqual(unsolvable["missing identity"], "requested concept")
        self.assertEqual(unsolvable["next operation"], "stop before the accepted retrieval operation")
        self.assertNotIn("rewritten retrieval input", unsolvable)
        self.assertNotIn("ranked candidate output", unsolvable)

    def test_verifier_recomputes_the_fixture_and_rejects_tampering(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            output = lab05.apply_query_rewriting(
                fixture_path=CASES / "query-rewriting-cases.json",
                report_dir=report_dir,
            )
            verification = lab05.verify_stage_b(
                fixture_path=CASES / "query-rewriting-cases.json",
                report_dir=report_dir,
            )
            self.assertEqual(verification["outcome"], "passed")
            self.assertEqual(verification["verified cases"], 2)

            tampered = json.loads(output.read_text(encoding="utf-8"))
            tampered["cases"][0]["rewritten retrieval input"] = "Define provenance link."
            output.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "does not match"):
                lab05.verify_stage_b(
                    fixture_path=CASES / "query-rewriting-cases.json",
                    report_dir=report_dir,
                )

    def test_cli_applies_and_verifies_the_stage_b_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            output = io.StringIO()
            with redirect_stdout(output):
                apply_code = main([
                    "lab05", "apply-query-rewriting",
                    "--report-dir", str(report_dir),
                ])
                verify_code = main([
                    "lab05", "verify-query-rewriting",
                    "--report-dir", str(report_dir),
                ])
            self.assertEqual(apply_code, 0)
            self.assertEqual(verify_code, 0)
            self.assertIn("query-rewriting result", output.getvalue())
            self.assertIn("Query-rewriting verification passed for 2 cases", output.getvalue())

            result_path = report_dir / "query-rewriting" / "query-rewriting-results.json"
            self.assertTrue(result_path.is_file())
            self.assertNotRegex(output.getvalue(), r"\b(?:Authoring )?Stage [A-E]\b")

    def test_rejects_a_case_without_an_explicit_identity_availability_boundary(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = json.loads((CASES / "query-rewriting-cases.json").read_text(encoding="utf-8"))
            fixture["cases"][1].pop("identity_available_inside_information_need")
            fixture_path = Path(tmp) / "invalid-cases.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "identity availability"):
                lab05.apply_query_rewriting(
                    fixture_path=fixture_path,
                    report_dir=Path(tmp) / "reports" / "lab05",
                )


if __name__ == "__main__":
    unittest.main()
