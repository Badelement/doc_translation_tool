# Repo Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize the workspace so the root stays minimal, `source/` is self-contained, and `releases/` is reserved for generated artifacts.

**Architecture:** Keep only workspace-level navigation files at the root. Treat `source/` as the project root for code, docs, tests, and scripts, and update human-facing docs so paths consistently reference `source/` and `releases/`.

**Tech Stack:** Markdown docs, shell/PowerShell build scripts, Python project layout

---

### Task 1: Keep The Workspace Root Minimal

**Files:**
- Modify: `/Users/badelement/doc_translation_tool_source 2/.gitignore`
- Modify: `/Users/badelement/doc_translation_tool_source 2/README.md`
- Create: `/Users/badelement/doc_translation_tool_source 2/releases/README.md`

- [ ] Confirm the root should only contain workspace navigation files and top-level folders.
- [ ] Ensure `.gitignore` ignores release artifacts and source-local caches only.
- [ ] Keep the root `README.md` focused on workspace navigation, not project internals.
- [ ] Keep `releases/README.md` focused on generated output layout expectations.

### Task 2: Remove Workspace Junk

**Files:**
- Remove: stray `.DS_Store` files under the workspace

- [ ] Find remaining `.DS_Store` files in the workspace.
- [ ] Delete only those junk files.
- [ ] Re-scan to confirm they are gone.

### Task 3: Normalize Path References

**Files:**
- Modify: `/Users/badelement/doc_translation_tool_source 2/source/README.md`
- Modify: `/Users/badelement/doc_translation_tool_source 2/source/PACKAGING.md`
- Modify: `/Users/badelement/doc_translation_tool_source 2/source/PACKAGING_MACOS.md`
- Modify: `/Users/badelement/doc_translation_tool_source 2/source/CLAUDE.md`
- Modify: any other high-signal docs still referencing the old root or `dist/` layout

- [ ] Update the most user-facing docs first.
- [ ] Replace old `dist/` references with `../releases/` where appropriate.
- [ ] Replace old “project root” phrasing with `source/` when that is now the intended working directory.
- [ ] Leave lower-value historical notes alone unless they create active confusion.

### Task 4: Verify The New Layout

**Files:**
- Verify: `/Users/badelement/doc_translation_tool_source 2`
- Verify: `/Users/badelement/doc_translation_tool_source 2/source/scripts/build_macos.sh`

- [ ] List the workspace root and confirm it remains minimal.
- [ ] Run `bash -n` against the macOS build script after path edits.
- [ ] Search key docs for stale `dist/` and old-root references.
- [ ] Report what was intentionally not changed.
