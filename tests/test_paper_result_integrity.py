import hashlib
import json
from pathlib import Path

import validate_paper_repository


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "paper_results_manifest.json"
IMMUTABLE_RESULT_DIRECTORIES = (
    "results_paper_final/formal_sgct_signature_sensitivity",
    "results_paper_final/formal_main_scalability_uniform",
    "results_paper_final/formal_id_length_sweep",
    "results_paper_final/formal_experiment10_algorithm_comparison",
    "results_paper_final/formal_experiment13_sgct_signature_grouping",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_paper_result_manifest_covers_and_verifies_immutable_allowlist():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["algorithm"] == "sha256"
    assert tuple(manifest["immutable_directories"]) == IMMUTABLE_RESULT_DIRECTORIES

    expected_paths = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for directory in IMMUTABLE_RESULT_DIRECTORIES
        for path in (REPOSITORY_ROOT / directory).rglob("*")
        if path.is_file()
    }
    entries = manifest["files"]
    recorded_paths = {entry["path"] for entry in entries}
    assert recorded_paths == expected_paths
    assert len(recorded_paths) == len(entries)

    immutable_roots = tuple((REPOSITORY_ROOT / path).resolve() for path in IMMUTABLE_RESULT_DIRECTORIES)
    for entry in entries:
        assert not Path(entry["path"]).is_absolute()
        result_path = (REPOSITORY_ROOT / entry["path"]).resolve()
        assert any(result_path.is_relative_to(root) for root in immutable_roots)
        assert result_path.stat().st_size == entry["bytes"]
        assert _sha256(result_path) == entry["sha256"]


def test_repository_validator_reports_no_paper_alignment_errors():
    assert validate_paper_repository.run_checks() == []
