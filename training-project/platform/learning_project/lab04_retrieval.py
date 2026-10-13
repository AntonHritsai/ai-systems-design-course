"""Laboratory 04 Stage C2 query-time ranked candidate outputs (not judgments)."""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import PureWindowsPath
import unicodedata
from contextlib import ExitStack
from pathlib import Path

import yaml

from .lab04 import DEFAULT_STAGE_B_FIXTURE, _read_fixture, _build_boundary_comparison
from .lab04_index import (DEFAULT_STAGE_C1_FIXTURE, verify_stage_c1, _read_stage_c1_fixture,
                          _representation_contract, _require_encoder_matches_contract,
                          load_local_retrieval_unit_encoder, _compare_bindings, _required_configuration)
from .workflow import WorkflowError

STAGE_C2_DIRECTORY = "stage-c2"
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
DEFAULT_STAGE_C2_FIXTURE = Path(__file__).resolve().parents[2] / "cases" / "lab04" / "stage-c2-fixture.json"
EXCLUDED_WORDS = ("a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "by", "with", "from", "is", "are", "it", "its", "how", "can", "which", "what", "that", "this")
STOP_WORDS = set(EXCLUDED_WORDS)


def _c2_configuration(path: Path) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read Stage C2 configuration: {exc}") from exc
    if not isinstance(config, dict) or config.get("schema_version") != "1.0" or config.get("result count k") != 1 or config.get("reranking candidate count") != 2 or config.get("tie order") != "stable retrieval identifier ascending" or config.get("excluded lexical function words") != list(EXCLUDED_WORDS) or config.get("lexical rule") != "lowercase exact alphabetic content-word overlap; distinct shared tokens counted once" or config.get("embedding rule") != "query encoding under the Stage C1 representation contract; exact cosine over every indexed unit" or config.get("hybrid rule") != "divide each independent ranking score by its ranking maximum, add by stable retrieval identifier; empty ranking contributes nothing" or config.get("reranking rule") != "cosine order over the first two lexical candidates only":
        raise WorkflowError("Incompatible Stage C2 retrieval configuration.")
    return config


def _words(text: str) -> set[str]:
    """Exact lowercase alphabetic content words; articles/prepositions excluded."""
    return set(re.findall(r"[a-z]+", text.lower())) - STOP_WORDS


def _context(report_dir: Path, b_fixture: Path, c_fixture: Path) -> tuple[dict, dict, list[dict]]:
    fixture = _read_fixture(b_fixture)
    expected = _build_boundary_comparison(fixture)
    try:
        actual = json.loads((report_dir / "stage-b" / "boundary-comparison.json").read_text())
        decision = yaml.safe_load((report_dir / "stage-b" / "boundary-decision.yaml").read_text())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise WorkflowError(f"Cannot read Stage B evidence: {exc}") from exc
    if actual != expected or not isinstance(decision, dict):
        raise WorkflowError("Stage B evidence does not match the supplied fixture.")
    selected = decision.get("selected chunking configuration")
    if decision.get("selected retrieval-unit definition") != f"source fragment under {selected}" or not decision.get("rationale"):
        raise WorkflowError("Malformed Stage B boundary decision.")
    units = next((x["source_fragments"] for x in expected["chunking_configuration_results"] if x["chunking_configuration_id"] == selected), None)
    if units is None:
        raise WorkflowError("Unknown Stage B chunking configuration.")
    try:
        verify_stage_c1(report_dir=report_dir, fixture_path=c_fixture)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        raise WorkflowError(f"Malformed Stage C1 evidence: {exc}") from exc
    try:
        artifact = json.loads((report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_text())
        manifest = json.loads((report_dir / "stage-c1" / "index-manifest.json").read_text())
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read Stage C1 evidence: {exc}") from exc
    if artifact.get("canonical knowledge collection version") != expected["canonical_knowledge_collection_version"] or artifact.get("chunking configuration") != selected:
        raise WorkflowError("Stage C1 embeddings do not match Stage B.")
    if manifest.get("indexed retrieval units") != [u["stable_retrieval_identifier"] for u in units]:
        raise WorkflowError("Malformed Stage C1 index membership.")
    entries = artifact.get("retrieval-unit embeddings")
    if not isinstance(entries, list) or len(entries) != len(units) or not all(isinstance(e, dict) for e in entries):
        raise WorkflowError("Malformed Stage C1 embeddings.")
    for entry, unit in zip(entries, units):
        if entry.get("stable retrieval identifier") != unit["stable_retrieval_identifier"] or entry.get("provenance link") != unit["provenance_link"]:
            raise WorkflowError("Stage C1 embeddings do not match Stage B provenance.")
    return fixture, artifact, units


class _WindowsFiles:
    """Win32 handles with no delete sharing; no path operation after opening a child."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CreateDirectoryW.argtypes = (wintypes.LPCWSTR, ctypes.c_void_p)
        self.kernel.CreateDirectoryW.restype = wintypes.BOOL
        self.kernel.GetFileInformationByHandleEx.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                               ctypes.c_void_p, wintypes.DWORD)
        self.kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
        self.kernel.WriteFile.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
        self.kernel.WriteFile.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.restype = wintypes.BOOL

    def _open(self, path, access, disposition, flags):
        handle = self.kernel.CreateFileW(str(path), access, 0x1 | 0x2, None, disposition, flags | 0x200000, None)
        if handle == self.wintypes.HANDLE(-1).value:
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return handle

    def open_directory(self, path):
        class AttributeTag(self.ctypes.Structure):
            _fields_ = [('attributes', self.wintypes.DWORD), ('tag', self.wintypes.DWORD)]
        handle = self._open(path, 0x80, 3, 0x02000000)  # FILE_READ_ATTRIBUTES; OPEN_EXISTING; BACKUP_SEMANTICS
        try:
            info = AttributeTag()
            if not self.kernel.GetFileInformationByHandleEx(handle, 9, self.ctypes.byref(info), self.ctypes.sizeof(info)):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            if info.attributes & 0x400 or not info.attributes & 0x10:
                raise OSError('Reparse point or non-directory in report path')
            return handle
        except BaseException:
            self.close(handle)
            raise

    def make_directory(self, path):
        if not self.kernel.CreateDirectoryW(str(path), None):
            error = self.ctypes.get_last_error()
            if error in (80, 183):
                raise FileExistsError(str(path))
            raise self.ctypes.WinError(error)

    def create_file(self, path):
        return self._open(path, 0x40000000, 1, 0)  # GENERIC_WRITE; CREATE_NEW; OPEN_REPARSE_POINT

    def write(self, handle, data):
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + 65536]
            written = self.wintypes.DWORD()
            if not self.kernel.WriteFile(handle, chunk, len(chunk), self.ctypes.byref(written), None):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            if not written.value:
                raise OSError('Zero-byte stage write')
            offset += written.value

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise self.ctypes.WinError(self.ctypes.get_last_error())


def _windows_filesystem():
    return _WindowsFiles()


def _write_stage_c2_windows(output, content, report_dir, api, stage_directory: str = STAGE_C2_DIRECTORY):
    """Hold every directory component without delete sharing until the exclusive write completes."""
    report = PureWindowsPath(report_dir.absolute() if isinstance(report_dir, Path) else report_dir)
    destination = PureWindowsPath(output.absolute() if isinstance(output, Path) else output)
    if (not report.is_absolute() or not report.drive or '..' in report.parts or
            '..' in destination.parts or
            destination.parent != report / stage_directory or
            destination.name in ('', '.', '..') or ':' in destination.name or
            destination.name.rstrip(' .') != destination.name or
            destination.stem.upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                           *(f'COM{i}' for i in range(1, 10)),
                                           *(f'LPT{i}' for i in range(1, 10))}):
        raise WorkflowError('Invalid Windows stage output path.')
    try:
        with ExitStack() as stack:
            current = PureWindowsPath(report.anchor)
            for component in (None, *report.parts[1:]):
                if component is not None:
                    current = current / component
                handle = api.open_directory(current)
                stack.callback(api.close, handle)
            stage = report / stage_directory
            try:
                api.make_directory(stage)
            except FileExistsError:
                pass
            stage_handle = api.open_directory(stage)
            stack.callback(api.close, stage_handle)
            file_handle = api.create_file(destination)
            stack.callback(api.close, file_handle)
            api.write(file_handle, content.encode('utf-8'))
    except OSError as exc:
        raise WorkflowError(f'Cannot securely create stage output at {output}: {exc}') from exc


def write_secure_stage_output(output: Path, content: str, report_dir: Path, stage_directory: str) -> None:
    """Create one report file under the named stage directory without path-following races."""
    if stage_directory in ("", ".", "..") or "/" in stage_directory or "\\" in stage_directory:
        raise WorkflowError("Invalid stage directory name.")
    _write_stage_c2_output(output, content, report_dir, stage_directory=stage_directory)


def _write_stage_c2_output(output: Path, content: str, report_dir: Path, stage_directory: str = STAGE_C2_DIRECTORY) -> None:
    """Create one report file once beneath directory descriptors, never following a path after validation."""
    if os.name == "nt":
        _write_stage_c2_windows(output, content, report_dir, _windows_filesystem(), stage_directory=stage_directory)
        return
    if (os.name != "posix" or not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW"))
            or not _OPEN_SUPPORTS_DIR_FD or os.mkdir not in os.supports_dir_fd):
        raise WorkflowError("Secure stage output creation is unavailable on this platform.")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        with ExitStack() as stack:
            parent = os.open("/", directory_flags)
            stack.callback(os.close, parent)
            for component in report_dir.absolute().parts[1:]:
                parent = os.open(component, directory_flags, dir_fd=parent)
                stack.callback(os.close, parent)
            try:
                os.mkdir(stage_directory, dir_fd=parent)
            except FileExistsError:
                pass
            stage = os.open(stage_directory, directory_flags, dir_fd=parent)
            stack.callback(os.close, stage)
            fd = os.open(output.name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                         0o666, dir_fd=stage)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
    except OSError as exc:
        raise WorkflowError(f"Cannot securely create stage output at {output}: {exc}") from exc


def execute_retrieval(*, report_dir: Path, case_id: str, configuration_id: str,
                      b_fixture_path: Path = DEFAULT_STAGE_B_FIXTURE,
                      c1_fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE,
                      c2_fixture_path: Path = DEFAULT_STAGE_C2_FIXTURE,
                      encoder=None, model_dir: Path | None = None,
                      required_retrieval_configuration_id: str = "required-course-seed-v1") -> Path:
    """Run one declared case/configuration against validated prepared evidence."""
    configuration = _c2_configuration(c2_fixture_path)
    fixture, artifact, units = _context(report_dir, b_fixture_path, c1_fixture_path)
    case = next((c for c in fixture["evaluation_cases"] if c["evaluation_case_id"] == case_id), None)
    if case is None or configuration_id not in fixture["retrieval_contract"]["compared retrieval configurations"]:
        raise WorkflowError("Unknown evaluation case or retrieval configuration.")
    operation = case["operation_input"]
    query = operation["text query"]
    version = operation["canonical knowledge collection version"]
    if version != artifact["canonical knowledge collection version"]:
        raise WorkflowError("Stale index for the declared collection version.")
    lexical = sorted([{"stable retrieval identifier": u["stable_retrieval_identifier"],
                       "score": len(_words(query) & _words(u["text"]))} for u in units],
                     key=lambda x: (-x["score"], x["stable retrieval identifier"]))
    lexical = [x for x in lexical if x["score"] > 0]
    embedding = []
    if configuration_id != "lexical retrieval":
        c_fixture = _read_stage_c1_fixture(c1_fixture_path)
        manifest = json.loads((report_dir / "stage-c1" / "index-manifest.json").read_text())
        required = _required_configuration(c_fixture, required_retrieval_configuration_id)
        _, failed = _compare_bindings(c_fixture, manifest, required, report_dir)
        if failed or required["the canonical knowledge collection version"] != version:
            raise WorkflowError("Stale index: pre-use binding check failed.")
        loaded = encoder if encoder is not None else load_local_retrieval_unit_encoder(model_dir)
        contract = _representation_contract(c_fixture)
        _require_encoder_matches_contract(loaded, contract)
        expected_vectors = loaded.encode([unit["text"] for unit in units])
        if expected_vectors != [e["retrieval-unit embedding"] for e in artifact["retrieval-unit embeddings"]]:
            raise WorkflowError("Stage C1 embeddings do not match the declared encoder and Stage B fragments.")
        normalized = unicodedata.normalize("NFC", query).strip()
        if not normalized:
            raise WorkflowError("Empty normalized text query.")
        try:
            vectors = loaded.encode([normalized])
            vector = vectors[0]
            if len(vectors) != 1 or len(vector) != contract["embedding dimension"] or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in vector) or not any(vector):
                raise WorkflowError("Incompatible query embedding.")
            norm = math.sqrt(sum(v*v for v in vector))
            candidate_ids = ({item["stable retrieval identifier"] for item in lexical[:2]}
                             if configuration_id == "lexical retrieval followed by embedding-based reranking" else None)
            for entry in artifact["retrieval-unit embeddings"]:
                if candidate_ids is not None and entry["stable retrieval identifier"] not in candidate_ids:
                    continue
                indexed = entry["retrieval-unit embedding"]
                if len(indexed) != len(vector) or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in indexed) or not any(indexed):
                    raise WorkflowError("Incompatible indexed retrieval-unit embedding.")
                score = sum(a*b for a, b in zip(vector, indexed)) / (norm * math.sqrt(sum(v*v for v in indexed)))
                embedding.append({"stable retrieval identifier": entry["stable retrieval identifier"], "score": score})
        except (IndexError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            raise WorkflowError(f"Incompatible query or indexed embedding: {exc}") from exc
        embedding.sort(key=lambda x: (-x["score"], x["stable retrieval identifier"]))
    ranking = embedding if configuration_id == "embedding-based retrieval" else lexical
    evidence = {"embedding ranking": embedding} if configuration_id == "embedding-based retrieval" else {"lexical ranking": lexical}
    if configuration_id == "hybrid retrieval":
        scores = {}
        for items in (lexical, embedding):
            if items:
                maximum = items[0]["score"]
                if maximum == 0:
                    raise WorkflowError("Cannot normalize a zero maximum score.")
                for item in items:
                    identifier = item["stable retrieval identifier"]
                    scores[identifier] = scores.get(identifier, 0.0) + item["score"] / maximum
        ranking = sorted(({"stable retrieval identifier": key, "score": value} for key, value in scores.items()),
                         key=lambda x: (-x["score"], x["stable retrieval identifier"]))
        evidence = {"lexical ranking": lexical, "embedding ranking": embedding, "hybrid ranking": ranking}
    if configuration_id == "lexical retrieval followed by embedding-based reranking":
        bounded = lexical[:configuration["reranking candidate count"]]
        by_embedding = {item["stable retrieval identifier"]: item["score"] for item in embedding}
        ranking = sorted(({"stable retrieval identifier": item["stable retrieval identifier"],
                           "score": by_embedding[item["stable retrieval identifier"]]} for item in bounded),
                         key=lambda x: (-x["score"], x["stable retrieval identifier"]))
        evidence = {"lexical ranking": lexical, "bounded candidate set": bounded, "reranked candidate set": ranking}
    by_id = {u["stable_retrieval_identifier"]: u for u in units}
    result = {
        "schema_version": "1.0", "evaluation case": case_id,
        "retrieval configuration": configuration_id, "text query": query,
        "canonical knowledge collection version": version,
        "ranking evidence": evidence,
        "ranked candidate output": [
            {"rank": i, "stable retrieval identifier": x["stable retrieval identifier"],
             "provenance link": by_id[x["stable retrieval identifier"]]["provenance_link"],
             "score": x["score"]} for i, x in enumerate(ranking[:configuration["result count k"]], 1)],
    }
    output = report_dir / STAGE_C2_DIRECTORY / f"{case_id.lower().replace(' ', '-')}-{configuration_id.lower().replace(' ', '-')}.json"
    _write_stage_c2_output(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n", report_dir)
    return output


def verify_stage_c2(*, report_dir: Path, b_fixture_path: Path = DEFAULT_STAGE_B_FIXTURE,
                    c1_fixture_path: Path = DEFAULT_STAGE_C1_FIXTURE,
                    c2_fixture_path: Path = DEFAULT_STAGE_C2_FIXTURE, encoder=None,
                    model_dir: Path | None = None) -> dict:
    """Independently derive every score and output from supplied cases and Stage B/C1 evidence."""
    settings = _c2_configuration(c2_fixture_path)
    fixture, artifact, units = _context(report_dir, b_fixture_path, c1_fixture_path)
    c1 = _read_stage_c1_fixture(c1_fixture_path)
    try:
        manifest = json.loads((report_dir / "stage-c1" / "index-manifest.json").read_text())
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read Stage C1 index manifest: {exc}") from exc
    required = _required_configuration(c1, "required-course-seed-v1")
    _, failed = _compare_bindings(c1, manifest, required, report_dir)
    versions = {case["operation_input"]["canonical knowledge collection version"]
                for case in fixture["evaluation_cases"]}
    if failed or versions != {required["the canonical knowledge collection version"]}:
        raise WorkflowError("Stale index: required-course-seed-v1 pre-use binding is not admissible.")
    declared = _representation_contract(c1)
    loaded = encoder if encoder is not None else load_local_retrieval_unit_encoder(model_dir)
    _require_encoder_matches_contract(loaded, declared)
    if loaded.encode([u["text"] for u in units]) != [e["retrieval-unit embedding"] for e in artifact["retrieval-unit embeddings"]]:
        raise WorkflowError("Stage C1 vectors differ from the declared encoder and Stage B fragments.")
    checks = 0
    for case in fixture["evaluation_cases"]:
        query = case["operation_input"]["text query"]
        words = _words(query)
        lex = [{"stable retrieval identifier": u["stable_retrieval_identifier"], "score": len(words.intersection(_words(u["text"]))) }
               for u in units]
        lex = sorted((r for r in lex if r["score"] > 0), key=lambda r: (-r["score"], r["stable retrieval identifier"]))
        query_vectors = loaded.encode([unicodedata.normalize("NFC", query).strip()])
        if len(query_vectors) != 1 or len(query_vectors[0]) != declared["embedding dimension"]:
            raise WorkflowError("Incompatible verification query embedding.")
        q = query_vectors[0]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in q) or not any(q):
            raise WorkflowError("Incompatible verification query embedding.")
        cos = []
        for entry in artifact["retrieval-unit embeddings"]:
            v = entry["retrieval-unit embedding"]
            if len(v) != len(q) or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in v) or not any(v):
                raise WorkflowError("Invalid indexed vector.")
            score = sum(a*b for a, b in zip(q, v)) / (math.sqrt(sum(a*a for a in q)) * math.sqrt(sum(b*b for b in v)))
            cos.append({"stable retrieval identifier": entry["stable retrieval identifier"], "score": score})
        cos.sort(key=lambda r: (-r["score"], r["stable retrieval identifier"]))
        by_id = {u["stable_retrieval_identifier"]: u["provenance_link"] for u in units}
        for configuration in fixture["retrieval_contract"]["compared retrieval configurations"]:
            if configuration == "lexical retrieval":
                evidence, order = {"lexical ranking": lex}, lex
            elif configuration == "embedding-based retrieval":
                evidence, order = {"embedding ranking": cos}, cos
            elif configuration == "hybrid retrieval":
                merged = {}
                for scores in (lex, cos):
                    if scores:
                        if scores[0]["score"] == 0:
                            raise WorkflowError("Cannot normalize zero maximum score.")
                        for r in scores:
                            key = r["stable retrieval identifier"]
                            merged[key] = merged.get(key, 0.0) + r["score"] / scores[0]["score"]
                order = sorted(({"stable retrieval identifier": key, "score": val} for key, val in merged.items()),
                               key=lambda r: (-r["score"], r["stable retrieval identifier"]))
                evidence = {"lexical ranking": lex, "embedding ranking": cos, "hybrid ranking": order}
            else:
                bounded = lex[:settings["reranking candidate count"]]
                lookup = {r["stable retrieval identifier"]: r["score"] for r in cos}
                order = sorted(({"stable retrieval identifier": r["stable retrieval identifier"], "score": lookup[r["stable retrieval identifier"]]} for r in bounded),
                               key=lambda r: (-r["score"], r["stable retrieval identifier"]))
                evidence = {"lexical ranking": lex, "bounded candidate set": bounded, "reranked candidate set": order}
            expected = {
                "schema_version": "1.0", "evaluation case": case["evaluation_case_id"],
                "retrieval configuration": configuration, "text query": query,
                "canonical knowledge collection version": case["operation_input"]["canonical knowledge collection version"],
                "ranking evidence": evidence,
                "ranked candidate output": [
                    {"rank": index, "stable retrieval identifier": r["stable retrieval identifier"],
                     "provenance link": by_id[r["stable retrieval identifier"]], "score": r["score"]}
                    for index, r in enumerate(order[:settings["result count k"]], 1)],
            }
            path = report_dir / STAGE_C2_DIRECTORY / f"{case['evaluation_case_id'].lower().replace(' ', '-')}-{configuration.lower().replace(' ', '-')}.json"
            try:
                actual = json.loads(path.read_text())
            except (OSError, ValueError) as exc:
                raise WorkflowError(f"Cannot read Stage C2 output {path}: {exc}") from exc
            if actual != expected:
                raise WorkflowError(f"Stage C2 output differs from independently derived ranking: {path}")
            checks += 1
    return {"outcome": "passed", "verified outputs": checks,
            "verification boundary": "ranking evidence only; no relevance judgment"}
