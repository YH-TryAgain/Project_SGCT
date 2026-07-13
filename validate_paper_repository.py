"""Read-only validation of the public SGCT paper repository."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Iterable

from algorithm_base_config import ALGORITHM_LIBRARY, DISPLAY_NAMES, PAPER_ALGORITHMS
from formal_experiment import PAPER_EXPERIMENTS, PAPER_EXPERIMENT_RESULT_DIRS
from generate_paper_tables import RAW_SOURCES, validate_input_sources


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "paper_results_manifest.json"
EXPECTED_ALGORITHMS = [
    "SGCT",
    "DRCT",
    "LAPCT",
    "EMDT",
    "DQTA",
    "EAQ-CBB",
    "NLHQT(n=2)",
]
EXPECTED_RESULTS = tuple(
    f"results_paper_final/{name}"
    for name in (
        "formal_sgct_signature_sensitivity",
        "formal_main_scalability_uniform",
        "formal_id_length_sweep",
        "formal_experiment10_algorithm_comparison",
        "formal_experiment13_sgct_signature_grouping",
    )
)
PUBLIC_DOCUMENTS = ("README.md", "REPRODUCIBILITY.md", "FORMAL_EXPERIMENTS.md")
REMOVED_ROOT_PATHS = (
    ".vscode",
    "old_save",
    "results",
    "BGVT.py",
    "BGVT_Final.py",
    "DL_PCT_Final copy.py",
    "FHS_RAC.py",
    "HT" + "_EEAC.py",
    "ICT.py",
    "SD_CGQT.py",
    "SUBF_CGDFSA.py",
    "Exp1.py",
    "Exp2.py",
    "Exp3.py",
    "Exp4.py",
    "exp5.py",
    "exp6.py",
    "DRCT_final.py",
    "DRCT_strict.py",
    "OCG" + "_HLCT.py",
    "OCG" + "_HLCT_PB.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_errors() -> list[str]:
    if not MANIFEST.is_file():
        return ["paper_results_manifest.json is missing"]
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    if data.get("algorithm") != "sha256":
        errors.append("manifest algorithm is not sha256")
    if tuple(data.get("immutable_directories", [])) != EXPECTED_RESULTS:
        errors.append("manifest immutable-directory allowlist differs")
    expected_files = {
        path.relative_to(ROOT).as_posix()
        for relative in EXPECTED_RESULTS
        for path in (ROOT / relative).rglob("*")
        if path.is_file()
    }
    entries = data.get("files", [])
    recorded = {entry.get("path") for entry in entries}
    if len(recorded) != len(entries) or recorded != expected_files:
        errors.append("manifest file set differs from immutable directories")
        return errors
    immutable_roots = tuple((ROOT / relative).resolve() for relative in EXPECTED_RESULTS)
    for entry in entries:
        relative = Path(entry["path"])
        if relative.is_absolute():
            errors.append(f"absolute manifest path: {entry['path']}")
            continue
        path = (ROOT / relative).resolve()
        if not any(path.is_relative_to(item) for item in immutable_roots):
            errors.append(f"manifest path outside allowlist: {entry['path']}")
        elif path.stat().st_size != entry["bytes"]:
            errors.append(f"byte-count mismatch: {entry['path']}")
        elif _sha256(path) != entry["sha256"]:
            errors.append(f"SHA-256 mismatch: {entry['path']}")
    return errors


def _algorithm_errors() -> list[str]:
    errors = []
    if PAPER_ALGORITHMS != EXPECTED_ALGORITHMS:
        errors.append("PAPER_ALGORITHMS is not the exact seven-protocol order")
    if list(ALGORITHM_LIBRARY) != EXPECTED_ALGORITHMS:
        errors.append("ALGORITHM_LIBRARY is not limited to the paper algorithms")
    if ALGORITHM_LIBRARY.get("SGCT", {}).get("class", object).__module__ != "SGCT":
        errors.append("SGCT is not implemented by SGCT.py")
    for excluded in ("HT" + "-EEAC", "HT" + "_EEAC", "HLCT" + "-Base"):
        if excluded in PAPER_ALGORITHMS or excluded in ALGORITHM_LIBRARY:
            errors.append(f"excluded algorithm remains registered: {excluded}")
    if DISPLAY_NAMES.get("DQTA(k_max=3)") != "DQTA":
        errors.append("DQTA display mapping is incorrect")
    if DISPLAY_NAMES.get("EAQ_CBB") != "EAQ-CBB":
        errors.append("EAQ-CBB display mapping is incorrect")
    if DISPLAY_NAMES.get("NLHQT(n=2)") != "NLHQT(n=2)":
        errors.append("NLHQT display mapping is incorrect")
    return errors


def _experiment_errors() -> list[str]:
    errors = []
    if tuple(PAPER_EXPERIMENT_RESULT_DIRS.values()) != EXPECTED_RESULTS:
        errors.append("paper experiment result mapping differs from the allowlist")
    forbidden = ("ber", "energy", "hlct", "ovg", "fcw", "check_gating")
    for name in PAPER_EXPERIMENTS:
        if any(marker in name.lower() for marker in forbidden):
            errors.append(f"non-paper experiment is registered: {name}")
    errors.extend(validate_input_sources())
    for name, path in RAW_SOURCES.items():
        if not path.is_file():
            errors.append(f"processing input is missing ({name}): {path.as_posix()}")
    return errors


def _result_directory_errors() -> list[str]:
    root = ROOT / "results_paper_final"
    actual = {
        path.relative_to(ROOT).as_posix() for path in root.iterdir() if path.is_dir()
    }
    expected = set(EXPECTED_RESULTS)
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        return [f"paper-result directory set differs; extra={extra}, missing={missing}"]
    return []


def _removed_path_errors() -> list[str]:
    return [f"historical path remains: {path}" for path in REMOVED_ROOT_PATHS if (ROOT / path).exists()]


def _public_document_errors() -> list[str]:
    errors = []
    forbidden_phrases = (
        "Signature" + "-Guided Collision Tree",
        "Sparse Signature" + "-Guided",
        "HLCT" + "-Base",
        "HT" + "-EEAC",
    )
    for relative in PUBLIC_DOCUMENTS:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"public document is missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8-sig")
        for phrase in forbidden_phrases:
            if phrase in text:
                errors.append(f"{relative} contains superseded paper term: {phrase}")
    return errors


def _text_files() -> Iterable[Path]:
    suffixes = {".py", ".md", ".txt", ".json", ".ini", ".yml", ".yaml"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        relative = path.relative_to(ROOT)
        if any(
            part in {".git", ".pytest_cache", "results_paper_final", "__pycache__"}
            for part in relative.parts
        ):
            continue
        if relative.parts[:2] == ("docs", "superpowers"):
            continue
        yield path


def _absolute_path_errors() -> list[str]:
    errors = []
    drive_pattern = re.compile("(?<![A-Za-z])[A-Za-z]:" + r"[\\/]")
    unix_markers = ("/" + "home/", "/" + "Users/")
    for path in _text_files():
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if drive_pattern.search(text) or any(marker in text for marker in unix_markers):
            errors.append(f"hard-coded absolute path in {path.relative_to(ROOT).as_posix()}")
    return errors


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("immutable result manifest", _manifest_errors),
    ("seven paper algorithms", _algorithm_errors),
    ("paper experiment configuration", _experiment_errors),
    ("exact paper-result directory set", _result_directory_errors),
    ("historical path removal", _removed_path_errors),
    ("paper-facing documentation", _public_document_errors),
    ("portable repository paths", _absolute_path_errors),
)


def run_checks() -> list[str]:
    errors = []
    for _, check in CHECKS:
        errors.extend(check())
    return errors


def main() -> None:
    errors = []
    for name, check in CHECKS:
        check_errors = check()
        if check_errors:
            print(f"FAIL: {name}")
            for error in check_errors:
                print(f"  - {error}")
            errors.extend(check_errors)
        else:
            print(f"PASS: {name}")
    if errors:
        print(f"Repository validation failed with {len(errors)} issue(s).")
        raise SystemExit(1)
    print("PASS: repository matches the submitted SGCT manuscript.")


if __name__ == "__main__":
    main()
