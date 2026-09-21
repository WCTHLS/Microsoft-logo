import colorsys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

try:
    from scipy import ndimage
    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    _HAS_SCIPY = False


# The PDF/reference badge uses one coordinated theme for BOTH zones.
# Never resolve the face and ribbon as two independent themes.
THEME_GRADES = {
    "purple": {
        "inner": "#0F0717 - #532982",
        "outer": "#6B3F9E - #C6B1DE",
        "ribbon_back": "#8A5AB5 - #D4C2E6",
        "ribbon_front": "#7548A5 - #B79BD0",
    },
    "teal": {
        "inner": "#001D1F - #00666D",
        "outer": "#18BFCA - #A6E9ED",
        "ribbon_back": "#35C8D1 - #B4ECEF",
        "ribbon_front": "#20AEB9 - #82D7DD",
    },
    "blue": {
        # Sampled from the supplied real Microsoft badge.
        "inner": "#0A2134 - #1E4D75",
        "outer": "#4889CC - #AAD0F0",
        # Kept for compatibility with callers that expect these keys.
        "ribbon_back": "#5796D5 - #AACFF0",
        "ribbon_front": "#4685C3 - #95B7D6",
    },
}

# Measured from the real reference badge: fitting lightness against pixel
# (x, y) position for the face gives a diagonal gradient (dark bottom-left ->
# light top-right) at roughly -40 degrees, NOT a horizontal grade. See
# analysis notes in the accompanying explanation.
GRADIENT_ANGLE_DEG = -40.0
SHADING_STRENGTH = 0.0
WHITE_L = 0.90
SEAM_MAX_SIZE = 600

# How strongly the outer/ribbon zone's local light/dark structure (seam,
# ribbon faces) is allowed to nudge lightness away from the flat target
# gradient, and how far that nudge is allowed to go.
OUTER_SHADE_GAIN = 1.1
OUTER_SHADE_CLIP = 0.16


def _hex_to_rgb(value):
    value = str(value).strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"Invalid hex colour: {value!r}")
    return np.array(
        [int(value[i:i + 2], 16) for i in (0, 2, 4)],
        dtype=np.float32,
    )


def _split_stops(value):
    text = str(value or "").replace("\u2013", "-").replace("\u2014", "-")
    tokens = [token.strip().lstrip("#") for token in text.split("-")]
    return [token for token in tokens if len(token) in (3, 6)]


def _lighten(rgb, lightness_delta, saturation_delta=0.0):
    r, g, b = rgb / 255.0
    h, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    lightness = min(1.0, max(0.0, lightness + lightness_delta))
    saturation = min(1.0, max(0.0, saturation + saturation_delta))
    return np.array(
        colorsys.hls_to_rgb(h, lightness, saturation),
        dtype=np.float32,
    ) * 255.0


