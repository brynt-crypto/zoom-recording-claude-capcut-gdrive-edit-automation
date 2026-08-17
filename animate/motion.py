"""Ken Burns motion: map a motion name to scale/position keyframes on a segment.

CRITICAL correctness rule (see the plan + pycapcut segment.py:233): NEVER keyframe
`uniform_scale` — pycapcut silently remaps it to `scale_x` only, leaving `scale_y`
unlinked, which horizontally STRETCHES the image. We always emit MATCHED
`scale_x` + `scale_y` keyframes for a true proportional zoom.

Edge rule: position units are half-canvas widths/heights (1.0 == canvas edge).
The image only fully covers the canvas while scaled > 1, and a pan by `offset`
stays inside the frame only while `scale - 1 >= |offset|`. Every preset below
keeps a margin so no blank edge is ever exposed.
"""
from __future__ import annotations

from . import config

# The motion vocabulary Claude may use in the storyboard.
MOTIONS = frozenset({
    "static", "zoom_in", "zoom_out",
    "pan_left", "pan_right", "pan_up", "pan_down",
    "zoom_in_pan_left", "zoom_in_pan_right",
})


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def plan_keyframes(motion: str, dur: float) -> list[dict]:
    """Return an ordered list of {prop, t, value} keyframes for `motion` over a
    scene of `dur` seconds. `prop` is one of position_x/position_y/scale_x/scale_y.

    Pure and side-effect free so it can be unit-tested. Guarantees:
      * never emits "uniform_scale"
      * every scale_x keyframe has a matching scale_y at the same time & value
      * scale >= 1.0 at every keyframe, and >= 1 + |offset| whenever panning
      * all times lie within [0, dur]
    """
    dur = max(0.01, float(dur))
    if motion not in MOTIONS:
        raise ValueError(f"unknown motion: {motion!r}")

    zmin, zmax = config.ZOOM_MIN, config.ZOOM_MAX
    ps, off = config.PAN_SCALE, config.PAN_OFFSET

    def scale_pair(t: float, value: float) -> list[dict]:
        return [{"prop": "scale_x", "t": t, "value": value},
                {"prop": "scale_y", "t": t, "value": value}]

    kfs: list[dict] = []
    if motion == "static":
        # No motion — leave the segment at its default 1.0 scale, centred.
        return kfs

    if motion == "zoom_in":
        kfs += scale_pair(0.0, zmin) + scale_pair(dur, zmax)
        return kfs
    if motion == "zoom_out":
        kfs += scale_pair(0.0, zmax) + scale_pair(dur, zmin)
        return kfs

    if motion in ("pan_left", "pan_right", "pan_up", "pan_down"):
        # Hold a constant scale (> 1 + off) and slide across.
        kfs += scale_pair(0.0, ps) + scale_pair(dur, ps)
        axis = "position_x" if motion in ("pan_left", "pan_right") else "position_y"
        # pan_left: content enters from the left  -> travel +off -> -off
        # pan_up:   camera rises                  -> travel -off -> +off
        if motion in ("pan_left", "pan_up"):
            start_v, end_v = (+off, -off) if motion == "pan_left" else (-off, +off)
        else:  # pan_right, pan_down
            start_v, end_v = (-off, +off) if motion == "pan_right" else (+off, -off)
        kfs += [{"prop": axis, "t": 0.0, "value": start_v},
                {"prop": axis, "t": dur, "value": end_v}]
        return kfs

    if motion in ("zoom_in_pan_left", "zoom_in_pan_right"):
        # Combine a zoom with a pan; start scale already exceeds |off| so the
        # edge is never exposed even at the start of the move.
        s0, s1 = ps, zmax
        kfs += scale_pair(0.0, s0) + scale_pair(dur, s1)
        start_v, end_v = (+off, -off) if motion.endswith("left") else (-off, +off)
        kfs += [{"prop": "position_x", "t": 0.0, "value": start_v},
                {"prop": "position_x", "t": dur, "value": end_v}]
        return kfs

    return kfs  # unreachable (guarded above)


# pycapcut KeyframeProperty attribute name per our prop string.
_PROP_ATTR = {
    "position_x": "position_x", "position_y": "position_y",
    "scale_x": "scale_x", "scale_y": "scale_y",
}


def apply(seg, p, motion: str, dur: float) -> None:
    """Add the motion's keyframes to a pycapcut VideoSegment `seg`.

    Order matters: a scale_x keyframe flips the segment's internal uniform_scale
    flag off (segment.py:231), after which scale_y is accepted. plan_keyframes
    always pairs them, so we're safe.
    """
    for kf in plan_keyframes(motion, dur):
        prop = getattr(p.KeyframeProperty, _PROP_ATTR[kf["prop"]])
        seg.add_keyframe(prop, _secs(kf["t"]), float(kf["value"]))
