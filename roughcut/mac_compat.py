"""Make a pycapcut-generated draft openable by CapCut on macOS.

pycapcut writes the WINDOWS draft layout:
  - the timeline goes in `draft_content.json`
  - `platform` is stamped as {"os": "windows", "app_version": "6.7.0"}

CapCut on macOS instead reads `draft_info.json` and expects a mac platform
block plus a handful of keys the Windows schema omits. A draft written the
Windows way shows up in CapCut's project list but refuses to open.

`make_mac_compatible()` writes the mac-flavoured `draft_info.json` alongside the
original `draft_content.json` (the Windows file is left untouched, so the same
draft folder still works if opened on the Windows machine).

No-ops on non-macOS hosts.
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

# CapCut for macOS is sandboxed (`com.apple.security.app-sandbox`) and only holds
# `files.user-selected.read-write`. It therefore CANNOT read media that lives in a
# File Provider mount such as ~/Library/CloudStorage/OneDrive-... — the clips show
# up red as "Unsupported Media" even though the files are perfectly readable by
# every other process. Media must be staged somewhere CapCut can reach; ~/Movies
# works because that is where CapCut keeps its own drafts.
STAGE_ROOT = Path.home() / "Movies" / "CapCutPipeline"
_UNREADABLE_MARKERS = ("/Library/CloudStorage/",)

# Keys present in a native macOS draft but absent from pycapcut's Windows output.
_MAC_ONLY_DEFAULTS = {
    "draft_type": "video",
    "mixed_track_mode_on": False,
    "smart_ads_info": {"page_from": "", "routine": "", "draft_url": ""},
    "uneven_animation_template_info": {
        "composition": "", "content": "", "order": "", "sub_template_info_list": [],
    },
    "function_assistant_info": {
        "smart_rec_applied": False, "fixed_rec_applied": False,
        "auto_adjust": False, "auto_adjust_segid_list": [],
        "color_correction": False, "color_correction_segid_list": [],
        "enhance_quality": False,
    },
}

# What a macOS CapCut 9.x draft advertises.
_MAC_PLATFORM = {"os": "mac", "app_id": 359289, "app_source": "cc",
                 "app_version": "9.0.0", "os_version": ""}
_MAC_NEW_VERSION = "177.0.0"


def make_mac_compatible(draft_path: str | Path) -> Path | None:
    """Write draft_info.json (macOS layout) next to draft_content.json.

    Returns the path written, or None if skipped (not macOS / nothing to read).
    """
    if sys.platform != "darwin":
        return None

    folder = Path(draft_path)
    content = folder / "draft_content.json"
    if not content.is_file():
        return None

    data = json.loads(content.read_text(encoding="utf-8"))

    # Present the draft as macOS-native so CapCut 9.x will load it.
    data["platform"] = dict(_MAC_PLATFORM)
    data["new_version"] = _MAC_NEW_VERSION
    for key, default in _MAC_ONLY_DEFAULTS.items():
        data.setdefault(key, default)

    out = folder / "draft_info.json"
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return out


def _needs_staging(path: str) -> bool:
    return any(m in path for m in _UNREADABLE_MARKERS)


def stage_media(draft_path: str | Path, job: str,
                stage_root: Path | None = None) -> dict:
    """Copy sandbox-unreadable media next to CapCut and repoint the draft at it.

    Any material whose path sits in a File Provider mount (OneDrive/iCloud) is
    copied to <stage_root>/<job>/ and the draft's paths are rewritten. Files
    already outside such a mount are left alone. Re-uses an existing staged copy
    when the size already matches, so repeat builds don't re-copy gigabytes.

    Returns {"staged": [...], "reused": [...], "bytes": int, "root": str}.
    """
    if sys.platform != "darwin":
        return {"staged": [], "reused": [], "bytes": 0, "root": ""}

    folder = Path(draft_path)
    root = Path(stage_root or STAGE_ROOT) / job
    staged, reused, total = [], [], 0

    for fname in ("draft_content.json", "draft_info.json"):
        fp = folder / fname
        if not fp.is_file():
            continue
        data = json.loads(fp.read_text(encoding="utf-8"))
        changed = False

        for _, mats in data.get("materials", {}).items():
            if not isinstance(mats, list):
                continue
            for item in mats:
                if not isinstance(item, dict):
                    continue
                src = item.get("path")
                if not src or not _needs_staging(src):
                    continue
                s = Path(src)
                if not s.is_file():
                    continue
                root.mkdir(parents=True, exist_ok=True)
                dest = root / s.name
                if dest.is_file() and dest.stat().st_size == s.stat().st_size:
                    if str(dest) not in reused:
                        reused.append(str(dest))
                else:
                    shutil.copy2(s, dest)
                    total += dest.stat().st_size
                    if str(dest) not in staged:
                        staged.append(str(dest))
                item["path"] = str(dest)
                changed = True

        if changed:
            fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    return {"staged": staged, "reused": reused, "bytes": total, "root": str(root)}
