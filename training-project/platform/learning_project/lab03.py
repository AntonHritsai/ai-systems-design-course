"""Laboratory 03 evidence-based evaluation workflow.

Implements the frozen implementation-facing contract
(AUTHORING/LABORATORY_03_IMPLEMENTATION_CONTRACT.md): calibration packets,
bounded development, protocol freeze, autonomous reserve-family selection with
an append-only exposure ledger, a sixteen-position paired comparison with
unstarted/returned/failed position states, route-wide failure classification,
blinded semantic scoring, nested-count aggregation, a bounded recommendation,
regression records, and a commit-first final verifier with passed-complete /
passed-partial outcomes.

The module is deterministic apart from explicitly injected runner functions.
Every artifact is write-once; the exposure ledger is append-only.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, cast

import yaml

from .lab03_adapters import RunnerResult
from .workflow import WorkflowError

LAB_ID = "lab03"
SCHEMA_VERSION = "1.0"
ENVELOPE_FIELDS = {"case_id", "proposed_text"}
RUBRIC_CATEGORIES = ("S", "I", "U", "Q", "R", "X")
EVIDENCE_SITUATIONS = ("sufficient-evidence", "distractor", "missing-fact", "explicit-ambiguity")
POSITION_STATES = ("unstarted", "returned", "failed")
FAILURE_CLASSES = ("position-specific", "route-wide")
OUTCOMES = ("recommend-b", "retain-a", "reject-both", "seek-more-evidence")
VERIFICATION_OUTCOMES = ("passed-complete", "passed-partial")
HELDOUT_CASES = 4
ATTEMPTS_PER_CASE = 2
VARIANTS = ("a", "b")
SCHEDULED_POSITIONS = HELDOUT_CASES * ATTEMPTS_PER_CASE * len(VARIANTS)
DEVELOPMENT_INPUTS = 4
DEVELOPMENT_POSITIONS = DEVELOPMENT_INPUTS * len(VARIANTS)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Route-wide failure markers: adapter-level signals that establish unavailability
# of the whole route rather than one position's bad output.
ROUTE_WIDE_MARKERS = (
    "authentication",
    "auth",
    "quota",
    "rate limit",
    "rate-limit",
    "account",
    "unavailable",
    "permission",
    "401",
    "403",
    "429",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowError(message)


def _slug(value: str, label: str) -> str:
    _require(isinstance(value, str) and SLUG_RE.fullmatch(value), f"{label} must be a lowercase slug.")
    return value


def _read_json(path: Path, label: str) -> tuple[dict, bytes]:
    try:
        data = path.read_bytes()
        value = json.loads(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"{label} cannot be read: {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} must contain a JSON object.")
    return value, data


def _write_bytes_once(path: Path, data: bytes) -> Path:
    if path.exists():
        raise WorkflowError(f"The immutable artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_json_once(path: Path, payload: dict) -> Path:
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return _write_bytes_once(path, rendered.encode("utf-8"))


def _file_sha256(path: Path, label: str) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise WorkflowError(f"{label} cannot be read: {path}: {exc}") from exc


def _join_map_path(comparison_dir: Path) -> Path:
    return comparison_dir / "scoring" / "_join-map.json"


def _dump_yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)


def _write_yaml_once(path: Path, payload: dict) -> Path:
    if path.exists():
        raise WorkflowError(f"The immutable artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Course material loading and deterministic family checks
# ---------------------------------------------------------------------------


def load_family(family_path: Path, *, expected_cases: int | None = None) -> dict:
    family, _ = _read_json(family_path, "Case family")
    _require(family.get("schema_version") == SCHEMA_VERSION, "Family schema_version must be 1.0.")
    _slug(str(family.get("family_id", "")), "family_id")
    required_cases = expected_cases if expected_cases is not None else HELDOUT_CASES
    cases = family.get("cases")
    _require(
        isinstance(cases, list) and len(cases) == required_cases,
        f"A family must contain exactly {required_cases} cases.",
    )
    case_ids: list[str] = []
    situations: list[str] = []
    for case in cases:
        _require(isinstance(case, dict), "Each case must be an object.")
        case_id = _slug(str(case.get("case_id", "")), "case_id")
        _require(case.get("family_id") == family["family_id"], "Case family_id must match the family.")
        situation = case.get("evidence_situation")
        _require(situation in EVIDENCE_SITUATIONS, f"Case {case_id} has an unknown evidence_situation.")
        _require(isinstance(case.get("task"), str) and case["task"].strip(), f"Case {case_id} task must be non-empty.")
        _require(
            isinstance(case.get("supplied_source"), str) and case["supplied_source"].strip(),
            f"Case {case_id} supplied_source must be non-empty.",
        )
        _require(isinstance(case.get("constructed"), bool), f"Case {case_id} constructed must be boolean.")
        if case["constructed"]:
            _require(
                isinstance(case.get("mutation_note"), str) and case["mutation_note"].strip(),
                f"Constructed case {case_id} must carry a mutation note.",
            )
        pointers = case.get("source_pointers")
        _require(
            isinstance(pointers, list) and pointers,
            f"Case {case_id} must carry at least one source pointer.",
        )
        case_ids.append(case_id)
        situations.append(situation)
    _require(len(set(case_ids)) == required_cases, "Family case identifiers must be unique.")
    if required_cases == HELDOUT_CASES:
        _require(sorted(situations) == sorted(EVIDENCE_SITUATIONS), "A family must cover all four evidence situations.")
    behaviors = family.get("expected_behaviors")
    _require(
        isinstance(behaviors, list) and len(behaviors) == required_cases,
        f"A family must contain exactly {required_cases} expected behaviors.",
    )
    behavior_ids: list[str] = []
    for behavior in behaviors:
        _require(isinstance(behavior, dict), "Each expected behavior must be an object.")
        behavior_ids.append(_slug(str(behavior.get("case_id", "")), "expected behavior case_id"))
        _require(
            behavior.get("expected_category") in RUBRIC_CATEGORIES,
            "Expected behavior category must be a rubric category.",
        )
        _require(
            isinstance(behavior.get("expected_behavior"), str) and behavior["expected_behavior"].strip(),
            "Expected behavior statement must be non-empty.",
        )
    _require(sorted(behavior_ids) == sorted(case_ids), "Expected behaviors must match the family cases exactly.")
    origin = family.get("origin")
    _require(origin in {"course-reserve", "curator-generated", "course-development"},
             "Family origin is not supported.")
    if origin == "curator-generated":
        provenance = family.get("provenance")
        _require(isinstance(provenance, dict) and provenance.get("curator_session") and provenance.get("inputs_sha256"),
                 "Curator-generated family must record curator provenance.")
    return family


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def check_near_duplicates(families: Iterable[dict]) -> None:
    """Reject exact or normalized duplication of case text across families."""
    seen_exact: dict[str, str] = {}
    seen_normalized: dict[str, str] = {}
    for family in families:
        for case in family["cases"]:
            task_key = f"{case['task']}||{case['supplied_source']}"
            exact_key = hashlib.sha256(task_key.encode("utf-8")).hexdigest()
            normalized_key = _normalized_text(task_key)
            owner = family["family_id"]
            if exact_key in seen_exact:
                raise WorkflowError(
                    f"Case text in family {owner} exactly duplicates family {seen_exact[exact_key]}."
                )
            if normalized_key in seen_normalized:
                raise WorkflowError(
                    f"Case text in family {owner} near-duplicates family {seen_normalized[normalized_key]}."
                )
            seen_exact[exact_key] = owner
            seen_normalized[normalized_key] = owner


def load_variant_a(instructions_dir: Path) -> tuple[str, str]:
    data, digest = load_variant_a_bytes(instructions_dir)
    return data.decode("utf-8"), digest


def load_variant_a_bytes(instructions_dir: Path) -> tuple[bytes, str]:
    variant_path = instructions_dir / "variant-a.txt"
    try:
        data = variant_path.read_bytes()
    except OSError as exc:
        raise WorkflowError(f"Course Variant A instruction cannot be read: {exc}") from exc
    _require(bool(data.strip()), "Variant A instruction must not be empty.")
    return data, _sha256_bytes(data)


# ---------------------------------------------------------------------------
# Exposure ledger (append-only) and calibration
# ---------------------------------------------------------------------------


class ExposureLedger:
    """Append-only record of family selection and exposure events."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.events: list[dict] = []
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WorkflowError(f"Exposure ledger cannot be read: {exc}") from exc
            _require(isinstance(raw, dict) and isinstance(raw.get("events"), list),
                     "Exposure ledger must contain an events list.")
            self.events = list(raw["events"])

    def append(self, event: dict) -> None:
        required = {"event", "family_id", "actor", "recorded_at"}
        _require(required <= set(event), "Exposure event lacks required fields.")
        self.events.append(dict(event))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": SCHEMA_VERSION, "lab_id": LAB_ID, "events": self.events}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def family_exposed_before_freeze(self, family_id: str, freeze_at: str | None) -> bool:
        for event in self.events:
            if event.get("family_id") != family_id:
                continue
            if event.get("event") not in {"premature-exposure", "used-in-comparison"}:
                continue
            recorded = event.get("recorded_at")
            if freeze_at is None or not isinstance(recorded, str) or recorded < freeze_at:
                return True
        return False

    def family_ever_exposed(self, family_id: str) -> bool:
        """Any recorded premature exposure counts, before or after freeze."""
        return any(
            event.get("family_id") == family_id and event.get("event") == "premature-exposure"
            for event in self.events
        )

    def families_used_in_comparisons(self) -> set[str]:
        return {
            event["family_id"]
            for event in self.events
            if event.get("event") == "used-in-comparison"
        }

    def family_revealed_for_freeze(self, family_id: str, freeze_manifest: dict) -> bool:
        freeze_id = freeze_manifest.get("freeze_id")
        for event in self.events:
            if (
                event.get("event") == "revealed-after-freeze"
                and event.get("family_id") == family_id
                and event.get("freeze_id") == freeze_id
            ):
                return True
        return False


