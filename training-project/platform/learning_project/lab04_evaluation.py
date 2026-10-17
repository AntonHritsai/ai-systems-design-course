"""Laboratory 04 Stage C3 evaluation: judgments, metrics, operational evidence, decision."""
from __future__ import annotations

import json
from pathlib import Path

from .workflow import WorkflowError

STAGE_C3_DIRECTORY = "stage-c3"
DEFAULT_STAGE_C3_FIXTURE = Path(__file__).resolve().parents[2] / "cases" / "lab04" / "stage-c3-fixture.json"
_CASE_IDS = ("Evaluation Case A", "Evaluation Case B")
_COMPARED_CONFIGURATIONS = ("lexical retrieval", "embedding-based retrieval", "hybrid retrieval",
                            "lexical retrieval followed by embedding-based reranking")
_BINDING_RULE = ("the evaluator-only expected result identifiers of both evaluation cases are constructed under "
                 "chunking configuration sentence-pair-v1; retrieval metrics computed under another chunking "
                 "configuration are not comparable with these expected results")


def _read_stage_c3_fixture(fixture_path: Path) -> dict:
    try:
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read Stage C3 fixture: {exc}") from exc
    if not isinstance(fixture, dict) or fixture.get("schema_version") != "1.0":
        raise WorkflowError("Incompatible Stage C3 fixture.")
    binding = fixture.get("expected-result chunking configuration binding")
    if (not isinstance(binding, dict) or binding.get("chunking configuration") != "sentence-pair-v1"
            or binding.get("binding rule") != _BINDING_RULE):
        raise WorkflowError("The Stage C3 fixture does not bind the evaluator-only expected results to chunking configuration sentence-pair-v1.")
    cases = fixture.get("evaluation_cases")
    if not isinstance(cases, list) or len(cases) != 2:
        raise WorkflowError("The Stage C3 fixture must declare exactly two evaluation cases.")
    for case in cases:
        if (not isinstance(case, dict)
                or case.get("evaluation_case_id") not in _CASE_IDS
                or case.get("case_version") != 1
                or not isinstance(case.get("relevance judging basis"), str) or not case["relevance judging basis"].strip()
                or case.get("evaluator-only expected result") != ["F-A"]
                or not isinstance(case.get("approving designated human evaluator"), str) or not case["approving designated human evaluator"].strip()
                or not isinstance(case.get("expected result provenance"), str) or not case["expected result provenance"].strip()):
            raise WorkflowError("Malformed Stage C3 evaluation case record.")
    if [c["evaluation_case_id"] for c in cases] != list(_CASE_IDS):
        raise WorkflowError("The Stage C3 fixture must declare both evaluation cases in order.")
    return fixture


def _load_stage_c3_inputs(report_dir: Path, fixture: dict) -> dict[str, dict[str, list[dict]]]:
    """Read every archived Stage C2 ranked candidate output keyed by case, then configuration."""
    outputs: dict[str, dict[str, list[dict]]] = {}
    for case in fixture["evaluation_cases"]:
        case_id = case["evaluation_case_id"]
        outputs[case_id] = {}
        for configuration in _COMPARED_CONFIGURATIONS:
            path = report_dir / "stage-c2" / f"{case_id.lower().replace(' ', '-')}-{configuration.lower().replace(' ', '-')}.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise WorkflowError(f"Cannot read archived Stage C2 output {path}: {exc}") from exc
            if not isinstance(data, dict) or data.get("evaluation case") != case_id or data.get("retrieval configuration") != configuration:
                raise WorkflowError(f"Archived Stage C2 output does not match its declared case and configuration: {path}")
            ranked = data.get("ranked candidate output")
            if not isinstance(ranked, list) or any(not isinstance(item, dict) for item in ranked):
                raise WorkflowError(f"Malformed ranked candidate output in {path}.")
            outputs[case_id][configuration] = ranked
    return outputs


