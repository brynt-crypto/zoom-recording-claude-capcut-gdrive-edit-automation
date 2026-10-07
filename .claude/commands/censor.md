---
description: Blur and mute what must not ship in a recording — build the plan, encode the censored master, verify it frame by frame
argument-hint: [job name]
---

You are censoring a raw recording **before** it is edited. API keys, client
names, phone numbers and carrier branding get blurred or silenced in the source,
so every later step — rough cut, finishing, upload — only ever sees the safe
copy.

Engine: `python -m censor <command> <job>`. The plan schema is documented in
`censor/plan.py`; the workflow is in `docs/censoring.md`.

## 1. Find what has to go

Watch the recording, or scan it with the user, and list every moment where
something private is on screen or spoken. For each one note the **source**
seconds and, for anything visual, the box in **source pixels**.

Screen shares are where this bites: an `.env` file, a settings dialog, a browser
tab title, a CRM record. A panel that slides in needs its own wider box for the
slide-in frames, and a list that scrolls needs a box tall enough for the whole
scroll.

## 2. Write `jobs/<job>/censor_plan.json`

Follow the schema in `censor/plan.py`. Every box and mute window needs a `name`
saying what is being hidden — that name is what the user reviews, and it is what
the verifier prints. Record what you deliberately left visible in
`not_blurred_by_user_choice`, and anything you are unsure about in
`residual_risk`.

## 3. ⛔ REVIEW GATE

Show the user the full list — every box, every window, in their own words — plus
what you chose not to censor. **Do not encode until they approve.** Something
missed here ships.

## 4. Preview, then encode

A preview renders in seconds and is enough to check the boxes land right:

```
python -m censor encode <job> --preview 640x360 --out /tmp/<job>_preview.mp4
```

Look at the preview at each window. Then the real encode (long — it re-encodes
the whole recording):

```
python -m censor encode <job>
```

## 5. Verify — never skip this

```
python -m censor verify <job> --sheet
```

Every blur window is compared against the original: the original's sharp text
edges must be gone in the censored copy. Every mute window must be digitally
silent, and the durations must match. The contact sheet is for your own eyes —
look at it, don't just read the OK lines.

Report `ALL OK` or the exact failures. On a FAIL, widen the box or the window in
the plan and re-encode; never hand-wave a failure.

## 6. Hand off

The censored file is now the source for `/roughcut`. The original stays where it
is — never delete it.

`python -m censor map <job>` maps the censor windows onto the rough-cut timeline
after the cut exists, which is how you find where a window ended up in the final
edit (for a bleep, or to check a blur survived the cut).
