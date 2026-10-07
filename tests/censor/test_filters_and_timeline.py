from censor import filters, timeline
from censor.encode import encode_cmd

PLAN = {
    "crop": {"x": 100, "y": 0, "w": 1920, "h": 1080, "out_w": 1280, "out_h": 720},
    "blur": [{"name": "key", "box": [10, 20, 100, 50], "windows": [[1.0, 2.0], [5.0, 6.0]]},
             {"name": "name", "box": [0, 0, 40, 40], "windows": [[3.0, 4.0]]}],
    "mute": [{"name": "phone", "window": [7.0, 8.0]}],
}


def test_filter_covers_every_box_and_window():
    f = filters.build_filter(PLAN)
    assert "split=3" in f                      # one leg per box + the base
    for a, z in ((1.0, 2.0), (5.0, 6.0), (3.0, 4.0)):
        assert f"between(t,{a},{z})" in f
    assert "crop=1920:1080:100:0,scale=1280:720[vout]" in f
    assert "volume=0" in f and "[aout]" in f


def test_preview_is_video_only_and_resized():
    f = filters.build_filter(PLAN, preview="640x360")
    assert "scale=640:360[vout]" in f
    # No audio leg: a preview is for looking at boxes, and encoding audio would
    # only slow it down.
    assert "[aout]" not in f
    assert not filters.has_audio_leg(PLAN, preview="640x360")


def test_encode_maps_the_filter_audio_only_when_it_exists():
    with_audio = encode_cmd("in.mp4", "out.mp4", "f.filter", audio_leg=True)
    assert "[aout]" in with_audio and "-c:a" in with_audio and "aac" in with_audio

    without = encode_cmd("in.mp4", "out.mp4", "f.filter", audio_leg=False)
    assert "[aout]" not in without
    assert "0:a?" in without and "copy" in without


EDL = {"keep": [{"start": 0.0, "end": 10.0},      # 0–10   -> 0–10
                {"start": 20.0, "end": 30.0}]}    # 20–30  -> 10–20


def test_window_inside_one_kept_segment():
    assert timeline.map_window(2.0, 4.0, EDL["keep"]) == [[2.0, 4.0]]


def test_window_shifts_by_earlier_cuts():
    # 22–24 in the source sits 2s into the second kept segment, which starts at
    # 10s on the timeline.
    assert timeline.map_window(22.0, 24.0, EDL["keep"]) == [[12.0, 14.0]]


def test_window_spanning_a_cut_is_merged_into_one_span():
    # 8–10 and 20–22 survive the cut and land back to back on the timeline, so
    # they read as one continuous window rather than two.
    assert timeline.map_window(8.0, 22.0, EDL["keep"]) == [[8.0, 12.0]]


def test_window_removed_by_the_cut_maps_to_nothing():
    assert timeline.map_window(12.0, 18.0, EDL["keep"]) == []


def test_intro_offsets_every_span():
    assert timeline.map_window(2.0, 4.0, EDL["keep"], 5.0) == [[7.0, 9.0]]


def test_content_duration_counts_intro_plus_kept():
    assert timeline.content_duration(EDL, 5.0) == 25.0
