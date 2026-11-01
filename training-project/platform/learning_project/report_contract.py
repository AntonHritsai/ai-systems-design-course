"""Reusable student-report contract for the course laboratories.

One checker serves every laboratory report route. Each laboratory supplies its
exact headings, ordered checkpoint screenshots, required evidence inventory,
internal-vocabulary pattern, and label. The checker validates the public
student contract only: structure, identity, completion state, checkpoint
links, and evidence presence. Commit-bound completion verification lives here
as well, so every laboratory binds its evidence to one exact branch head with
the same drift rules.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .workflow import WorkflowError


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowError(message)


def validate_report_contract(
    *,
    report_dir: Path,
    lab_id: str,
    lab_label: str,
    headings: tuple[str, ...],
    screenshots: tuple[str, ...],
    required_evidence: tuple[str, ...],
    internal_stage_pattern: str,
    evidence_present_message: str,
    personal_branch_pattern: str | None = None,
    personal_branch_example: str | None = None,
) -> dict:
    """Validate one laboratory's public report and evidence inventory."""
    checks: list[dict[str, str]] = []

    def check(check_id: str, action) -> None:
        try:
            message = action()
        except Exception as exc:  # noqa: BLE001 - collect every report defect
            checks.append({"check_id": check_id, "status": "failed", "message": str(exc)})
        else:
            checks.append({"check_id": check_id, "status": "passed", "message": message})

    report_path = report_dir / "REPORT.md"
    try:
        text = report_path.read_text(encoding="utf-8")
    except OSError:
        text = ""

    def check_headings() -> str:
        _require(report_path.is_file(), "REPORT.md is required.")
        found = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
        _require(
            found == list(headings),
            "REPORT.md must contain the exact required report headings in order.",
        )
        return "required report headings are present in order"

    def check_internal_vocabulary() -> str:
        internal_term = re.search(internal_stage_pattern, text, flags=re.IGNORECASE)
        _require(internal_term is None, "Internal course-development vocabulary is not permitted in the report.")
        return "no internal course-development vocabulary is present"

    def check_identity() -> str:
        fork = re.search(r"https://github\.com/([^/\s]+)/([^\s)]+)", text)
        _require(fork is not None, "The report identity section must contain the student's GitHub fork URL.")
        _require(fork.group(1).lower() != "sobol-mo", "The fork URL must identify the student's fork.")
        branch = re.search(r"^\s*[-*]?\s*Особиста гілка:\s*`?([^`\s]+)`?\s*$", text, re.MULTILINE)
        branch_value = branch.group(1) if branch is not None else ""
        _require(branch is not None, "The report identity section must contain a personal branch.")
        _require(branch_value.lower() not in {"main", "master"}, "The personal branch must not be main or master.")
        if personal_branch_pattern is not None:
            _require(
                re.fullmatch(personal_branch_pattern, branch_value) is not None,
                f"The personal branch must match {personal_branch_example or personal_branch_pattern}.",
            )
        return "fork URL and personal branch are recorded"

    def check_completion() -> str:
        completion = re.search(
            r"^\s*[-*]?\s*Статус завершення:\s*`?(complete|honest-partial)`?\s*$",
            text,
            re.MULTILINE,
        )
        _require(
            completion is not None,
            "The report identity section must record the completion state `complete` or `honest-partial`.",
        )
        return "the completion state is recorded"

    def check_data_uri() -> str:
        _require("data:image/" not in text.lower(), "REPORT.md must not contain a data URI.")
        return "the source report embeds no data URIs"

    def check_screenshots() -> str:
        image_targets = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
        expected_targets = [f"screenshots/{name}" for name in screenshots]
        _require(
            image_targets == expected_targets,
            "REPORT.md must contain exactly these relative screenshot links in order: "
            + ", ".join(screenshots),
        )
        screenshot_dir = report_dir / "screenshots"
        missing = [name for name in screenshots[:-1] if not (screenshot_dir / name).is_file()]
        _require(not missing, "Required checkpoint screenshot files are missing: " + ", ".join(missing))
        actual = {path.name for path in screenshot_dir.glob("*.png")} if screenshot_dir.is_dir() else set()
        unexpected = sorted(actual - set(screenshots))
        _require(not unexpected, "Unexpected screenshot files are present: " + ", ".join(unexpected))
        return "six exact relative links and five pre-verification screenshot files are present"

    def check_evidence() -> str:
        missing = [relative for relative in required_evidence if not (report_dir / relative).is_file()]
        _require(not missing, f"Required {lab_label} evidence is missing: " + ", ".join(missing))
        return evidence_present_message

    check("report-headings", check_headings)
    check("internal-vocabulary", check_internal_vocabulary)
    check("report-identity", check_identity)
    check("report-completion", check_completion)
    check("report-data-uri", check_data_uri)
    check("report-screenshots", check_screenshots)
    check("stage-evidence", check_evidence)
    return {
        "schema_version": "1.0",
        "lab_id": lab_id,
        "status": "passed" if all(item["status"] == "passed" for item in checks) else "failed",
        "checks": checks,
    }


def verify_report_contract(
    *,
    report_dir: Path,
    final_commit: str,
    lab_id: str,
    lab_label: str,
    screenshots: tuple[str, ...],
    validation: dict,
) -> dict:
    """Bind complete laboratory evidence to an exact current branch head."""
    checks = list(validation["checks"])

    def check_final_commit() -> str:
        _require(
            re.fullmatch(r"[0-9a-f]{40}", final_commit) is not None,
            "Final student commit must be a full lowercase 40-character Git hash.",
        )
        try:
            git_root = Path(subprocess.run(
                ["git", "-C", str(report_dir), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()).resolve()
            resolved = subprocess.run(
                ["git", "-C", str(git_root), "rev-parse", "--verify", f"{final_commit}^{{commit}}"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            head = subprocess.run(
                ["git", "-C", str(git_root), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise WorkflowError("Final student commit is missing or unresolvable in the report repository.") from exc
        _require(resolved == final_commit, "Final student commit did not resolve to the exact supplied hash.")
        _require(resolved == head, "Final student commit must be the current branch head.")
        try:
            report_relative = report_dir.resolve().relative_to(git_root).as_posix()
        except ValueError as exc:
            raise WorkflowError(f"{lab_label} report directory is outside the final commit repository.") from exc
        changed = subprocess.run(
            ["git", "-C", str(git_root), "diff", "--name-only", resolved, "--", report_relative],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        untracked = subprocess.run(
            ["git", "-C", str(git_root), "ls-files", "--others", "--exclude-standard", "--", report_relative],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        allowed = {
            f"{report_relative}/verification-report.json",
            f"{report_relative}/screenshots/{screenshots[-1]}",
            f"{report_relative}/submission/REPORT.md",
        }
        drift = sorted({*changed, *untracked} - allowed)
        _require(not drift, f"{lab_label} evidence changed after the final commit: " + ", ".join(drift))
        return f"exact final commit {resolved} is the current branch head"

    try:
        message = check_final_commit()
    except Exception as exc:  # noqa: BLE001 - write a complete verification report on failure
        checks.insert(0, {"check_id": "final-commit", "status": "failed", "message": str(exc)})
    else:
        checks.insert(0, {"check_id": "final-commit", "status": "passed", "message": message})

    verification = {
        "schema_version": "1.0",
        "lab_id": lab_id,
        "outcome": "passed" if all(item["status"] == "passed" for item in checks) else "failed",
        "final_commit": final_commit,
        "checks": checks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output = report_dir / "verification-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(verification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return verification
