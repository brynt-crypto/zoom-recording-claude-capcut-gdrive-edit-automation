# Build Manifest

Turn the approved beat plan into `jobs/<job>/finishing_manifest.json` — exact
CapCut editing instructions. Read `jobs/<job>/transcript_final.json` and use the
`final_start`/`final_end` fields so every `final_in`/`final_out` is in
FINISHED-timeline seconds; also record `src_in`/`src_out` (original source time)
for traceability.

For each beat give: start timestamp (final + source), CapCut action, on-screen
text, placement on screen, animation in, animation out, whether to use
blur/shadow/glass/plain, whether to add a punch-in, and whether subtitles stay
standard or become emphasized.

`treatment` MUST be exactly one of:
`subtitle_only`, `subtitle+punch_in`, `left_card`, `right_card`,
`bottom_banner`, `floating_label`, `pseudo_split`, `end_screen`.

Schema:
```json
{"job": "<job>", "beats": [
  {"id": 1, "type": "hook", "treatment": "subtitle+punch_in",
   "final_in": 0.0, "final_out": 4.2, "src_in": 10.0, "src_out": 14.2,
   "spoken": "...", "reason": "...", "text": "On-screen copy",
   "placement": "lower_third", "anim_in": "fade", "anim_out": "fade",
   "glass": true, "punch_in": 1.12, "subtitle_emphasis": false,
   "reposition_overlays": false, "accent": null}
]}
```

Constraints: preserve speaker visibility; keep subtitles readable; avoid covering
the face; avoid noisy editing; keep motion elegant and short; premium modern UI
styling; build for CapCut Desktop. Do not add a beat for every sentence — only
the strongest moments.
