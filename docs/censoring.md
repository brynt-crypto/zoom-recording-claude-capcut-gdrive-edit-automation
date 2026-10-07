# Censoring a recording

Live calls put private things on screen: `.env` files with API keys, CRM
records, a member's phone number, a carrier's branding. Censoring happens
**before** the edit, in the source file, so no later stage — rough cut,
finishing, export, upload — ever handles the uncensored picture.

Two separate mechanisms, often used together:

| What | Where | Tool |
|---|---|---|
| Blur a screen region / silence a span in the **source** | before the rough cut | `python -m censor` |
| Bleep a **spoken phrase** in the finished edit | during finishing | `finishing.pipeline --bleep` |
| Redact **names and PII in a transcript** | any time | `tools/redact_transcript.py` |

`tools/redact_transcript.py` here is the offline, dependency-free redactor: a
fixed deny-list (`tools/pii_config.json`, gitignored — it holds real names)
swapped for initials, with a self-check that fails the run if any listed name
survives. Sir BRY has a *different* tool with the same filename (Presidio-based,
"Member 1/2/3" numbering) driven by its transcript-redactor skill. They are not
copies of each other.

## The plan

One `censor_plan.json` per job, in the job directory. The schema is documented
in `censor/plan.py`; in short:

- `crop` — the 16:9 crop and output size, so a plan survives any delivery size.
- `blur` — boxes in **source pixels** with the **source-second** windows they
  apply to. Applied before the crop.
- `mute` — source-second windows to silence.
- `name` on every entry — what is being hidden. This is what the user reviews
  and what the verifier prints.
- `not_blurred_by_user_choice` and `residual_risk` — decisions, on the record.

Validation refuses a plan that censors nothing and a box with no windows,
because both look like they are working and hide nothing.

## The workflow

```bash
python -m censor encode <job> --preview 640x360 --out /tmp/preview.mp4  # seconds
python -m censor encode <job>                                          # the real master
python -m censor verify <job> --sheet
python -m censor map <job>        # after the rough cut exists
```

**Always verify.** Blur windows are checked against the original: sharp text
edges present there must be gone in the censored copy (a frame fails if it keeps
more than 25% of them). Mute windows must be digitally silent, under −60 dBFS.
Durations must match. `--sheet` writes a contact sheet of every window — look at
it; the numbers alone will not catch a box that is in the right place at the
wrong moment.

## Traps worth knowing

- **Panels that slide in.** A box sized for the resting position misses the
  frames where it is still moving. Give the slide-in its own wider box and a
  short window.
- **Lists that scroll.** Size the box for the whole scroll, not the first frame.
- **A blur that survives the cut.** `map` translates source windows onto the
  rough-cut timeline, so you can confirm where a window ended up once cuts have
  moved everything.
- **The captions still say it.** Blurring the screen does not change the
  transcript. Use `--bleep` for the audio and fix `transcript_final.json` for
  the captions.
