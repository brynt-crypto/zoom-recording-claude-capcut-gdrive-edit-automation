"""Tunable defaults for the /animate engine.

Reuses roughcut's CapCut drafts root + branding so output stays consistent with
the rest of the pipeline. All time values are SECONDS unless noted.
"""
from __future__ import annotations
import os
from pathlib import Path

# Reuse the drafts root, intro/outro clips and assets dir from roughcut so every
# skill writes drafts to the same CapCut location and shares the same branding.
from roughcut.build_draft import DEFAULT_DRAFTS_ROOT as DRAFTS_ROOT  # noqa: F401
from roughcut.config import INTRO_PATH, OUTRO_PATH, ASSETS_DIR  # noqa: F401
from roughcut.config import INBOX_DIR  # drop-folder (assets/to_edit)  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent

# --- Reference storyboard (optional creative direction Claude follows) -------
# A brief the user supplies to steer scene ideas + image prompts for the whole
# video. Discovered from jobs/<job>/reference.* or this shared drop folder, or
# passed explicitly via --reference. Claude reads .md/.txt directly, PDFs via the
# Read tool's page range, and views any reference images.
STORYBOARD_REF_DIR = os.path.join(ASSETS_DIR, "storyboard_ref")
REFERENCE_EXTS = (".md", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp")

# --- Canvas ------------------------------------------------------------------
# Fixed 16:9 canvas. NEVER read dimensions from the transcript — a narration
# (audio-only) source reports width/height 0.
CANVAS_W = 1920
CANVAS_H = 1080
FPS = 30

# --- Transcription -----------------------------------------------------------
# The /animate command passes device="cuda"; CLI default stays CPU-safe.
WHISPER_MODEL = "medium"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"
LANGUAGE = None                 # None = auto-detect

# --- Google Imagen -----------------------------------------------------------
# Model tiers (see https://ai.google.dev/gemini-api/docs/imagen). Keep the ids
# here so a model refresh is a one-line change.
IMAGEN_MODELS = {
    "fast":     "imagen-4.0-fast-generate-001",
    "standard": "imagen-4.0-generate-001",
    "ultra":    "imagen-4.0-ultra-generate-001",
}
IMAGEN_COST_USD = {"fast": 0.02, "standard": 0.04, "ultra": 0.06}
DEFAULT_TIER = "standard"
# 16:9 at 2K gives crop headroom so Ken Burns pans/zooms never expose the edge.
IMAGEN_ASPECT = "16:9"
IMAGEN_SIZE = "2K"
IMAGEN_MAX_RETRIES = 3

# --- Image provider ----------------------------------------------------------
# manual  = you generate images (ChatGPT/Codex) and drop them in ($0, subscription)
# imagen  = automatic via Google Imagen
# codex   = shell out to the OpenAI `codex` CLI (best-effort)
DEFAULT_PROVIDER = "manual"
CODEX_TIMEOUT_SEC = 300

# --- Ken Burns motion --------------------------------------------------------
# position units are HALF-canvas widths/heights (1.0 == canvas edge). To never
# expose a blank edge while panning, the image must stay scaled so that
# |offset| <= scale - 1 at every keyframe. These presets respect that with a
# safety margin (see animate/motion.py).
ZOOM_MIN = 1.0
ZOOM_MAX = 1.18         # end scale for a zoom-in
PAN_SCALE = 1.16        # held scale during a pure pan
PAN_OFFSET = 0.10       # max pan travel from centre (< PAN_SCALE - 1)
SCENE_FADE = 0.25       # gentle cross-fade in on every scene (seconds)

# --- Scene authoring guidance (surfaced in prep) -----------------------------
SCENE_MIN_SEC = 3.0
SCENE_MAX_SEC = 10.0
SCENE_TARGET_SEC = 7.0

# --- Captions palette --------------------------------------------------------
ACCENT_HEX = "#22D3EE"
GLASS_BASE_HEX = "#0B0F14"

# --- Style anchor: prepended to every Imagen prompt for a consistent look ----
STYLE_ANCHOR = (
    "TED-Ed-style flat vector explainer illustration, clean geometric shapes, "
    "bold flat colors, soft long shadows, generous negative space, minimal detail, "
    "cohesive warm palette, no text, no watermark, 16:9"
)
DEFAULT_NEGATIVE = "text, letters, watermark, signature, photorealistic, 3d render, cluttered, busy"


def _read_dotenv() -> dict[str, str]:
    """Best-effort parse of a repo-root .env (KEY=VALUE per line). No dependency
    on python-dotenv. Returns {} if the file is absent."""
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def resolve_api_key() -> str:
    """Return the Google Gemini/Imagen API key from the environment or a repo
    .env file. Raises SystemExit with actionable guidance if unset.

    Only call this in the --generate phase; --dry-run must never need a key.
    """
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(name)
        if val:
            return val
    dotenv = _read_dotenv()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if dotenv.get(name):
            return dotenv[name]
    raise SystemExit(
        "No Google API key found. Get one at https://aistudio.google.com/apikey "
        "and set it, e.g.:\n"
        '    setx GEMINI_API_KEY "your-key-here"   (then reopen the terminal)\n'
        "or add a line  GEMINI_API_KEY=your-key-here  to a .env file at the repo root."
    )
