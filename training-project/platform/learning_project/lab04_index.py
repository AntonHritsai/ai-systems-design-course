"""Laboratory 04 Stage C1 retrieval-unit embeddings and vector-index slice.

Section 3 of the Module 04 theory supplies the representation contract; Section 4
supplies index preparation, the index manifest, and the pre-use binding check that
classifies an index version as stale under the rebuild condition.

The training project depends only on PyYAML and Pillow. The declared local embedding
model is provided by the optional ``lab04`` extra and is imported lazily, so every
module import in this package keeps working without that extra.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Protocol, cast

from .lab04 import (
    BOUNDARY_COMPARISON_FILENAME,
    BOUNDARY_DECISION_FILENAME,
    DEFAULT_STAGE_B_FIXTURE,
    STAGE_B_DIRECTORY,
)
from .workflow import WorkflowError


STAGE_C1_DIRECTORY = "stage-c1"
DEFAULT_STAGE_C1_FIXTURE = Path(__file__).resolve().parents[2] / "cases" / "lab04" / "stage-c1-fixture.json"
DEFAULT_MODEL_DIRECTORY = Path(__file__).resolve().parents[2] / "models" / "potion-base-8M"
RETRIEVAL_UNIT_EMBEDDINGS_FILENAME = "retrieval-unit-embeddings.json"
INDEX_MANIFEST_FILENAME = "index-manifest.json"
MODEL_PROVENANCE_FILENAME = "model-provenance.json"
MODEL_WEIGHTS_FILENAME = "model.safetensors"
BINDING_CHECK_PREFIX = "binding-check-"
DECLARED_BINDINGS = (
    "the canonical knowledge collection version",
    "the chunking configuration that realizes the retrieval-unit definition recorded in the retrieval contract",
    "the embedding model and representation version",
    "the required embedding dimension and embedding space",
    "a stable retrieval identifier and provenance link for every retrieval unit",
)


class RetrievalUnitEncoder(Protocol):
    """The declared local capability that produces retrieval-unit embeddings."""

    embedding_model: str
    model_revision: str
    representation_version: str
    embedding_dimension: int
    embedding_space: str

    def encode(self, texts: list[str]) -> list[list[float]]: ...


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowError(message)


def _write_new_output(output: Path, content: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(output, flags, 0o666)
    except FileExistsError as exc:
        raise WorkflowError(f"Output already exists at {output}.") from exc
    except OSError as exc:
        raise WorkflowError(f"Cannot create output at {output}: {exc}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)


def _compute_file_digest(path: Path) -> str:
    """Return the hex-encoded SHA-256 digest of the file at *path*."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
    except OSError as exc:
        raise WorkflowError(f"Cannot read {path} to compute the file digest: {exc}") from exc
    return h.hexdigest()


def _read_stage_c1_fixture(path: Path) -> dict:
    try:
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot read the Laboratory 04 Stage C1 fixture: {exc}") from exc
    _require(isinstance(fixture, dict), "The Laboratory 04 Stage C1 fixture must be an object.")
    _require(fixture.get("schema_version") == "1.0", "Unsupported Laboratory 04 Stage C1 fixture version.")
    contract = fixture.get("representation_contract")
    _require(isinstance(contract, dict), "The Stage C1 fixture lacks the representation contract.")
    # Fix #5 (Logic #4): declared_bindings may be non-iterable; convert explicitly to avoid TypeError.
    try:
        declared = tuple(fixture.get("declared_bindings", ()))
    except TypeError as exc:
        raise WorkflowError("The Stage C1 fixture has a malformed declared_bindings field.") from exc
    _require(
        declared == DECLARED_BINDINGS,
        "The Stage C1 fixture does not declare the five vector-index bindings.",
    )
    _require(
        isinstance(fixture.get("index_version"), str) and fixture["index_version"],
        "The Stage C1 fixture lacks an index version.",
    )
    configurations = fixture.get("required_retrieval_configurations")
    _require(
        isinstance(configurations, list) and len(configurations) == 2 and all(isinstance(item, dict) for item in configurations),
        "The Stage C1 fixture requires exactly two required retrieval configurations.",
    )
    return cast(dict, fixture)


