import json
from pathlib import Path

import pytest

import prepare_chatgpt_handout as handout


def setup_sources(root, monkeypatch):
    (root / "docs").mkdir()
    source = root / "docs/current.md"
    source.write_text("Current science\n", encoding="utf-8")
    monkeypatch.setattr(handout, "collect_documents", lambda _: ["docs/current.md"])
    monkeypatch.setattr(handout, "git", lambda *args: "test-head\n")
    return source


def test_refresh_replaces_generated_copies_and_preserves_canonical_sources(tmp_path, monkeypatch):
    source = setup_sources(tmp_path, monkeypatch)
    handout.build_handout(tmp_path)
    source.write_text("New science\n", encoding="utf-8")
    handout.build_handout(tmp_path)
    target = tmp_path / "docs/chatgpt-handout/repository/docs/current.md"
    assert target.read_text() == source.read_text() == "New science\n"
    assert (tmp_path / "docs/chatgpt-handout.zip").is_file()
    assert not list((tmp_path / "docs").glob(".chatgpt-handout-previous-*"))


def test_upload_index_does_not_replace_repository_readme(tmp_path, monkeypatch):
    setup_sources(tmp_path, monkeypatch)
    readme = tmp_path / "README.md"
    readme.write_text("Original repository README\n")
    monkeypatch.setattr(handout, "collect_documents", lambda _: ["README.md", "docs/current.md"])
    handout.build_handout(tmp_path)
    copied = tmp_path / "docs/chatgpt-handout/repository/README.md"
    assert copied.read_bytes() == readme.read_bytes()
    assert "Original repository README" in (tmp_path / "docs/chatgpt-handout/CHATGPT_HANDOUT.md").read_text()


def test_refresh_preserves_unrecognized_user_documents(tmp_path, monkeypatch):
    setup_sources(tmp_path, monkeypatch)
    handout.build_handout(tmp_path)
    unexpected = tmp_path / "docs/chatgpt-handout/USER_NOTES.md"
    unexpected.write_text("Keep my notes\n")
    with pytest.raises(ValueError, match="unrecognized"):
        handout.build_handout(tmp_path)
    assert unexpected.read_text() == "Keep my notes\n"


def test_manifest_cannot_delete_paths_outside_generated_folder(tmp_path, monkeypatch):
    source = setup_sources(tmp_path, monkeypatch)
    handout.build_handout(tmp_path)
    marker = tmp_path / "docs/chatgpt-handout" / handout.MARKER
    manifest = json.loads(marker.read_text())
    manifest["generated_files"]["../current.md"] = "invalid"
    marker.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsafe"):
        handout.build_handout(tmp_path)
    assert source.read_text() == "Current science\n"


def test_export_follows_document_links_and_rewrites_combined_targets(tmp_path, monkeypatch):
    (tmp_path / "docs/guides").mkdir(parents=True)
    (tmp_path / "configs").mkdir()
    (tmp_path / "code").mkdir()
    original = (
        "# Start\n\n[Guide](<guides/Next (1).md#details>)\n"
        "[Settings](../configs/example.json)\n[Implementation](../code/example.py)\n"
        "[Website](https://example.org/reference)\n"
        "`[inline example](missing.md)`\n\n"
        "```markdown\n[code example](also-missing.md)\n```\n"
    )
    (tmp_path / "docs/current.md").write_text(original, encoding="utf-8")
    (tmp_path / "docs/guides/Next (1).md").write_text("# Details\n\n[More](deeper.md)\n")
    (tmp_path / "docs/guides/deeper.md").write_text("# More\n")
    (tmp_path / "configs/example.json").write_text('{"frozen": true}\n')
    (tmp_path / "code/example.py").write_text("# Repository-only implementation\n")

    def fake_git(root, *args):
        return "docs/current.md\0" if args[0] == "diff" else "test-head\n" if args[0] in {"branch", "rev-parse"} else ""

    monkeypatch.setattr(handout, "git", fake_git)
    handout.build_handout(tmp_path)
    folder = tmp_path / "docs/chatgpt-handout"
    manifest = json.loads((folder / handout.MARKER).read_text())
    assert set(manifest["source_files"]) == {
        "docs/current.md", "docs/guides/Next (1).md", "docs/guides/deeper.md", "configs/example.json",
    }
    combined = (folder / "CHATGPT_HANDOUT.md").read_text()
    assert f'[Guide](#{handout.section_id("docs/guides/Next (1).md")}-details)' in combined
    assert '[Website](https://example.org/reference)' in combined
    assert "ZIP: `repository/configs/example.json`" in combined
    assert "repository reference: `code/example.py`" in combined
    assert "`[inline example](missing.md)`" in combined
    assert "[code example](also-missing.md)" in combined
    assert (tmp_path / "docs/current.md").read_text() == original
    assert manifest["export_link_adjusted_copies"] == ["docs/current.md"]
    exported_names = [p.relative_to(folder).as_posix() for p in folder.rglob("*.md")]
    assert handout.audit_links(folder, exported_names)["broken_links"] == []


