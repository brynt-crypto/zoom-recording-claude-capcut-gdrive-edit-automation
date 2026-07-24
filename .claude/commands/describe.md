---
description: Generate a course-portal description (title + overview + bullets) from a finished video's transcript and display it as a copy-paste code block
argument-hint: [job name]
---

You write a **course-portal description** for a finished video: a title drawn
from the transcript, a short overview, and bullet points of what the video
covers. It becomes the lesson description inside the user's course portal, so it
must be **informative, straightforward, and strictly on-topic** — no fluff, no
invented facts, only what's actually in the transcript.

Helper runs in the project venv:
`./.venv/Scripts/python.exe -m drive_sync.describe <sub> ...`

## 1. Resolve the job

`<job>` comes from `$ARGUMENTS`. If none given, list `jobs/` and confirm the
intended job with the user (usually the most recent). The helper errors if the
job has no transcript — tell the user to run the rough cut first.

## 2. Read the edited video's transcript

```
./.venv/Scripts/python.exe -m drive_sync.describe text <job>
```
This prints the readable prose of the **edited** content (from
`transcript_final.json` — what survived the cut, so trimmed pre-roll/housekeeping
is excluded) plus a header with the detected language and word count. Read it.

## 3. Draft the description (you, from the transcript only)

Write in **English** (course portal), even if the call was Taglish. Structure:

- **Title** — concise and specific to the ACTUAL topic (e.g. the marketing
  technique / subject taught), not a generic "Weekly Call" or a date.
- **Overview** — 1–2 sentences on what the video teaches / covers.
- **Key takeaways** — **5–7 bullets**, each a short, standalone, informative
  line about a real point made in the video.

Rules: no invented facts (summarize only what's said); straightforward tone; no
"in this video…" filler; **no `--` dashes** (use a period or comma); keep it
scannable.

## 4. Display it as a copy-paste code block

Show the full description inside a single fenced ```text code block (title line,
blank line, overview, blank line, then the bullets) so the user can copy-paste it
straight into the course portal. Do **NOT** save a local `.txt` and do **NOT**
upload anything — display only.

If the user wants changes, revise and re-display the code block.

## Notes
- This command only READS the transcript and prints the description — it never
  writes files, uploads, or touches the video / CapCut drafts.
- Optional (only if the user explicitly asks to save/upload a description file):
  `drive_sync.describe name <job>` gives the paired `.txt` filename + export dir,
  and `drive_sync.describe upload <job> "<name>"` copies a written `.txt` to the
  Drive folder. Not part of the default flow.
- To remove this feature: delete `.claude/commands/describe.md` and
  `drive_sync/describe.py`.