def _returned_unit_ids(outputs: dict[str, dict[str, list[dict]]], case_id: str) -> set[str]:
    returned: set[str] = set()
    for ranked in outputs[case_id].values():
        for item in ranked:
            identifier = item.get("stable retrieval identifier")
            if not isinstance(identifier, str) or not identifier:
                raise WorkflowError("Malformed stable retrieval identifier in an archived Stage C2 output.")
            returned.add(identifier)
    return returned


def record_relevance_judgments(*, report_dir: Path, c3_fixture_path: Path = DEFAULT_STAGE_C3_FIXTURE,
                               judgments_path: Path, evaluator: str) -> Path:
    """Record the designated human evaluator's application of the relevance judging basis."""
    if not isinstance(evaluator, str) or not evaluator.strip():
        raise WorkflowError("A designated human evaluator identity is required.")
    fixture = _read_stage_c3_fixture(c3_fixture_path)
    outputs = _load_stage_c3_inputs(report_dir, fixture)
    try:
        supplied = json.loads(Path(judgments_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read the supplied relevance judgments: {exc}") from exc
    if not isinstance(supplied, dict) or set(supplied) != set(_CASE_IDS):
        raise WorkflowError("Relevance judgments must be supplied for exactly both evaluation cases.")
    judged_cases = []
    for case in fixture["evaluation_cases"]:
        case_id = case["evaluation_case_id"]
        returned = _returned_unit_ids(outputs, case_id)
        entries = supplied[case_id]
        if not isinstance(entries, list) or not entries:
            raise WorkflowError(f"Relevance judgments for {case_id} must be a non-empty list.")
        identifiers = [entry.get("stable retrieval identifier") for entry in entries if isinstance(entry, dict)]
        if len(identifiers) != len(entries) or len(set(identifiers)) != len(identifiers):
            raise WorkflowError(f"Relevance judgments for {case_id} must name each returned retrieval unit exactly once.")
        if set(identifiers) != returned:
            raise WorkflowError(f"Relevance judgments for {case_id} must cover exactly the retrieval units returned by the compared configurations.")
        normalized = []
        for entry in entries:
            if (not isinstance(entry, dict)
                    or entry.get("stable retrieval identifier") not in returned
                    or entry.get("relevance judgment") not in ("relevant", "not relevant")
                    or not isinstance(entry.get("rationale"), str) or not entry["rationale"].strip()):
                raise WorkflowError(f"Malformed relevance judgment for {case_id}.")
            normalized.append({"stable retrieval identifier": entry["stable retrieval identifier"],
                               "relevance judgment": entry["relevance judgment"],
                               "rationale": entry["rationale"]})
        normalized.sort(key=lambda item: item["stable retrieval identifier"])
        judged_cases.append({
            "evaluation case": case_id,
            "relevance judging basis": case["relevance judging basis"],
            "returned retrieval units judged": sorted(returned),
            "relevance judgments": normalized,
        })
    result = {
        "schema_version": "1.0",
        "designated human evaluator": evaluator,
        "judged evaluation cases": judged_cases,
        "observation boundary": "relevance judgments over returned retrieval units; no retrieval metric",
    }
    output = report_dir / STAGE_C3_DIRECTORY / "relevance-judgments.json"
    from .lab04_retrieval import write_secure_stage_output
    write_secure_stage_output(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                              report_dir, STAGE_C3_DIRECTORY)
    return output


def _load_recorded_judgments(report_dir: Path) -> tuple[dict, dict[str, dict[str, str]]]:
    """Read the recorded relevance judgments; return the record and an identifier-to-judgment map per case."""
    path = report_dir / STAGE_C3_DIRECTORY / "relevance-judgments.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read the recorded relevance judgments: {exc}") from exc
    if (not isinstance(record, dict) or record.get("schema_version") != "1.0"
            or not isinstance(record.get("designated human evaluator"), str) or not record["designated human evaluator"].strip()
            or not isinstance(record.get("judged evaluation cases"), list)):
        raise WorkflowError("Malformed recorded relevance judgments; run record-relevance-judgments first.")
    judgments: dict[str, dict[str, str]] = {}
    for entry in record["judged evaluation cases"]:
        if (not isinstance(entry, dict) or entry.get("evaluation case") not in _CASE_IDS
                or not isinstance(entry.get("relevance judging basis"), str) or not entry["relevance judging basis"].strip()
                or not isinstance(entry.get("relevance judgments"), list) or not entry["relevance judgments"]):
            raise WorkflowError("Malformed recorded relevance judgments; run record-relevance-judgments first.")
        mapping: dict[str, str] = {}
        for judgment in entry["relevance judgments"]:
            if (not isinstance(judgment, dict)
                    or not isinstance(judgment.get("stable retrieval identifier"), str)
                    or judgment.get("relevance judgment") not in ("relevant", "not relevant")
                    or not isinstance(judgment.get("rationale"), str) or not judgment["rationale"].strip()):
                raise WorkflowError("Malformed recorded relevance judgment.")
            mapping[judgment["stable retrieval identifier"]] = judgment["relevance judgment"]
        judgments[entry["evaluation case"]] = mapping
    if set(judgments) != set(_CASE_IDS):
        raise WorkflowError("Recorded relevance judgments must cover both evaluation cases.")
    return record, judgments


def _metric(numerator: int, denominator: int) -> dict:
    if denominator == 0:
        return {"numerator": numerator, "denominator": 0, "value": "undefined",
                "reason": "undefined because no returned retrieval unit was available for a relevance judgment"}
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator}


