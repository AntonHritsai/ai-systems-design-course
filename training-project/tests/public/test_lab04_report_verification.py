import json
import subprocess
from pathlib import Path

from learning_project.cli import _build_parser, main
from learning_project.lab04 import validate_lab04_report, verify_lab04


SCREENSHOTS = (
    "01-boundary-selection.png",
    "02-embedding-index.png",
    "03-retrieval-comparison.png",
    "04-relevance-metrics.png",
    "05-operational-decision.png",
    "06-final-verification.png",
)

STAGE_EVIDENCE = (
    "stage-b/boundary-comparison.json",
    "stage-b/boundary-decision.yaml",
    "stage-c1/retrieval-unit-embeddings.json",
    "stage-c1/index-manifest.json",
    "stage-c1/binding-check-required-course-seed-v1.json",
    "stage-c1/binding-check-required-course-seed-v2.json",
    "stage-c2/evaluation-case-a-lexical-retrieval.json",
    "stage-c2/evaluation-case-a-embedding-based-retrieval.json",
    "stage-c2/evaluation-case-a-hybrid-retrieval.json",
    "stage-c2/evaluation-case-a-lexical-retrieval-followed-by-embedding-based-reranking.json",
    "stage-c2/evaluation-case-b-lexical-retrieval.json",
    "stage-c2/evaluation-case-b-embedding-based-retrieval.json",
    "stage-c2/evaluation-case-b-hybrid-retrieval.json",
    "stage-c2/evaluation-case-b-lexical-retrieval-followed-by-embedding-based-reranking.json",
    "stage-c3/relevance-judgments.json",
    "stage-c3/retrieval-metrics.json",
    "stage-c3/operational-evidence.json",
    "stage-c3/configuration-decision.json",
)


def _report_text() -> str:
    links = "\n".join(f"![Свідчення](screenshots/{name})" for name in SCREENSHOTS)
    return f"""# Лабораторна робота 04

## Ідентифікація

- URL форка: https://github.com/student/ai-systems-design-course
- Особиста гілка: lab04-student
- Статус завершення: `complete`

## Мета роботи

Підготувати перевірену конфігурацію інформаційного пошуку.

## Хід виконання

### Вибір меж

Зафіксовано дію, результат і підставу для продовження.

{links}

## Висновки

Мету досягнуто повністю: підготовлено індекс, порівняно результати, обчислено метрики та зафіксовано рішення.
"""


def _prepare_complete_report(report_dir: Path) -> None:
    report_dir.mkdir(parents=True)
    (report_dir / "REPORT.md").write_text(_report_text(), encoding="utf-8")
    screenshot_dir = report_dir / "screenshots"
    screenshot_dir.mkdir()
    for name in SCREENSHOTS[:-1]:
        (screenshot_dir / name).write_bytes(b"student screenshot")
    for relative in STAGE_EVIDENCE:
        path = report_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")


def _commit(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Student"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "student@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "Lab 04 evidence"], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_report_validator_accepts_exact_public_contract(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "lab04"
    _prepare_complete_report(report_dir)

    result = validate_lab04_report(report_dir=report_dir)

    assert result["status"] == "passed"
    assert all(check["status"] == "passed" for check in result["checks"])


def test_report_validator_rejects_internal_heading_and_report_defects(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "lab04"
    _prepare_complete_report(report_dir)
    report = report_dir / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace("## Хід виконання", "## Authoring Stage C1")
    text = text.replace("- Статус завершення: `complete`\n", "")
    text = text.replace("https://github.com/student/ai-systems-design-course", "data:image/png;base64,AAAA")
    text = text.replace("](screenshots/03-retrieval-comparison.png)", "](screenshots/unexpected.png)")
    report.write_text(text, encoding="utf-8")
    (report_dir / "stage-c3" / "configuration-decision.json").unlink()

    result = validate_lab04_report(report_dir=report_dir)

    assert result["status"] == "failed"
    messages = "\n".join(check["message"] for check in result["checks"] if check["status"] == "failed").lower()
    assert "required report headings" in messages
    assert "internal course-development vocabulary" in messages
    assert "data uri" in messages
    assert "03-retrieval-comparison.png" in messages
    assert "fork url" in messages
    assert "completion state" in messages
    assert "configuration-decision.json" in messages
    assert "authoring stage" not in messages


def test_report_validator_rejects_internal_stage_vocabulary_in_body(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "lab04"
    _prepare_complete_report(report_dir)
    report = report_dir / "REPORT.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "Зафіксовано дію, результат і підставу для продовження.",
            "Authoring Stage C1 завершено.",
        ),
        encoding="utf-8",
    )

    result = validate_lab04_report(report_dir=report_dir)

    assert result["status"] == "failed"
    messages = "\n".join(check["message"] for check in result["checks"] if check["status"] == "failed").lower()
    assert "internal course-development vocabulary" in messages
    assert "authoring stage" not in messages


def test_lab04_cli_exposes_report_validation_and_final_verification(tmp_path: Path) -> None:
    parser = _build_parser()
    root_commands = next(action for action in parser._subparsers._group_actions if action.dest == "command")
    lab04_parser = root_commands.choices["lab04"]
    commands = next(
        action for action in lab04_parser._subparsers._group_actions if action.dest == "lab04_command"
    ).choices
    assert {"validate-report", "verify"} <= set(commands)

    defective = tmp_path / "defective"
    defective.mkdir()
    assert main(["lab04", "validate-report", "--report-dir", str(defective)]) == 1


def test_final_verification_binds_exact_head_and_writes_report(tmp_path: Path) -> None:
    root = tmp_path / "student-repository"
    report_dir = root / "reports" / "lab04"
    _prepare_complete_report(report_dir)
    final_commit = _commit(root)

    result = verify_lab04(report_dir=report_dir, final_commit=final_commit)

    assert result["outcome"] == "passed"
    assert result["final_commit"] == final_commit
    written = json.loads((report_dir / "verification-report.json").read_text(encoding="utf-8"))
    assert written == result


def test_final_verification_is_nonpassing_for_invalid_commit_or_drift(tmp_path: Path) -> None:
    root = tmp_path / "student-repository"
    report_dir = root / "reports" / "lab04"
    _prepare_complete_report(report_dir)
    final_commit = _commit(root)

    invalid = verify_lab04(report_dir=report_dir, final_commit="a" * 40)
    assert invalid["outcome"] == "failed"

    (report_dir / "REPORT.md").write_text(_report_text() + "\nЗміна після коміту.\n", encoding="utf-8")
    drifted = verify_lab04(report_dir=report_dir, final_commit=final_commit)
    assert drifted["outcome"] == "failed"
    final_check = next(check for check in drifted["checks"] if check["check_id"] == "final-commit")
    assert "changed after" in final_check["message"]
