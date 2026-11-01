"""Laboratory 05 retrieval-unit selection tests."""

from __future__ import annotations

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
F_A = (
    "A provenance link binds each evidence passage to its originating record identifier, "
    "record version, and exact sentence span. The link lets a reviewer locate the passage "
    "used to justify a proposed concept definition."
)
F_B = (
    "A proposal-run receipt records the source and version of the model used to produce a "
    "concept proposal; it does not locate the evidence passage."
)
F_X = (
    "A constructed retrieval unit whose provenance link does not resolve to registered sources."
)
TEXT_QUERY = "How can an auditor trace an excerpt to its origin and revision?"


def _seed_query_rewriting(report_dir: Path) -> None:
    lab05 = importlib.import_module("learning_project.lab05")
    lab05.apply_query_rewriting(
        fixture_path=CASES / "query-rewriting-cases.json",
        report_dir=report_dir,
    )


class RetrievalUnitSelectionTests(unittest.TestCase):
    def test_selects_one_unit_and_records_ordered_exclusions(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _seed_query_rewriting(report_dir)
            output = lab05.apply_retrieval_unit_selection(
                fixture_path=CASES / "retrieval-unit-selection-cases.json",
                report_dir=report_dir,
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["selection record id"], "SR-05-1")
        self.assertEqual(result["retrieval-unit admission criteria"], "RUS-05-v1")
        self.assertEqual(result["context budget characters"], 300)
        self.assertEqual(result["text query"], TEXT_QUERY)
        self.assertEqual(
            [unit["retrieval unit id"] for unit in result["ranked candidate output"]],
            ["F-A", "F-B", "F-X"],
        )
        self.assertEqual(result["ranked candidate output"][0]["text character count"], 215)
        self.assertEqual(result["ranked candidate output"][1]["text character count"], 143)
        self.assertEqual(result["ranked candidate output"][2]["text character count"], 90)
        self.assertEqual(result["ranked candidate output"][0]["text"], F_A)
        self.assertEqual(result["ranked candidate output"][1]["text"], F_B)
        self.assertEqual(result["ranked candidate output"][2]["text"], F_X)

        selected = result["supplied source evidence"]
        self.assertEqual([unit["retrieval unit id"] for unit in selected], ["F-A"])
        self.assertEqual(selected[0]["provenance link"]["record id"], "R-A")
        self.assertEqual(result["remaining context budget characters"], 85)

        exclusions = {item["retrieval unit id"]: item for item in result["exclusions"]}
        self.assertEqual(set(exclusions), {"F-B", "F-X"})
        self.assertEqual(exclusions["F-B"]["failed criterion"], "context-budget fit")
        self.assertEqual(exclusions["F-X"]["failed criterion"], "provenance-link resolution")
        self.assertNotIn("context-budget fit", exclusions["F-X"].get("evaluated criteria", ["provenance-link resolution"]))
        self.assertNotIn("relevance judgment", result)
        self.assertNotIn("bounded model request", result)
        self.assertNotIn("candidate concept definition", result)

    def test_verifier_recomputes_the_selection_record_and_rejects_tampering(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _seed_query_rewriting(report_dir)
            output = lab05.apply_retrieval_unit_selection(
                fixture_path=CASES / "retrieval-unit-selection-cases.json",
                report_dir=report_dir,
            )
            verification = lab05.verify_retrieval_unit_selection(
                fixture_path=CASES / "retrieval-unit-selection-cases.json",
                report_dir=report_dir,
            )
            self.assertEqual(verification["outcome"], "passed")
            self.assertEqual(verification["selected retrieval units"], 1)
            self.assertEqual(verification["excluded retrieval units"], 2)

            tampered = json.loads(output.read_text(encoding="utf-8"))
            tampered["supplied source evidence"].append({"retrieval unit id": "F-B"})
            output.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "does not match"):
                lab05.verify_retrieval_unit_selection(
                    fixture_path=CASES / "retrieval-unit-selection-cases.json",
                    report_dir=report_dir,
                )

    def test_cli_applies_and_verifies_retrieval_unit_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            output = io.StringIO()
            with redirect_stdout(output):
                rewrite_code = main([
                    "lab05", "apply-query-rewriting",
                    "--report-dir", str(report_dir),
                ])
                apply_code = main([
                    "lab05", "apply-retrieval-unit-selection",
                    "--report-dir", str(report_dir),
                ])
                verify_code = main([
                    "lab05", "verify-retrieval-unit-selection",
                    "--report-dir", str(report_dir),
                ])
            self.assertEqual(rewrite_code, 0)
            self.assertEqual(apply_code, 0)
            self.assertEqual(verify_code, 0)
            self.assertIn("selection record", output.getvalue())
            self.assertIn("Retrieval-unit selection verification passed", output.getvalue())
            result_path = report_dir / "retrieval-unit-selection" / "selection-record.json"
            self.assertTrue(result_path.is_file())
            self.assertNotRegex(output.getvalue(), r"\b(?:Authoring )?Stage [A-E]\b")
            self.assertNotRegex(output.getvalue(), r"\bGate [A-E]\b")

    def test_requires_the_solvable_rewritten_retrieval_input(self):
        lab05 = importlib.import_module("learning_project.lab05")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            with self.assertRaisesRegex(WorkflowError, "query-rewriting result"):
                lab05.apply_retrieval_unit_selection(
                    fixture_path=CASES / "retrieval-unit-selection-cases.json",
                    report_dir=report_dir,
                )


if __name__ == "__main__":
    unittest.main()
