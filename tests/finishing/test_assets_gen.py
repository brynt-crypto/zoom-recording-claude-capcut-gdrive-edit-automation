# tests/finishing/test_assets_gen.py
import os
import subprocess
from PIL import Image
from finishing.assets_gen import render_card, sample_style_ref


def test_render_card_produces_transparent_png(tmp_path):
    out = str(tmp_path / "card.png")
    render_card(out, title="Key Point", subtitle="automation", accent_hex="#22D3EE",
                kind="side_card", width=600, height=300)
    assert os.path.exists(out)
    img = Image.open(out)
    assert img.mode == "RGBA"
    # device_scale_factor=2 → actual rendered dimensions are 2× the requested viewport.
    assert img.size == (1200, 600)
    # Has at least one fully transparent pixel (corner) -> background is transparent.
    assert img.getpixel((0, 0))[3] == 0


def test_sample_style_ref_missing_dir_returns_empty(tmp_path):
    result = sample_style_ref(str(tmp_path / "nope"), str(tmp_path / "out"))
    assert result == []
    # Nonexistent input dir must NOT cause the output dir to be created.
    assert not (tmp_path / "out").exists()


def test_sample_style_ref_extracts_frames(tmp_path):
    style_dir = tmp_path / "style_ref"
    style_dir.mkdir()
    out_dir = tmp_path / "frames"
    vid = style_dir / "test_clip.mp4"
    # Create a 6-second synthetic video with ffmpeg lavfi testsrc.
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
         "-t", "6", "-pix_fmt", "yuv420p", str(vid)],
        check=True, capture_output=True)
    frames = sample_style_ref(str(style_dir), str(out_dir), per_video=3)
    assert len(frames) == 3
    for f in frames:
        assert os.path.exists(f)