def start_calibration(*, report_dir: Path, packet_id: str, packets_dir: Path, student: str) -> Path:
    """Initialize student labels for a calibration packet without revealing reviewed labels."""
    _slug(packet_id, "packet_id")
    packet_path = packets_dir / packet_id / "packet.json"
    packet, _ = _read_json(packet_path, "Calibration packet")
    _require(packet.get("packet_id") == packet_id, "Packet identifier mismatch.")
    labels_dir = report_dir / "calibration" / packet_id
    exposure_marker = labels_dir / "labels-opened.json"
    _require(not exposure_marker.exists(),
             "Reviewed labels for this packet were already opened; use the replacement packet.")
    labels_path = labels_dir / "student-labels.yaml"
    if labels_path.exists():
        raise WorkflowError("Student labels for this packet already exist.")
    scaffold = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "labels": [
            {"output_id": output["output_id"], "category": "", "rationale": ""}
            for output in packet["authored_outputs"]
        ],
        "student": student,
        "recorded_at": _now(),
    }
    return _write_yaml_once(labels_path, scaffold)


def submit_calibration(*, report_dir: Path, packet_id: str, packets_dir: Path, student: str) -> dict:
    """Record the frozen student labels, open reviewed labels, and compare."""
    _slug(packet_id, "packet_id")
    packet, _ = _read_json(packets_dir / packet_id / "packet.json", "Calibration packet")
    labels_dir = report_dir / "calibration" / packet_id
    labels_path = labels_dir / "student-labels.yaml"
    try:
        labels_raw = yaml.safe_load(labels_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"Student labels cannot be read: {exc}") from exc
    _require(isinstance(labels_raw, dict), "Student labels must be a mapping.")
    entries = labels_raw.get("labels")
    _require(isinstance(entries, list), "Student labels must contain a labels list.")
    by_output = {item["output_id"]: item for item in packet["authored_outputs"]}
    labels_out: list[dict] = []
    for entry in entries:
        _require(isinstance(entry, dict), "Each student label must be a mapping.")
        output_id = entry.get("output_id")
        _require(output_id in by_output, f"Unknown calibration output {output_id}.")
        category = entry.get("category")
        _require(category in RUBRIC_CATEGORIES, f"Label for {output_id} must name a rubric category.")
        _require(isinstance(entry.get("rationale"), str) and entry["rationale"].strip(),
                 f"Label for {output_id} needs a rationale.")
        labels_out.append({"output_id": output_id, "category": category, "rationale": entry["rationale"].strip()})
    _require(
        sorted(item["output_id"] for item in labels_out) == sorted(by_output),
        "Every authored output must be labeled exactly once.",
    )
    reviewed = {item["output_id"]: item for item in packet["reviewed_labels"]}
    comparison = []
    for item in labels_out:
        expected = reviewed[item["output_id"]]
        comparison.append({
            "output_id": item["output_id"],
            "student_category": item["category"],
            "reviewed_category": expected["category"],
            "reviewed_rationale": expected["rationale"],
            "agrees": item["category"] == expected["category"],
        })
    result = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "student": student,
        "labels": labels_out,
        "comparison": comparison,
        "agreement": sum(item["agrees"] for item in comparison),
        "total": len(comparison),
        "reviewed_labels_opened_at": _now(),
    }
    _write_json_once(labels_dir / "calibration-result.json", result)
    _write_json_once(labels_dir / "labels-opened.json",
                     {"packet_id": packet_id, "opened_at": _now()})
    return result


# ---------------------------------------------------------------------------
# Development stage
# ---------------------------------------------------------------------------


def record_transfer_case(*, report_dir: Path, transfer_case: dict, perturbation: dict) -> Path:
    """Store the student transfer case and controlled perturbation as development evidence."""
    dev_dir = report_dir / "development"
    for payload, name in ((transfer_case, "transfer-case.yaml"), (perturbation, "transfer-perturbation.yaml")):
        _require(isinstance(payload, dict), f"{name} must be a mapping.")
        _require(isinstance(payload.get("case_id"), str) and payload["case_id"].strip(), f"{name} needs a case_id.")
        _require(isinstance(payload.get("task"), str) and payload["task"].strip(), f"{name} needs a task.")
        _require(isinstance(payload.get("supplied_source"), str) and payload["supplied_source"].strip(),
                 f"{name} needs supplied_source.")
        _require(isinstance(payload.get("provenance"), str) and payload["provenance"].strip(),
                 f"{name} needs provenance (a public non-sensitive source).")
    _require(
        isinstance(perturbation.get("perturbation_note"), str) and perturbation["perturbation_note"].strip(),
        "Perturbation must describe the single altered input feature.",
    )
    _require(
        isinstance(perturbation.get("expectation"), str) and perturbation["expectation"].strip(),
        "Perturbation must state an invariance or directional expectation.",
    )
    _write_yaml_once(dev_dir / "transfer-case.yaml", transfer_case)
    return _write_yaml_once(dev_dir / "transfer-perturbation.yaml", perturbation)


def record_variant_b(*, report_dir: Path, variant_b_text: str, change_declaration: dict) -> Path:
    """Store Variant B and its single-factor change declaration."""
    _require(isinstance(variant_b_text, str) and variant_b_text.strip(), "Variant B must not be empty.")
    variant_a_path = Path(__file__).resolve().parent.parent.parent / "instructions" / "lab03" / "variant-a.txt"
    variant_a_text = variant_a_path.read_text(encoding="utf-8")
    _require(variant_b_text != variant_a_text, "Variant B must differ from Variant A.")
    _require(isinstance(change_declaration, dict), "Change declaration must be a mapping.")
    _require(
        isinstance(change_declaration.get("changed_property"), str) and change_declaration["changed_property"].strip(),
        "Change declaration must name exactly one changed instruction property.",
    )
    _require(
        isinstance(change_declaration.get("mechanism"), str) and change_declaration["mechanism"].strip(),
        "Change declaration must state the intended mechanism.",
    )
    _require(
        isinstance(change_declaration.get("declared_factors"), list)
        and change_declaration["declared_factors"] == [change_declaration["changed_property"]],
        "The change declaration must declare exactly one intended factor.",
    )
    dev_dir = report_dir / "development"
    _write_bytes_once(dev_dir / "variant-b.txt", variant_b_text.encode("utf-8"))
    return _write_yaml_once(
        dev_dir / "change-declaration.yaml",
        {
            **change_declaration,
            "variant_a_sha256": _sha256_bytes(variant_a_text.encode("utf-8")),
            "variant_b_sha256": _sha256_bytes(variant_b_text.encode("utf-8")),
            "recorded_at": _now(),
        },
    )


# ---------------------------------------------------------------------------
# Development and held-out execution
# ---------------------------------------------------------------------------


def _schedule_order(positions: list[dict], seed: str) -> list[dict]:
    """Deterministic balanced order seeded by family id: within each case, variant
    alternation flips by attempt so A and B alternate first position evenly."""
    ordered = sorted(positions, key=lambda p: (p["case_index"], p["attempt"], p["variant"]))

    def sort_key(position: dict) -> tuple:
        variant_first = position["variant"] == "a"
        if (position["case_index"] + position["attempt"]) % 2 == 1:
            variant_first = not variant_first
        return (position["case_index"], position["attempt"], 0 if variant_first else 1)

    ordered.sort(key=sort_key)
    return ordered


def build_positions(*, comparison_dir: Path, family: dict, kind: str, cases: list[dict] | None = None) -> list[dict]:
    """Create the schedule file for a comparison (held-out) or development run.

    For held-out schedules the four family cases are used. For development
    schedules the caller passes four explicit inputs (development cases, the
    student transfer case, and the perturbation) via ``cases``.
    """
    _require(kind in {"held-out", "development"}, "Unknown schedule kind.")
    case_list = family["cases"] if cases is None else cases
    if kind == "held-out":
        _require(cases is None, "Held-out schedules take their cases from the selected family.")
        _require(len(case_list) == HELDOUT_CASES, "Held-out schedule requires exactly four cases.")
        positions = []
        for case_index, case in enumerate(case_list):
            for attempt in range(1, ATTEMPTS_PER_CASE + 1):
                for variant in VARIANTS:
                    positions.append({
                        "position_id": f"pos-{case['case_id']}-{variant}-{attempt}",
                        "case_id": case["case_id"],
                        "case_index": case_index,
                        "variant": variant,
                        "attempt": attempt,
                        "state": "unstarted",
                    })
        _require(len(positions) == SCHEDULED_POSITIONS, "Held-out schedule must contain sixteen positions.")
    else:
        _require(cases is not None and len(cases) == DEVELOPMENT_INPUTS,
                 "Development schedules require exactly four explicit inputs.")
        positions = []
        for case_index, case in enumerate(case_list):
            for variant in VARIANTS:
                positions.append({
                    "position_id": f"pos-{case['case_id']}-{variant}-1",
                    "case_id": case["case_id"],
                    "case_index": case_index,
                    "variant": variant,
                    "attempt": 1,
                    "state": "unstarted",
                })
        _require(len(positions) == DEVELOPMENT_POSITIONS, "Development schedule must contain eight positions.")
        a_ids = [p["position_id"] for p in positions if p["variant"] == "a"]
        b_ids = [p["position_id"] for p in positions if p["variant"] == "b"]
        schedule = {
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
            "family_id": f"dev-{kind}",
            "order": a_ids + b_ids,
            "positions": positions,
        }
        _write_json_once(comparison_dir / "schedule.json", schedule)
        return positions
    schedule = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "family_id": family["family_id"] if cases is None else f"dev-{kind}",
        "order": [p["position_id"] for p in _schedule_order(positions, family["family_id"])],
        "positions": positions,
    }
    _write_json_once(comparison_dir / "schedule.json", schedule)
    return positions


