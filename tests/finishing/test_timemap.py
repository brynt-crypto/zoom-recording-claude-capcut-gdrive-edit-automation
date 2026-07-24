from finishing.timemap import build_segments, src_to_final, enrich_transcript

EDL = {"source": "c.mp4", "fps": 30, "width": 1920, "height": 1080,
       "keep": [{"start": 10.0, "end": 13.0}, {"start": 20.0, "end": 22.0}]}

def test_segments_lay_end_to_end():
    segs = build_segments(EDL)
    assert segs[0] == {"src_start": 10.0, "src_end": 13.0, "final_start": 0.0, "final_end": 3.0}
    assert segs[1] == {"src_start": 20.0, "src_end": 22.0, "final_start": 3.0, "final_end": 5.0}

def test_segments_with_intro_offset():
    segs = build_segments(EDL, intro_dur=2.0)
    assert segs[0]["final_start"] == 2.0

def test_src_to_final_inside_and_cut():
    segs = build_segments(EDL)
    assert src_to_final(21.0, segs) == 4.0      # 3.0 + (21-20)
    assert src_to_final(15.0, segs) is None      # falls in a cut

def test_enrich_drops_cut_words():
    t = {"source": "c.mp4", "fps": 30.0, "width": 1920, "height": 1080,
         "words": [{"i": 0, "start": 11.0, "end": 11.5, "text": "kept"},
                   {"i": 1, "start": 15.0, "end": 15.5, "text": "cut"}]}
    out = enrich_transcript(t, EDL)
    assert [w["text"] for w in out["words"]] == ["kept"]
    assert out["words"][0]["final_start"] == 1.0
    assert out["final_duration"] == 5.0
