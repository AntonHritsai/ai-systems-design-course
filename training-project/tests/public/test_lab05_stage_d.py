from __future__ import annotations

import importlib
import json
import subprocess
import unittest
from pathlib import Path

from learning_project.cli import _build_parser, main
from learning_project.lab05 import (
    LAB05_REQUIRED_EVIDENCE,
    LAB05_REPORT_SCREENSHOTS,
    validate_lab05_report,
    verify_lab05,
)

try:  # resolve helpers both under the dotted module path and a tests-rooted run
    from .test_lab05_stage_c4 import (
        _prepare as _seed_conditions,
        _run_evaluation_stack,
        _seed_generation,
    )
except ImportError:
    from test_lab05_stage_c4 import (
        _prepare as _seed_conditions,
        _run_evaluation_stack,
        _seed_generation,
    )

REPORT_TEXT = """# Лабораторна робота 05

## Ідентифікація

- Прізвище та ім'я студента: Тестовий Студент
- Ідентифікатор студента: student-01
- URL форка: https://github.com/student/ai-systems-design-course
- Особиста гілка: lab05/student-01
- Статус завершення: `complete`

## Мета роботи

Підготувати перевірену конфігурацію операції пропозиції поняття з використанням моделі.

## Хід виконання

### Перетворення інформаційної потреби

Зафіксовано дію, результат і підставу для продовження.

![переписування запиту](screenshots/01-query-rewriting.png)

### Відбір одиниць інформаційного пошуку

Зафіксовано дію, результат і підставу для продовження.

![відбір одиниць](screenshots/02-retrieval-unit-selection.png)

### Побудова обмеженого запиту до моделі

Зафіксовано дію, результат і підставу для продовження.

![побудова контексту](screenshots/03-context-construction.png)

### Генерування з цитуванням твердження або відмова

Зафіксовано дію, результат і підставу для продовження.

![генерування](screenshots/04-generation-outcomes.png)

### Оцінювання та обмежене рішення щодо конфігурації

Зафіксовано дію, результат і підставу для продовження.

![рішення](screenshots/05-configuration-decision.png)

### Остаточна перевірка

Зафіксовано дію, результат і підставу для завершення.

![остаточна перевірка](screenshots/06-final-verification.png)

## Висновки

Мету досягнуто повністю: виконано переписування запиту, відбір одиниць інформаційного пошуку,
побудову обмеженого запиту до моделі, генерування, оцінювання та обмежене рішення щодо конфігурації.
"""


def _complete_tree(report_dir: Path) -> None:
    lab05 = importlib.import_module("learning_project.lab05")
    _seed_generation(report_dir)
    _seed_conditions(report_dir)
    _run_evaluation_stack(report_dir)
    lab05.record_configuration_decision(
        report_dir=report_dir,
        decision="adopt the candidate configuration",
        rationale="Every evaluated acceptance condition is satisfied.",
        recorded_by="student-01",
    )
    for role in ("experiment-baseline", "candidate-configuration"):
        for case in ("ec-05-1", "ec-05-2", "ec-05-3"):
            run_dir = report_dir / "generation" / "runs" / role / case
            response = run_dir / "raw-response.txt"
            if not response.is_file():
                response.write_text("full provider response body\n", encoding="utf-8")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "REPORT.md").write_text(REPORT_TEXT, encoding="utf-8")
    screenshots = report_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)
    for name in LAB05_REPORT_SCREENSHOTS[:-1]:
        (screenshots / name).write_bytes(b"student screenshot")