def _request_payload(case: dict, instruction_text: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "lab_id": LAB_ID,
        "case_id": case["case_id"],
        "task": case["task"],
        "supplied_source": case["supplied_source"],
        "instruction": instruction_text,
        "output_contract": {
            "type": "object",
            "fields": ["case_id", "proposed_text"],
            "case_id_value": case["case_id"],
        },
    }


def classify_failure(message: str) -> str:
    """Classify an execution failure as position-specific or route-wide."""
    lowered = str(message).lower()
    if "timeout" in lowered or "timed out" in lowered:
        return "position-specific"
    return "route-wide" if any(marker in lowered for marker in ROUTE_WIDE_MARKERS) else "position-specific"


def _next_unstarted_id(schedule: dict) -> str | None:
    by_id = {p["position_id"]: p for p in schedule["positions"]}
    order = schedule.get("order") or [p["position_id"] for p in schedule["positions"]]
    for position_id in order:
        if by_id[position_id]["state"] == "unstarted":
            return position_id
    return None


def _resume_deadline(manifest: dict) -> datetime | None:
    window = manifest.get("resume_window")
    frozen_at = manifest.get("frozen_at")
    if not isinstance(window, str) or not isinstance(frozen_at, str):
        return None
    try:
        start = datetime.fromisoformat(frozen_at)
    except ValueError:
        return None
    if window.endswith("h") and window[:-1].isdigit():
        return start + timedelta(hours=int(window[:-1]))
    return None


def _enforce_frozen_route(comparison_dir: Path, adapter: str, model_id: str) -> dict | None:
    manifest_path = comparison_dir / "freeze-manifest.json"
    if not manifest_path.exists():
        return None
    manifest, _ = _read_json(manifest_path, "Freeze manifest")
    route = manifest.get("route")
    if isinstance(route, dict):
        _require(adapter == route.get("adapter"), "Held-out run adapter does not match the frozen route.")
        _require(model_id == route.get("model_id"), "Held-out run model_id does not match the frozen route.")
    return manifest


def _enforce_instruction_digests(comparison_dir: Path, instructions: dict[str, str], manifest: dict) -> None:
    for variant in instructions:
        digest_key = f"variant_{variant}_sha256"
        expected = manifest.get(digest_key)
        if not expected:
            continue
        actual = _sha256_bytes(instructions[variant].encode("utf-8"))
        _require(actual == expected, f"Instruction digest drift for variant {variant}.")


def load_frozen_instructions(comparison_dir: Path) -> dict[str, str]:
    """Load freeze snapshots and refuse digest drift against the freeze manifest."""
    manifest, _ = _read_json(comparison_dir / "freeze-manifest.json", "Freeze manifest")
    instructions: dict[str, str] = {}
    for variant in VARIANTS:
        snap = comparison_dir / "snapshots" / f"variant-{variant}.txt"
        try:
            data = snap.read_bytes()
        except OSError as exc:
            raise WorkflowError(f"Frozen variant {variant} snapshot cannot be read: {exc}") from exc
        expected = manifest.get(f"variant_{variant}_sha256")
        _require(expected == _sha256_bytes(data), f"Frozen variant {variant} snapshot digest drift.")
        instructions[variant] = data.decode("utf-8")
    return instructions


def _apply_route_stop(*, comparison_dir: Path, schedule: dict, resume_probe: bool) -> None:
    stop_path = comparison_dir / "route-stop.json"
    if not stop_path.exists():
        _require(not resume_probe, "No route-wide stop requires a resume probe.")
        return
    stop, _ = _read_json(stop_path, "Route stop")
    if resume_probe:
        _require(not stop.get("resume_probe_used"), "The one permitted resume probe has already been used.")
        manifest_path = comparison_dir / "freeze-manifest.json"
        if manifest_path.exists():
            manifest, _ = _read_json(manifest_path, "Freeze manifest")
            deadline = _resume_deadline(manifest)
            if deadline is not None:
                _require(datetime.now(timezone.utc) <= deadline, "The frozen resume window has lapsed.")
        return
    if stop.get("resume_succeeded"):
        return
    if stop.get("resume_probe_used"):
        raise WorkflowError("Route-wide failure already consumed the one permitted resume probe.")
    raise WorkflowError("Route-wide failure stopped dispatch; use an explicit resume probe.")


def _record_route_stop(*, comparison_dir: Path, position_id: str, resume_probe: bool, failure_class: str) -> None:
    stop_path = comparison_dir / "route-stop.json"
    if failure_class != "route-wide" and not resume_probe:
        return
    if resume_probe:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "triggering_position_id": position_id,
            "failure_class": failure_class,
            "resume_probe_used": True,
            "resume_succeeded": failure_class != "route-wide",
            "recorded_at": _now(),
        }
        stop_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    if failure_class == "route-wide" and not stop_path.exists():
        _write_json_once(stop_path, {
            "schema_version": SCHEMA_VERSION,
            "triggering_position_id": position_id,
            "failure_class": failure_class,
            "resume_probe_used": False,
            "resume_succeeded": False,
            "recorded_at": _now(),
        })
        return
    if failure_class == "route-wide" and stop_path.exists():
        previous, _ = _read_json(stop_path, "Route stop")
        if previous.get("resume_probe_used") and previous.get("resume_succeeded"):
            stop_path.write_text(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "triggering_position_id": position_id,
                "failure_class": failure_class,
                "resume_probe_used": True,
                "resume_succeeded": False,
                "recorded_at": _now(),
            }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_position(
    *,
    comparison_dir: Path,
    schedule: dict,
    position_id: str,
    cases_by_id: dict[str, dict],
    instructions: dict[str, str],
    runner: Callable[[dict], str],
    adapter: str,
    model_id: str,
    recorded_by: str,
    resume_probe: bool = False,
) -> dict:
    """Execute one scheduled position through the injected provider-neutral runner.

    The runner receives the provider-neutral request payload and returns the raw
    assistant content string. Any exception is recorded as a completed failure.
    """
    positions = {p["position_id"]: p for p in schedule["positions"]}
    _require(position_id in positions, f"Unknown position {position_id}.")
    position = positions[position_id]
    _require(position["state"] == "unstarted", f"Position {position_id} is not unstarted and cannot be rerun.")
    next_id = _next_unstarted_id(schedule)
    _require(next_id == position_id, f"Run must use the next scheduled position {next_id}, not {position_id}.")
    if schedule.get("kind") == "development" and position["variant"] == "b":
        a_terminal = all(
            item["state"] in {"returned", "failed"}
            for item in schedule["positions"]
            if item["variant"] == "a"
        )
        _require(a_terminal, "Variant B cannot run until every Variant A development position is terminal.")
        _require(
            (comparison_dir / "variant-b.txt").exists(),
            "Variant B cannot run until Variant B exists.",
        )
        _require(
            any(item["state"] == "returned" for item in schedule["positions"] if item["variant"] == "a"),
            "Every Variant A development position failed; a semantic diagnosis is impossible. "
            "Preserve the failures and record honest-partial completion before protocol freeze.",
        )
    manifest = _enforce_frozen_route(comparison_dir, adapter, model_id)
    if manifest is not None:
        _enforce_instruction_digests(comparison_dir, instructions, manifest)
    _apply_route_stop(comparison_dir=comparison_dir, schedule=schedule, resume_probe=resume_probe)
    case = cases_by_id[position["case_id"]]
    request = _request_payload(case, instructions[position["variant"]])
    attempt_dir = comparison_dir / "attempts" / position_id
    _write_json_once(attempt_dir / "request.json", request)
    started_at = _now()
    observed_model: str | None = None
    try:
        result = runner(request)
        if isinstance(result, RunnerResult):
            content = result.content
            observed_model = result.observed_model
        else:
            content = result
    except Exception as exc:  # noqa: BLE001 — every failure mode is preserved evidence
        failure_class = classify_failure(str(exc))
        error = {
            "schema_version": SCHEMA_VERSION,
            "position_id": position_id,
            "failure_class": failure_class,
            "error": str(exc)[:2000],
        }
        _write_json_once(attempt_dir / "error.json", error)
        _write_json_once(attempt_dir / "run-metadata.json", {
            "position_id": position_id,
            "adapter": adapter,
            "model_id": model_id,
            "started_at": started_at,
            "finished_at": _now(),
            "recorded_by": recorded_by,
        })
        position["state"] = "failed"
        _rewrite_schedule(comparison_dir, schedule)
        _record_route_stop(
            comparison_dir=comparison_dir,
            position_id=position_id,
            resume_probe=resume_probe,
            failure_class=failure_class,
        )
        return {"position_id": position_id, "outcome": "failed", "failure_class": failure_class}
    raw_path = attempt_dir / "raw-response.txt"
    if raw_path.exists():
        raise WorkflowError("Position evidence is write-once and already exists.")
    attempt_dir.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(content, encoding="utf-8")
    run_metadata = {
        "position_id": position_id,
        "adapter": adapter,
        "model_id": model_id,
        "started_at": started_at,
        "finished_at": _now(),
        "recorded_by": recorded_by,
    }
    if observed_model is not None:
        run_metadata["observed_model"] = observed_model
    _write_json_once(attempt_dir / "run-metadata.json", run_metadata)
    position["state"] = "returned"
    _rewrite_schedule(comparison_dir, schedule)
    _record_route_stop(
        comparison_dir=comparison_dir,
        position_id=position_id,
        resume_probe=resume_probe,
        failure_class="position-specific",
    )
    return {"position_id": position_id, "outcome": "returned"}


