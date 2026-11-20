# Documentation organization and link repair - 2026-11-20

The user requested clearer Markdown organization and working document links.
The repository's canonical links already resolved, but the previous upload
bundle omitted linked guides and its combined Markdown retained source-relative
paths. Those export defects are corrected.

## Navigation

[The documentation index](../README.md) groups current research, practical
guides/methods and historical reports. The root README points to it and to
the current status/handoff. The older research-notes index is explicitly
historical. Reports, plans and scientific results retain their original paths
and content; redundant generated handout copies are replaced after validation.
Ignored local handout/ZIP paths are shown as text in the canonical index, so
the GitHub documentation does not link to files that are absent from Git.

## Export behavior

- Collection follows local document links recursively, including Markdown
  guides and supporting JSON/text documents under docs or configs.
- The ZIP's grouped index links to documents under repository/. Canonical
  relative Markdown links work between the included documents.
- The combined CHATGPT_HANDOUT.md uses internal section/heading links with
  unique IDs per source document. Same-named headings do not collide.
- Unbundled code/data references are readable repository paths instead of
  broken hyperlinks. Non-Markdown supporting files are identified as ZIP
  attachments in the combined document.
- Code blocks/inline examples and external URLs retain their source text.
  No external website availability claim follows from this local audit.
- Canonical documents are unchanged by export. The manifest distinguishes
  canonical source hashes from generated-copy hashes when exported links differ.
- A broken canonical link prevents replacement of the previous export.
  Existing protection against unknown files, manual edits and path traversal
  remains in place.

## Validation and provenance

The [machine-readable audit](DOCUMENTATION_LINKS.json) records exact counts,
test results, current Git status, preservation checks and changed-file hashes.
The [focused test log](DOCUMENTATION_LINKS_TESTS.txt) records the executed tests.
The prior Prompt2 benchmark evidence remains a frozen earlier snapshot.
This follow-up made no model calls or scientific-design changes.

Read-only canonical link check:

```powershell
.venv/Scripts/python.exe scripts/maintenance/prepare_chatgpt_handout.py --check-links
```

Refresh the generated handout after completing documentation changes:

```powershell
.venv/Scripts/python.exe scripts/maintenance/prepare_chatgpt_handout.py
```

Only the researcher stages, commits or pushes. The branch is main and current
pre-next-user-commit HEAD is 558846c82002c2cb6070fbfff9bed22f514424a3
(`smoke test`). This commit appeared through an external Git operation during
the follow-up; Codex made no Git writes. The documentation cleanup remains
unstaged. Exact status is in the audit JSON.
The following selective commands are suggestions for researcher review only:

```powershell
git status --short
git diff -- README.md docs/README.md docs/recherche/README.md tests/README.md scripts/maintenance/prepare_chatgpt_handout.py
git add -- README.md docs/README.md docs/recherche/README.md tests/README.md
git add -- docs/research/FPA_STATUS.md docs/research/FPA_HANDOFF.md docs/research/FPA_DECISIONS.md docs/research/README_WORKFLOW_V2.md
git add -- scripts/maintenance/prepare_chatgpt_handout.py tests/chronos_fpa/integration/test_chatgpt_handout.py
git add -- docs/maintenance/DOCUMENTATION_LINKS.md docs/maintenance/DOCUMENTATION_LINKS.json docs/maintenance/DOCUMENTATION_LINKS_TESTS.txt
git diff --cached
git commit -m "docs: organize research navigation and repair handout links"
```

Keep generated handout files, data/result artifacts, the source ZIP and the
venv ignored. uv.lock is unchanged by this work. The prior Prompt2 report
retains its historical pre-commit status; use the current audit for the
documentation follow-up.
