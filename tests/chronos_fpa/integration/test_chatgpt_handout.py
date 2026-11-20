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
