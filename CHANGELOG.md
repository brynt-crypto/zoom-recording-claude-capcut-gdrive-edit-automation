# Changelog

## 2026-09-17 — repo cleanup

### Changed
- **CFE v1 retired; v2 is now the only finishing engine, "CFE Standard".**
  The v2 modules took the plain names (`beats`, `anim`, `overlays`, `cards`,
  `prompts/`, `templates/card.html`) and the v1 overlay engine and card renderer
  were deleted. Drafts are named `<Job> (CFE Standard)`; the `--v2` flag is gone
  and the manifest is `finishing_manifest.json` again.
  Manifests written for v1 remain valid — the schema is a superset.
  Jobs finished before this keep their `finishing_manifest_v2.json` and still
  build via `--manifest <path>`.
- **Media locations are configurable.** `MEDIA_ROOT`, `JOBS_DIR`, `OUTPUT_DIR`
  and `WORK_DIR` in `.env` move the big files out of the project folder;
  unset, everything stays where it was.
- **The host's on-screen name comes from `HOST_NAMES`** instead of being
  hardcoded in the engine, its prompts and the redactor.
- Every draft canvas is pinned to 16:9 1920x1080 (pycapcut wrote
  `"ratio": "original"`, so CapCut resized the canvas to the first clip).
- README rewritten as an overview; setup split per OS under `docs/`.

### Added
- `censor/` — the Sept 11 one-off censoring scripts promoted into a tested
  package with a CLI (`python -m censor filter|encode|map|verify`) and a
  `/censor` command with a review gate and a mandatory verify.
- Bleep censoring in finishing: `--bleep "phrase"` / `--bleep-windows`.
- `common/` — `.env` reading and path resolution shared by every package.
- `scripts/preview_cards.py` — contact sheet of a draft's cards composited onto
  real frames, to check placement without opening CapCut.
- `pyproject.toml` with optional extras (`animate`, `windows-gpu`, `dev`),
  a `Makefile`, and CI running the tests that do not need CapCut.

### Removed
- `/cfe2` (merged into `/capcut-finishing-editor`).
- `requirements-LAPTOP-*.txt` — the machine-specific copy.
