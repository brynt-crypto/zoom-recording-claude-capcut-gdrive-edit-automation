# Writing image prompts (for Google Imagen)

Every scene's `image_prompt` is combined with a built-in **style anchor**
(TED-Ed-style flat vector, clean shapes, flat colors, soft shadows, negative
space, no text, 16:9) plus the storyboard's global `style` note. So you only need
to describe the **subject and composition** — don't re-state the style each time.

## Do
- Describe **one clear subject / metaphor** and its composition.
  - Good: "a single seedling breaking through cracked concrete, sun overhead, wide empty sky"
  - Weak: "growth" (too abstract for an image model)
- Name the **composition** so Ken Burns has room: mention wide framing, where the
  subject sits, and empty space (helps pans/zooms avoid awkward crops).
- Keep a **recurring visual language** across scenes (same character style, same
  color family) via the global `style` field, e.g.
  `"warm palette: terracotta, teal, cream; rounded characters; consistent world"`.

## Don't
- Don't ask for on-screen words/labels/UI text — Imagen renders text poorly and
  captions are added separately. (`no text` is already in the anchor + negative.)
- Don't request photorealism, logos, real people/brands, or dense detail.
- Don't pack multiple ideas into one image — split into two scenes instead.

## Honor the reference (if provided)
If the user supplied a reference brief/storyboard, derive the global `style` and
each scene's imagery FROM it — reuse its described palette, character look, and
per-section visual ideas so the video matches their intent. For reference
*images*, describe what you see (composition, palette, shape language) in the
prompts, since Imagen generates from text, not from the images themselves.

## Global `style` field
Write one sentence that pins the palette + character/world style for the whole
video. It is woven into every prompt so all scenes match. Example:
`"warm flat-vector world, terracotta/teal/cream palette, rounded friendly shapes, consistent soft lighting"`

## Optional `negative_prompt`
Defaults are applied automatically (text, watermark, photorealistic, cluttered).
Only set this to exclude something specific to a scene.