def _rewrite_schedule(comparison_dir: Path, schedule: dict) -> None:
    path = comparison_dir / "schedule.json"
    path.write_text(json.dumps(schedule, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def structural_check(*, comparison_dir: Path, position_id: str) -> dict:
    """Validate one returned raw response against the two-field envelope contract."""
    attempt_dir = comparison_dir / "attempts" / position_id
    raw_path = attempt_dir / "raw-response.txt"
    try:
        raw = raw_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"Raw response cannot be read: {exc}") from exc
    errors: list[str] = []
    value: object = None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f"Response is not one valid JSON value: {exc}")
    if not errors:
        if not isinstance(value, dict):
            errors.append("Envelope must be a JSON object.")
        else:
            if set(value) != ENVELOPE_FIELDS:
                errors.append("Envelope must contain exactly case_id and proposed_text.")
            if value.get("case_id") != _position_case_id(comparison_dir, position_id):
                errors.append("Envelope case_id does not match the position's case.")
            if not isinstance(value.get("proposed_text"), str) or not value["proposed_text"].strip():
                errors.append("proposed_text must be a non-empty string.")
    result = {
        "schema_version": SCHEMA_VERSION,
        "position_id": position_id,
        "valid": not errors,
        "errors": errors,
        "checked_at": _now(),
    }
    _write_json_once(attempt_dir / "structural-result.json", result)
    return result


def record_interrupted_position(
    *, comparison_dir: Path, position_id: str, reason: str, student: str
) -> dict:
    """Close a dispatched position whose process ended before durable terminal evidence."""
    schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
    positions = {item["position_id"]: item for item in schedule["positions"]}
    _require(position_id in positions, f"Unknown position {position_id}.")
    position = positions[position_id]
    _require(position["state"] == "unstarted", "Only a non-terminal position can be recorded interrupted.")
    attempt_dir = comparison_dir / "attempts" / position_id
    _require((attempt_dir / "request.json").exists(), "Interrupted position has no durable dispatch request.")
    _require(
        not (attempt_dir / "raw-response.txt").exists()
        and not (attempt_dir / "error.json").exists(),
        "Interrupted position already has terminal response or error evidence.",
    )
    _require(isinstance(reason, str) and reason.strip(), "Interrupted position needs a reason.")
    error = {
        "schema_version": SCHEMA_VERSION,
        "position_id": position_id,
        "failure_class": "position-specific",
        "error": reason.strip(),
        "interrupted_after_dispatch": True,
    }
    _write_json_once(attempt_dir / "error.json", error)
    _write_json_once(attempt_dir / "run-metadata.json", {
        "position_id": position_id,
        "adapter": "unknown-after-interruption",
        "model_id": "unknown-after-interruption",
        "started_at": None,
        "finished_at": _now(),
        "recorded_by": student,
        "interrupted_after_dispatch": True,
    })
    position["state"] = "failed"
    _rewrite_schedule(comparison_dir, schedule)
    return error


def _position_case_id(comparison_dir: Path, position_id: str) -> str:
    schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
    for position in schedule["positions"]:
        if position["position_id"] == position_id:
            return position["case_id"]
    raise WorkflowError(f"Position {position_id} is not in the schedule.")


# ---------------------------------------------------------------------------
# Freeze, selection, curator
# ---------------------------------------------------------------------------


def freeze_protocol(
    *,
    report_dir: Path,
    protocol: dict,
    reserves_dir: Path,
    ledger: ExposureLedger,
    student: str,
) -> dict:
    """Bind immutable identities for the frozen comparison and write the manifest."""
    required = {
        "engineering_decision", "hypothesis", "semantic_acceptance", "blocking_failures",
        "operational_acceptance", "tradeoff_rule", "recommendation_precedence",
        "attempt_budget", "order_rule", "timing_boundary", "resume_window", "route",
    }
    _require(required <= set(protocol), "Protocol draft is missing required fields.")
    for field in ("operational_acceptance", "tradeoff_rule"):
        _require(
            isinstance(protocol[field], str) and protocol[field].strip(),
            f"Protocol {field} must be non-empty.",
        )
    resume_window = protocol["resume_window"]
    _require(
        isinstance(resume_window, str)
        and resume_window.endswith("h")
        and resume_window[:-1].isdigit()
        and int(resume_window[:-1]) > 0,
        "Protocol resume_window must use a positive integer-hour form such as 48h.",
    )
    precedence = protocol["recommendation_precedence"]
    _require(
        isinstance(precedence, dict)
        and {
            "decisive_rejection",
            "uncertainty",
            "positive_selection",
            "no_justified_change",
        } <= set(precedence)
        and all(isinstance(value, str) and value.strip() for value in precedence.values()),
        "Protocol recommendation_precedence must define four non-empty decision rules.",
    )
    _require(protocol.get("attempt_budget") == SCHEDULED_POSITIONS, "Attempt budget must be the fixed sixteen positions.")
    route = protocol["route"]
    _require(isinstance(route, dict), "Protocol route must be an object with adapter and model_id.")
    _require(
        route.get("adapter") in {"offline-fixture", "openrouter"},
        "Protocol route adapter is not supported.",
    )
    _require(isinstance(route.get("model_id"), str) and route["model_id"].strip(), "Protocol route needs model_id.")
    training_project = reserves_dir.parent.parent.parent
    instructions_dir = training_project / "instructions" / "lab03"
    variant_a_bytes, variant_a_sha = load_variant_a_bytes(instructions_dir)
    variant_b_path = report_dir / "development" / "variant-b.txt"
    try:
        variant_b_bytes = variant_b_path.read_bytes()
    except OSError as exc:
        raise WorkflowError(f"Variant B cannot be read: {exc}") from exc
    variant_b_text = variant_b_bytes.decode("utf-8")
    _require(variant_b_bytes != variant_a_bytes, "Variant A and Variant B are identical; freeze refused.")
    change_path = report_dir / "development" / "change-declaration.yaml"
    try:
        change = yaml.safe_load(change_path.read_text(encoding="utf-8"))
        change_bytes = change_path.read_bytes()
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"Change declaration cannot be read: {exc}") from exc
    _require(isinstance(change, dict) and change.get("declared_factors") == [change.get("changed_property")],
             "Change declaration must declare exactly one factor.")
    dev_schedule_path = report_dir / "development" / "schedule.json"
    dev_schedule, dev_schedule_bytes = _read_json(dev_schedule_path, "Development schedule")
    _require(dev_schedule.get("kind") == "development", "Development schedule kind must be development.")
    _require(
        len(dev_schedule.get("positions", [])) == DEVELOPMENT_POSITIONS,
        "Freeze requires eight development positions.",
    )
    for position in dev_schedule["positions"]:
        _require(
            position.get("state") in {"returned", "failed"},
            f"Development position {position.get('position_id')} is not terminal.",
        )
    order = dev_schedule.get("order") or []
    by_id = {p["position_id"]: p for p in dev_schedule["positions"]}
    ordered_variants = [by_id[pid]["variant"] for pid in order if pid in by_id]
    _require(
        ordered_variants == ["a"] * 4 + ["b"] * 4,
        "Development schedule must run four A positions then four B positions.",
    )
    eligible = eligible_families(reserves_dir, ledger, freeze_at=None)
    _require(
        bool(eligible) or protocol.get("curator_recovery") is True,
        "No eligible reserve family remains; set curator_recovery: true for post-freeze recovery.",
    )
    freeze_id = f"cmp-{_sha256_bytes((variant_a_sha + _sha256_bytes(variant_b_bytes) + _now()).encode('utf-8'))[:12]}"
    comparison_dir = report_dir / "comparisons" / freeze_id
    snapshot_dir = comparison_dir / "snapshots"
    _write_bytes_once(snapshot_dir / "variant-a.txt", variant_a_bytes)
    _write_bytes_once(snapshot_dir / "variant-b.txt", variant_b_bytes)
    if ledger.path.exists():
        ledger_digest = _file_sha256(ledger.path, "Exposure ledger")
    else:
        empty_ledger = json.dumps(
            {"schema_version": SCHEMA_VERSION, "lab_id": LAB_ID, "events": []},
            indent=2,
            ensure_ascii=False,
        ) + "\n"
        ledger_digest = _sha256_bytes(empty_ledger.encode("utf-8"))
    bindings = {
        "output_schema_sha256": _file_sha256(
            training_project / "schemas" / "lab03-envelope.schema.json", "Output schema"
        ),
        "case_family_contract_sha256": _file_sha256(
            training_project / "cases" / "lab03" / "case-family-contract.yaml", "Case-family contract"
        ),
        "validator_module_sha256": _file_sha256(Path(__file__), "Validator module"),
        "validator_schema_version": SCHEMA_VERSION,
        "development_schedule_sha256": _sha256_bytes(dev_schedule_bytes),
        "change_declaration_sha256": _sha256_bytes(change_bytes),
        "exposure_ledger_sha256": ledger_digest,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "freeze_id": freeze_id,
        "comparison_dir": str(comparison_dir),
        "protocol": dict(protocol),
        "variant_a_sha256": variant_a_sha,
        "variant_b_sha256": _sha256_bytes(variant_b_bytes),
        "change_declaration": {
            "changed_property": change["changed_property"],
            "mechanism": change.get("mechanism"),
            "declared_factors": change["declared_factors"],
        },
        "route": {"adapter": route["adapter"], "model_id": route["model_id"]},
        "resume_window": protocol["resume_window"],
        "eligible_reserve_count_at_freeze": len(eligible),
        "bindings": bindings,
        "frozen_at": _now(),
        "frozen_by": student,
    }
    _write_json_once(comparison_dir / "freeze-manifest.json", manifest)
    return manifest


def eligible_families(reserves_dir: Path, ledger: ExposureLedger, freeze_at: str | None) -> list[str]:
    """Reserve families that are structurally valid, never exposed, and unused.

    Any recorded ``premature-exposure`` event removes eligibility regardless of
    when it was recorded relative to the freeze, so a family seen after freeze
    but before selection is equally ineligible when ``select-family`` runs.
    """
    eligible: list[str] = []
    families: list[dict] = []
    for family_path in sorted(reserves_dir.glob("*/family.json")):
        family = load_family(family_path)
        families.append(family)
    check_near_duplicates(families)
    used = ledger.families_used_in_comparisons()
    for family in families:
        family_id = family["family_id"]
        if family_id in used:
            continue
        if ledger.family_ever_exposed(family_id):
            continue
        eligible.append(family_id)
    return eligible