def _aggregate(entries: list[dict], configuration: str, k: int) -> dict:
    """Aggregate one configuration's per-case entries under the declared counting rule."""
    selected = [entry for entry in entries if entry["retrieval configuration"] == configuration]
    precision_numerator = sum(entry[f"precision@{k}"]["numerator"] for entry in selected)
    precision_denominator = sum(entry[f"precision@{k}"]["denominator"] for entry in selected)
    recall_numerator = sum(entry[f"recall@{k}"]["numerator"] for entry in selected)
    recall_denominator = sum(entry[f"recall@{k}"]["denominator"] for entry in selected)
    return {
        "retrieval configuration": configuration,
        "aggregation rule": "judged returned retrieval units counted across both evaluation cases; an empty ranked candidate output contributes no judged returned retrieval unit to the precision denominator",
        f"precision@{k}": _metric(precision_numerator, precision_denominator),
        f"recall@{k}": _metric(recall_numerator, recall_denominator),
    }


def _derive_metrics(*, report_dir: Path, fixture: dict, k: int, judgments: dict[str, dict[str, str]],
                    b_fixture_path, c1_fixture_path, c2_fixture_path, encoder, model_dir) -> dict:
    """Recompute every metric from verified Stage C2 outputs and recorded relevance judgments."""
    from .lab04_retrieval import verify_stage_c2
    verification = verify_stage_c2(report_dir=report_dir, b_fixture_path=b_fixture_path,
                                   c1_fixture_path=c1_fixture_path, c2_fixture_path=c2_fixture_path,
                                   encoder=encoder, model_dir=model_dir)
    if verification.get("outcome") != "passed":
        raise WorkflowError("Stage C2 verification failed; retrieval metrics are not computable.")
    outputs = _load_stage_c3_inputs(report_dir, fixture)
    per_case = []
    for case in fixture["evaluation_cases"]:
        case_id = case["evaluation_case_id"]
        expected = case["evaluator-only expected result"]
        judged = judgments[case_id]
        for configuration in _COMPARED_CONFIGURATIONS:
            ranked = [item["stable retrieval identifier"] for item in outputs[case_id][configuration]][:k]
            judged_returned = [identifier for identifier in ranked if identifier in judged]
            if ranked:
                precision = _metric(sum(1 for identifier in ranked if judged.get(identifier) == "relevant"), len(ranked))
            else:
                precision = {"numerator": 0, "denominator": 0, "value": "undefined",
                             "reason": "undefined because no returned retrieval unit was available for a relevance judgment"}
            recall = _metric(sum(1 for identifier in expected if identifier in ranked), len(expected))
            per_case.append({
                "retrieval configuration": configuration,
                "evaluation case": case_id,
                "ranked candidate output": ranked,
                "judged returned retrieval units": judged_returned,
                f"precision@{k}": precision,
                f"recall@{k}": recall,
            })
    aggregate = [_aggregate(per_case, configuration, k) for configuration in _COMPARED_CONFIGURATIONS]
    return {
        "schema_version": "1.0",
        "configured result count k": k,
        "expected-result chunking configuration binding": fixture["expected-result chunking configuration binding"]["binding rule"],
        "per-case metrics": per_case,
        "aggregate metrics": aggregate,
        "observation boundary": "retrieval metrics over the ranked candidate output; no operational evidence and no downstream claim",
    }