def _commit(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Student"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "student@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "Lab 05 evidence"], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class ValidateLab05Report(unittest.TestCase):
    def test_accepts_the_complete_public_contract(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)

            result = validate_lab05_report(report_dir=report_dir)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["lab_id"], "lab05")
        self.assertTrue(all(check["status"] == "passed" for check in result["checks"]))
        self.assertEqual(
            [check["check_id"] for check in result["checks"]],
            [
                "report-headings",
                "internal-vocabulary",
                "report-identity",
                "report-completion",
                "report-data-uri",
                "report-screenshots",
                "stage-evidence",
            ],
        )

    def test_rejects_report_defects_and_missing_evidence(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            report = report_dir / "REPORT.md"
            text = report.read_text(encoding="utf-8")
            text = text.replace("## Хід виконання", "## Authoring Stage C4")
            text = text.replace("- Статус завершення: `complete`\n", "")
            text = text.replace(
                "https://github.com/student/ai-systems-design-course",
                "data:image/png;base64,AAAA",
            )
            text = text.replace("](screenshots/04-generation-outcomes.png)", "](screenshots/unexpected.png)")
            report.write_text(text, encoding="utf-8")
            (report_dir / "evaluation" / "configuration-decision.json").unlink()

            result = validate_lab05_report(report_dir=report_dir)

            messages = "\n".join(
                check["message"] for check in result["checks"] if check["status"] == "failed"
            ).lower()

        self.assertEqual(result["status"], "failed")
        self.assertIn("required report headings", messages)
        self.assertIn("internal course-development vocabulary", messages)
        self.assertIn("fork url", messages)
        self.assertIn("completion state", messages)
        self.assertIn("data uri", messages)
        self.assertIn("04-generation-outcomes.png", messages)
        self.assertIn("configuration-decision.json", messages)
        self.assertNotIn("authoring stage", messages)

    def test_rejects_internal_stage_vocabulary_in_body(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            report = report_dir / "REPORT.md"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "Зафіксовано дію, результат і підставу для продовження.",
                    "Стадія Stage D завершена.",
                    1,
                ),
                encoding="utf-8",
            )

            result = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in result["checks"] if check["status"] == "failed"
            ).lower()

        self.assertEqual(result["status"], "failed")
        self.assertIn("internal course-development vocabulary", messages)
        self.assertNotIn("authoring stage", messages)

    def test_rejects_a_personal_branch_outside_the_lab05_namespace(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            report = report_dir / "REPORT.md"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "- Особиста гілка: lab05/student-01",
                    "- Особиста гілка: feature/student-01",
                ),
                encoding="utf-8",
            )

            result = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in result["checks"] if check["status"] == "failed"
            )

        self.assertEqual(result["status"], "failed")
        self.assertIn("lab05/<student-id>", messages)

    def test_rejects_personal_branch_with_characters_outside_the_contract(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            report = report_dir / "REPORT.md"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "- Особиста гілка: lab05/student-01",
                    "- Особиста гілка: lab05/student@01",
                ),
                encoding="utf-8",
            )

            result = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in result["checks"] if check["status"] == "failed"
            )

        self.assertEqual(result["status"], "failed")
        self.assertIn("lab05/<student-id>", messages)

    def test_rejects_bare_authoring_stage_label(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            report = report_dir / "REPORT.md"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "Зафіксовано дію, результат і підставу для продовження.",
                    "Authoring Stage завершена.",
                    1,
                ),
                encoding="utf-8",
            )

            result = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in result["checks"] if check["status"] == "failed"
            ).lower()

        self.assertEqual(result["status"], "failed")
        self.assertIn("internal course-development vocabulary", messages)

    def test_rejects_stage_a_label_in_body(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            report = report_dir / "REPORT.md"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "Зафіксовано дію, результат і підставу для продовження.",
                    "Стадія Stage A завершена.",
                    1,
                ),
                encoding="utf-8",
            )

            result = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in result["checks"] if check["status"] == "failed"
            ).lower()

        self.assertEqual(result["status"], "failed")
        self.assertIn("internal course-development vocabulary", messages)

    def test_rejects_missing_screenshot_file_and_unexpected_screenshot(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports" / "lab05"
            _complete_tree(report_dir)
            (report_dir / "screenshots" / "02-retrieval-unit-selection.png").unlink()

            missing = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in missing["checks"] if check["status"] == "failed"
            )

            self.assertEqual(missing["status"], "failed")
            self.assertIn("02-retrieval-unit-selection.png", messages)

            (report_dir / "screenshots" / "02-retrieval-unit-selection.png").write_bytes(b"restored")
            (report_dir / "screenshots" / "07-extra.png").write_bytes(b"extra")

            unexpected = validate_lab05_report(report_dir=report_dir)
            messages = "\n".join(
                check["message"] for check in unexpected["checks"] if check["status"] == "failed"
            )

        self.assertEqual(unexpected["status"], "failed")
        self.assertIn("07-extra.png", messages)

    def test_required_evidence_covers_the_whole_declared_workflow(self) -> None:
        self.assertIn("query-rewriting/query-rewriting-results.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("retrieval-unit-selection/selection-record.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("context-construction/bounded-model-request.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("generation/shared-experiment-protocol.json", LAB05_REQUIRED_EVIDENCE)
        for case in ("ec-05-1", "ec-05-2", "ec-05-3"):
            self.assertIn(f"generation/cases/{case}/bounded-model-request.json", LAB05_REQUIRED_EVIDENCE)
            for role in ("experiment-baseline", "candidate-configuration"):
                self.assertIn(f"generation/runs/{role}/{case}/raw-response.txt", LAB05_REQUIRED_EVIDENCE)
                self.assertIn(f"generation/runs/{role}/{case}/raw-outcome.json", LAB05_REQUIRED_EVIDENCE)
                self.assertIn(f"generation/runs/{role}/{case}/run-metadata.json", LAB05_REQUIRED_EVIDENCE)
                self.assertIn(f"evaluation/judgments/{role}/{case}/judgment.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("evaluation/acceptance-conditions.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("evaluation/rubric-pass-rate.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("evaluation/acceptance-evaluation.json", LAB05_REQUIRED_EVIDENCE)
        self.assertIn("evaluation/configuration-decision.json", LAB05_REQUIRED_EVIDENCE)
        self.assertEqual(len(LAB05_REPORT_SCREENSHOTS), 6)
        self.assertTrue(LAB05_REPORT_SCREENSHOTS[-1] == "06-final-verification.png")


class VerifyLab05Completion(unittest.TestCase):
    def test_binds_exact_head_and_writes_the_verification_report(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "student-repository"
            report_dir = root / "reports" / "lab05"
            _complete_tree(report_dir)
            final_commit = _commit(root)

            result = verify_lab05(report_dir=report_dir, final_commit=final_commit)
            written = json.loads(
                (report_dir / "verification-report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["outcome"], "passed")
        self.assertEqual(result["lab_id"], "lab05")
        self.assertEqual(result["final_commit"], final_commit)
        self.assertEqual(written, result)

    def test_fails_for_unresolvable_commit_and_for_post_commit_drift(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "student-repository"
            report_dir = root / "reports" / "lab05"
            _complete_tree(report_dir)
            final_commit = _commit(root)

            invalid = verify_lab05(report_dir=report_dir, final_commit="a" * 40)
            self.assertEqual(invalid["outcome"], "failed")

            (report_dir / "REPORT.md").write_text(REPORT_TEXT + "\nЗміна після коміту.\n", encoding="utf-8")
            drifted = verify_lab05(report_dir=report_dir, final_commit=final_commit)
            self.assertEqual(drifted["outcome"], "failed")
            final_check = next(
                check for check in drifted["checks"] if check["check_id"] == "final-commit"
            )
            self.assertIn("changed after", final_check["message"])

    def test_allows_only_the_declared_post_commit_outputs(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "student-repository"
            report_dir = root / "reports" / "lab05"
            _complete_tree(report_dir)
            final_commit = _commit(root)
            (report_dir / "screenshots" / "06-final-verification.png").write_bytes(b"final")
            (report_dir / "submission").mkdir()
            (report_dir / "submission" / "REPORT.md").write_text("Teams copy", encoding="utf-8")

            result = verify_lab05(report_dir=report_dir, final_commit=final_commit)

        self.assertEqual(result["outcome"], "passed")


class Lab05ReportCLISurface(unittest.TestCase):
    def test_exposes_validate_report_and_verify_commands(self) -> None:
        parser = _build_parser()
        root_commands = next(
            action for action in parser._subparsers._group_actions if action.dest == "command"
        )
        lab05_parser = root_commands.choices["lab05"]
        commands = next(
            action
            for action in lab05_parser._subparsers._group_actions
            if action.dest == "lab05_command"
        ).choices
        self.assertLessEqual({"validate-report", "verify"}, set(commands))

    def test_validate_report_returns_nonzero_for_a_defective_tree(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            defective = Path(tmp) / "defective"
            defective.mkdir()
            code = main(["lab05", "validate-report", "--report-dir", str(defective)])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