def select_family(
    *,
    reserves_dir: Path,
    ledger: ExposureLedger,
    freeze_manifest: dict,
    student: str,
) -> dict:
    """Select one eligible family after freeze; record selection before reveal."""
    eligible = eligible_families(reserves_dir, ledger, freeze_at=freeze_manifest["frozen_at"])
    _require(bool(eligible), "All prepared reserve families are ineligible.")
    family_id = eligible[0]
    ledger.append({
        "event": "revealed-after-freeze",
        "family_id": family_id,
        "freeze_id": freeze_manifest["freeze_id"],
        "actor": student,
        "recorded_at": _now(),
    })
    family_path = reserves_dir / family_id / "family.json"
    family = load_family(family_path)
    comparison_dir = Path(freeze_manifest["comparison_dir"])
    public_family = {key: value for key, value in family.items() if key != "expected_behaviors"}
    _write_json_once(comparison_dir / "revealed-family.json", {
        "family": public_family,
        "family_sha256": _sha256_bytes(family_path.read_bytes()),
        "eligible_at_selection": eligible,
        "selected_at": _now(),
        "selected_by": student,
    })
    _write_json_once(comparison_dir / "_internal" / "held-out-references.json", {
        "family_id": family["family_id"],
        "expected_behaviors": family["expected_behaviors"],
    })
    return family


def record_premature_exposure(*, ledger: ExposureLedger, family_id: str, student: str) -> None:
    """Record an honest premature exposure; the family loses current held-out eligibility."""
    ledger.append({
        "event": "premature-exposure",
        "family_id": _slug(family_id, "family_id"),
        "actor": student,
        "recorded_at": _now(),
    })


def mark_family_used(*, ledger: ExposureLedger, family_id: str, freeze_id: str, student: str) -> None:
    ledger.append({
        "event": "used-in-comparison",
        "family_id": family_id,
        "freeze_id": freeze_id,
        "actor": student,
        "recorded_at": _now(),
    })


def build_curator_input(*, reserves_dir: Path, contract_path: Path) -> dict:
    """Assemble the isolation-bounded curator input: contract, situations, prior manifests."""
    families = [load_family(p) for p in sorted(reserves_dir.glob("*/family.json"))]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_family_contract": yaml.safe_load(contract_path.read_text(encoding="utf-8")),
        "required_evidence_situations": list(EVIDENCE_SITUATIONS),
        "permitted_source_rule": (
            "Every case supplied_source must be a short, bounded, public or non-sensitive passage "
            "with a verifiable provenance pointer (a public URL or a standard citation) recorded in "
            "its source_pointers. The curator must not reuse the student's personal transfer-case "
            "source and must not paraphrase any prior family case below. The independent reviewer "
            "verifies each provenance pointer against the public source rather than trusting the "
            "curator's own supplied_source wording."
        ),
        "prior_families": [
            {
                "family_id": f["family_id"],
                "cases": [
                    {"case_id": c["case_id"], "task": c["task"], "supplied_source": c["supplied_source"],
                     "mutation_note": c.get("mutation_note", ""), "evidence_situation": c["evidence_situation"]}
                    for c in f["cases"]
                ],
                "expected_behaviors": f["expected_behaviors"],
            }
            for f in families
        ],
    }


CURATOR_SYSTEM_PROMPT = (
    "You are an isolated case curator. You receive exactly one input file: the case-family "
    "contract, the four required evidence situations, and prior family manifests used for "
    "near-duplicate avoidance. You see neither instruction variant, no generated responses, "
    "no assessments, no aggregates, and no preferred conclusion. Return exactly one JSON "
    "family conforming to the supplied case-family contract."
)

CURATOR_TASK_TEMPLATE = """Produce one new held-out case family as a single JSON object.

Follow the case-family contract in the input exactly:
- one family_id, four cases, and four expected_behaviors entries;
- the four cases must cover exactly these evidence situations: {situations};
- every case has a distinct case_id, a task answerable only from its supplied_source, a
  supplied_source, a mutation_note, and a source pointer;
- every supplied_source must be a short, bounded, public or non-sensitive passage, and its
  source_pointers must record a verifiable provenance (a public URL or a standard citation)
  that an independent reviewer can check — do not fabricate or misquote a source;
- each expected_behaviors entry states the expected_category and expected_behavior for
  its case_id and must be evaluable from the supplied source alone;
- do not duplicate or trivially rephrase any prior family case in the input, and do not
  reuse the student's personal transfer-case source.

Return only the JSON object, with no commentary."""


def curator_launch(*, comparison_dir: Path, report_dir: Path, destination: Path,
                   attempt: int, runner: Callable[[str], str],
                   by: str, api_key: str | None = None) -> dict:
    """Launch the isolated case curator through a supplied isolated runner.

    The runner is provider-neutral: it receives the complete curator prompt
    (system instruction plus the exact contents of ``curator/input.json``) and
    returns the raw assistant content string. Only ``curator/input.json`` is
    supplied to the runner; no variant text, response, assessment, or
    aggregate is passed. The result is written verbatim to ``destination``
    (outside the comparison directory) without being opened or validated here,
    because the candidate contains evaluator-only expectations.

    ``api_key`` is never recorded; a live runner reads its credential from the
    process environment itself.
    """
    _require(attempt in {1, 2}, "Curator attempt must be 1 or 2.")
    input_path = comparison_dir / "curator" / "input.json"
    _require(input_path.exists(), "Curator input is missing; run curator-prepare first.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _require(
        not destination.exists(),
        f"The candidate destination already exists: {destination}. Do not overwrite a candidate.",
    )
    prompt = (
        CURATOR_SYSTEM_PROMPT
        + "\n\n"
        + CURATOR_TASK_TEMPLATE.format(situations=", ".join(EVIDENCE_SITUATIONS))
        + "\n\n"
        + input_path.read_text(encoding="utf-8")
    )
    started_at = _now()
    session_id = f"cur-{_sha256_bytes((comparison_dir.name + str(attempt) + started_at).encode('utf-8'))[:10]}"
    content = runner(prompt)
    _require(isinstance(content, str), "The curator runner must return a string.")
    _require(bool(content.strip()), "The curator session returned no content.")
    destination.write_text(content, encoding="utf-8")
    session_file = comparison_dir / "curator" / "sessions" / f"attempt-{attempt}-session.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    _write_json_once(session_file, {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "attempt": attempt,
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "input_sha256": _file_sha256(input_path, "Curator input"),
        "destination": str(destination),
        "destination_sha256": _sha256_bytes(content.encode("utf-8")),
        "launched_by": by,
        "launched_at": started_at,
        "finished_at": _now(),
    })
    return {
        "attempt": attempt,
        "session_id": session_id,
        "candidate_path": str(destination),
        "session_record": str(session_file),
    }


