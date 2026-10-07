from finishing.style import hex_to_rgb01, subtitle_style, subtitle_background, resolve_font

def test_hex_to_rgb01():
    assert hex_to_rgb01("#FFFFFF") == (1.0, 1.0, 1.0)
    assert hex_to_rgb01("#000000") == (0.0, 0.0, 0.0)
    r, g, b = hex_to_rgb01("#22D3EE")
    assert abs(r - 34/255) < 1e-6 and abs(g - 211/255) < 1e-6 and abs(b - 238/255) < 1e-6

def test_subtitle_style_emphasis_keeps_consistent_size_changes_color():
    base = subtitle_style(False, "#22D3EE")
    emph = subtitle_style(True, "#22D3EE")
    # Consistent size — emphasis changes weight/color only, not scale.
    assert emph.size == base.size
    assert emph.bold and not base.bold
    assert base.color == (1.0, 1.0, 1.0)
    assert emph.color == hex_to_rgb01("#22D3EE")
    assert base.align == 1 and emph.align == 1  # centered

def test_subtitle_background_is_rounded_translucent():
    bg = subtitle_background()
    assert bg.round_radius > 0
    assert 0.0 < bg.alpha < 1.0

def test_resolve_font_known_and_unknown():
    assert resolve_font("Montserrat") is not None
    assert resolve_font("NoSuchFont___") is None


def test_glass_cards_are_horizontally_centered():
    # Wide glass cards must sit centered (transform_x == 0); a sideways offset
    # would push a near-full-width card off-center and clip it.
    from finishing import config
    for key in ("left_card", "right_card", "bottom_banner", "floating_label"):
        tx = config.LAYOUT[key][0]
        assert tx == 0.0, f"{key} should be centered (transform_x=0), got {tx}"
