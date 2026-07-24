# assets/

Branding clips and the optional drop-folder for footage to edit.

## Put your branding clips here (exact names)
- `intro.mp4` — prepended to every rough cut
- `outro.mp4` — appended to every rough cut

They're added as **separate, editable segments** in CapCut (you can swap or trim
them anytime). Replace these files whenever you rebrand — no code change needed.

## to_edit/  (drop-folder)
Drop a video in `to_edit/` and `/roughcut` will pick it up first. If it's empty,
`/roughcut` scans your configured video folders instead (see `ROUGHCUT_SCAN_DIRS`
in `.env.example`).
