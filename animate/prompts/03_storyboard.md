# storyboard.json — schema & example

Write this file to `jobs/<job>/storyboard.json`. The pipeline validates it before
generating images or building; fix any reported errors and re-save.

## Schema
```jsonc
{
  "job": "photosynthesis",                 // must match the job name
  "style": "warm flat-vector world, terracotta/teal/cream palette, rounded shapes",
  "scenes": [
    {
      "id": 1,                             // unique int, 1-based, in order
      "start": 0.0,                        // narration seconds; scene 1 == 0.0
      "end": 7.4,                          // > start; contiguous with next.start
      "spoken": "Every plant runs a tiny chemical factory.",  // context, not shown
      "caption": "Photosynthesis",         // short on-screen label; "" = none
      "image_prompt": "a leaf drawn as a glowing factory, sunbeams entering, wide empty sky, subject centered",
      "negative_prompt": "",               // optional; default filters applied
      "motion": "zoom_in",                 // see allowed values below
      "emphasis": true                     // optional; stronger zoom + bold caption
    }
  ]
}
```

## Allowed `motion` values
`static`, `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `pan_up`, `pan_down`,
`zoom_in_pan_left`, `zoom_in_pan_right`.

## Validation rules (enforced by animate/storyboard.py)
- `scenes` non-empty; scene 1 `start == 0.0`.
- Each scene: `end > start`, duration ≥ 3s, `start` == previous `end` (contiguous,
  no gaps/overlaps), `end` ≤ narration duration.
- `motion` ∈ the list above; `image_prompt` non-empty.
- The last scene should end near the narration duration (don't leave a long tail
  uncovered).

## After writing it
1. Present the storyboard as a table (id · time · motion · caption · prompt) plus
   **scene count × per-image price = estimated cost**, and WAIT for approval.
2. On "go": `--generate` (add `--fast` for cheaper drafts, `--ultra` for best).
3. Review the PNGs; regenerate any weak ones with `--generate --regen <ids>`.
4. Close CapCut, then `--build`.