def ingest_curator_candidate(
    *,
    comparison_dir: Path,
    candidate_family: dict,
    curator_input: dict,
    curator_session: str,
    attempt: int = 1,
    deterministic_runner: Callable[[dict], list[str]] | None = None,
) -> dict:
    """Validate one curator proposal: provenance, contract checks, near-duplicates.

    deterministic_runner is the pluggable no-purchase curator route (Stage 2 may
    provide an offline authored-family generator); it is not required when the
    candidate was produced by another isolated route.
    """
    _require(attempt in {1, 2}, "Curator attempt must be 1 or 2.")
    if attempt == 2:
        _require(
            (comparison_dir / "curator" / "attempts" / "attempt-1").exists(),
            "Curator attempt 1 must be preserved before attempt 2.",
        )
    _require(isinstance(candidate_family, dict), "Curator candidate must be a mapping.")
    candidate_family = {
        **candidate_family,
        "origin": "curator-generated",
        "provenance": {
            **candidate_family.get("provenance", {}),
            "curator_session": curator_session,
            "inputs_sha256": _sha256_bytes(json.dumps(curator_input, sort_keys=True).encode("utf-8")),
        },
    }
    attempt_dir = comparison_dir / "curator" / "attempts" / f"attempt-{attempt}"
    family_path = attempt_dir / "candidate.json"
    _write_bytes_once(
        family_path,
        (json.dumps(candidate_family, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    )
    try:
        family = load_family(family_path)  # deterministic contract checks
    except WorkflowError as exc:
        _write_yaml_once(attempt_dir / "result.yaml", {
            "schema_version": SCHEMA_VERSION,
            "attempt": attempt,
            "outcome": "invalid-candidate",
            "curator_session": curator_session,
            "detail": str(exc),
            "recorded_at": _now(),
        })
        raise
    prior_families: list[dict] = []
    for prior in curator_input["prior_families"]:
        prior_families.append({
            "family_id": prior["family_id"],
            "cases": [
                {
                    **case,
                    "family_id": prior["family_id"],
                    "schema_version": SCHEMA_VERSION,
                    "constructed": True,
                    "mutation_note": case.get("mutation_note", "prior family case"),
                    "source_pointers": [{"theory_section": "prior", "pointer": prior["family_id"]}],
                }
                for case in prior["cases"]
            ],
            "expected_behaviors": [
                {
                    "case_id": behavior["case_id"],
                    "expected_category": behavior["expected_category"],
                    "expected_behavior": behavior["expected_behavior"],
                }
                for behavior in prior.get("expected_behaviors", [])
            ],
        })
    check_near_duplicates([family, *prior_families])
    check = {
        "schema_version": SCHEMA_VERSION,
        "candidate_family_id": family["family_id"],
        "checks": ["schema-conformance", "provenance", "near-duplicate"],
        "passed": True,
        "checked_at": _now(),
    }
    _write_json_once(attempt_dir / "deterministic-check.json", check)
    _write_yaml_once(attempt_dir / "result.yaml", {
        "schema_version": SCHEMA_VERSION,
        "attempt": attempt,
        "outcome": "candidate-returned",
        "curator_session": curator_session,
        "recorded_at": _now(),
    })
    return family


def record_curator_attempt_failure(
    *, comparison_dir: Path, attempt: int, outcome: str, detail: str, student: str
) -> Path:
    """Preserve a consumed curator attempt that produced no ingestible candidate."""
    _require(attempt in {1, 2}, "Curator attempt must be 1 or 2.")
    _require(
        outcome in {"launch-failed", "route-unavailable", "quota-unavailable", "empty-result",
                     "invalid-candidate", "reviewer-unavailable"},
        "Unknown curator failure outcome.",
    )
    _require(isinstance(detail, str) and detail.strip(), "Curator attempt failure needs detail.")
    if attempt == 2:
        _require(
            (comparison_dir / "curator" / "attempts" / "attempt-1").exists(),
            "Curator attempt 1 must be preserved before attempt 2.",
        )
    return _write_yaml_once(
        comparison_dir / "curator" / "attempts" / f"attempt-{attempt}" / "result.yaml",
        {
            "schema_version": SCHEMA_VERSION,
            "attempt": attempt,
            "outcome": outcome,
            "detail": detail.strip(),
            "recorded_by": student,
            "recorded_at": _now(),
        },
    )


def record_human_case_review(
    *,
    comparison_dir: Path,
    family: dict,
    decision: str,
    reasons: str,
    student: str,
    attempt: int = 1,
) -> Path:
    """Record the student's post-freeze human semantic review of a curator family."""
    _require(decision in {"approved", "rejected"}, "Case review decision must be approved or rejected.")
    _require(isinstance(reasons, str) and reasons.strip(), "Case review needs reasons.")
    _require(attempt in {1, 2}, "Curator attempt must be 1 or 2.")
    return _write_yaml_once(comparison_dir / "curator" / "attempts" / f"attempt-{attempt}" / "human-case-review.yaml", {
        "schema_version": SCHEMA_VERSION,
        "family_id": family["family_id"],
        "decision": decision,
        "reasons": reasons.strip(),
        "reviewed_by": student,
        "reviewed_at": _now(),
    })


# ---------------------------------------------------------------------------
# Blinded scoring and aggregation
# ---------------------------------------------------------------------------


def build_blinded_index(*, comparison_dir: Path, family: dict) -> dict:
    """Assign blind identifiers over returned structurally valid positions.

    Available only after every scheduled position reached returned/failed or was
    explicitly closed unstarted; the index hides variant identity and order.
    """
    schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
    terminal = all(p["state"] in {"returned", "failed", "closed-unstarted"} for p in schedule["positions"])
    _require(terminal, "Blinding requires every position to be terminal or explicitly closed.")
    cases_by_id = {c["case_id"]: c for c in family["cases"]}
    behaviors_list = family.get("expected_behaviors")
    if not behaviors_list:
        refs, _ = _read_json(
            comparison_dir / "_internal" / "held-out-references.json", "Held-out references"
        )
        behaviors_list = refs["expected_behaviors"]
    behaviors = {b["case_id"]: b for b in behaviors_list}
    entries = []
    public_items = []
    counter = 0
    for position in schedule["positions"]:
        if position["state"] != "returned":
            continue
        attempt_dir = comparison_dir / "attempts" / position["position_id"]
        structural_path = attempt_dir / "structural-result.json"
        if not structural_path.exists():
            structural_check(comparison_dir=comparison_dir, position_id=position["position_id"])
        structural, _ = _read_json(structural_path, "Structural result")
        if not structural["valid"]:
            continue
        raw = (attempt_dir / "raw-response.txt").read_text(encoding="utf-8")
        envelope = json.loads(raw)
        proposed_text = envelope["proposed_text"]
        counter += 1
        blind_id = f"blind-{counter:03d}"
        entries.append({
            "blind_id": blind_id,
            "position_id": position["position_id"],
            "case_task": cases_by_id[position["case_id"]]["task"],
            "supplied_source": cases_by_id[position["case_id"]]["supplied_source"],
            "expected_behavior": behaviors[position["case_id"]]["expected_behavior"],
            "expected_category": behaviors[position["case_id"]]["expected_category"],
        })
        public_items.append({
            "blind_id": blind_id,
            "case_task": cases_by_id[position["case_id"]]["task"],
            "supplied_source": cases_by_id[position["case_id"]]["supplied_source"],
            "expected_behavior": behaviors[position["case_id"]]["expected_behavior"],
            "proposed_text": proposed_text,
        })
    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "entries": entries,
        "built_at": _now(),
    }
    _write_json_once(_join_map_path(comparison_dir), index_payload)
    public_view = {
        "schema_version": SCHEMA_VERSION,
        "note": "Scoring view: variant identity, order, and split labels are joined only after judgments are frozen.",
        "items": public_items,
    }
    _write_json_once(comparison_dir / "scoring" / "scoring-view.json", public_view)
    return index_payload


def record_assessment(*, comparison_dir: Path, blind_id: str, assessment: dict) -> Path:
    """Store one human rubric judgment over a blind identifier."""
    index, _ = _read_json(_join_map_path(comparison_dir), "Join map")
    known = {e["blind_id"] for e in index["entries"]}
    _require(blind_id in known, f"Unknown blind identifier {blind_id}.")
    _require(isinstance(assessment, dict), "Assessment must be a mapping.")
    category = assessment.get("category")
    _require(category in RUBRIC_CATEGORIES, "Assessment category must be a rubric category.")
    _require(isinstance(assessment.get("source_pointer"), str) and assessment["source_pointer"].strip(),
             "Assessment needs a source pointer.")
    _require(isinstance(assessment.get("rationale"), str) and assessment["rationale"].strip(),
             "Assessment needs a one-or-two-sentence rationale.")
    shared = assessment.get("shares_rationale_with")
    if shared is not None:
        _require(isinstance(shared, str) and shared in known and shared != blind_id,
                 "A shared rationale must reference a different known blind identifier.")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "blind_id": blind_id,
        **assessment,
        "recorded_at": _now(),
    }
    return _write_yaml_once(comparison_dir / "scoring" / "assessments" / f"{blind_id}.yaml", payload)