# ---------------------------------------------------------------------------
# Vectorised RGB <-> HLS. We need per-pixel HLS math for the outer-zone
# shading step below. Doing that shading in raw RGB (multiplying all three
# channels by the same ratio) is what caused the cyan-tinted highlight bug:
# once the brightest channel clips at 1.0 the others keep rising, so the hue
# silently drifts. Adjusting lightness in HLS space and converting back
# cannot shift hue, because hue/saturation are set directly rather than
# emerging from clipped channel ratios.
# ---------------------------------------------------------------------------
def _rgb_to_hls_np(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    l = (minc + maxc) / 2.0
    delta = maxc - minc

    s = np.zeros_like(l)
    nz = delta > 1e-6
    denom_low = maxc + minc
    denom_high = 2.0 - maxc - minc
    s[nz] = np.where(
        l[nz] <= 0.5,
        delta[nz] / np.where(denom_low[nz] == 0, 1.0, denom_low[nz]),
        delta[nz] / np.where(denom_high[nz] == 0, 1.0, denom_high[nz]),
    )

    safe_delta = np.where(nz, delta, 1.0)
    rc = (maxc - r) / safe_delta
    gc = (maxc - g) / safe_delta
    bc = (maxc - b) / safe_delta

    h = np.zeros_like(l)
    h = np.where(r == maxc, bc - gc, h)
    h = np.where((g == maxc) & (r != maxc), 2.0 + rc - bc, h)
    h = np.where((b == maxc) & (r != maxc) & (g != maxc), 4.0 + gc - rc, h)
    h = (h / 6.0) % 1.0
    h = np.where(nz, h, 0.0)
    return h, l, s


def _hls_to_rgb_np(h, l, s):
    def _channel(m1, m2, hue):
        hue = hue % 1.0
        return np.where(
            hue < 1.0 / 6.0,
            m1 + (m2 - m1) * hue * 6.0,
            np.where(
                hue < 0.5,
                m2,
                np.where(
                    hue < 2.0 / 3.0,
                    m1 + (m2 - m1) * (2.0 / 3.0 - hue) * 6.0,
                    m1,
                ),
            ),
        )

    m2 = np.where(l <= 0.5, l * (1.0 + s), l + s - l * s)
    m1 = 2.0 * l - m2
    r = _channel(m1, m2, h + 1.0 / 3.0)
    g = _channel(m1, m2, h)
    b = _channel(m1, m2, h - 1.0 / 3.0)
    return np.stack([r, g, b], axis=-1)


def _theme_distance(value, theme_name, role=None):
    stops = _split_stops(value)
    if not stops:
        return float("inf")

    input_colours = [_hex_to_rgb(stop) for stop in stops]
    roles = (role,) if role in ("inner", "outer") else ("inner", "outer")
    reference_colours = []
    for candidate_role in roles:
        reference_colours.extend(
            _hex_to_rgb(stop)
            for stop in _split_stops(THEME_GRADES[theme_name][candidate_role])
        )

    return min(
        float(np.abs(source - reference).sum())
        for source in input_colours
        for reference in reference_colours
    )


def _detect_coordinated_theme(inner_grade, outer_grade):
    """Choose ONE theme for the complete badge.

    Inner colour is authoritative because it identifies the badge face most
    reliably. This also fixes mixed input such as a blue inner face together
    with an accidentally extracted teal outer stop. Only if the inner value
    does not resemble an official theme do we inspect the outer value.
    """
    inner_scores = {
        name: _theme_distance(inner_grade, name, role="inner")
        for name in THEME_GRADES
    }
    inner_theme = min(inner_scores, key=inner_scores.get)
    if inner_scores[inner_theme] <= 96:
        return inner_theme

    outer_scores = {
        name: _theme_distance(outer_grade, name, role="outer")
        for name in THEME_GRADES
    }
    outer_theme = min(outer_scores, key=outer_scores.get)
    if outer_scores[outer_theme] <= 96:
        return outer_theme

    return None


def _resolve_custom_grade(value, role):
    stops = _split_stops(value)
    if len(stops) >= 2:
        return _hex_to_rgb(stops[0]), _hex_to_rgb(stops[1])

    colour = (
        _hex_to_rgb(stops[0])
        if stops
        else np.array([128, 128, 128], dtype=np.float32)
    )
    if role == "inner":
        return colour, _lighten(colour, 0.28, 0.05)
    return colour, _lighten(colour, 0.32, -0.05)


def _official_grade(theme_name, role):
    stops = _split_stops(THEME_GRADES[theme_name][role])
    return _hex_to_rgb(stops[0]), _hex_to_rgb(stops[1])


def recolor_diamond_badge(
    image: Image.Image,
    outer_grade: str,
    inner_grade: str,
    angle_deg: float = GRADIENT_ANGLE_DEG,
    shading: float = SHADING_STRENGTH,
    white_gap_ring: bool = True,
    remove_background: bool = True,
    clean_seams: bool = False,
) -> Image.Image:
    """Recolour the diamond badge while preserving 100% of template sharpness,
    3D ribbon depth, textures, and anti-aliased edge transitions."""
    source = image.convert("RGBA")
    
    # Detect requested theme
    theme = _detect_coordinated_theme(inner_grade, outer_grade)
    
    # Native template support:
    # Purple uses diamond_template.png directly
    if theme == "purple":
        return source
    # Teal uses diamond_template_teal.jpg directly
    if theme == "teal":
        return source

    arr = np.asarray(source).astype(np.float32)
    rgb = arr[:, :, :3] / 255.0
    alpha = arr[:, :, 3].copy()
    opaque = alpha > 10

    # For other colors derived from the teal template, base hue is teal (H≈0.510)
    base_h = 0.510

    # Determine target hue and saturation scaling
    if theme == "blue":
        target_h = 0.575
        sat_scale = 1.0
    elif theme and theme in THEME_GRADES:
        stops = _split_stops(THEME_GRADES[theme]["outer"])
        ref_rgb = _hex_to_rgb(stops[0]) / 255.0
        target_h, target_l, target_s = colorsys.rgb_to_hls(ref_rgb[0], ref_rgb[1], ref_rgb[2])
        sat_scale = float(np.clip(target_s / 0.50, 0.5, 2.0))
    else:
        stops = _split_stops(outer_grade) or _split_stops(inner_grade)
        ref_rgb = _hex_to_rgb(stops[0]) / 255.0 if stops else np.array([0.42, 0.25, 0.62], dtype=np.float32)
        target_h, target_l, target_s = colorsys.rgb_to_hls(ref_rgb[0], ref_rgb[1], ref_rgb[2])
        sat_scale = 1.0

    delta_h = target_h - base_h

    # Convert entire template to HLS
    h, l, s = _rgb_to_hls_np(rgb)

    # Only protect truly neutral white/near-white border pixels
    neutral_white = (l > 0.88) & (s < 0.10) & opaque
    colored = opaque & ~neutral_white

    # Shift hue and scale saturation for colored areas
    new_h = h.copy()
    new_s = s.copy()

    new_h[colored] = (h[colored] + delta_h) % 1.0
    new_s[colored] = np.clip(s[colored] * sat_scale, 0.0, 1.0)

    # Convert back to RGB (lightness stays 100% original)
    new_rgb = _hls_to_rgb_np(new_h, l, new_s)

    # Ensure white pixels remain untouched
    new_rgb[neutral_white] = rgb[neutral_white]

    output = np.dstack(
        [np.clip(new_rgb * 255.0, 0, 255), alpha]
    ).astype(np.uint8)

    return Image.fromarray(output, "RGBA")


def load_diamond_template(badge) -> Image.Image:
    """Load diamond_template.png for purple, and diamond_template_teal.jpg for teal and blue."""
    template_dir = Path(__file__).parent.parent / "templates"
    
    theme = _detect_coordinated_theme(
        badge.inner_colour if hasattr(badge, 'inner_colour') else "",
        badge.outer_colour if hasattr(badge, 'outer_colour') else "",
    )
    
    # Purple uses the native purple template
    if theme == "purple":
        template_path = template_dir / "diamond_template.png"
    else:
        # Teal, blue, and other colors use diamond_template_teal.jpg
        template_path = template_dir / "diamond_template_teal.jpg"
        if not template_path.exists():
            template_path = template_dir / "diamond_template_teal.png"
        if not template_path.exists():
            template_path = template_dir / "diamond_template.png"

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found at {template_path}")
    
    base = Image.open(template_path).convert("RGBA")
    return recolor_diamond_badge(
        base,
        outer_grade=badge.outer_colour,
        inner_grade=badge.inner_colour,
    )
