import pytest

from censor import plan as plan_mod


def _plan(**over):
    p = {
        "crop": {"x": 0, "y": 0, "w": 1920, "h": 1080, "out_w": 1920, "out_h": 1080},
        "blur": [{"name": "api key on screen", "box": [10, 20, 100, 50],
                  "windows": [[1.0, 2.0]]}],
        "mute": [{"name": "member says a phone number", "window": [3.0, 4.0]}],
    }
    p.update(over)
    return p


def test_a_good_plan_validates():
    assert plan_mod.validate(_plan()) == []


def test_plan_that_censors_nothing_is_rejected():
    errs = plan_mod.validate(_plan(blur=[], mute=[]))
    assert any("censors nothing" in e for e in errs)


def test_box_with_no_window_is_rejected():
    # A box with no window blurs nothing — silently shipping that would leak.
    errs = plan_mod.validate(_plan(blur=[{"name": "key", "box": [0, 0, 5, 5], "windows": []}]))
    assert any("windows is empty" in e for e in errs)


def test_backwards_window_is_rejected():
    errs = plan_mod.validate(_plan(mute=[{"name": "x", "window": [9.0, 8.0]}]))
    assert any("ends at or before it starts" in e for e in errs)


def test_unnamed_box_is_rejected():
    errs = plan_mod.validate(_plan(blur=[{"name": "  ", "box": [0, 0, 5, 5],
                                          "windows": [[1.0, 2.0]]}]))
    assert any("name is empty" in e for e in errs)


def test_load_raises_on_an_invalid_plan(tmp_path):
    import json
    f = tmp_path / "censor_plan.json"
    f.write_text(json.dumps(_plan(blur=[], mute=[])))
    with pytest.raises(ValueError, match="invalid censor plan"):
        plan_mod.load(f)
