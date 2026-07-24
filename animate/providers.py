"""Pluggable image providers + shared batch orchestration.

The storyboard/motion/CapCut-draft core is provider-agnostic; only "produce a
PNG for this scene" differs. Providers:

  manual  — you generate images yourself (e.g. in ChatGPT/Codex using your
            subscription) and drop them in as scene_<id>.png. $0, always works.
            `generate` writes a copy-paste prompt sheet listing what's missing.
  imagen  — Google Imagen via google-genai (automatic, ~$0.02-0.06/image).
  codex   — shell out to the OpenAI `codex` CLI per scene (best-effort; see notes).

Shared here: idempotent skipping, --dry-run placeholders, retries, cost tally.
"""
from __future__ import annotations
import shutil
import subprocess
import time
from pathlib import Path

from . import config, imagen_client

PROVIDERS = ("manual", "imagen", "codex")


def scene_png(scenes_dir: Path, scene_id: int) -> Path:
    return scenes_dir / f"scene_{scene_id}.png"


# --- dry-run placeholder (provider-agnostic) --------------------------------
def _placeholder(path: Path, scene: dict) -> None:
    from PIL import Image, ImageDraw

    w, h = 1920, 1080
    sid = int(scene.get("id", 0))
    palette = [(24, 33, 47), (30, 41, 59), (17, 39, 46), (46, 33, 24), (28, 25, 45)]
    img = Image.new("RGB", (w, h), palette[sid % len(palette)])
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, w - 60, h - 60], outline=(120, 180, 200), width=4)
    d.text((90, 90), f"SCENE {sid}  [{scene.get('motion', 'static')}]", fill=(180, 220, 235))
    d.text((90, 150), (scene.get("image_prompt") or "")[:90], fill=(150, 170, 185))
    d.text((90, h - 130), "DRY-RUN PLACEHOLDER — no image generated", fill=(120, 140, 155))
    img.save(path)


# --- prompt sheet for manual mode -------------------------------------------
def write_prompt_sheet(scenes: list[dict], style: str, scenes_dir: Path,
                       missing_ids: list[int]) -> Path:
    """Write a copy-paste sheet so the user can generate the missing images in
    ChatGPT/Codex and save them as scene_<id>.png."""
    lines = ["# Image prompt sheet", "",
             f"Save each result as `scene_<id>.png` in `{scenes_dir}`.",
             "Aspect 16:9. Style is baked into each prompt below.", ""]
    if style.strip():
        lines += [f"**Global style:** {style.strip()}", ""]
    by_id = {int(s["id"]): s for s in scenes}
    for sid in missing_ids:
        s = by_id[sid]
        lines += [f"## scene_{sid}.png  ({s.get('motion', 'static')})",
                  imagen_client.full_prompt(s, style), ""]
    sheet = scenes_dir / "prompt_sheet.md"
    sheet.write_text("\n".join(lines), encoding="utf-8")
    return sheet


# --- codex CLI provider (best-effort) ---------------------------------------
def _codex_generate_one(scene: dict, style: str, out: Path) -> None:
    """Ask the `codex` CLI to produce an image file at `out`.

    NOTE: the Codex CLI is a coding agent, not an image API. This calls it in
    non-interactive `exec` mode and then verifies the PNG exists. If your Codex
    setup can't emit image files directly this will raise — share your working
    invocation and we'll wire it exactly.
    """
    codex = shutil.which("codex") or "codex"
    prompt = (
        f"Generate a single image and save it as a PNG to this exact path: {out}. "
        f"16:9 aspect ratio. Do not ask questions; just produce the file. "
        f"Image description: {imagen_client.full_prompt(scene, style)}"
    )
    subprocess.run([codex, "exec", prompt], capture_output=True, text=True,
                   timeout=config.CODEX_TIMEOUT_SEC, check=False)
    if not out.exists():
        raise RuntimeError(
            "codex exec did not produce an image file (Codex is a coding agent; "
            "its ability to emit images depends on your setup)")


# --- orchestration ----------------------------------------------------------
def generate(scenes: list[dict], scenes_dir: str | Path, style: str = "", *,
             provider: str = "manual", tier: str = config.DEFAULT_TIER,
             dry_run: bool = False, regen_ids: set[int] | None = None) -> dict:
    """Ensure a PNG exists for every scene. Returns a summary dict:
    {generated, skipped, failed, needs_manual, cost_usd, provider, tier, sheet}."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r} (choose {PROVIDERS})")
    scenes_dir = Path(scenes_dir)
    scenes_dir.mkdir(parents=True, exist_ok=True)
    regen_ids = regen_ids or set()

    generated: list[int] = []
    skipped: list[int] = []
    failed: list[dict] = []
    needs_manual: list[int] = []

    # Set up the automatic provider's per-image callable.
    one = None
    per_cost = 0.0
    if not dry_run and provider == "imagen":
        client = imagen_client.make_client(config.resolve_api_key())
        model = config.IMAGEN_MODELS[tier]
        per_cost = config.IMAGEN_COST_USD[tier]
        one = lambda s, o: imagen_client.generate_one(client, s, style, model, o)  # noqa: E731
    elif not dry_run and provider == "codex":
        one = lambda s, o: _codex_generate_one(s, style, o)  # noqa: E731

    for scene in scenes:
        sid = int(scene["id"])
        out = scene_png(scenes_dir, sid)
        if out.exists() and sid not in regen_ids:
            skipped.append(sid)
            continue
        if dry_run:
            _placeholder(out, scene)
            generated.append(sid)
            continue
        if provider == "manual":
            needs_manual.append(sid)
            continue
        # automatic provider with retry/backoff
        last_err: Exception | None = None
        for attempt in range(1, config.IMAGEN_MAX_RETRIES + 1):
            try:
                one(scene, out)
                generated.append(sid)
                last_err = None
                break
            except Exception as e:
                last_err = e
                time.sleep(min(2 ** attempt, 8))
        if last_err is not None:
            failed.append({"id": sid, "error": str(last_err)})

    sheet = None
    if needs_manual:
        sheet = str(write_prompt_sheet(scenes, style, scenes_dir, needs_manual))

    return {
        "provider": provider, "tier": tier,
        "generated": generated, "skipped": skipped,
        "failed": failed, "needs_manual": needs_manual,
        "cost_usd": round(len(generated) * per_cost, 4),
        "sheet": sheet,
    }
