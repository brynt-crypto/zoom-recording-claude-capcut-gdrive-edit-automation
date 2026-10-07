---
description: Scan Google Drive for new Zoom recordings and run the full rough-cut → finishing → upload pipeline with approval gates
argument-hint: [optional recording filename to force]
---

You are running the **end-to-end Zoom-to-published pipeline**. It connects Google
Drive (mounted locally at `G:\` via Drive for Desktop) to the existing rough-cut
and finishing engines, with a **STOP-and-approve gate at every stage**.

Helper engine runs in the project venv:
`./.venv/Scripts/python.exe -m drive_sync.<module> ...`

> **macOS note.** On a Mac the invocation is `~/.venvs/capcut-mac/bin/python -m
> drive_sync.<module> ...` (the `.venv/Scripts/python.exe` above is the Windows
> venv).
>
> ⚠️ **Do NOT use `./.venv-mac/`.** It sits inside the OneDrive-synced project
> folder, where OneDrive turns files into cloud placeholders whose reads **hang
> forever instead of failing**. The Mac venv now lives on local disk at
> `~/.venvs/capcut-mac`. Prepend it to PATH so ffmpeg resolves:
> `PATH="$HOME/.venvs/capcut-mac/bin:$PATH"`. (2026-08-20.) Google Drive mounts under `~/Library/CloudStorage/GoogleDrive-<email>/`
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

> **⚡ Use CFE v2 for weekly Zoom calls (standing instruction, 2026-09-10).** Before finishing,
> confirm with **one option only**, in plain text — e.g. *"Proceeding with CFE v2: structured cards
> (numbered steps, checklists, quotes) render correctly, where v1 collapses multi-line cards into
> run-on text. Reply go."* Then follow `/cfe2`: write `jobs/<job>/finishing_manifest_v2.json`,
> validate with `finishing.beats_v2.validate`, and build
> `finishing.pipeline <job> --v2 --captions --no-endscreen --bleep-windows jobs/<job>/bleep_windows.json`.
> Result: draft `<job> (CFE2 Edit)`. No end card, intro/outro kept, host-only lower third, cards ≤10s.
> The v1 `/capcut-finishing-editor` steps below are superseded for Zoom calls.

> **📐 Every Zoom edit is 16:9 at 1920×1080 (standing instruction, 2026-09-14).** Both the rough-cut
> and finishing drafts must open in CapCut as a 16:9 canvas, whatever the recording's own size.
> The builders enforce this: `roughcut/build_draft.py` and `finishing/build_finish.py` create the canvas at
> 1920×1080 and call `force_canvas_16x9()` after save. That pins `"ratio":"16:9"`; otherwise CapCut
> resizes the canvas to the first clip, the 1920×1016 intro. After every build, confirm the draft JSON
> shows `"ratio":"16:9"` and plays the intended media file. Crop odd recordings (e.g. 4802×1460 gallery view)
> to 16:9 before the rough cut.

6. **Finishing (fully automatic).** On approval, run the
   **`/capcut-finishing-editor`** workflow for `<job>` end-to-end without pausing
   for style input — use the default dark-tech style:
   - Prep: `./.venv/Scripts/python.exe -m finishing.pipeline <job> --prep`
   - Read `jobs/<job>/transcript_final.json` and write
     `jobs/<job>/finishing_manifest.json` per the `finishing/prompts/` guides
     (beats, subtitles, overlays, punch-ins). **Never author an `end_screen` beat.**
   - Build with captions:
     `./.venv/Scripts/python.exe -m finishing.pipeline <job> --captions`
     (CapCut must be closed). Result: draft `<job>_(CFE Edit)_v1`.
   - ⛔ **No end card by default.** The video runs straight from the last spoken
     line into the branded `outro.mp4`. Only pass `--endscreen` if the user asks
     for an end card. Keep the outro — never pass `--no-outro`.

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

    Ask: *"Want the censored transcript for this call?"* This step is **optional** and
    runs in your separate agent-hub project (set `HUB_DIR` to its folder; this repo
    does not ship the transcript redactor). Point it at this job's transcript instead
    of re-transcribing:
    ```
    cd "$HUB_DIR"
    python tools/run_transcript_redactor.py --autoedit <job> --dry-run
    ```
    **Always dry-run first and audit it** before creating the Doc — search the output
    for participant first names AND for business names / domains / emails, which a
    name detector does not catch on its own. Add anything that leaks to the name list,
    re-run, and only then run without `--dry-run`.

12c. **Optional — publish to a members' portal.** If the recording also goes into a
    course/lesson portal, write the portal copy yourself from
    `jobs/<job>/transcript_final.json` (never a YouTube-metadata prompt — wrong
    platform). Format:
    - **Title:** `<Month> <D>th - <Call series name> - <what it was about>`
    - **Description:** one short intro paragraph, then a **Key takeaways** heading
      with 8–12 substantive bullets. No hashtags, timestamps or clickbait, and never
      name a participant (the host is fine).
    Show it for approval first. Set the lesson's video to the Drive link, and put the
    censored transcript in the lesson's transcript field (not as a file attachment).

## STEP 4 — Reclaim disk space (always offer, never assume)

13. **Always show what can be freed — every run, even if the user won't delete
    anything today.** Run the dry run; it verifies the upload landed in Drive
    (exists + size-matched) and lists every reclaimable item with its size and
    what breaks if it goes (including which CapCut draft would open black):
    ```
    ./.venv/Scripts/python.exe -m drive_sync.cleanup <job> --export "<export filename>"
    ```
    If it prints `REFUSING TO DELETE`, the upload isn't confirmed yet — do NOT
    delete anything, but still show the "Reclaimable once the upload is confirmed"
    list, and re-check once Drive finishes syncing. If the user says "leave it for
    now", keep the files and list them again on the next run.

14. ⛔ **Gate — approve the cleanup.** Show the itemised list with sizes and the
    total, then ask: *"The approved edit is safely in Drive. Delete these local
    copies to free `<total>`?"* Wait for approval. The user may approve only some
    items — if so, skip cleanup and tell them which paths to remove by hand.

15. On approval, delete:
    ```
    ./.venv/Scripts/python.exe -m drive_sync.cleanup <job> --export "<export filename>" --confirm
    ```
    Report how much was freed. `jobs/<job>/audio.wav` is always listed as opt-in;
    add `--include-audio` only if the user approves removing it.

    **Always kept** (never offer to delete these): the original recording in the
    Drive input folder, the **approved** CapCut draft, and `jobs/<job>/` working
    files (so finishing can re-run without re-transcribing). Add
    `--include-roughcut` ONLY if the user explicitly asks to drop the
    `<job>_roughcut` draft too.

---

## Notes
- **Drive for Desktop** must be running (so `G:\` is mounted). All steps are local
  file copies — no OAuth/API.
- **Shared Drive gotchas** (if your team folder lives in a Shared Drive):
  - A folder with the same name can exist twice — an empty one in My Drive and
    the real one in the Shared Drive. Point `DRIVE_UPLOAD_DIR` at the Shared
    Drive path, and never locate the folder by name.
  - Any API call against a Shared Drive needs `supportsAllDrives=True`
    (and `includeItemsFromAllDrives=True` when listing).
  - Moving a file INTO a Shared Drive strips its "anyone with the link"
    sharing. Re-add it afterwards, or embedded videos stop playing.
  - To embed a Drive video on another site use the `/file/d/<id>/preview`
    iframe; a native `<video>` tag pointing at Drive will not play.
- **CapCut staging:** CapCut is sandboxed and can't read cloud-synced folders
  (OneDrive etc.), so media is staged to `~/Movies/CapCutPipeline/<job>/`. That
  copy is what the drafts point at — it's in the cleanup list, and deleting it
  makes those drafts open black.
- **Idempotent:** re-running `/scan` only surfaces genuinely new recordings (the
  ledger in `drive_sync/state.json` tracks what's been processed).
- **Reuse, don't rebuild:** Step 2 delegates to the existing `/roughcut` and
  `/capcut-finishing-editor` flows — follow their own rules (CapCut closed,
  auto-versioned drafts, never overwrite a polished draft).
- **To remove this feature entirely:** delete `.claude/commands/scan.md` and the
  `drive_sync/` folder. Nothing else is touched.
