"""Refresh a disposable, upload-ready documentation snapshot; never edit sources."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import tempfile
import time
from urllib.parse import unquote
import zipfile


SCHEMA = "fpa_chatgpt_handout_v1"
MARKER = "HANDOUT_MANIFEST.json"
SUPPORT = (
    "docs/research/README_WORKFLOW_V2.md", "docs/research/FPA_NORTH_STAR.md",
    "docs/research/FPA_STATUS.md", "docs/research/FPA_DECISIONS.md",
    "docs/research/FPA_PROTOCOL_EXPLORATORY.md", "docs/research/FPA_HANDOFF.md",
    "docs/reference/BENCHMARK_REPORT.md", "docs/reference/FPA_HYPOTHESES.md",
    "docs/reference/CHRONOS_PHASE2.md", "docs/reference/CHRONOS_PHASE3_DESIGN.md",
    "codex-prompts/CURRENT_TASK.md",
)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", *args], cwd=root, text=True, encoding="utf-8"
    )


def document_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute() and ".." not in path.parts
        and not name.startswith(("docs/archive/", "docs/chatgpt-handout/", "docs/.chatgpt-handout-"))
        and (path.suffix == ".md" or (name.startswith(("docs/", "configs/")) and path.suffix in {".json", ".txt"}))
    )


def collect_documents(root: Path) -> list[str]:
    changed = git(root, "diff", "HEAD", "--name-only", "--diff-filter=ACMRT", "-z").split("\0")
    changed += git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    priority = {name: i for i, name in enumerate((
        "docs/research/FPA_HANDOFF.md", "docs/reference/FPA_INCREMENTAL_VALUE_AND_EVENT_SAMPLING.md",
        "docs/research/FPA_STATUS.md", "docs/research/FPA_DECISIONS.md",
        "docs/research/FPA_NORTH_STAR.md", "docs/research/FPA_PROTOCOL_EXPLORATORY.md",
    ))}
    selected = {p for p in changed + list(SUPPORT) if document_path(p) and (root / p).is_file()}
    pending = list(selected)
    while pending:
        source = pending.pop()
        if not source.endswith(".md"):
            continue
        if not (root / source).resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Source escapes repository: {source}")
        for link in markdown_links((root / source).read_text(encoding="utf-8")):
            target = local_target(source, link["target"])
            if target is None:
                continue
            name, _ = target
            path = root / name
            if document_path(name) and path.is_file() and path.resolve().is_relative_to(root.resolve()) and name not in selected:
                selected.add(name)
                pending.append(name)
    return sorted(selected,
                  key=lambda p: (priority.get(p, 99), p))


LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\((<[^>]+>|[^\s()]+(?:\([^)]*\)[^\s()]*)?)\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$")


def prose_lines(markdown):
    """Yield source offsets and lines outside fenced code."""
    fence, offset = None, 0
    for line in markdown.splitlines(keepends=True):
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif fence is None:
            yield offset, line
        offset += len(line)


def markdown_links(markdown):
    for offset, line in prose_lines(markdown):
        code = [m.span() for m in re.finditer(r"(`+).*?\1", line)]
        for match in LINK.finditer(line):
            if any(a <= match.start() < b for a, b in code):
                continue
            yield {"start": offset + match.start(), "end": offset + match.end(),
                   "label": match.group(1), "target": match.group(2).strip("<>"),
                   "original": match.group(0)}


def local_target(source, target):
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
        return None
    path, _, fragment = target.partition("#")
    path = unquote(path).replace("\\", "/")
    if not path:
        name = source
    elif path.startswith("/"):
        name = posixpath.normpath(path.lstrip("/"))
    else:
        name = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    return name, unquote(fragment)


def section_id(name):
    return "doc-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def heading_ids(markdown):
    counts = {}
    for offset, line in prose_lines(markdown):
        heading = HEADING.match(line)
        if heading:
            title = re.sub(r"<[^>]*>", "", heading.group(1))
            title = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
            count = counts.get(title, 0)
            counts[title] = count + 1
            yield offset, title + (f"-{count}" if count else "")


def render_document(markdown, source, sources, combined=False):
    edits = []
    for link in markdown_links(markdown):
        target = local_target(source, link["target"])
        if target is None:
            continue
        name, fragment = target
        if name in sources:
            if not combined:
                continue
            if name.endswith(".md"):
                anchor = section_id(name) + ("-" + fragment if fragment else "")
                replacement = f'[{link["label"]}](#{anchor})'
            else:
                replacement = f'{link["label"]} (ZIP: `repository/{name}`)'
        else:
            suffix = "#" + fragment if fragment else ""
            replacement = f'{link["label"]} (repository reference: `{name}{suffix}`)'
        edits.append((link["start"], link["end"], replacement))
    if combined:
        edits += [(offset, offset, f'<a id="{section_id(source)}-{slug}"></a>\n\n')
                  for offset, slug in heading_ids(markdown)]
    for start, end, replacement in sorted(edits, key=lambda item: (item[0], item[1]), reverse=True):
        markdown = markdown[:start] + replacement + markdown[end:]
    return markdown


def audit_links(root, names):
    checked, missing = 0, []
    for source in names:
        if not source.endswith(".md"):
            continue
        for link in markdown_links((root / source).read_text(encoding="utf-8-sig")):
            target = local_target(source, link["target"])
            if target is None:
                continue
            checked += 1
            name, fragment = target
            path = root / name
            if not path.resolve().is_relative_to(root.resolve()) or not path.exists():
                missing.append({"source": source, "target": link["target"], "reason": "missing file"})
            elif fragment and path.suffix == ".md":
                text = path.read_text(encoding="utf-8-sig")
                anchors = {slug for _, slug in heading_ids(text)}
                anchors.update(re.findall(r'<a\s+(?:id|name)=["\x27]([^"\x27]+)["\x27]', text))
                if fragment not in anchors:
                    missing.append({"source": source, "target": link["target"], "reason": "missing anchor"})
    return {"markdown_files": sum(n.endswith(".md") for n in names),
            "local_links_checked": checked, "broken_links": missing}


def document_group(name):
    if name.startswith(("docs/research/", "project-chatgpt/", "codex-prompts/")):
        return "Current research and workflow"
    return "References and supporting files"


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


def rename_directory(source: Path, destination: Path) -> None:
    """Tolerate brief Windows scanner locks; preserve data on lasting failure."""
    for attempt in range(8):
        try:
            source.rename(destination)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(.025 * 2**attempt, .2))


def build_handout(root: Path, review_assets=()) -> dict:
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
    validation = audit_links(root, sources)
    if validation["broken_links"]:
        raise ValueError(f'Canonical document links are invalid: {validation["broken_links"]}')
    source_names = set(sources)
    contents = {"repository/" + name: (
        render_document(data.decode("utf-8"), name, source_names).encode("utf-8")
        if name.endswith(".md") else data) for name, data in source_contents.items()}
    asset_metadata = {}
    for requested in review_assets:
        path = Path(requested)
        path = path if path.is_absolute() else root / path
        resolved = path.resolve()
        if (path.is_symlink() or not resolved.is_relative_to((root / "result").resolve())
                or resolved.suffix.lower() not in {".pdf", ".png", ".csv"} or not resolved.is_file()):
            raise ValueError("Review assets must be explicit PDF/PNG/CSV files under result/")
        name = "review-assets/" + resolved.name
        if name in contents:
            raise ValueError("Review asset names must be distinct")
        data = resolved.read_bytes()
        contents[name] = data
        asset_metadata[name] = {"source": resolved.relative_to(root).as_posix(),
                                "source_sha256": hashlib.sha256(data).hexdigest()}
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    branch, head = git(root, "branch", "--show-current").strip(), git(root, "rev-parse", "HEAD").strip()
    intro = (
        "# Latest ChatGPT handout\n\n"
        f"Snapshot: {utc}; branch: {branch}; existing HEAD: {head}.\n\n"
        "Upload CHATGPT_HANDOUT.md for one readable document, or the sibling "
        "chatgpt-handout.zip for source copies and hashes. Canonical originals "
        "remain in the repository. This generated folder is replaced at each "
        "completed prompt; do not edit copies here. Active documents and their "
        "linked references are included. Archives are excluded even when changed "
        "or linked by the documentation index. Archived documents, code, datasets and model "
        "outputs are not included except explicitly attached review assets; their references are shown as plain repository "
        "paths. Start with FPA_HANDOFF, the current scientific report and FPA_STATUS. "
        "Older reports are historical evidence. Document copies live under "
        "repository/; export-only links may differ from canonical sources. "
        "The manifest records canonical source hashes and generated copy hashes "
        "separately. The combined Markdown uses internal section links and names "
        "non-Markdown attachments available in the ZIP.\n\n"
    )
    index, combined = [intro], [intro, "## Contents\n\n"]
    if asset_metadata:
        links = "## Scientific review attachments\n\n" + "".join(
            f"- [{Path(name).name}](<{name}>)\n" for name in asset_metadata) + "\n"
        index.append(links)
        combined.append(links)
    for group in ("Current research and workflow", "References and supporting files"):
        index.append(f"## {group}\n\n")
        combined.append(f"### {group}\n\n")
        for name in sources:
            if document_group(name) != group:
                continue
            index.append(f"- [{name}](<repository/{name}>)\n")
            if name.endswith(".md"):
                combined.append(f"- [{name}](#{section_id(name)})\n")
            else:
                combined.append(f"- `{name}` (attachment in ZIP)\n")
        index.append("\n")
        combined.append("\n")
    contents["README.md"] = "".join(index).encode("utf-8")
    for name in sources:
        if name.endswith(".md"):
            combined += [f'\n\n---\n\n<a id="{section_id(name)}"></a>\n\nSource: `{name}`\n\n',
                         render_document(source_contents[name].decode("utf-8"), name, source_names, combined=True)]
    contents["CHATGPT_HANDOUT.md"] = "".join(combined).encode("utf-8")
    generated = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    manifest = {"schema": SCHEMA, "created_utc": utc, "branch": branch, "pre_user_commit_head": head,
                "source_files": {name: hashlib.sha256(source_contents[name]).hexdigest() for name in sources},
                "generated_files": generated,
                "review_assets": asset_metadata,
                "export_link_adjusted_copies": [name for name in sources if contents["repository/" + name] != source_contents[name]],
                "canonical_link_validation": validation}
    stage = Path(tempfile.mkdtemp(prefix=".chatgpt-handout-pending-", dir=docs))
    if stage.resolve().parent != docs.resolve():
        raise ValueError("Unexpected staging location")
    for name, data in contents.items():
        target = contained(stage, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (stage / MARKER).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validate_disposable(stage)
    exported_links = audit_links(stage, [name for name in contents if name.endswith(".md")])
    if exported_links["broken_links"]:
        raise ValueError(f'Export links are invalid: {exported_links["broken_links"]}')
    backup = None
    if previous_names is not None:
        backup = stage.with_name(stage.name.replace("pending", "previous"))
        if backup.resolve().parent != docs.resolve() or backup.exists():
            raise ValueError("Unsafe handout backup location")
        rename_directory(destination, backup)
    try:
        rename_directory(stage, destination)
    except OSError:
        if backup is not None:
            rename_directory(backup, destination)
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
    parser.add_argument("--check-links", action="store_true", help="Read-only audit of all canonical Markdown file/heading links")
    parser.add_argument("--review-assets", nargs="*", type=Path, default=[],
                        help="Explicit current PDF/PNG/CSV artifacts under result/ to attach; no archive scanning")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.check_links:
        names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
        result = audit_links(root, sorted({n for n in names if n.endswith(".md") and (root / n).is_file()}))
        print(json.dumps(result, indent=2))
        raise SystemExit(bool(result["broken_links"]))
    print(json.dumps(build_handout(root, args.review_assets), indent=2))
