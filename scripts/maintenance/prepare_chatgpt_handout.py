"""Refresh a disposable, upload-ready documentation snapshot; never edit sources."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile


SCHEMA = "fpa_chatgpt_handout_v1"
MARKER = "HANDOUT_MANIFEST.json"
SUPPORT = (
    "AGENTS.md", "README.md", "README_CHRONOS.md", "docs/PROJECT_STRUCTURE.md",
    "tests/README.md", "docs/CHRONOS_PHASE1.md", "docs/CHRONOS_PHASE2.md",
    "docs/CHRONOS_PHASE3_DESIGN.md",
    "docs/future works/FPA_CHRONOS_RESEARCH_PLAN (1).md",
    "docs/research/README_WORKFLOW_V2.md", "docs/research/FPA_NORTH_STAR.md",
    "docs/research/FPA_STATUS.md", "docs/research/FPA_DECISIONS.md",
    "docs/research/FPA_PROTOCOL_EXPLORATORY.md", "docs/research/FPA_HYPOTHESES.md",
    "docs/research/FPA_TECHNICAL_GATES.md", "docs/research/FPA_REFERENCES.md",
    "docs/research/FPA_HANDOFF.md",
)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", *args], cwd=root, text=True, encoding="utf-8"
    )


def document_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute() and ".." not in path.parts
        and not name.startswith(("docs/chatgpt-handout/", "docs/.chatgpt-handout-"))
        and (path.suffix == ".md" or (name.startswith("docs/") and path.suffix in {".json", ".txt"}))
    )


def collect_documents(root: Path) -> list[str]:
    changed = git(root, "diff", "--name-only", "--diff-filter=ACMRT", "-z").split("\0")
    changed += git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    priority = {name: i for i, name in enumerate((
        "docs/research/FPA_HANDOFF.md", "docs/research/BENCHMARK_REPORT.md",
        "docs/research/FPA_STATUS.md", "docs/research/FPA_DECISIONS.md",
        "docs/research/FPA_NORTH_STAR.md", "docs/research/FPA_PROTOCOL_EXPLORATORY.md",
    ))}
    return sorted({p for p in changed + list(SUPPORT) if document_path(p) and (root / p).is_file()},
                  key=lambda p: (priority.get(p, 99), p))


def contained(directory: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError(f"Unsafe managed path: {name}")
    path = directory.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError(f"Managed path escapes its folder: {name}")
    return path


def validate_disposable(directory: Path) -> list[str]:
    if directory.is_symlink():
        raise ValueError("Handout folder must not be a symlink")
    marker = directory / MARKER
    if not marker.is_file():
        raise ValueError("Refusing to refresh an existing folder without a handout manifest")
    manifest = json.loads(marker.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unrecognized handout manifest; source preserved")
    managed = manifest["generated_files"]
    for name in managed:
        contained(directory, name)
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Refusing a symlink inside the disposable handout")
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(managed) | {MARKER}:
        raise ValueError("Handout contains unrecognized or missing files; preserve it for inspection")
    for name, digest in manifest["generated_files"].items():
        if hashlib.sha256(contained(directory, name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Handout copy was manually changed; preserve it: {name}")
    return list(managed) + [MARKER]


def remove_managed(directory: Path, names: list[str]) -> None:
    """Delete only the exact validated generated files, with no recursive delete."""
    for name in names:
        contained(directory, name).unlink()
    for child in sorted((p for p in directory.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        child.rmdir()
    directory.rmdir()


def build_handout(root: Path) -> dict:
    root = root.resolve()
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    if docs.resolve() != root / "docs":
        raise ValueError("Docs folder resolves outside the repository")
    destination = docs / "chatgpt-handout"
    if destination.resolve() != root / "docs/chatgpt-handout":
        raise ValueError("Handout target resolves outside its dedicated location")
    previous_names = validate_disposable(destination) if destination.exists() else None
    sources = collect_documents(root)
    source_contents = {}
    for name in sources:
        source = root / name
        if not source.resolve().is_relative_to(root):
            raise ValueError(f"Source escapes repository: {name}")
        source_contents[name] = source.read_bytes()
    contents = {"repository/" + name: data for name, data in source_contents.items()}
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    branch, head = git(root, "branch", "--show-current").strip(), git(root, "rev-parse", "HEAD").strip()
    intro = (
        "# Latest ChatGPT handout\n\n"
        f"Snapshot: {utc}; branch: {branch}; existing HEAD: {head}.\n\n"
        "Upload CHATGPT_HANDOUT.md for one readable document, or the sibling "
        "chatgpt-handout.zip for source copies and hashes. Canonical originals "
        "remain in the repository. This generated folder is replaced at each "
        "completed prompt; do not edit copies here. Source-relative links refer "
        "to the original repository. Code, datasets and model outputs are not "
        "included. Start with FPA_HANDOFF, BENCHMARK_REPORT and FPA_STATUS; "
        "older reports are historical evidence. Source copies live under repository/. Changed/new documents "
        "plus historical context are listed below.\n\n"
    )
    contents["README.md"] = (intro + "\n".join(f"- {name}" for name in sources) + "\n").encode()
    combined = [intro]
    for name in sources:
        if name.endswith(".md"):
            combined += [f"\n\n---\n\nSource: {name}\n\n", source_contents[name].decode("utf-8")]
    contents["CHATGPT_HANDOUT.md"] = "".join(combined).encode("utf-8")
    generated = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    manifest = {"schema": SCHEMA, "created_utc": utc, "branch": branch, "pre_user_commit_head": head,
                "source_files": {name: hashlib.sha256(source_contents[name]).hexdigest() for name in sources}, "generated_files": generated}
    stage = Path(tempfile.mkdtemp(prefix=".chatgpt-handout-pending-", dir=docs))
    if stage.resolve().parent != docs.resolve():
        raise ValueError("Unexpected staging location")
    for name, data in contents.items():
        target = contained(stage, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (stage / MARKER).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validate_disposable(stage)
    backup = None
    if previous_names is not None:
        backup = stage.with_name(stage.name.replace("pending", "previous"))
        if backup.resolve().parent != docs.resolve() or backup.exists():
            raise ValueError("Unsafe handout backup location")
        destination.rename(backup)
    try:
        stage.rename(destination)
    except OSError:
        if backup is not None:
            backup.rename(destination)
        raise
    if backup is not None:
        remove_managed(backup, previous_names)
    archive = docs / "chatgpt-handout.zip"
    archive_tmp = docs / ".chatgpt-handout.zip.tmp"
    with zipfile.ZipFile(archive_tmp, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(destination))
    archive_tmp.replace(archive)
    return {"directory": str(destination), "archive": str(archive), "source_documents": len(sources)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build_handout(Path(__file__).resolve().parents[2]), indent=2))
