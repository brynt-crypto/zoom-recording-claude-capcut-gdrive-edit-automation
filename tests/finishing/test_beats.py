from finishing.beats import validate, normalize, TREATMENTS

def _beat(**kw):
    b = {"id": 1, "type": "hook", "treatment": "subtitle_only",
         "final_in": 0.0, "final_out": 2.0, "text": "hi"}
    b.update(kw)
    return b

def test_valid_manifest_has_no_errors():
    m = {"job": "x", "beats": [_beat()]}
    assert validate(m, final_duration=10.0) == []

def test_bad_treatment_flagged():
    m = {"job": "x", "beats": [_beat(treatment="explode")]}
    errs = validate(m, final_duration=10.0)
    assert any("treatment" in e for e in errs)

def test_out_of_bounds_flagged():
    m = {"job": "x", "beats": [_beat(final_out=99.0)]}
    errs = validate(m, final_duration=10.0)
    assert any("bounds" in e for e in errs)

def test_inverted_range_flagged():
    m = {"job": "x", "beats": [_beat(final_in=5.0, final_out=4.0)]}
    assert any("range" in e for e in validate(m, final_duration=10.0))

def test_normalize_fills_defaults_and_sorts():
    m = {"job": "x", "beats": [_beat(id=2, final_in=5.0, final_out=6.0),
                               _beat(id=1, final_in=0.0, final_out=1.0)]}
    out = normalize(m)
    assert [b["id"] for b in out["beats"]] == [1, 2]
    assert out["beats"][0]["glass"] is True
    assert out["beats"][0]["punch_in"] is None

def test_normalize_no_beats_key_does_not_crash():
    m = {"job": "x"}
    out = normalize(m)
    assert out["beats"] == []

def test_normalize_preserves_extra_top_level_keys():
    m = {"job": "x", "source": "c.mp4", "beats": [_beat()]}
    out = normalize(m)
    assert out["source"] == "c.mp4"

def test_missing_treatment_single_error():
    m = {"job": "x", "beats": [_beat(treatment=None)]}
    # Remove the treatment key so it's actually missing
    m["beats"][0] = dict(m["beats"][0])
    del m["beats"][0]["treatment"]
    errs = validate(m, final_duration=10.0)
    treatment_errs = [e for e in errs if "treatment" in e]
    assert len(treatment_errs) == 1
    assert "invalid treatment 'None'" not in errs[0] if errs else True
    # Verify the single error is about missing field
    assert any("missing required field 'treatment'" in e for e in errs)