def _representation_contract(fixture: dict) -> dict:
    contract = cast(dict, fixture["representation_contract"])
    for field in ("embedding model", "model revision", "representation version", "embedding space"):
        _require(isinstance(contract.get(field), str) and contract[field], f"The representation contract lacks {field}.")
    _require(
        isinstance(contract.get("embedding dimension"), int) and contract["embedding dimension"] > 0,
        "The representation contract lacks a positive embedding dimension.",
    )
    return contract


def _stage_b_evidence(report_dir: Path) -> tuple[dict, dict]:
    stage_directory = report_dir / STAGE_B_DIRECTORY
    try:
        comparison = json.loads((stage_directory / BOUNDARY_COMPARISON_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot read the Laboratory 04 Stage B evidence: {exc}") from exc
    decision = _load_decision(stage_directory / BOUNDARY_DECISION_FILENAME)
    _require(isinstance(comparison, dict), "The boundary comparison must be an object.")
    _require(isinstance(decision, dict), "The boundary decision must be an object.")
    return comparison, decision


def _load_decision(path: Path) -> Any:
    import yaml

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"Cannot read the boundary decision: {exc}") from exc


def _selected_retrieval_units(report_dir: Path) -> tuple[str, list[dict]]:
    comparison, decision = _stage_b_evidence(report_dir)
    selected = decision.get("selected chunking configuration")
    results = comparison.get("chunking_configuration_results")
    _require(isinstance(results, list), "The boundary comparison lacks its chunking configuration results.")
    for result in cast(list[dict], results):
        if result.get("chunking_configuration_id") == selected:
            units = result.get("source_fragments")
            _require(isinstance(units, list) and bool(units), "The selected chunking configuration produced no retrieval unit.")
            return cast(str, selected), cast(list[dict], units)
    raise WorkflowError(f"The boundary decision selects an unknown chunking configuration {selected}.")


def _require_encoder_matches_contract(encoder: RetrievalUnitEncoder, contract: dict) -> None:
    declared = {
        "embedding model": contract["embedding model"],
        "model revision": contract["model revision"],
        "representation version": contract["representation version"],
        "embedding dimension": contract["embedding dimension"],
        "embedding space": contract["embedding space"],
    }
    loaded = {
        "embedding model": encoder.embedding_model,
        "model revision": encoder.model_revision,
        "representation version": encoder.representation_version,
        "embedding dimension": encoder.embedding_dimension,
        "embedding space": encoder.embedding_space,
    }
    _require(
        loaded == declared,
        "The loaded local embedding model is not the declared representation contract: "
        f"declared {declared}, loaded {loaded}.",
    )


class _LocalRetrievalUnitEncoder:
    """The declared local embedding model, loaded from the pinned local snapshot."""

    def __init__(self, model: Any, provenance: dict) -> None:
        self._model = model
        self.embedding_model = provenance["embedding model"]
        self.model_revision = provenance["model revision"]
        self.representation_version = provenance["representation version"]
        self.embedding_dimension = provenance["embedding dimension"]
        self.embedding_space = provenance["embedding space"]

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in row] for row in self._model.encode(texts)]


def load_local_retrieval_unit_encoder(model_dir: Path | None = None) -> RetrievalUnitEncoder:
    """Load the declared local embedding model or stop with the acquisition command."""
    directory = Path(model_dir) if model_dir is not None else DEFAULT_MODEL_DIRECTORY
    if not directory.is_dir():
        raise WorkflowError(
            f"The mandatory local embedding model is unavailable at {directory}. Run "
            f"'uv run learning-project lab04 fetch-embedding-model --model-dir {directory}' once while the "
            "model download is available, then repeat this command."
        )
    provenance_path = directory / MODEL_PROVENANCE_FILENAME
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot read the local model provenance at {provenance_path}: {exc}") from exc

    # Fix #1 (Security): verify the model weights exist and match the recorded digest before
    # trusting the self-declared provenance.  A same-dimension model swapped into the
    # directory with the provenance file left in place is caught here; a provenance-only
    # directory (no weights) is also caught.
    weights_path = directory / MODEL_WEIGHTS_FILENAME
    recorded_digest = provenance.get("model file digest")
    if recorded_digest is not None:
        if not weights_path.is_file():
            raise WorkflowError(
                f"The local model provenance at {directory} records a file digest but "
                f"{MODEL_WEIGHTS_FILENAME} is absent. Remove that directory and run "
                "'uv run learning-project lab04 fetch-embedding-model' to re-acquire the model."
            )
        actual_digest = _compute_file_digest(weights_path)
        if actual_digest != recorded_digest:
            raise WorkflowError(
                f"The {MODEL_WEIGHTS_FILENAME} at {directory} does not match the recorded digest. "
                "The model files may have been replaced or corrupted. Remove that directory and run "
                "'uv run learning-project lab04 fetch-embedding-model' to re-acquire the model."
            )

    try:
        from model2vec import StaticModel
    except ImportError as exc:
        raise WorkflowError(
            "The optional 'lab04' extra that provides the declared local embedding model is not installed. "
            "Run 'uv sync --extra lab04' in the training project, then repeat this command."
        ) from exc

    # Fix #5 (Logic #4): a weights-less directory or a corrupt safetensors file raises a raw
    # ValueError from model2vec; wrap it as WorkflowError.
    try:
        model = StaticModel.from_pretrained(directory, force_download=False)
    except ValueError as exc:
        raise WorkflowError(
            f"The local embedding model at {directory} could not be loaded: {exc}. "
            "The model files may be absent or corrupt. Remove that directory and run "
            "'uv run learning-project lab04 fetch-embedding-model' to re-acquire the model."
        ) from exc

    return _LocalRetrievalUnitEncoder(model, cast(dict, provenance))


