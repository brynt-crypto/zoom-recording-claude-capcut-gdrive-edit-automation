"""End-to-end pycapcut smoke test: build a real CapCut draft from placeholder
stills + a silent wav and assert the saved draft has image keyframes + an audio
segment. This exercises the actual pycapcut integration (the net-new risk)."""
import json
import wave
from pathlib import Path

import pytest

from animate import providers, build_draft


def _make_wav(path: Path, seconds: float = 20.0, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def _scenes():
    return [{"id": 1, "start": 0.0, "end": 7.0, "motion": "zoom_in",
             "image_prompt": "a", "caption": "Intro", "emphasis": True},
            {"id": 2, "start": 7.0, "end": 13.0, "motion": "pan_left",
             "image_prompt": "b", "caption": ""},
            {"id": 3, "start": 13.0, "end": 20.0, "motion": "static",
             "image_prompt": "c", "caption": "End"}]


def test_build_draft_smoke(tmp_path):
    pytest.importorskip("pycapcut")
    scenes = _scenes()
    scenes_dir = tmp_path / "scenes"
    providers.generate(scenes, scenes_dir, dry_run=True)  # placeholder PNGs
    audio = tmp_path / "narration.wav"
    _make_wav(audio, seconds=20.0)

    drafts_root = tmp_path / "drafts"
    res = build_draft.build("smoke", scenes, str(audio), str(scenes_dir),
                            "Smoke Animated", drafts_root=str(drafts_root),
                            intro_path=None, outro_path=None)

    draft_dir = Path(res["draft_path"])
    assert draft_dir.exists()
    assert res["n_scenes"] == 3
    assert res["n_captions"] == 2  # scenes 1 and 3 have captions

    # The saved draft JSON must carry matched scale keyframes (Ken Burns) and an
    # audio material for the narration.
    jsons = list(draft_dir.glob("*.json"))
    assert jsons, "no draft json written"
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in jsons)
    assert "KFTypeScaleX" in blob and "KFTypeScaleY" in blob, "no Ken Burns scale keyframes"
    assert "KFTypePositionX" in blob, "no pan keyframes"
    # narration audio present (material type audio + our track name)
    data = json.loads(max(jsons, key=lambda p: p.stat().st_size).read_text(encoding="utf-8"))
    assert json.dumps(data).count("narration") >= 1


def test_build_missing_images_raises(tmp_path):
    pytest.importorskip("pycapcut")
    scenes = _scenes()
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    audio = tmp_path / "narration.wav"
    _make_wav(audio)
    with pytest.raises(RuntimeError, match="missing scene images"):
        build_draft.build("smoke", scenes, str(audio), str(scenes_dir), "X",
                          drafts_root=str(tmp_path / "drafts"))