def compute_retrieval_metrics(*, report_dir: Path, c3_fixture_path: Path = DEFAULT_STAGE_C3_FIXTURE,
                              b_fixture_path=None, c1_fixture_path=None, c2_fixture_path=None,
                              encoder=None, model_dir=None) -> Path:
    """Compute precision@k and recall@k from verified Stage C2 outputs and recorded relevance judgments."""
    from .lab04 import DEFAULT_STAGE_B_FIXTURE
    from .lab04_index import DEFAULT_STAGE_C1_FIXTURE
    from .lab04_retrieval import DEFAULT_STAGE_C2_FIXTURE, write_secure_stage_output
    b_fixture_path = DEFAULT_STAGE_B_FIXTURE if b_fixture_path is None else b_fixture_path
    c1_fixture_path = DEFAULT_STAGE_C1_FIXTURE if c1_fixture_path is None else c1_fixture_path
    c2_fixture_path = DEFAULT_STAGE_C2_FIXTURE if c2_fixture_path is None else c2_fixture_path
    fixture = _read_stage_c3_fixture(c3_fixture_path)
    try:
        c2_settings = json.loads(Path(c2_fixture_path).read_text(encoding="utf-8"))
        k = c2_settings["result count k"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise WorkflowError(f"Cannot read the Stage C2 configured result count: {exc}") from exc
    _, judgments = _load_recorded_judgments(report_dir)
    result = _derive_metrics(report_dir=report_dir, fixture=fixture, k=k, judgments=judgments,
                             b_fixture_path=b_fixture_path, c1_fixture_path=c1_fixture_path,
                             c2_fixture_path=c2_fixture_path, encoder=encoder, model_dir=model_dir)
    output = report_dir / STAGE_C3_DIRECTORY / "retrieval-metrics.json"
    write_secure_stage_output(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                              report_dir, STAGE_C3_DIRECTORY)
    return output


def verify_stage_c3(*, report_dir: Path, c3_fixture_path: Path = DEFAULT_STAGE_C3_FIXTURE,
                    b_fixture_path=None, c1_fixture_path=None, c2_fixture_path=None,
                    encoder=None, model_dir=None) -> dict:
    """Independently recompute every metric and compare it with the recorded Stage C3 metrics."""
    from .lab04 import DEFAULT_STAGE_B_FIXTURE
    from .lab04_index import DEFAULT_STAGE_C1_FIXTURE
    from .lab04_retrieval import DEFAULT_STAGE_C2_FIXTURE
    b_fixture_path = DEFAULT_STAGE_B_FIXTURE if b_fixture_path is None else b_fixture_path
    c1_fixture_path = DEFAULT_STAGE_C1_FIXTURE if c1_fixture_path is None else c1_fixture_path
    c2_fixture_path = DEFAULT_STAGE_C2_FIXTURE if c2_fixture_path is None else c2_fixture_path
    fixture = _read_stage_c3_fixture(c3_fixture_path)
    try:
        c2_settings = json.loads(Path(c2_fixture_path).read_text(encoding="utf-8"))
        k = c2_settings["result count k"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise WorkflowError(f"Cannot read the Stage C2 configured result count: {exc}") from exc
    _, judgments = _load_recorded_judgments(report_dir)
    expected = _derive_metrics(report_dir=report_dir, fixture=fixture, k=k, judgments=judgments,
                               b_fixture_path=b_fixture_path, c1_fixture_path=c1_fixture_path,
                               c2_fixture_path=c2_fixture_path, encoder=encoder, model_dir=model_dir)
    path = report_dir / STAGE_C3_DIRECTORY / "retrieval-metrics.json"
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read the recorded Stage C3 retrieval metrics: {exc}") from exc
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise WorkflowError("Stage C3 retrieval metrics differ from the independently derived values.")
    return {"outcome": "passed", "verified metric entries": len(expected["per-case metrics"]),
            "verification boundary": "metric arithmetic over verified Stage C2 outputs and recorded relevance judgments; no relevance judgment of its own"}


def measure_operational_evidence(*, report_dir: Path, c3_fixture_path: Path = DEFAULT_STAGE_C3_FIXTURE,
                                 b_fixture_path=None, c1_fixture_path=None, c2_fixture_path=None,
                                 encoder=None, model_dir=None, runs: int = 3) -> Path:
    """Measure the declared operational-evidence items for every compared retrieval configuration."""
    import time
    from uuid import uuid4
    from .lab04 import DEFAULT_STAGE_B_FIXTURE
    from .lab04_index import DEFAULT_STAGE_C1_FIXTURE
    from .lab04_retrieval import DEFAULT_STAGE_C2_FIXTURE, write_secure_stage_output, execute_retrieval
    b_fixture_path = DEFAULT_STAGE_B_FIXTURE if b_fixture_path is None else b_fixture_path
    c1_fixture_path = DEFAULT_STAGE_C1_FIXTURE if c1_fixture_path is None else c1_fixture_path
    c2_fixture_path = DEFAULT_STAGE_C2_FIXTURE if c2_fixture_path is None else c2_fixture_path
    fixture = _read_stage_c3_fixture(c3_fixture_path)
    _load_recorded_judgments(report_dir)
    if not isinstance(runs, int) or runs < 1:
        raise WorkflowError("The number of measured runs must be a positive integer.")
    measurements = []
    for configuration in _COMPARED_CONFIGURATIONS:
        latencies: list[float] = []
        failures: list[str] = []
        for _ in range(runs):
            import shutil
            scratch = report_dir.parent / f"{report_dir.name}-c3-op-{uuid4().hex[:8]}"
            shutil.copytree(report_dir, scratch)
            shutil.rmtree(scratch / "stage-c2", ignore_errors=True)
            started = time.perf_counter()
            try:
                for case in fixture["evaluation_cases"]:
                    execute_retrieval(report_dir=scratch, case_id=case["evaluation_case_id"],
                                      configuration_id=configuration, b_fixture_path=b_fixture_path,
                                      c1_fixture_path=c1_fixture_path, c2_fixture_path=c2_fixture_path,
                                      encoder=encoder, model_dir=model_dir)
            except WorkflowError as exc:
                failures.append(str(exc))
            latencies.append(time.perf_counter() - started)
            shutil.rmtree(scratch, ignore_errors=True)
        measurements.append({
            "retrieval configuration": configuration,
            "prepared-index build or update cost": {
                "measurement boundary": "one Stage C1 index preparation already recorded in the archived evidence; no rebuild is measured here",
                "measurement": "not re-measured; the archived Stage C1 evidence is reused for every compared configuration"},
            "query latency": {
                "measurement boundary": f"wall-clock seconds for executing both declared text queries once per run, averaged over {runs} runs in one process",
                "measurement": round(sum(latencies) / len(latencies), 6)},
            "query cost": {
                "measurement boundary": "model-backed encodes are charged per text query plus the index re-encoding validation performed by execute-retrieval; CPU-only lexical scoring adds no model cost",
                "measurement": "measured as encodes per execution: one query encode per text query plus the indexed-unit re-encoding validation under the declared encoder"},
            "resource consumption": {
                "measurement boundary": "in-process peak is not instrumented; the consumed resources are the pinned local model, its memory footprint at load, and CPU time only",
                "measurement": "local model reuse in one process; no network access; no additional hardware"},
            "execution failures": {
                "measurement boundary": "WorkflowError outcomes raised while executing both declared text queries under this configuration",
                "measurement": failures},
        })
    result = {
        "schema_version": "1.0",
        "runs per configuration": runs,
        "operational measurements": measurements,
        "observation boundary": "operational evidence is not a relevance measure; no measurement from this record enters the numerator or denominator of precision@k or recall@k",
    }
    output = report_dir / STAGE_C3_DIRECTORY / "operational-evidence.json"
    write_secure_stage_output(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                              report_dir, STAGE_C3_DIRECTORY)
    return output


def record_configuration_decision(*, report_dir: Path, c3_fixture_path: Path = DEFAULT_STAGE_C3_FIXTURE,
                                  selected_configuration_id: str, rationale: str, decided_by: str) -> Path:
    """Record one bounded configuration decision supported by the Stage C3 evidence."""
    from .lab04_retrieval import write_secure_stage_output
    fixture = _read_stage_c3_fixture(c3_fixture_path)
    _load_recorded_judgments(report_dir)
    if selected_configuration_id not in _COMPARED_CONFIGURATIONS:
        raise WorkflowError("Unknown retrieval configuration selection.")
    if not isinstance(rationale, str) or len(rationale.strip()) < 120:
        raise WorkflowError("A bounded configuration decision requires a substantive rationale argued from the recorded metrics and operational evidence.")
    if not isinstance(decided_by, str) or not decided_by.strip():
        raise WorkflowError("A decision actor identity is required.")
    metrics_path = report_dir / STAGE_C3_DIRECTORY / "retrieval-metrics.json"
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read the recorded retrieval metrics; run compute-retrieval-metrics first: {exc}") from exc
    if not isinstance(metrics, dict) or metrics.get("schema_version") != "1.0" or not isinstance(metrics.get("aggregate metrics"), list):
        raise WorkflowError("Malformed recorded retrieval metrics; run compute-retrieval-metrics first.")
    k = metrics.get("configured result count k")
    if not isinstance(k, int) or k < 1:
        raise WorkflowError("Malformed configured result count in the recorded retrieval metrics.")
    result = {
        "schema_version": "1.0",
        "selected retrieval configuration": selected_configuration_id,
        "experiment-baseline retrieval configuration": "lexical retrieval",
        "candidate retrieval configuration": "embedding-based retrieval",
        "decided by": decided_by,
        "rationale": rationale,
        "decision boundary": ("bounded to Evaluation Case A and Evaluation Case B, canonical knowledge collection version course-seed-v1, "
                              "the sentence-pair-v1 retrieval-unit boundary, the declared relevance judging basis, and the configured result count k=1"),
        "authority boundary": ("a bounded configuration decision about the retrieval configuration; it does not establish the quality of the candidate "
                               "concept definition produced downstream, does not establish that the complete user workflow achieves its intended result, "
                               "and does not authorize any change to the canonical knowledge collection"),
        "aggregate metrics at decision time": metrics["aggregate metrics"],
        "observation boundary": "one bounded configuration decision; no downstream claim",
    }
    output = report_dir / STAGE_C3_DIRECTORY / "configuration-decision.json"
    write_secure_stage_output(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                              report_dir, STAGE_C3_DIRECTORY)
    return output
