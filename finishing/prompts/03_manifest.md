# CFE Standard — Build Manifest

Write `jobs/<job>/finishing_manifest.json`. Read
`jobs/<job>/transcript_final.json` and use `final_start` / `final_end` so every
`final_in` / `final_out` is in FINISHED-timeline seconds; also record
`src_in` / `src_out` for traceability.

`treatment` MUST be one of:

**Core treatments:** `subtitle_only`, `subtitle+punch_in`, `left_card`,
`right_card`, `bottom_banner`, `floating_label`, `pseudo_split`, `end_screen`

**Motion graphics:** `process_flow`, `checklist`, `timeline`, `comparison`,
`bar_chart`, `quote`, `stat_counter`, `lower_third`, `cta`

## Schema

```json
{"job": "<job>", "beats": [
  {"id": 1, "type": "hook", "treatment": "process_flow",
   "final_in": 120.0, "final_out": 130.0, "src_in": 300.0, "src_out": 310.0,
   "spoken": "...", "reason": "why this beat earns a graphic",
   "text": "Card title",
   "layers": [
     {"text": "First step",  "offset": 0.0},
     {"text": "Second step", "offset": 0.8},
     {"text": "Third step",  "offset": 1.6}
   ],
   "anim_in": "slide_up", "anim_out": "fade",
   "glass": true, "punch_in": null, "subtitle_emphasis": false,
   "accent": null, "bold_reason": ""}
]}
```

## Field notes

- **`text`** is the card title. For non-layered cards you may put the whole card
  in `text` as multiple lines: the FIRST line is the title, each following line
  becomes a row. Line structure is preserved.
- **`layers`** drives a staggered reveal and is REQUIRED for `process_flow`,
  `checklist` and `timeline`. Each layer is one row, revealed at
  `final_in + offset`. Offsets of 0.6–1.0s apart read well; make sure the last
  layer still lands comfortably before `final_out`.
- **`anim_in` / `anim_out`** are vocabulary keys, not CapCut names. Omit them to
  accept the treatment's default.
- **`bold_reason`** is required whenever any animation on the beat is bold-tier.
- **`accent`** overrides the palette accent for one beat. Use rarely.

## Per-treatment content shapes

| Treatment | `text` shape |
|---|---|
| `process_flow` / `checklist` / `timeline` | title in `text`, steps in `layers` |
| `comparison` | line 1 title, line 2 the "before", line 3 the "after" |
| `bar_chart` | line 1 title, then rows as `Label \| Value` |
| `stat_counter` | line 1 the figure, line 2 the label |
| `quote` | line 1 the quote, line 2 the attribution |
| `lower_third` | line 1 the host's name (`HOST_NAMES` in `.env`), line 2 the role — HOST ONLY |

## Constraints

Preserve speaker visibility. Keep subtitles readable. Never cover the face.
Keep motion elegant and short. Do not add a beat for every sentence — only the
strongest moments. Respect the bold budget of 4.