def fetch_embedding_model(*, model_dir: Path, fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE) -> dict:
    """Acquire the pinned local snapshot once and record the local model provenance."""
    fixture = _read_stage_c1_fixture(fixture_path)
    contract = _representation_contract(fixture)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise WorkflowError(
            "The optional 'lab04' extra that provides the model download capability is not installed. "
            "Run 'uv sync --extra lab04' in the training project, then repeat this command."
        ) from exc

    directory = Path(model_dir)
    if directory.is_dir() and (directory / MODEL_PROVENANCE_FILENAME).is_file():
        try:
            present = json.loads((directory / MODEL_PROVENANCE_FILENAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"Cannot read the local model provenance at {directory}: {exc}") from exc
        if present.get("model revision") == contract["model revision"]:
            # Fix #6 (Logic #5): a provenance-only directory (revision matches but no model files)
            # must not be reported as success.
            weights_path = directory / MODEL_WEIGHTS_FILENAME
            if not weights_path.is_file():
                raise WorkflowError(
                    f"The local model provenance at {directory} records the correct revision but "
                    f"{MODEL_WEIGHTS_FILENAME} is absent. Remove that directory and repeat."
                )
            return cast(dict, present)
        raise WorkflowError(
            f"The local model at {directory} records another model revision; remove that directory and repeat."
        )

    directory.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=contract["embedding model"],
        revision=contract["model revision"],
        local_dir=directory,
    )

    # Fix #1 (Security): record the SHA-256 digest of the model weights at acquisition time so
    # load_local_retrieval_unit_encoder can verify identity beyond self-declared metadata.
    weights_path = directory / MODEL_WEIGHTS_FILENAME
    if not weights_path.is_file():
        raise WorkflowError(
            f"The snapshot download completed but {MODEL_WEIGHTS_FILENAME} is absent at {directory}. "
            "The repository may not contain a safetensors weights file."
        )
    model_file_digest = _compute_file_digest(weights_path)

    provenance = {
        "embedding model": contract["embedding model"],
        "model revision": contract["model revision"],
        "representation version": contract["representation version"],
        "embedding dimension": contract["embedding dimension"],
        "embedding space": contract["embedding space"],
        "model file digest": model_file_digest,
    }
    (directory / MODEL_PROVENANCE_FILENAME).write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return provenance


