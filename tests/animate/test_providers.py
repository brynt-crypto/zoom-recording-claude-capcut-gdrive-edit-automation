"""Provider orchestration: dry-run placeholders, manual prompt sheet, idempotency."""
from animate import providers


def _scenes():
    return [{"id": 1, "start": 0.0, "end": 7.0, "motion": "zoom_in",
             "image_prompt": "a leaf as a factory", "caption": "Photosynthesis"},
            {"id": 2, "start": 7.0, "end": 13.0, "motion": "pan_left",
             "image_prompt": "sunlight hitting chloroplasts", "caption": ""}]


def test_dry_run_writes_placeholders_and_is_free(tmp_path):
    res = providers.generate(_scenes(), tmp_path, "warm vector", dry_run=True)
    assert res["cost_usd"] == 0.0
    assert sorted(res["generated"]) == [1, 2]
    assert (tmp_path / "scene_1.png").exists()
    assert (tmp_path / "scene_2.png").exists()


def test_idempotent_skip(tmp_path):
    providers.generate(_scenes(), tmp_path, dry_run=True)
    res = providers.generate(_scenes(), tmp_path, dry_run=True)
    assert sorted(res["skipped"]) == [1, 2]
    assert res["generated"] == []


def test_regen_forces_one(tmp_path):
    providers.generate(_scenes(), tmp_path, dry_run=True)
    res = providers.generate(_scenes(), tmp_path, dry_run=True, regen_ids={2})
    assert res["generated"] == [2]
    assert res["skipped"] == [1]


def test_manual_writes_prompt_sheet(tmp_path):
    res = providers.generate(_scenes(), tmp_path, "warm vector", provider="manual")
    assert sorted(res["needs_manual"]) == [1, 2]
    assert res["cost_usd"] == 0.0
    sheet = tmp_path / "prompt_sheet.md"
    assert sheet.exists()
    body = sheet.read_text(encoding="utf-8")
    assert "scene_1.png" in body and "warm vector" in body


def test_manual_uses_existing_images(tmp_path):
    providers.generate(_scenes(), tmp_path, dry_run=True)  # make the PNGs
    res = providers.generate(_scenes(), tmp_path, provider="manual")
    assert res["needs_manual"] == []
    assert sorted(res["skipped"]) == [1, 2]
