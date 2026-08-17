---
description: Scan Google Drive for new Zoom recordings and run the full rough-cut → finishing → upload pipeline with approval gates
argument-hint: [optional recording filename to force]
---

You are running the **end-to-end Zoom-to-published pipeline**. It connects Google
Drive (mounted locally at `G:\` via Drive for Desktop) to the existing rough-cut
and finishing engines, with a **STOP-and-approve gate at every stage**.

Helper engine runs in the project venv:
`./.venv/Scripts/python.exe -m drive_sync.<module> ...`

> **macOS note.** On a Mac the invocation is `./.venv-mac/bin/python -m
> drive_sync.<module> ...` (the `.venv/Scripts/python.exe` above is the Windows
> venv). Google Drive mounts under `~/Library/CloudStorage/GoogleDrive-<email>/`
> instead of `G:\` — the code auto-detects this, so the module commands are the
> same; only the python path differs. For the "is CapCut running?" check in
> Step 4, use `pgrep -x CapCut` instead of the PowerShell `Get-Process` command.

Drive layer scripts print a machine-readable block between `DRIVE_SYNC_JSON` and
`END_DRIVE_SYNC_JSON` — parse that for filenames/paths/job slug.

**Never skip an approval gate.** Work the three steps in order. Stop and wait for
the user at each ⛔ gate.

---

## STEP 1 — Detect & approve the raw footage

1. Scan the Drive input folder:
   ```
   ./.venv/Scripts/python.exe -m drive_sync.scan
   ```
   Present the result, clearly marking which recordings are **NEW** (not yet in
   the ledger) vs already processed. Show size and the proposed `job` slug.

2. ⛔ **Gate — confirm the footage.** If `$ARGUMENTS` names a recording, point to
   the match but still confirm. If there are multiple new recordings, use
   AskUserQuestion to let the user pick which one. Ask: *"Is this the correct raw
   footage to edit?"* Wait for approval.

3. On approval, ingest it locally (copies into `assets/to_edit` under the clean
   job name so Whisper reads a real local file):
   ```
   ./.venv/Scripts/python.exe -m drive_sync.ingest "<recording filename>"
   ```
   Capture `local_path` and `job` from the JSON block. Use these for Step 2.

---

## STEP 2 — Rough cut → approve → finishing → approve

4. **Rough cut.** Follow the existing **`/roughcut`** workflow on the ingested
   file, passing `--name <job>` and building the draft. Confirm CapCut is closed
   first:
   ```
   powershell -c "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"
   ```
   Run the rough-cut pipeline (GPU defaults; this is a long file — use
   `run_in_background: true`). Honour `/roughcut`'s own brief + manual-trim
   questions. Result: draft `<job>_roughcut`.

5. ⛔ **Gate — approve the rough cut.** Tell the user the `<job>_roughcut` draft
   is ready in CapCut and summarise the cuts (from `jobs/<job>/cuts_report.md`).
   Wait for approval. If they want changes, adjust and rebuild, then re-ask.

6. **Finishing (fully automatic).** On approval, run the
   **`/capcut-finishing-editor`** workflow for `<job>` end-to-end without pausing
   for style input — use the default dark-tech style:
   - Prep: `./.venv/Scripts/python.exe -m finishing.pipeline <job> --prep`
   - Read `jobs/<job>/transcript_final.json` and write
     `jobs/<job>/finishing_manifest.json` per the `finishing/prompts/` guides
     (beats, subtitles, overlays, punch-ins). **Never author an `end_screen` beat.**
   - Build with captions and no end card:
     `./.venv/Scripts/python.exe -m finishing.pipeline <job> --captions --no-endscreen`
     (CapCut must be closed). Result: draft `<job>_(CFE Edit)_v1`.
   - ⛔ **No end card, ever.** `--no-endscreen` is mandatory: the video runs straight
     from the last spoken line into the branded `outro.mp4`. Keep the outro — never
     pass `--no-outro`. (Standing instruction, 2026-07-30.)

7. ⛔ **Gate — approve the edit.** Notify the user clearly: **"The edit is done."**
   Report the `<job>_(CFE Edit)_v1` draft and what was added. Ask whether they
   want adjustments or approve. If adjustments → re-run finishing (auto-versions
   to `_v2`, etc.), then re-ask. On approval, mark progress:
   ```
   ./.venv/Scripts/python.exe -c "from drive_sync import state; state.mark('<source filename>', roughcut='done', finishing='done')"
   ```

---

## STEP 3 — Detect the export → upload → report

8. **Snapshot the export folder**, then hand off to the user. Record a marker:
   ```
   ./.venv/Scripts/python.exe -c "from datetime import datetime; print(datetime.now().isoformat(timespec='seconds'))"
   ```
   Tell the user: export the approved draft from CapCut into the export folder
   (`...\Edited Zoom Outputs`) and **say when it's done**. Do NOT poll — wait for
   the user to confirm.

9. When the user confirms, detect the new export:
   ```
   ./.venv/Scripts/python.exe -m drive_sync.scan --export --since "<marker>"
   ```
   Confirm the detected filename with the user (if more than one appears, ask
   which is the right export).

10. ⛔ **Gate — approve the upload.** Ask: *"Upload this to the team Google Drive
    folder?"* Wait for approval.

11. On approval, upload (a local copy into the team folder that Drive syncs up):
    ```
    ./.venv/Scripts/python.exe -m drive_sync.upload "<export filename>" --job <job>
    ```
    If it reports the name already exists with different content, ask before
    re-running with `--overwrite`.

12. **Final report.** Print a clear summary of everything done:
    - Source recording (Drive) → job slug
    - Rough-cut draft: `<job>_roughcut`
    - Finishing draft: `<job>_(CFE Edit)_v1`
    - Exported file detected: `<export filename>`
    - Uploaded to: the configured team upload folder + its link
      (the destination is defined by `UPLOAD_DIR`/`UPLOAD_LINK` in `drive_sync/config.py`,
      which read `DRIVE_UPLOAD_DIR`/`DRIVE_UPLOAD_FOLDER_URL` from your `.env`)
    - Ledger status for this recording (from `drive_sync/state.json`)

## STEP 3.5 — Offer the censored transcript (always offer, never assume)

12b. Once the upload is confirmed, **offer to censor the transcript** — don't wait to be
    asked. This job already has a transcript, so the redactor reuses it instead of
    re-transcribing (faster, and it uses the larger Whisper model this pipeline ran).

    Ask: *"Want the censored transcript for this call?"* On yes, run it from the
    **Sir BRY** project (that's where the redactor lives — do not copy anything across):
    ```
    cd "/Users/bry/Library/CloudStorage/OneDrive-Personal/Phillip(Phylsong)/CLAUDE CODE/Sir BRY (My AI Agent)"
    ./.venv-mac/bin/python tools/run_transcript_redactor.py --autoedit <job> --dry-run
    ```
    **Always dry-run first and audit it** before creating the Doc — grep the output for
    participant first names AND for business names / domains / emails, which the name
    detector does not catch on its own. Anything that leaks goes into `known_names.txt`,
    then re-run. Only then run it again without `--dry-run` to create the Google Doc.

    If they also want it on the portal, that's the **portal lesson**: `/portal-description`
    for the lesson title + description, and `tools/publish_transcript.py` for the
    transcript field. Never use the `/youtube` skill for portal copy — wrong brand.

## STEP 4 — Reclaim disk space (always offer, never assume)

13. **Show what can be freed.** Run the dry run first — it verifies the upload
    landed in Drive (exists + size-matched) before proposing anything:
    ```
    ./.venv/Scripts/python.exe -m drive_sync.cleanup <job> --export "<export filename>"
    ```
    If it prints `REFUSING TO DELETE`, the upload isn't confirmed yet — do NOT
    delete anything; tell the user and re-check once Drive finishes syncing.

14. ⛔ **Gate — approve the cleanup.** Show the itemised list with sizes and the
    total, then ask: *"The approved edit is safely in Drive. Delete these local
    copies to free `<total>`?"* Wait for approval. The user may approve only some
    items — if so, skip cleanup and tell them which paths to remove by hand.

15. On approval, delete:
    ```
    ./.venv/Scripts/python.exe -m drive_sync.cleanup <job> --export "<export filename>" --confirm
    ```
    Report how much was freed.

    **Always kept** (never offer to delete these): the original recording in the
    Drive input folder, the **approved** CapCut draft, and `jobs/<job>/` working
    files (so finishing can re-run without re-transcribing). Add
    `--include-roughcut` ONLY if the user explicitly asks to drop the
    `<job>_roughcut` draft too.

---

## Notes
- **Drive for Desktop** must be running (so `G:\` is mounted). All steps are local
  file copies — no OAuth/API.
- **Idempotent:** re-running `/scan` only surfaces genuinely new recordings (the
  ledger in `drive_sync/state.json` tracks what's been processed).
- **Reuse, don't rebuild:** Step 2 delegates to the existing `/roughcut` and
  `/capcut-finishing-editor` flows — follow their own rules (CapCut closed,
  auto-versioned drafts, never overwrite a polished draft).
- **To remove this feature entirely:** delete `.claude/commands/scan.md` and the
  `drive_sync/` folder. Nothing else is touched.
