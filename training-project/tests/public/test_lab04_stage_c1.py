"""Public tests for the Laboratory 04 Stage C1 embeddings-and-index slice."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from learning_project import lab04_index
from learning_project.cli import main
from learning_project.lab04 import prepare_boundary_comparison, record_boundary_decision
from learning_project.workflow import WorkflowError


CASES = Path(__file__).resolve().parents[2] / "cases" / "lab04"
STAGE_B_FIXTURE = CASES / "stage-b-fixture.json"
STAGE_C1_FIXTURE = CASES / "stage-c1-fixture.json"
REAL_MODEL_DIR = os.environ.get("LAB04_REAL_MODEL_DIR")


class _StubEncoder:
    """Deterministic stand-in for the declared local embedding model."""

    def __init__(self, **overrides: object) -> None:
        self.embedding_model = "course-test-model"
        self.model_revision = "revision-1"
        self.representation_version = "course-static-embed-v1"
        self.embedding_dimension = 256
        self.embedding_space = "course-test-model@revision-1/course-static-embed-v1"
        for key, value in overrides.items():
            setattr(self, key, value)

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < int(self.embedding_dimension):
            block = hashlib.sha256(digest + counter.to_bytes(2, "big")).digest()
            values.extend(round((byte / 255.0) * 2.0 - 1.0, 6) for byte in block)
            counter += 1
        return values[: int(self.embedding_dimension)]


class _LyingEncoder(_StubEncoder):
    """Declares the contract while returning vectors of another length."""

    def _vector(self, text: str) -> list[float]:
        return [0.5] * 8


def _write_stage_c1_fixture(directory: Path, encoder: _StubEncoder) -> Path:
    fixture = json.loads(STAGE_C1_FIXTURE.read_text(encoding="utf-8"))
    fixture["representation_contract"] = {
        "embedding model": encoder.embedding_model,
        "model revision": encoder.model_revision,
        "representation version": encoder.representation_version,
        "embedding dimension": encoder.embedding_dimension,
        "embedding space": encoder.embedding_space,
        "vector-similarity measure": "cosine similarity with the untransformed [-1, 1] score convention",
        "input normalization": "Unicode NFC followed by stripping leading and trailing whitespace; an empty normalized input is refused",
    }
    path = directory / "stage-c1-fixture.json"
    path.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    return path


def _stage_b_report(directory: Path) -> Path:
    report_dir = directory / "reports" / "lab04"
    prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
    record_boundary_decision(
        report_dir=report_dir,
        selected_chunking_configuration_id="sentence-pair-v1",
        rationale="The sentence-pair boundary rule preserves the originating-record relationship.",
        student="student-01",
        fixture_path=STAGE_B_FIXTURE,
    )
    return report_dir


def _prepare_embeddings(directory: Path, encoder: _StubEncoder) -> tuple[Path, Path]:
    report_dir = _stage_b_report(directory)
    fixture_path = _write_stage_c1_fixture(directory, encoder)
    lab04_index.prepare_retrieval_unit_embeddings(
        report_dir=report_dir,
        fixture_path=fixture_path,
        encoder=encoder,
    )
    return report_dir, fixture_path


class Lab04StageC1EmbeddingTests(unittest.TestCase):
    def test_prepare_retrieval_unit_embeddings_is_compatible_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir, _ = _prepare_embeddings(directory, _StubEncoder())
            artifact = json.loads(
                (report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_text(encoding="utf-8")
            )
            self.assertEqual(artifact["chunking configuration"], "sentence-pair-v1")
            self.assertEqual(
                [unit["stable retrieval identifier"] for unit in artifact["retrieval-unit embeddings"]],
                ["F-A", "F-B"],
            )
            for unit in artifact["retrieval-unit embeddings"]:
                self.assertEqual(len(unit["retrieval-unit embedding"]), 256)
                self.assertEqual(unit["embedding dimension"], 256)
                self.assertEqual(unit["embedding space"], _StubEncoder().embedding_space)
                self.assertIn("character_span", unit["provenance link"])
            first = (report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_bytes()

            second_report, _ = _prepare_embeddings(directory / "second", _StubEncoder())
            second = (second_report / "stage-c1" / "retrieval-unit-embeddings.json").read_bytes()
            self.assertEqual(first, second)

    def test_prepare_retrieval_unit_embeddings_refuses_an_encoder_outside_the_declared_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            fixture_path = _write_stage_c1_fixture(Path(temp), _StubEncoder())
            with self.assertRaisesRegex(WorkflowError, "representation contract"):
                lab04_index.prepare_retrieval_unit_embeddings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    encoder=_StubEncoder(embedding_space="other-model@revision-9/other-space"),
                )

    def test_prepare_retrieval_unit_embeddings_refuses_a_vector_of_another_length(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            fixture_path = _write_stage_c1_fixture(Path(temp), _StubEncoder())
            with self.assertRaisesRegex(WorkflowError, "embedding dimension"):
                lab04_index.prepare_retrieval_unit_embeddings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    encoder=_LyingEncoder(),
                )

    def test_prepare_retrieval_unit_embeddings_stops_when_the_local_model_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            with self.assertRaisesRegex(WorkflowError, "fetch-embedding-model"):
                lab04_index.prepare_retrieval_unit_embeddings(
                    report_dir=report_dir,
                    fixture_path=STAGE_C1_FIXTURE,
                    model_dir=Path(temp) / "absent-model",
                )

    def test_course_representation_contract_declares_the_pinned_local_embedding_model(self) -> None:
        fixture = json.loads(STAGE_C1_FIXTURE.read_text(encoding="utf-8"))
        contract = fixture["representation_contract"]
        self.assertEqual(contract["embedding model"], "minishlab/potion-base-8M")
        self.assertEqual(contract["model revision"], "bf8b056651a2c21b8d2565580b8569da283cab23")
        self.assertEqual(contract["embedding dimension"], 256)
        self.assertIn("potion-base-8M@", contract["embedding space"])
        self.assertEqual(len(fixture["declared_bindings"]), 5)


class Lab04StageC1IndexTests(unittest.TestCase):
    def test_prepare_vector_index_records_every_declared_binding_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            manifest_path = lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for binding in json.loads(fixture_path.read_text(encoding="utf-8"))["declared_bindings"]:
                self.assertIn(binding, manifest)
            self.assertEqual(manifest["index version"], "vector-index-course-seed-v1")
            self.assertEqual(len(manifest["a stable retrieval identifier and provenance link for every retrieval unit"]), 2)
            self.assertIn("complete for the declared chunking configuration", manifest["completeness status"])

            with self.assertRaisesRegex(WorkflowError, "already exists"):
                lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)

    def test_check_index_bindings_distinguishes_admissible_from_the_rebuild_condition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)

            admissible = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v1",
            )
            self.assertEqual(admissible["outcome"], "admissible")
            self.assertIsNone(admissible["failed binding"])

            stale = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v2",
            )
            self.assertEqual(stale["outcome"], "stale")
            self.assertEqual(stale["failed binding"], "the canonical knowledge collection version")
            self.assertIn("replacement index version", stale["rebuild condition"])

            with self.assertRaisesRegex(WorkflowError, "Unknown required retrieval configuration"):
                lab04_index.check_index_bindings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    required_retrieval_configuration_id="required-course-seed-v9",
                )

    def test_verify_stage_c1_rejects_a_tampered_retrieval_unit_embedding_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
            for required in ("required-course-seed-v1", "required-course-seed-v2"):
                lab04_index.check_index_bindings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    required_retrieval_configuration_id=required,
                )
            self.assertEqual(
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)["outcome"],
                "passed",
            )

            embeddings_path = report_dir / "stage-c1" / "retrieval-unit-embeddings.json"
            artifact = json.loads(embeddings_path.read_text(encoding="utf-8"))
            artifact["retrieval-unit embeddings"][0]["retrieval-unit embedding"] = [0.1, 0.2]
            embeddings_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "embedding dimension"):
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)


class Lab04StageC1CommandLineTests(unittest.TestCase):
    def test_binding_check_output_classifies_the_vector_index_not_its_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir, fixture_path = _prepare_embeddings(directory, _StubEncoder())
            self.assertEqual(
                main(["lab04", "prepare-index", "--report-dir", str(report_dir), "--fixture", str(fixture_path)]),
                0,
            )

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "lab04",
                            "check-index-bindings",
                            "--report-dir",
                            str(report_dir),
                            "--fixture",
                            str(fixture_path),
                            "--required-retrieval-configuration-id",
                            "required-course-seed-v2",
                        ]
                    ),
                    0,
                )

            self.assertIn(
                "The vector index identified by index version vector-index-course-seed-v1 is stale for required-course-seed-v2",
                output.getvalue(),
            )
            self.assertNotIn("The index version vector-index-course-seed-v1 is stale", output.getvalue())

    def test_cli_prepares_the_index_and_reports_both_binding_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir, fixture_path = _prepare_embeddings(directory, _StubEncoder())

            self.assertEqual(
                main(["lab04", "prepare-index", "--report-dir", str(report_dir), "--fixture", str(fixture_path)]),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "lab04",
                        "check-index-bindings",
                        "--report-dir",
                        str(report_dir),
                        "--fixture",
                        str(fixture_path),
                        "--required-retrieval-configuration-id",
                        "required-course-seed-v1",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "lab04",
                        "check-index-bindings",
                        "--report-dir",
                        str(report_dir),
                        "--fixture",
                        str(fixture_path),
                        "--required-retrieval-configuration-id",
                        "required-course-seed-v2",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(["lab04", "verify-stage-c1", "--report-dir", str(report_dir), "--fixture", str(fixture_path)]),
                0,
            )

    def test_cli_stops_when_the_mandatory_local_model_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir = _stage_b_report(directory)
            code = main(
                [
                    "lab04",
                    "prepare-embeddings",
                    "--report-dir",
                    str(report_dir),
                    "--model-dir",
                    str(directory / "absent-model"),
                ]
            )
            self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# Fix #1 (Security) + Fix #6 (Logic #5): digest enforcement and fetch file check
# ---------------------------------------------------------------------------

class Lab04StageC1SecurityTests(unittest.TestCase):
    """Tests for Fix #1 (Security) and Fix #6 (Logic #5).

    Fix #1: load_local_retrieval_unit_encoder must detect a swapped same-dimension
    model by verifying the recorded SHA-256 digest of model.safetensors before
    trusting the self-declared provenance metadata.

    Fix #6: fetch_embedding_model must not report success when the provenance
    records the correct revision but the model weights file is absent.
    """

    def _make_provenance(self, directory: Path, digest: str | None = None) -> None:
        """Write a minimal model-provenance.json under *directory*."""
        fixture = json.loads(STAGE_C1_FIXTURE.read_text(encoding="utf-8"))
        contract = fixture["representation_contract"]
        provenance: dict = {
            "embedding model": contract["embedding model"],
            "model revision": contract["model revision"],
            "representation version": contract["representation version"],
            "embedding dimension": contract["embedding dimension"],
            "embedding space": contract["embedding space"],
        }
        if digest is not None:
            provenance["model file digest"] = digest
        (directory / lab04_index.MODEL_PROVENANCE_FILENAME).write_text(
            json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
        )

    def test_fetch_embedding_model_refuses_provenance_only_directory(self) -> None:
        """A directory that holds only the provenance file (no weights) must not
        be returned as a successfully acquired model (Fix #6)."""
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "model"
            directory.mkdir()
            self._make_provenance(directory)
            # No model.safetensors written — provenance exists, weights absent.
            with self.assertRaisesRegex(WorkflowError, lab04_index.MODEL_WEIGHTS_FILENAME):
                lab04_index.fetch_embedding_model(
                    model_dir=directory, fixture_path=STAGE_C1_FIXTURE
                )

    def test_load_encoder_raises_workflow_error_for_digest_mismatch(self) -> None:
        """load_local_retrieval_unit_encoder must raise WorkflowError (not succeed
        silently) when the recorded digest does not match the actual weights file,
        catching a swapped same-dimension model (Fix #1)."""
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "model"
            directory.mkdir()
            weights_path = directory / lab04_index.MODEL_WEIGHTS_FILENAME
            weights_path.write_bytes(b"fake-model-weights-content")
            # Record the wrong digest — simulates a swapped model.
            self._make_provenance(directory, digest="0" * 64)
            with self.assertRaisesRegex(WorkflowError, "digest"):
                lab04_index.load_local_retrieval_unit_encoder(model_dir=directory)

    def test_load_encoder_raises_workflow_error_for_missing_weights_when_digest_recorded(self) -> None:
        """If the provenance records a digest but the weights file is gone, the
        loader must raise WorkflowError, not proceed to model2vec (Fix #1)."""
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "model"
            directory.mkdir()
            # Provenance with a digest, but no model.safetensors.
            self._make_provenance(directory, digest="a" * 64)
            with self.assertRaisesRegex(WorkflowError, lab04_index.MODEL_WEIGHTS_FILENAME):
                lab04_index.load_local_retrieval_unit_encoder(model_dir=directory)


# ---------------------------------------------------------------------------
# Fix #2 (Logic #1): _compare_bindings binding 2 and binding 5
# ---------------------------------------------------------------------------

class Lab04StageC1Binding2And5Tests(unittest.TestCase):
    """Tests for Fix #2 (Logic #1).

    Binding 2 required value must be derived from the Stage B boundary decision,
    not read back from the manifest (self-referential).  Binding 5 must compare
    the full per-unit provenance list, not a presence-only boolean.
    """

    def _full_pipeline(self, directory: Path) -> tuple[Path, Path]:
        report_dir, fixture_path = _prepare_embeddings(directory, _StubEncoder())
        lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
        return report_dir, fixture_path

    def test_check_index_bindings_detects_stale_when_manifest_chunking_config_differs_from_boundary_decision(self) -> None:
        """Tamper binding 2 in the manifest to claim a different chunking configuration
        than the boundary decision records; check_index_bindings must return stale (Fix #2)."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = self._full_pipeline(Path(temp))
            manifest_path = report_dir / "stage-c1" / "index-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            binding2_key = (
                "the chunking configuration that realizes the retrieval-unit definition "
                "recorded in the retrieval contract"
            )
            manifest[binding2_key] = "fixed-72-v1"  # different from boundary decision's sentence-pair-v1
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v1",
            )
            self.assertEqual(result["outcome"], "stale")
            self.assertEqual(result["failed binding"], binding2_key)

    def test_check_index_bindings_detects_stale_when_manifest_binding5_has_wrong_provenance_link(self) -> None:
        """Tamper binding 5 in the manifest to hold a non-empty list with bogus provenance
        links; check_index_bindings must return stale, not admissible (Fix #2)."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = self._full_pipeline(Path(temp))
            manifest_path = report_dir / "stage-c1" / "index-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            binding5_key = "a stable retrieval identifier and provenance link for every retrieval unit"
            manifest[binding5_key] = [
                {"stable retrieval identifier": "F-A", "provenance link": {"record_id": "BOGUS", "span": [0, 5]}},
                {"stable retrieval identifier": "F-B", "provenance link": {"record_id": "BOGUS", "span": [0, 5]}},
            ]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v1",
            )
            self.assertEqual(result["outcome"], "stale")
            self.assertEqual(result["failed binding"], binding5_key)


# ---------------------------------------------------------------------------
# Fix #3 (Logic #2): verify_stage_c1 must check provenance links in metadata bindings
# ---------------------------------------------------------------------------

class Lab04StageC1VerifyProvenanceLinkTests(unittest.TestCase):
    """Tests for Fix #3 (Logic #2).

    verify_stage_c1 must compare the provenance link for each metadata binding in
    the manifest against the Stage B evidence, not only the stable retrieval identifier.
    """

    def _full_pipeline_with_checks(self, directory: Path) -> tuple[Path, Path]:
        report_dir, fixture_path = _prepare_embeddings(directory, _StubEncoder())
        lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
        for required_id in ("required-course-seed-v1", "required-course-seed-v2"):
            lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id=required_id,
            )
        return report_dir, fixture_path

    def test_verify_stage_c1_rejects_tampered_manifest_metadata_binding_provenance_link(self) -> None:
        """A bogus provenance link inside the manifest's metadata binding must cause
        verify_stage_c1 to raise WorkflowError (Fix #3)."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = self._full_pipeline_with_checks(Path(temp))

            # Confirm baseline passes before tampering.
            self.assertEqual(
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)["outcome"],
                "passed",
            )

            manifest_path = report_dir / "stage-c1" / "index-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            binding5_key = "a stable retrieval identifier and provenance link for every retrieval unit"
            manifest[binding5_key][0]["provenance link"] = {
                "canonical_knowledge_record_id": "BOGUS",
                "record_version": 99,
                "character_span": "1-5",
            }
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "provenance link"):
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# Fix #4 (Logic #3): verify_stage_c1 must re-derive checked_bindings and config id
# ---------------------------------------------------------------------------

class Lab04StageC1VerifyBindingCheckDetailTests(unittest.TestCase):
    """Tests for Fix #4 (Logic #3).

    verify_stage_c1 must re-derive the full checked-bindings array and the
    required retrieval configuration id and compare them against the recorded
    binding-check file, not only outcome and failed_binding.
    """

    def _full_pipeline_with_checks(self, directory: Path) -> tuple[Path, Path]:
        report_dir, fixture_path = _prepare_embeddings(directory, _StubEncoder())
        lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
        for required_id in ("required-course-seed-v1", "required-course-seed-v2"):
            lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id=required_id,
            )
        return report_dir, fixture_path

    def test_verify_stage_c1_rejects_tampered_required_retrieval_configuration_id_in_binding_check(self) -> None:
        """Changing the required retrieval configuration id inside a recorded binding-check
        file must be detected by verify_stage_c1 (Fix #4)."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = self._full_pipeline_with_checks(Path(temp))

            check_path = report_dir / "stage-c1" / "binding-check-required-course-seed-v1.json"
            check_record = json.loads(check_path.read_text(encoding="utf-8"))
            check_record["required retrieval configuration id"] = "tampered-config-id"
            check_path.write_text(json.dumps(check_record, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "does not match the recorded index manifest"):
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)

    def test_verify_stage_c1_rejects_tampered_checked_bindings_required_value(self) -> None:
        """Replacing a required value inside the checked-bindings array of a recorded
        binding-check file must be detected by verify_stage_c1 (Fix #4)."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = self._full_pipeline_with_checks(Path(temp))

            check_path = report_dir / "stage-c1" / "binding-check-required-course-seed-v1.json"
            check_record = json.loads(check_path.read_text(encoding="utf-8"))
            # Tamper: change the required value of the first binding.
            check_record["checked bindings"][0]["required value"] = "tampered-collection-version"
            check_path.write_text(json.dumps(check_record, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "does not match the recorded index manifest"):
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# Fix #5 (Logic #4): raw KeyError / TypeError / ValueError → WorkflowError
# ---------------------------------------------------------------------------

class Lab04StageC1MalformedEvidenceTests(unittest.TestCase):
    """Tests for Fix #5 (Logic #4).

    Malformed evidence (missing keys, non-iterable fields, corrupt models) must
    raise WorkflowError, not propagate raw KeyError, TypeError, or ValueError.
    """

    def test_read_stage_c1_fixture_raises_workflow_error_for_non_iterable_declared_bindings(self) -> None:
        """A fixture with declared_bindings set to null must raise WorkflowError, not TypeError."""
        with tempfile.TemporaryDirectory() as temp:
            fixture = json.loads(STAGE_C1_FIXTURE.read_text(encoding="utf-8"))
            fixture["declared_bindings"] = None
            fixture_path = Path(temp) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture) + "\n", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                lab04_index._read_stage_c1_fixture(fixture_path)

    def test_verify_stage_c1_raises_workflow_error_for_missing_retrieval_unit_embedding_key(self) -> None:
        """An embedding entry that lacks the 'retrieval-unit embedding' key must cause
        verify_stage_c1 to raise WorkflowError, not a raw KeyError."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
            for required_id in ("required-course-seed-v1", "required-course-seed-v2"):
                lab04_index.check_index_bindings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    required_retrieval_configuration_id=required_id,
                )

            embeddings_path = report_dir / "stage-c1" / "retrieval-unit-embeddings.json"
            artifact = json.loads(embeddings_path.read_text(encoding="utf-8"))
            del artifact["retrieval-unit embeddings"][0]["retrieval-unit embedding"]
            embeddings_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

            with self.assertRaises(WorkflowError):
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)

    def test_check_index_bindings_raises_workflow_error_for_missing_manifest_key(self) -> None:
        """A manifest that is missing a declared binding key must cause check_index_bindings
        to return a graceful stale result (required != None) rather than raising a raw KeyError."""
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)

            manifest_path = report_dir / "stage-c1" / "index-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["the canonical knowledge collection version"]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            # Missing key → recorded_value = None (via .get()), required != None → stale, no exception.
            result = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v1",
            )
            self.assertEqual(result["outcome"], "stale")
            self.assertEqual(result["failed binding"], "the canonical knowledge collection version")


# ---------------------------------------------------------------------------
# Integration test: real local model
# ---------------------------------------------------------------------------

@unittest.skipUnless(REAL_MODEL_DIR, "LAB04_REAL_MODEL_DIR is not set")
class Lab04StageC1LocalModelTests(unittest.TestCase):
    def test_declared_local_model_reproduces_the_declared_dimension_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            lab04_index.prepare_retrieval_unit_embeddings(
                report_dir=report_dir,
                fixture_path=STAGE_C1_FIXTURE,
                model_dir=Path(REAL_MODEL_DIR),
            )
            artifact = json.loads(
                (report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [len(unit["retrieval-unit embedding"]) for unit in artifact["retrieval-unit embeddings"]],
                [256, 256],
            )


if __name__ == "__main__":
    unittest.main()