def prepare_retrieval_unit_embeddings(
    *,
    report_dir: Path,
    fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE,
    model_dir: Path | None = None,
    encoder: RetrievalUnitEncoder | None = None,
) -> Path:
    """Produce one compatible retrieval-unit embedding for every included retrieval unit."""
    fixture = _read_stage_c1_fixture(fixture_path)
    contract = _representation_contract(fixture)
    loaded = encoder if encoder is not None else load_local_retrieval_unit_encoder(model_dir)
    _require_encoder_matches_contract(loaded, contract)

    configuration, units = _selected_retrieval_units(report_dir)
    comparison, _ = _stage_b_evidence(report_dir)
    vectors = loaded.encode([unit["text"] for unit in units])
    _require(len(vectors) == len(units), "The embedding model returned a different number of embeddings than retrieval units.")

    entries = []
    for unit, vector in zip(units, vectors):
        values = [float(value) for value in vector]
        _require(
            len(values) == contract["embedding dimension"],
            "A retrieval-unit embedding does not match the declared embedding dimension "
            f"{contract['embedding dimension']}.",
        )
        _require(all(math.isfinite(value) for value in values), "A retrieval-unit embedding contains a non-finite coordinate.")
        _require(any(value != 0.0 for value in values), "A retrieval-unit embedding is the zero vector.")
        entries.append(
            {
                "stable retrieval identifier": unit["stable_retrieval_identifier"],
                "provenance link": unit["provenance_link"],
                "representation version": contract["representation version"],
                "embedding dimension": contract["embedding dimension"],
                "embedding space": contract["embedding space"],
                "retrieval-unit embedding": values,
            }
        )

    artifact = {
        "schema_version": "1.0",
        "representation contract": contract,
        "canonical knowledge collection version": comparison["canonical_knowledge_collection_version"],
        "chunking configuration": configuration,
        "retrieval-unit embeddings": entries,
    }
    output = report_dir / STAGE_C1_DIRECTORY / RETRIEVAL_UNIT_EMBEDDINGS_FILENAME
    _write_new_output(output, json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
    return output


def _read_embeddings(report_dir: Path) -> dict:
    path = report_dir / STAGE_C1_DIRECTORY / RETRIEVAL_UNIT_EMBEDDINGS_FILENAME
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot read the retrieval-unit embeddings: {exc}") from exc
    _require(isinstance(artifact, dict), "The retrieval-unit embeddings must be an object.")
    return cast(dict, artifact)


def _read_manifest(report_dir: Path) -> dict:
    path = report_dir / STAGE_C1_DIRECTORY / INDEX_MANIFEST_FILENAME
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot read the index manifest: {exc}") from exc
    _require(isinstance(manifest, dict), "The index manifest must be an object.")
    return cast(dict, manifest)


def prepare_vector_index(*, report_dir: Path, fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE) -> Path:
    """Bind the compatible embeddings and their associations into one vector index."""
    fixture = _read_stage_c1_fixture(fixture_path)
    artifact = _read_embeddings(report_dir)
    entries = artifact.get("retrieval-unit embeddings")
    _require(isinstance(entries, list) and bool(entries), "The retrieval-unit embeddings artifact is empty.")
    entries = cast(list[dict], entries)

    configuration, units = _selected_retrieval_units(report_dir)
    indexed = [entry["stable retrieval identifier"] for entry in entries]
    expected = [unit["stable_retrieval_identifier"] for unit in units]
    _require(
        indexed == expected,
        f"The retrieval-unit embeddings do not cover the declared chunking configuration {configuration}.",
    )
    contract = cast(dict, artifact["representation contract"])
    metadata_bindings = []
    for entry, unit in zip(entries, units):
        _require(
            entry.get("provenance link") == unit["provenance_link"],
            f"The provenance link of {entry.get('stable retrieval identifier')} does not match the Stage B evidence.",
        )
        _require(
            len(cast(list, entry["retrieval-unit embedding"])) == contract["embedding dimension"],
            "A retrieval-unit embedding does not match the declared embedding dimension.",
        )
        metadata_bindings.append(
            {
                "stable retrieval identifier": entry["stable retrieval identifier"],
                "provenance link": entry["provenance link"],
            }
        )

    manifest = {
        "schema_version": "1.0",
        "index version": fixture["index_version"],
        "the canonical knowledge collection version": artifact["canonical knowledge collection version"],
        "the chunking configuration that realizes the retrieval-unit definition recorded in the retrieval contract": configuration,
        "the embedding model and representation version": {
            "embedding model": contract["embedding model"],
            "model revision": contract["model revision"],
            "representation version": contract["representation version"],
        },
        "the required embedding dimension and embedding space": {
            "embedding dimension": contract["embedding dimension"],
            "embedding space": contract["embedding space"],
        },
        "a stable retrieval identifier and provenance link for every retrieval unit": metadata_bindings,
        "indexed retrieval units": indexed,
        "completeness status": (
            "complete for the declared chunking configuration: every retrieval unit of "
            f"{configuration} over {artifact['canonical knowledge collection version']} is indexed"
        ),
    }
    output = report_dir / STAGE_C1_DIRECTORY / INDEX_MANIFEST_FILENAME
    _write_new_output(output, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return output


def _required_configuration(fixture: dict, required_retrieval_configuration_id: str) -> dict:
    configurations = cast(list[dict], fixture["required_retrieval_configurations"])
    for configuration in configurations:
        if configuration.get("required_retrieval_configuration_id") == required_retrieval_configuration_id:
            return configuration
    raise WorkflowError(f"Unknown required retrieval configuration {required_retrieval_configuration_id}.")


def _compare_bindings(
    fixture: dict,
    manifest: dict,
    required: dict,
    report_dir: Path,
) -> tuple[list[dict], str | None]:
    """Compare each declared binding's required value against the recorded manifest value.

    Fix #2 (Logic #1):
    - Binding 2 required value is derived from the boundary decision (Stage B evidence), not
      read back from the manifest — reading from the manifest is self-referential and can never
      detect a stale chunking configuration recorded in the manifest itself.
    - Binding 5 required value is the full per-unit list of stable retrieval identifier and
      provenance link pairs derived from Stage B evidence, not a presence-only boolean.

    Fix #5 (Logic #4): manifest key access is guarded so a malformed manifest raises
    WorkflowError instead of a raw KeyError.
    """
    contract = _representation_contract(fixture)

    # Derive binding 2 and binding 5 required values from Stage B evidence.
    config_id, units = _selected_retrieval_units(report_dir)
    required_binding5 = [
        {"stable retrieval identifier": u["stable_retrieval_identifier"], "provenance link": u["provenance_link"]}
        for u in units
    ]

    try:
        required_values: dict[str, Any] = {
            "the canonical knowledge collection version": required["the canonical knowledge collection version"],
            # Binding 2: resolved from boundary decision, not from the manifest.
            "the chunking configuration that realizes the retrieval-unit definition recorded in the retrieval contract": config_id,
            "the embedding model and representation version": {
                "embedding model": contract["embedding model"],
                "model revision": contract["model revision"],
                "representation version": contract["representation version"],
            },
            "the required embedding dimension and embedding space": {
                "embedding dimension": contract["embedding dimension"],
                "embedding space": contract["embedding space"],
            },
            # Binding 5: full per-unit list from Stage B evidence, not a presence-only bool.
            "a stable retrieval identifier and provenance link for every retrieval unit": required_binding5,
        }
    except KeyError as exc:
        raise WorkflowError(f"The required retrieval configuration is missing a field: {exc}") from exc

    checks = []
    failed: str | None = None
    for binding in DECLARED_BINDINGS:
        required_value = required_values[binding]
        # Fix #5 (Logic #4): use .get() to avoid KeyError on a malformed manifest.
        recorded_value: Any = manifest.get(binding)
        matched = required_value == recorded_value
        checks.append({"binding": binding, "required value": required_value, "recorded value": recorded_value, "matched": matched})
        if not matched and failed is None:
            failed = binding
    return checks, failed


def check_index_bindings(
    *,
    report_dir: Path,
    required_retrieval_configuration_id: str,
    fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE,
) -> dict:
    """Compare the required bindings with the recorded manifest before the index is used."""
    fixture = _read_stage_c1_fixture(fixture_path)
    manifest = _read_manifest(report_dir)
    required = _required_configuration(fixture, required_retrieval_configuration_id)
    checks, failed = _compare_bindings(fixture, manifest, required, report_dir)
    stale = failed is not None
    record = {
        "schema_version": "1.0",
        "index version": manifest.get("index version"),
        "required retrieval configuration id": required_retrieval_configuration_id,
        "checked bindings": checks,
        "outcome": "stale" if stale else "admissible",
        "failed binding": failed,
        "rebuild condition": (
            None
            if not stale
            else (
                "a replacement index version bound to the required inputs must be prepared and identified "
                f"before the index version {manifest.get('index version')} is used for "
                f"{required_retrieval_configuration_id}"
            )
        ),
    }
    output = report_dir / STAGE_C1_DIRECTORY / f"{BINDING_CHECK_PREFIX}{required_retrieval_configuration_id}.json"
    _write_new_output(output, json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    return record


def verify_stage_c1(*, report_dir: Path, fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE) -> dict:
    """Verify Stage C1 evidence without performing retrieval or judging relevance."""
    fixture = _read_stage_c1_fixture(fixture_path)
    contract = _representation_contract(fixture)
    artifact = _read_embeddings(report_dir)
    manifest = _read_manifest(report_dir)
    configuration, units = _selected_retrieval_units(report_dir)

    # Fix #5 (Logic #4): guard against a missing "retrieval-unit embeddings" key with WorkflowError.
    try:
        entries = cast(list[dict], artifact["retrieval-unit embeddings"])
    except KeyError as exc:
        raise WorkflowError("The retrieval-unit embeddings artifact lacks the 'retrieval-unit embeddings' field.") from exc

    _require(
        [entry["stable retrieval identifier"] for entry in entries]
        == [unit["stable_retrieval_identifier"] for unit in units],
        f"The retrieval-unit embeddings do not cover the declared chunking configuration {configuration}.",
    )

    for entry, unit in zip(entries, units):
        # Fix #5 (Logic #4): guard against missing embedding key with WorkflowError.
        try:
            vector = cast(list[Any], entry["retrieval-unit embedding"])
        except KeyError as exc:
            raise WorkflowError(
                f"A retrieval-unit embedding entry for {entry.get('stable retrieval identifier')} "
                "lacks the 'retrieval-unit embedding' field."
            ) from exc

        _require(
            len(vector) == contract["embedding dimension"] and entry.get("embedding dimension") == contract["embedding dimension"],
            "A retrieval-unit embedding does not match the declared embedding dimension.",
        )
        _require(
            entry.get("embedding space") == contract["embedding space"]
            and entry.get("representation version") == contract["representation version"],
            "A retrieval-unit embedding was produced outside the declared representation contract.",
        )
        _require(
            entry.get("provenance link") == unit["provenance_link"],
            f"The provenance link of {entry.get('stable retrieval identifier')} does not match the Stage B evidence.",
        )

    _require(manifest.get("index version") == fixture["index_version"], "The index manifest records another index version.")
    _require(
        manifest.get("the chunking configuration that realizes the retrieval-unit definition recorded in the retrieval contract")
        == configuration,
        "The index manifest records another chunking configuration.",
    )

    # Fix #5 (Logic #4): guard against a missing metadata binding key with WorkflowError.
    try:
        bindings = cast(list[dict], manifest["a stable retrieval identifier and provenance link for every retrieval unit"])
    except KeyError as exc:
        raise WorkflowError(
            "The index manifest lacks the 'a stable retrieval identifier and provenance link for every retrieval unit' field."
        ) from exc

    _require(
        [binding["stable retrieval identifier"] for binding in bindings]
        == [entry["stable retrieval identifier"] for entry in entries],
        "The index manifest lacks a metadata binding for at least one indexed retrieval unit.",
    )

    # Fix #3 (Logic #2): verify provenance links in the metadata bindings against Stage B evidence,
    # not just the stable retrieval identifier list.
    for binding, unit in zip(bindings, units):
        _require(
            binding.get("provenance link") == unit["provenance_link"],
            f"The provenance link in the index manifest for "
            f"{binding.get('stable retrieval identifier')} does not match the Stage B evidence.",
        )

    configurations = cast(list[dict], fixture["required_retrieval_configurations"])
    for required in configurations:
        identifier = cast(str, required["required_retrieval_configuration_id"])
        path = report_dir / STAGE_C1_DIRECTORY / f"{BINDING_CHECK_PREFIX}{identifier}.json"
        try:
            recorded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"Cannot read the recorded pre-use binding check for {identifier}: {exc}") from exc
        _require(isinstance(recorded, dict), f"The recorded pre-use binding check for {identifier} must be an object.")

        # Fix #4 (Logic #3): re-derive the full checked-bindings array and the required retrieval
        # configuration id; the previous code only re-derived outcome and failed_binding, so a
        # tampered provenance link or record id inside the binding check went undetected.
        checks, failed = _compare_bindings(fixture, manifest, required, report_dir)
        expected_outcome = "stale" if failed is not None else "admissible"
        _require(
            recorded.get("outcome") == expected_outcome
            and recorded.get("failed binding") == failed
            and recorded.get("checked bindings") == checks
            and recorded.get("required retrieval configuration id") == identifier,
            f"The recorded pre-use binding check for {identifier} does not match the recorded index manifest.",
        )

    return {
        "outcome": "passed",
        "index version": manifest["index version"],
        "verification boundary": "structural consistency; no retrieval execution and no relevance judgment",
    }
