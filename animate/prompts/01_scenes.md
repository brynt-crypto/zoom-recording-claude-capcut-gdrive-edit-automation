# Segmenting narration into scenes

Input: `jobs/<job>/transcript.json` — `duration`, `words[]` (word-level times),
and `segments[]` (sentence-ish chunks with `start`/`end`/`text`).

## Method
1. Read `segments`. They are your raw beats. Group adjacent segments that express
   **one idea** into a single scene; split a long segment that shifts topic.
2. Aim for **~7s per scene** (never <3s or >10s). A 3-minute narration ⇒ ~20–26 scenes.
3. Set each scene's `start`/`end` from the transcript timestamps so visuals change
   in sync with the speech. Make them **exactly contiguous**:
   - scene 1 `start = 0.0`
   - every scene `start` = previous `end`
   - last scene `end` ≈ `transcript.duration` (within a fraction of a second)
4. Put the narration line in `spoken` (context for you and future edits) — it is
   NOT shown on screen.
5. Choose a `caption` only when a **key term, name, number, or label** deserves
   reinforcement. Most scenes can have `caption: ""`. Keep captions ≤ ~4 words.
6. Mark `emphasis: true` on a few pivotal scenes (the thesis, a big reveal). It
   gives a stronger zoom and a bolder caption — use sparingly (≤ ~15% of scenes).

## Motion assignment (rhythm)
Vary motion so the video breathes; don't repeat the same move back-to-back.
- New concept / establishing shot → `zoom_in`
- Concluding / pulling back → `zoom_out`
- Showing a process or journey → `pan_left` / `pan_right`
- Rising or falling ideas (growth, decline) → `pan_up` / `pan_down`
- A pivotal, energetic beat → `zoom_in_pan_left` / `zoom_in_pan_right`
- A calm, text-heavy caption beat → `static`
