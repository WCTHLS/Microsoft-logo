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
    clean_seams: bool = True,
) -> Image.Image:
    """Recolour the complete diamond using one coordinated badge theme."""
    source = image.convert("RGBA")
    arr = np.asarray(source).astype(np.float32)
    rgb = arr[:, :, :3] / 255.0
    alpha = arr[:, :, 3].copy()
    height, width = alpha.shape
    opaque = alpha > 0

    # Use one theme for face, frame and ribbon. This is the important fix.
    theme = _detect_coordinated_theme(inner_grade, outer_grade)
    if theme:
        inner_start, inner_end = _official_grade(theme, "inner")
        outer_start, outer_end = _official_grade(theme, "outer")
        ribbon_back_start, ribbon_back_end = _official_grade(theme, "ribbon_back")
        ribbon_front_start, ribbon_front_end = _official_grade(theme, "ribbon_front")
    else:
        inner_start, inner_end = _resolve_custom_grade(inner_grade, "inner")
        outer_start, outer_end = _resolve_custom_grade(outer_grade, "outer")
        # For custom themes, derive two related ribbon grades while preserving
        # the same separation used by the official themes.
        ribbon_back_start, ribbon_back_end = (
            _lighten(outer_start, 0.06, 0.0),
            _lighten(outer_end, 0.04, 0.0),
        )
        ribbon_front_start, ribbon_front_end = (
            _lighten(outer_start, -0.02, 0.0),
            _lighten(outer_end, -0.08, 0.0),
        )

    # Geometry mask of the central face. Bright source highlights cannot leak
    # into the ribbon classification.
    face_points = [
        (0.500 * width, 0.074 * height),
        (0.086 * width, 0.207 * height),
        (0.086 * width, 0.620 * height),
        (0.500 * width, 0.739 * height),
        (0.914 * width, 0.620 * height),
        (0.914 * width, 0.207 * height),
    ]
    face_image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(face_image).polygon(face_points, fill=255)
    face_geometry = np.asarray(face_image) > 0

    lightness = (rgb.max(2) + rgb.min(2)) / 2.0
    chroma = rgb.max(2) - rgb.min(2)
    neutral_white = (lightness > WHITE_L) & (chroma < 0.035) & opaque

    # Preserve the source template's exact front-ribbon overlap at the lower
    # V seam. The face polygon remains unchanged. Only bright source pixels in
    # the seam area are classified as ribbon, so no extra parallel strip is
    # created above the ribbon.
    lower_seam_zone = np.zeros_like(face_geometry)
    lower_seam_zone[int(0.585 * height):int(0.755 * height), :] = True
    source_front_ribbon = lower_seam_zone & (lightness > 0.40) & opaque

    inner_mask = face_geometry & opaque & ~neutral_white & ~source_front_ribbon
    outer_mask = ((~face_geometry) | source_front_ribbon) & opaque & ~neutral_white

    # Keep the exact source geometry for the complete outer artwork.
    # Do not create ribbon polygons: the template already contains the correct
    # ribbon faces, seam, side tabs and anti-aliased edges.
    outer_frame_mask = outer_mask
    white_mask = neutral_white

    # Diagonal grade (see GRADIENT_ANGLE_DEG note above), shared by both
    # zones so face, frame and ribbon read as one coordinated light source.
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    angle = np.deg2rad(angle_deg)
    projection = np.cos(angle) * xx + np.sin(angle) * yy

    def paint(mask, start, end):
        if not mask.any():
            return
        values = projection[mask]
        t = (values - values.min()) / (values.max() - values.min() + 1e-6)
        colour = (
            start[None, :] * (1.0 - t[:, None])
            + end[None, :] * t[:, None]
        ) / 255.0

        # Disabled by default. Kept only for API compatibility.
        if shading > 0.0:
            zone_lightness = lightness[mask]
            delta = np.clip(
                zone_lightness - float(np.median(zone_lightness)),
                -0.06,
                0.06,
            )
            colour = np.clip(colour + delta[:, None] * shading, 0.0, 1.0)

        rgb[mask] = colour

    paint(inner_mask, inner_start, inner_end)

    # Preserve the template's local light/dark structure for the entire outer
    # artwork. This retains the two ribbon faces instead of flattening them
    # into one colour. The target diagonal grade still controls the overall
    # blue. Shading is applied as a lightness-only nudge in HLS space (not a
    # per-channel RGB multiply) so bright highlights can't clip one channel
    # before another and drift the hue toward cyan.
    if outer_frame_mask.any():
        values = projection[outer_frame_mask]
        t = (values - values.min()) / (values.max() - values.min() + 1e-6)
        base_colour = (
            outer_start[None, :] * (1.0 - t[:, None])
            + outer_end[None, :] * t[:, None]
        ) / 255.0

        base_h, base_l, base_s = _rgb_to_hls_np(base_colour)

        src_l = lightness[outer_frame_mask]
        median_l = float(np.median(src_l))
        delta_l = np.clip(
            (src_l - median_l) * OUTER_SHADE_GAIN, -OUTER_SHADE_CLIP, OUTER_SHADE_CLIP
        )
        shaded_l = np.clip(base_l + delta_l, 0.0, 1.0)

        colour = np.clip(_hls_to_rgb_np(base_h, shaded_l, base_s), 0.0, 1.0)
        rgb[outer_frame_mask] = colour

    # Separate transparent canvas background from the interior white gap.
    background_mask = np.zeros_like(white_mask)
    seam_mask = np.zeros_like(white_mask)
    if _HAS_SCIPY and white_mask.any():
        labels, count = ndimage.label(white_mask)
        if count:
            border_labels = (
                set(labels[0, :])
                | set(labels[-1, :])
                | set(labels[:, 0])
                | set(labels[:, -1])
            )
            border_labels.discard(0)
            if border_labels:
                background_mask = np.isin(labels, list(border_labels))

            if clean_seams:
                sizes = ndimage.sum(
                    np.ones_like(labels), labels, index=range(1, count + 1)
                )
                seam_labels = [
                    label
                    for label in (np.where(sizes < SEAM_MAX_SIZE)[0] + 1)
                    if label not in border_labels
                ]
                if seam_labels:
                    seam_mask = np.isin(labels, seam_labels)

    # Tiny antialias specks use the coordinated outer start, never a separately
    # inferred colour.
    if seam_mask.any():
        rgb[seam_mask] = outer_start / 255.0

    output = np.dstack(
        [np.clip(rgb * 255.0, 0, 255), alpha]
    ).astype(np.uint8)

    if remove_background and background_mask.any():
        output[background_mask, 3] = 0

    return Image.fromarray(output, "RGBA")


def load_diamond_template(badge) -> Image.Image:
    base = Image.open(
        Path(__file__).parent.parent / "templates" / "diamond_template.png"
    )
    return recolor_diamond_badge(
        base,
        outer_grade=badge.outer_colour,
        inner_grade=badge.inner_colour,
    )