def test_combined_heading_links_are_unique_across_documents(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    for name in ("a", "b"):
        (tmp_path / f"docs/{name}.md").write_text(
            "# Same title\n\n## Details\n\n## Details\n\n[Second section](#details-1)\n"
        )
    monkeypatch.setattr(handout, "collect_documents", lambda _: ["docs/a.md", "docs/b.md"])
    monkeypatch.setattr(handout, "git", lambda *args: "test-head\n")
    handout.build_handout(tmp_path)
    combined = (tmp_path / "docs/chatgpt-handout/CHATGPT_HANDOUT.md").read_text()
    for name in ("a", "b"):
        anchor = handout.section_id(f"docs/{name}.md") + "-details-1"
        assert f'<a id="{anchor}"></a>' in combined
        assert f"[Second section](#{anchor})" in combined
    assert handout.audit_links(tmp_path / "docs/chatgpt-handout", ["CHATGPT_HANDOUT.md"])["broken_links"] == []


def test_broken_canonical_link_preserves_previous_export(tmp_path, monkeypatch):
    source = setup_sources(tmp_path, monkeypatch)
    handout.build_handout(tmp_path)
    previous = tmp_path / "docs/chatgpt-handout/CHATGPT_HANDOUT.md"
    before = previous.read_bytes()
    source.write_text("[Missing document](absent.md)\n")
    with pytest.raises(ValueError, match="Canonical document links"):
        handout.build_handout(tmp_path)
    assert previous.read_bytes() == before
    assert source.read_text() == "[Missing document](absent.md)\n"


def test_archives_are_excluded_even_when_changed_and_linked(tmp_path, monkeypatch):
    (tmp_path / "docs/archive").mkdir(parents=True)
    (tmp_path / "docs/reference").mkdir()
    (tmp_path / "docs/current.md").write_text(
        "# Current\n\n[Old plan](archive/old.md)\n[Method](reference/method.md)\n"
    )
    (tmp_path / "docs/archive/old.md").write_text("# Superseded instructions must stay archived\n")
    (tmp_path / "docs/reference/method.md").write_text("# Required scientific method\n")

    def fake_git(root, *args):
        if args[0] == "diff":
            return "docs/current.md\0docs/archive/old.md\0"
        if args[0] in {"branch", "rev-parse"}:
            return "test-head\n"
        return ""

    monkeypatch.setattr(handout, "git", fake_git)
    handout.build_handout(tmp_path)
    folder = tmp_path / "docs/chatgpt-handout"
    manifest = json.loads((folder / handout.MARKER).read_text())
    assert set(manifest["source_files"]) == {"docs/current.md", "docs/reference/method.md"}
    combined = (folder / "CHATGPT_HANDOUT.md").read_text()
    assert "Superseded instructions must stay archived" not in combined
    assert "Required scientific method" in combined
    assert "repository reference: `docs/archive/old.md`" in combined
    assert handout.audit_links(folder, ["CHATGPT_HANDOUT.md", "README.md"])["broken_links"] == []


def test_explicit_scientific_assets_are_hashed_attached_and_refreshable(tmp_path, monkeypatch):
    setup_sources(tmp_path, monkeypatch)
    (tmp_path / "result/pilot").mkdir(parents=True)
    asset = tmp_path / "result/pilot/figures.pdf"
    asset.write_bytes(b"%PDF-test scientific review")
    handout.build_handout(tmp_path, [asset])
    folder = tmp_path / "docs/chatgpt-handout"
    assert (folder / "review-assets/figures.pdf").read_bytes() == asset.read_bytes()
    marker = json.loads((folder / handout.MARKER).read_text())
    assert marker["review_assets"]["review-assets/figures.pdf"]["source"] == "result/pilot/figures.pdf"
    assert handout.audit_links(folder, ["README.md", "CHATGPT_HANDOUT.md"])["broken_links"] == []
    with pytest.raises(ValueError, match="under result"):
        handout.build_handout(tmp_path, [tmp_path / "docs/current.md"])
    assert (folder / "review-assets/figures.pdf").exists()
    handout.build_handout(tmp_path)
    assert not (folder / "review-assets/figures.pdf").exists()
    assert asset.exists()
