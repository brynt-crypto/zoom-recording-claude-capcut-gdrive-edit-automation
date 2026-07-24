"""Ken Burns motion keyframes: correctness guarantees (see animate/motion.py)."""
from animate import motion
from animate import config


def test_all_motions_plannable():
    for m in motion.MOTIONS:
        motion.plan_keyframes(m, 6.0)  # must not raise


def test_static_has_no_keyframes():
    assert motion.plan_keyframes("static", 5.0) == []


def test_never_emits_uniform_scale():
    for m in motion.MOTIONS:
        props = {kf["prop"] for kf in motion.plan_keyframes(m, 5.0)}
        assert "uniform_scale" not in props
        assert props <= {"position_x", "position_y", "scale_x", "scale_y"}


def test_scale_x_and_scale_y_are_matched():
    # Every scale_x keyframe must have a scale_y twin at the same time & value.
    for m in motion.MOTIONS:
        kfs = motion.plan_keyframes(m, 5.0)
        sx = sorted((kf["t"], kf["value"]) for kf in kfs if kf["prop"] == "scale_x")
        sy = sorted((kf["t"], kf["value"]) for kf in kfs if kf["prop"] == "scale_y")
        assert sx == sy, f"{m}: scale_x/scale_y not matched"


def test_times_within_scene_window():
    dur = 4.2
    for m in motion.MOTIONS:
        for kf in motion.plan_keyframes(m, dur):
            assert 0.0 <= kf["t"] <= dur + 1e-9


def test_scale_covers_pan_so_no_blank_edge():
    # Whenever a scene pans, the scale at every keyframe must be >= 1 + |offset|
    # so a canvas edge is never exposed.
    for m in motion.MOTIONS:
        kfs = motion.plan_keyframes(m, 5.0)
        pos = [abs(kf["value"]) for kf in kfs if kf["prop"].startswith("position")]
        if not pos:
            continue
        scales = [kf["value"] for kf in kfs if kf["prop"] == "scale_x"]
        assert scales, f"{m}: pans but never sets scale"
        assert min(scales) >= 1.0 + max(pos) - 1e-9, f"{m}: scale too small for pan"


def test_zoom_in_grows():
    kfs = motion.plan_keyframes("zoom_in", 5.0)
    sx = [kf for kf in kfs if kf["prop"] == "scale_x"]
    assert sx[0]["value"] == config.ZOOM_MIN
    assert sx[-1]["value"] == config.ZOOM_MAX