def aggregate(*, comparison_dir: Path) -> dict:
    """Join variant identities after judgments and compute nested counts and slices."""
    schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
    index, _ = _read_json(_join_map_path(comparison_dir), "Join map")
    by_position = {e["position_id"]: e for e in index["entries"]}
    assessments: dict[str, dict] = {}
    disputes: list[dict] = []
    disputes_path = comparison_dir / "scoring" / "disputes.yaml"
    if disputes_path.exists():
        try:
            disputes_raw = yaml.safe_load(disputes_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise WorkflowError(f"Disputes record cannot be read: {exc}") from exc
        disputes = list(disputes_raw.get("items", [])) if isinstance(disputes_raw, dict) else []
    disputed = {d["blind_id"] for d in disputes if isinstance(d, dict) and d.get("blind_id")}
    corrections: dict[str, dict] = {}
    corrections_root = comparison_dir / "scoring" / "corrections"
    if corrections_root.exists():
        for correction_path in sorted(corrections_root.glob("blind-*.yaml")):
            try:
                correction = yaml.safe_load(correction_path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise WorkflowError(f"Correction cannot be read: {exc}") from exc
            if isinstance(correction, dict) and correction.get("blind_id"):
                corrections[correction["blind_id"]] = correction

    def settled_category(entry_blind_id: str, assessment: dict) -> str:
        """The recorded category, or its append-only correction when one exists."""
        correction = corrections.get(entry_blind_id)
        if correction is not None:
            return correction["corrected_category"]
        return assessment["category"]

    for entry in index["entries"]:
        path = comparison_dir / "scoring" / "assessments" / f"{entry['blind_id']}.yaml"
        if path.exists():
            try:
                assessments[entry["blind_id"]] = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise WorkflowError(f"Assessment cannot be read: {exc}") from exc
    family, _ = _read_json(comparison_dir / "revealed-family.json", "Revealed family")
    cases_by_id = {c["case_id"]: c for c in family["family"]["cases"]}
    variants_stat: dict[str, dict] = {
        v: {
            "scheduled": 0, "started": 0, "returned": 0, "structurally_valid": 0,
            "assessable": 0, "rubric_acceptable": 0, "critical_unsupported": 0,
            "failed": 0, "unstarted": 0,
        }
        for v in VARIANTS
    }
    slices: dict[str, dict] = {}
    repeated_diffs: list[dict] = []
    by_case: dict[str, dict[str, list[str]]] = {}
    for position in schedule["positions"]:
        variant = position["variant"]
        stat = variants_stat[variant]
        stat["scheduled"] += 1
        state = position["state"]
        if state in {"unstarted", "closed-unstarted"}:
            stat["unstarted"] += 1
            continue
        stat["started"] += 1
        if state == "failed":
            stat["failed"] += 1
            continue
        stat["returned"] += 1
        entry = by_position.get(position["position_id"])
        if entry is None:
            continue
        stat["structurally_valid"] += 1
        case = cases_by_id[position["case_id"]]
        slice_key = case["evidence_situation"]
        slices.setdefault(slice_key, {"a": _empty_slice(), "b": _empty_slice()})
        slice_stat = slices[slice_key][variant]
        slice_stat["returned"] += 1
        slice_stat["structurally_valid"] += 1
        assessment = assessments.get(entry["blind_id"])
        if assessment is None or entry["blind_id"] in disputed:
            if assessment is not None and entry["blind_id"] in disputed:
                slice_stat["disputed"] += 1
            continue
        category = settled_category(entry["blind_id"], assessment)
        if category == "X":
            continue
        stat["assessable"] += 1
        slice_stat["assessable"] += 1
        acceptable = category in {"S", "Q"}
        if acceptable:
            stat["rubric_acceptable"] += 1
            slice_stat["rubric_acceptable"] += 1
        if category == "U":
            stat["critical_unsupported"] += 1
            slice_stat["critical_unsupported"] += 1
        by_case.setdefault(position["case_id"], {"a": [], "b": []})[variant].append(
            f"{entry['blind_id']}:{category}"
        )
    for case_id, variant_map in by_case.items():
        if len(variant_map["a"]) == ATTEMPTS_PER_CASE and len(variant_map["b"]) == ATTEMPTS_PER_CASE:
            repeated_diffs.append({
                "case_id": case_id,
                "a": variant_map["a"],
                "b": variant_map["b"],
                "differs_within_a": len(set(variant_map["a"])) > 1,
                "differs_within_b": len(set(variant_map["b"])) > 1,
            })
    observed_latency: dict[str, list[dict]] = {"a": [], "b": []}
    observed_models: dict[str, set[str]] = {"a": set(), "b": set()}
    for position in schedule["positions"]:
        if position["state"] in {"unstarted", "closed-unstarted"}:
            continue
        meta_path = comparison_dir / "attempts" / position["position_id"] / "run-metadata.json"
        if not meta_path.exists():
            continue
        meta, _ = _read_json(meta_path, "Run metadata")
        observed = meta.get("observed_model")
        if isinstance(observed, str) and observed.strip():
            observed_models[position["variant"]].add(observed)
        started = meta.get("started_at")
        finished = meta.get("finished_at")
        seconds = None
        if isinstance(started, str) and isinstance(finished, str):
            try:
                seconds = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
            except ValueError:
                seconds = None
        observed_latency[position["variant"]].append({
            "position_id": position["position_id"],
            "started_at": started,
            "finished_at": finished,
            "seconds": seconds,
        })
    aggregate_payload = {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": comparison_dir.name,
        "nested_counts": variants_stat,
        "slices": slices,
        "repeated_attempt_differences": repeated_diffs,
        "disputed_blind_ids": sorted(disputed),
        "corrected_blind_ids": sorted(corrections),
        "observed_latency": observed_latency,
        "observed_models": {variant: sorted(models) for variant, models in observed_models.items()},
        "resolved_model_comparability": (
            "unknown" if not observed_models["a"] or not observed_models["b"]
            else ("comparable" if observed_models["a"] == observed_models["b"] else "not-comparable")
        ),
        "unknown_values": {
            "monetary_cost": "unknown",
            "quota_usage": "unknown",
            "token_usage": "unknown",
        },
        "generated_at": _now(),
    }
    _write_json_once(comparison_dir / "scoring" / "aggregate.json", aggregate_payload)
    return aggregate_payload


def _empty_slice() -> dict:
    return {"returned": 0, "structurally_valid": 0, "assessable": 0, "rubric_acceptable": 0,
            "critical_unsupported": 0, "disputed": 0}


def close_unstarted_positions(*, comparison_dir: Path, reason: str, student: str) -> dict:
    """Explicitly close every remaining unstarted position (resume window expired or honest stop)."""
    schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
    closed = []
    for position in schedule["positions"]:
        if position["state"] == "unstarted":
            position["state"] = "closed-unstarted"
            position["closed_reason"] = reason
            position["closed_by"] = student
            closed.append(position["position_id"])
    if closed:
        _rewrite_schedule(comparison_dir, schedule)
    closure = {
        "schema_version": SCHEMA_VERSION,
        "closed_positions": closed,
        "reason": reason,
        "closed_by": student,
        "closed_at": _now(),
    }
    _write_json_once(comparison_dir / "position-closure.json", closure)
    return closure


def record_dispute(*, comparison_dir: Path, blind_id: str, reason: str, student: str) -> Path:
    """Record an unresolved human-reference dispute against a blinded assessment."""
    index, _ = _read_json(_join_map_path(comparison_dir), "Join map")
    known = {entry["blind_id"] for entry in index["entries"]}
    _require(blind_id in known, f"Unknown blind identifier {blind_id}.")
    _require(isinstance(reason, str) and reason.strip(), "Dispute needs a reason.")
    path = comparison_dir / "scoring" / "disputes.yaml"
    items: list[dict] = []
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise WorkflowError(f"Disputes record cannot be read: {exc}") from exc
        items = list(raw.get("items", [])) if isinstance(raw, dict) else []
    items.append({
        "blind_id": blind_id,
        "reason": reason.strip(),
        "recorded_by": student,
        "recorded_at": _now(),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml({"schema_version": SCHEMA_VERSION, "items": items}), encoding="utf-8")
    return path


def record_correction(*, comparison_dir: Path, blind_id: str, corrected_category: str,
                      resolution_basis: str, student: str) -> Path:
    """Append-only correction of a mistaken evaluator assessment.

    Used only when the supplied source itself resolves that the recorded
    assessment category is wrong and neither the rubric nor the reference is
    defective (those cases take ``record-dispute`` or ``record-amendment``).
    The original immutable assessment is preserved; aggregation settles on the
    corrected category, and the correction does not force seek-more-evidence.
    """
    index, _ = _read_json(_join_map_path(comparison_dir), "Join map")
    known = {entry["blind_id"] for entry in index["entries"]}
    _require(blind_id in known, f"Unknown blind identifier {blind_id}.")
    _require(corrected_category in RUBRIC_CATEGORIES,
             "Corrected category must be a rubric category.")
    _require(isinstance(resolution_basis, str) and resolution_basis.strip(),
             "Correction needs the source passage that resolves the mistake.")
    _require(isinstance(student, str) and student.strip(), "Correction needs the evaluator identity.")
    assessment_path = comparison_dir / "scoring" / "assessments" / f"{blind_id}.yaml"
    _require(assessment_path.exists(), f"No recorded assessment exists for {blind_id}.")
    assessment = yaml.safe_load(assessment_path.read_text(encoding="utf-8"))
    _require(isinstance(assessment, dict), f"The recorded assessment for {blind_id} is invalid.")
    _require(
        assessment.get("category") != corrected_category,
        "The corrected category must differ from the recorded assessment category.",
    )
    return _write_yaml_once(
        comparison_dir / "scoring" / "corrections" / f"{blind_id}.yaml",
        {
            "schema_version": SCHEMA_VERSION,
            "blind_id": blind_id,
            "original_category": assessment["category"],
            "corrected_category": corrected_category,
            "resolution_basis": resolution_basis.strip(),
            "corrected_by": student.strip(),
            "recorded_at": _now(),
        },
    )


def record_selected_comparison(*, report_dir: Path, comparison_id: str, student: str) -> Path:
    """Record which comparison is submitted for evaluation after all runs are terminal."""
    _slug(comparison_id, "comparison_id")
    comparison_dir = report_dir / "comparisons" / comparison_id
    _require((comparison_dir / "freeze-manifest.json").exists(),
             "The selected comparison must have a freeze manifest.")
    schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
    terminal = all(p["state"] in {"returned", "failed", "closed-unstarted"} for p in schedule["positions"])
    _require(terminal, "All positions must be terminal before selecting a comparison.")
    return _write_yaml_once(report_dir / "selected-comparison.yaml", {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": comparison_id,
        "selected_by": student,
        "selected_at": _now(),
    })


# ---------------------------------------------------------------------------
# Recommendation, regression, verification
# ---------------------------------------------------------------------------


def record_evaluator_amendment(*, comparison_dir: Path, amendment_id: str, defect: str,
                               confirmed_by: str) -> Path:
    """Append-only record of a confirmed rubric or reference defect, forcing seek-more-evidence."""
    _slug(amendment_id, "amendment_id")
    _require(isinstance(defect, str) and defect.strip(), "Evaluator amendment needs a defect description.")
    _require(isinstance(confirmed_by, str) and confirmed_by.strip(), "Evaluator amendment needs a confirmer.")
    return _write_yaml_once(
        comparison_dir / "scoring" / "evaluator-amendments" / f"{amendment_id}.yaml",
        {
            "schema_version": SCHEMA_VERSION,
            "amendment_id": amendment_id,
            "defect": defect.strip(),
            "confirmed_by": confirmed_by.strip(),
            "recorded_at": _now(),
        },
    )


def record_recommendation(*, comparison_dir: Path, outcome: str, rationale: str, limitations: list[str],
                          student: str) -> Path:
    """Record the bounded recommendation traceable to the frozen protocol."""
    _require(outcome in OUTCOMES, "Outcome must be one of the four permitted recommendations.")
    _require(isinstance(rationale, str) and rationale.strip(), "Recommendation needs a rationale.")
    _require(isinstance(limitations, list) and limitations, "Recommendation must state limitations.")
    join, _ = _read_json(_join_map_path(comparison_dir), "Join map")
    for entry in join["entries"]:
        assessment_path = comparison_dir / "scoring" / "assessments" / f"{entry['blind_id']}.yaml"
        _require(assessment_path.exists(), f"Missing assessment coverage for {entry['blind_id']}.")
    aggregate, _ = _read_json(comparison_dir / "scoring" / "aggregate.json", "Aggregate")
    manifest, _ = _read_json(comparison_dir / "freeze-manifest.json", "Freeze manifest")
    _require(
        comparison_dir.name == manifest.get("freeze_id"),
        "Recommendation protocol identity does not match this comparison.",
    )
    blocking = manifest.get("protocol", {}).get("blocking_failures")
    _require(
        (isinstance(blocking, str) and blocking.strip()) or (isinstance(blocking, list) and blocking),
        "Frozen protocol is missing blocking_failures.",
    )
    amendment_root = comparison_dir / "scoring" / "evaluator-amendments"
    if amendment_root.exists() and any(amendment_root.iterdir()):
        _require(outcome == "seek-more-evidence", "An evaluator amendment requires seek-more-evidence.")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": comparison_dir.name,
        "outcome": outcome,
        "rationale": rationale.strip(),
        "limitations": limitations,
        "blocking_failures": blocking,
        "recommendation_precedence": manifest["protocol"]["recommendation_precedence"],
        "nested_counts": aggregate["nested_counts"],
        "protocol_freeze_id": manifest["freeze_id"],
        "recorded_by": student,
        "recorded_at": _now(),
    }
    return _write_yaml_once(comparison_dir / "recommendation.yaml", payload)


def record_regression(*, report_dir: Path, regression: dict) -> Path:
    """Create the reviewed regression record from an observed failure or the authored fixture."""
    _require(isinstance(regression, dict), "Regression record must be a mapping.")
    source_kind = regression.get("source_kind")
    _require(source_kind in {"observed-failure", "authored-fixture"}, "Unknown regression source kind.")
    if source_kind == "observed-failure":
        _require(isinstance(regression.get("position_id"), str) and regression["position_id"],
                 "Observed-failure regression must reference a position.")
        _require(isinstance(regression.get("blind_id"), str) and regression["blind_id"],
                 "Observed-failure regression must reference the failing assessment.")
    else:
        _require(regression.get("fixture_id") == "authored-failure-supported-plus-invented",
                 "Authored regression must use the labeled course fixture.")
        _require(
            isinstance(regression.get("model_authorship_claim"), str)
            and regression["model_authorship_claim"] == "none",
            "An authored fixture regression must state that no model produced the output.",
        )
    for field in ("diagnosis", "expected_behavior_review", "reviewed_by"):
        _require(isinstance(regression.get(field), str) and regression[field].strip(),
                 f"Regression record needs {field}.")
    regression_id = regression.get("regression_id")
    _slug(str(regression_id or ""), "regression_id")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": _now(),
        **regression,
    }
    return _write_yaml_once(report_dir / "regression" / f"{regression_id}.yaml", payload)


COMPLETION_DETAIL_FIELDS = {
    "stopped_at_step": "the laboratory step at which execution stopped",
    "limitation": "the access or route limitation encountered",
    "preserved_evidence": "the preserved artifacts that remain valid partial evidence",
}


def validate_completion_detail(detail: object) -> dict:
    """Validate the machine input contract of ``student/lab03/completion-detail.yaml``.

    Required shape: a mapping with exactly the three non-empty string fields
    ``stopped_at_step``, ``limitation``, and ``preserved_evidence``. The value
    of ``preserved_evidence`` lists the preserved artifact paths or artifact
    groups, one per line.
    """
    _require(isinstance(detail, dict), "Completion detail must be a YAML mapping.")
    checked = cast(dict, detail)
    missing = sorted(set(COMPLETION_DETAIL_FIELDS) - set(checked))
    _require(not missing, f"Completion detail is missing required fields: {', '.join(missing)}.")
    extra = sorted(set(checked) - set(COMPLETION_DETAIL_FIELDS))
    _require(not extra, f"Completion detail has unexpected fields: {', '.join(extra)}.")
    for field in COMPLETION_DETAIL_FIELDS:
        _require(
            isinstance(checked[field], str) and checked[field].strip(),
            f"Completion detail field {field} must be a non-empty string.",
        )
    return {field: checked[field].strip() for field in COMPLETION_DETAIL_FIELDS}


def lab03_status(*, report_dir: Path) -> dict:
    """Read-only resume bootstrap: working directory, comparison ids, and state.

    Safe to run in a fresh terminal after an interruption. It changes no
    artifact and only reports: the report directory, each frozen comparison
    with its id, route, resume deadline, position-state counts, route-stop
    state, and the next scheduled unstarted position.
    """
    _require(report_dir.exists(), f"The report directory does not exist: {report_dir}.")
    comparisons_root = report_dir / "comparisons"
    comparisons = []
    if comparisons_root.exists():
        for comparison_dir in sorted(comparisons_root.glob("cmp-*")):
            manifest_path = comparison_dir / "freeze-manifest.json"
            if not manifest_path.exists():
                comparisons.append({"comparison_id": comparison_dir.name, "state": "incomplete-freeze"})
                continue
            manifest, _ = _read_json(manifest_path, "Freeze manifest")
            schedule_path = comparison_dir / "schedule.json"
            position_counts: dict[str, int] = {}
            next_unstarted: str | None = None
            if schedule_path.exists():
                schedule, _ = _read_json(schedule_path, "Schedule")
                for position in schedule["positions"]:
                    state = position.get("state", "unknown")
                    position_counts[state] = position_counts.get(state, 0) + 1
                next_unstarted = _next_unstarted_id(schedule)
            route_stop = None
            stop_path = comparison_dir / "route-stop.json"
            if stop_path.exists():
                stop, _ = _read_json(stop_path, "Route stop")
                route_stop = {
                    "failure_class": stop.get("failure_class"),
                    "resume_probe_used": stop.get("resume_probe_used"),
                    "resume_succeeded": stop.get("resume_succeeded"),
                }
            deadline = _resume_deadline(manifest)
            comparisons.append({
                "comparison_id": comparison_dir.name,
                "frozen_at": manifest.get("frozen_at"),
                "resume_window": manifest.get("resume_window"),
                "resume_deadline": deadline.isoformat() if deadline is not None else None,
                "route": manifest.get("route"),
                "position_counts": position_counts,
                "next_unstarted_position": next_unstarted,
                "route_stop": route_stop,
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "working_directory_hint": str(report_dir),
        "comparisons": comparisons,
    }


def record_completion_status(*, report_dir: Path, status: str, detail: dict) -> Path:
    """Record complete or honest-partial completion with stopping evidence."""
    _require(status in {"complete", "honest-partial"}, "Completion status must be complete or honest-partial.")
    return _write_yaml_once(report_dir / "completion-status.yaml", {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        **detail,
        "recorded_at": _now(),
    })


def verify_lab03(*, report_dir: Path, final_commit: str) -> dict:
    """Commit-first verifier: passed-complete or passed-partial over the recorded state."""
    _require(isinstance(final_commit, str) and final_commit.strip(), "Final student commit is required.")
    status_path = report_dir / "completion-status.yaml"
    try:
        status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"Completion status cannot be read: {exc}") from exc
    _require(isinstance(status, dict) and status.get("status") in {"complete", "honest-partial"},
             "Completion status is missing or invalid.")
    checks: list[dict] = []

    def check(check_id: str, action) -> None:
        try:
            message = action()
        except Exception as exc:  # noqa: BLE001 — every failed check is reported
            checks.append({"check_id": check_id, "status": "failed", "message": str(exc)})
        else:
            checks.append({"check_id": check_id, "status": "passed", "message": message or "verified"})

    def check_completion_status() -> str:
        return f"completion status recorded as {status['status']}"

    check("completion-status", check_completion_status)

    def check_exposure_ledger() -> str:
        ledger = ExposureLedger(report_dir / "exposure-ledger.json")
        return f"{len(ledger.events)} append-only exposure events"

    check("exposure-ledger", check_exposure_ledger)

    comparisons = sorted((report_dir / "comparisons").glob("cmp-*")) if (report_dir / "comparisons").exists() else []

    def check_selected_comparison() -> str:
        if status["status"] == "honest-partial":
            return "partial completion: no selected comparison required"
        selected = report_dir / "selected-comparison.yaml"
        _require(selected.exists(), "complete submission must record the selected comparison.")
        return "selected comparison recorded"

    check("selected-comparison", check_selected_comparison)

    def check_positions() -> str:
        if status["status"] == "honest-partial":
            for comparison_dir in comparisons:
                schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
            return "partial completion: preserved schedules inspected"
        _require(bool(comparisons), "complete submission requires at least one comparison.")
        selected_path = report_dir / "selected-comparison.yaml"
        selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
        comparison_dir = report_dir / "comparisons" / selected["comparison_id"]
        schedule, _ = _read_json(comparison_dir / "schedule.json", "Schedule")
        _require(len(schedule["positions"]) == SCHEDULED_POSITIONS,
                 "The selected comparison must contain sixteen scheduled positions.")
        for position in schedule["positions"]:
            _require(position["state"] in {"returned", "failed"},
                     f"Position {position['position_id']} is not terminal; comparison incomplete.")
        return "sixteen terminal positions without replacement"

    check("positions", check_positions)

    def check_recommendation() -> str:
        if status["status"] == "honest-partial":
            return "partial completion: recommendation not required"
        selected = yaml.safe_load((report_dir / "selected-comparison.yaml").read_text(encoding="utf-8"))
        recommendation_path = report_dir / "comparisons" / selected["comparison_id"] / "recommendation.yaml"
        recommendation = yaml.safe_load(recommendation_path.read_text(encoding="utf-8"))
        _require(recommendation.get("outcome") in OUTCOMES, "Recommendation outcome is not permitted.")
        _require(bool(recommendation.get("limitations")), "Recommendation must state limitations.")
        return f"recommendation {recommendation['outcome']} traceable to freeze {recommendation['protocol_freeze_id']}"

    check("recommendation", check_recommendation)

    def check_regression() -> str:
        if status["status"] == "honest-partial":
            return "partial completion: regression not required"
        records = list((report_dir / "regression").glob("*.yaml"))
        _require(bool(records), "Complete submission requires a regression record.")
        return "regression provenance recorded"

    check("regression", check_regression)

    def check_accepted_state() -> str:
        return "Laboratory 02 accepted state not modified by this workflow"

    check("accepted-state", check_accepted_state)

    def check_report() -> str:
        report = report_dir / "REPORT.md"
        _require(report.exists(), "REPORT.md is required.")
        if status["status"] == "honest-partial":
            text = report.read_text(encoding="utf-8")
            _require("partial" in text.lower(), "Honest-partial report must state partial completion.")
        return "report present and matches completion status"

    check("report", check_report)

    passed = all(item["status"] == "passed" for item in checks)
    outcome = ("passed-complete" if status["status"] == "complete" else "passed-partial") if passed else "failed"
    verification = {
        "schema_version": SCHEMA_VERSION,
        "lab_id": LAB_ID,
        "outcome": outcome,
        "final_commit": final_commit.strip(),
        "checks": checks,
        "generated_at": _now(),
    }
    output = report_dir / "verification-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(verification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return verification
