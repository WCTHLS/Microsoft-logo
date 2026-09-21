import base64
import re
from pathlib import Path
from io import BytesIO
from typing import Optional, Tuple

import cairosvg
from PIL import Image, ImageDraw

from models.badge_details import BadgeDetails
from xml.sax.saxutils import escape


class CircleRenderer:

    # ------------------------------------------------------------------
    # INTERNAL COORDINATE SYSTEM
    # ------------------------------------------------------------------
    WIDTH = 512
    HEIGHT = 512

    # ------------------------------------------------------------------
    # OUTPUT RESOLUTION
    # ------------------------------------------------------------------
    TARGET_SIZE = 2048
    DISPLAY_SIZE = TARGET_SIZE

    CENTER_X = 256
    CENTER_Y = 256

    OUTER_RADIUS = 220
    WHITE_RING_RADIUS = 191
    INNER_RADIUS = 152

    # ------------------------------------------------------------------
    # TOP ARC TEXT
    # ------------------------------------------------------------------
    ARC_TEXT_RADIUS = 163

    # ------------------------------------------------------------------
    # DATE ARC
    # ------------------------------------------------------------------
    DATE_ARC_RADIUS = 187
    DATE_DY = -8

    # ------------------------------------------------------------------
    # RIBBON
    # ------------------------------------------------------------------
    RIBBON_TOP = CENTER_Y + 54
    RIBBON_BOTTOM = CENTER_Y + 131

    # ------------------------------------------------------------------
    # MICROSOFT LOGO
    # ------------------------------------------------------------------
    LOGO_Y_TOP = CENTER_Y - round(INNER_RADIUS * 0.645)
    LOGO_HEIGHT = round(INNER_RADIUS * 0.270)
    LOGO_HALF_WIDTH = round(INNER_RADIUS * 0.575)
    LOGO_X = CENTER_X - LOGO_HALF_WIDTH
    LOGO_WIDTH = LOGO_HALF_WIDTH * 2

    # ------------------------------------------------------------------
    # ACHIEVEMENT TEXT
    # ------------------------------------------------------------------
    ACHIEVEMENT_Y = CENTER_Y + round(INNER_RADIUS * 0.030)
    ACHIEVEMENT_FONT_SIZE = 44
    ACHIEVEMENT_FONT_WEIGHT = 700

    # ------------------------------------------------------------------
    # PARTNER LOGO PLACEMENT
    # ------------------------------------------------------------------
    PARTNER_LOGO_CENTER_X = CENTER_X
    PARTNER_LOGO_CENTER_Y = ACHIEVEMENT_Y
    PARTNER_LOGO_MAX_WIDTH = round(INNER_RADIUS * 1.60)
    PARTNER_LOGO_MAX_HEIGHT = round(INNER_RADIUS * 0.52)
    PARTNER_LOGO_ALLOW_UPSCALE = True

    # ------------------------------------------------------------------
    # STACKED LAYOUT  (when BOTH partner logo AND achievement are present)
    # Partner logo sits on top, achievement text sits below it.
    # ------------------------------------------------------------------
    # Dedicated stacked layout when BOTH partner logo and achievement exist.
    STACK_PARTNER_CENTER_Y = CENTER_Y - 14
    STACK_ACHIEVEMENT_CENTER_Y = CENTER_Y + 28
    STACK_PARTNER_LOGO_MAX_WIDTH = round(INNER_RADIUS * 1.40)
    STACK_PARTNER_LOGO_MAX_HEIGHT = round(INNER_RADIUS * 0.27)
    STACK_ACHIEVEMENT_FONT_SIZE = 34
    STACK_ACHIEVEMENT_USABLE = 320
    STACK_ACHIEVEMENT_MIN = 18

    # ------------------------------------------------------------------
    # AUTO-FIT LIMITS
    # ------------------------------------------------------------------
    ARC_TEXT_BASE = 24
    ARC_TEXT_USABLE = 440
    ARC_TEXT_MIN = 14

    RIBBON_TEXT_BASE = 23
    RIBBON_TEXT_USABLE = 280
    RIBBON_TEXT_MIN = 8
    RIBBON_TEXT_WEIGHT = 400

    # ------------------------------------------------------------------
    # MICROSOFT LOGO ASSET
    # ------------------------------------------------------------------
    logo_path = Path(__file__).resolve().parent.parent / "logo" / "microsoft_logo.png"

    # ------------------------------------------------------------------
    # CIRCLE THEME COLOURS
    # ------------------------------------------------------------------
    CIRCLE_THEMES = {
        "teal": {
            "anchors": ["#1399A2", "#0E7379", "#18BFCA", "#008080",
                        "#A6E9ED", "#001D1F", "#00666D"],
            "outer": "#1399A2", "ribbon": "#0E7379",
        },
        "blue": {
            "anchors": ["#3487C7", "#2A6C9F", "#BFDDF5", "#091823", "#20547C"],
            "outer": "#3487C7", "ribbon": "#2A6C9F",
        },
        "purple": {
            "anchors": ["#6B3F9E", "#532982", "#C6B1DE", "#0F0717"],
            "outer": "#6B3F9E", "ribbon": "#532982",
        },
    }

    # ------------------------------------------------------------------
    # COLOUR HELPERS
    # ------------------------------------------------------------------
    def _first_hex(self, value):
        match = re.findall(r"#?[0-9A-Fa-f]{6}", str(value))
        if not match:
            return None
        return ("#" + match[0].lstrip("#")).upper()

    def _hex_rgb(self, hex_colour: str) -> Tuple[int, int, int]:
        hex_colour = hex_colour.lstrip("#")
        return tuple(int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))

    def _resolve_circle_colours(self, badge: BadgeDetails) -> Tuple[str, str]:
        candidates = []
        for value in (getattr(badge, "outer_colour", None),
                      getattr(badge, "inner_colour", None)):
            hex_colour = self._first_hex(value)
            if hex_colour:
                candidates.append(self._hex_rgb(hex_colour))

        best_theme = "teal"
        best_distance = float("inf")

        if candidates:
            for theme_name, specification in self.CIRCLE_THEMES.items():
                for anchor in specification["anchors"]:
                    anchor_rgb = self._hex_rgb(anchor)
                    for candidate in candidates:
                        distance = sum(
                            abs(a - b)
                            for a, b in zip(anchor_rgb, candidate)
                        )
                        if distance < best_distance:
                            best_distance = distance
                            best_theme = theme_name

        specification = self.CIRCLE_THEMES[best_theme]
        return specification["outer"], specification["ribbon"]

    # ------------------------------------------------------------------
    # TEXT AUTO-FIT
    # ------------------------------------------------------------------
    def _text_width(self, text, font_size, weight) -> int:
        text = str(text or "")
        if not text:
            return 0
        safe_text = escape(text)
        measurement_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="4000" height="400">'
            '<text x="20" y="200" '
            "font-family=\"'Segoe UI', Arial, sans-serif\" "
            f'font-size="{font_size}" font-weight="{weight}">'
            f'{safe_text}</text></svg>'
        )
        png = cairosvg.svg2png(
            bytestring=measurement_svg.encode("utf-8"),
            output_width=4000,
            output_height=400,
        )
        with Image.open(BytesIO(png)) as rendered_text:
            bounding_box = rendered_text.getbbox()
        if not bounding_box:
            return 0
        return bounding_box[2] - bounding_box[0]

    def _fit_font_size(self, text, base, usable, weight, min_size) -> int:
        width = self._text_width(text, base, weight)
        if width <= 0 or width <= usable:
            return base
        return max(min_size, int(base * usable / width))

    # ------------------------------------------------------------------
    # MICROSOFT LOGO EMBEDDING
    # ------------------------------------------------------------------
    def _embed_logo(self, logo_path: str) -> str:
        if not logo_path:
            return ""
        path = Path(logo_path)
        if not path.exists() or not path.is_file():
            return ""
        data = path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    # ------------------------------------------------------------------
    # PARTNER LOGO BYTE NORMALIZATION
    # ------------------------------------------------------------------
    def _normalize_logo_bytes(self, logo_data):
        if logo_data is None:
            return None
        if isinstance(logo_data, memoryview):
            return logo_data.tobytes()
        if isinstance(logo_data, bytearray):
            return bytes(logo_data)
        if isinstance(logo_data, bytes):
            return logo_data
        return None

    # ------------------------------------------------------------------
    # PARTNER LOGO TRANSPARENT PADDING REMOVAL
    # ------------------------------------------------------------------
    def _trim_transparent_padding(self, image: Image.Image) -> Image.Image:
        image = image.convert("RGBA")

        # If the upload already has transparency, crop by the alpha channel.
        alpha_channel = image.getchannel("A")
        bounding_box = alpha_channel.getbbox()
        full_box = (0, 0, image.width, image.height)
        if bounding_box and bounding_box != full_box:
            return image.crop(bounding_box)

        # PNG/JPG/WEBP partner logos often arrive on a large opaque white
        # canvas. Remove only the edge-connected background, then crop to the
        # visible logo. This makes different source canvas sizes render at the
        # same badge size without deleting enclosed white areas in a logo.
        rgb_probe = image.convert("RGB")
        marker = (1, 2, 3)
        corners = (
            (0, 0),
            (image.width - 1, 0),
            (0, image.height - 1),
            (image.width - 1, image.height - 1),
        )

        corner_colours = [rgb_probe.getpixel(point) for point in corners]
        light_background = all(min(colour) >= 220 for colour in corner_colours)
        corner_spread = max(
            max(colour[channel] for colour in corner_colours)
            - min(colour[channel] for colour in corner_colours)
            for channel in range(3)
        )

        if light_background and corner_spread <= 24:
            for point in corners:
                if rgb_probe.getpixel(point) != marker:
                    ImageDraw.floodfill(
                        rgb_probe,
                        point,
                        marker,
                        thresh=28,
                    )

            cleaned_alpha = image.getchannel("A")
            alpha_pixels = cleaned_alpha.load()
            probe_pixels = rgb_probe.load()
            for y in range(image.height):
                for x in range(image.width):
                    if probe_pixels[x, y] == marker:
                        alpha_pixels[x, y] = 0

            image.putalpha(cleaned_alpha)
            bounding_box = cleaned_alpha.getbbox()
            if bounding_box:
                image = image.crop(bounding_box)

        return image

    # ------------------------------------------------------------------
    # PARTNER LOGO PREPARATION
    #   max_height lets callers shrink the logo (used in the stacked layout).
    # ------------------------------------------------------------------
    def _prepare_partner_logo(self, logo_data,
                              max_height=None,
                              max_width=None) -> Tuple[str, int, int]:
        logo_bytes = self._normalize_logo_bytes(logo_data)
        if not logo_bytes:
            return "", 0, 0

        try:
            with Image.open(BytesIO(logo_bytes)) as source:
                partner_logo = source.convert("RGBA")
        except Exception as error:
            raise ValueError(
                "The partner logo retrieved from PostgreSQL "
                "is not a valid image."
            ) from error

        partner_logo = self._trim_transparent_padding(partner_logo)
        source_width, source_height = partner_logo.size
        if source_width <= 0 or source_height <= 0:
            return "", 0, 0

        limit_height = max_height or self.PARTNER_LOGO_MAX_HEIGHT
        limit_width = max_width or self.PARTNER_LOGO_MAX_WIDTH

        width_scale = limit_width / source_width
        height_scale = limit_height / source_height
        scale = min(width_scale, height_scale)

        if not self.PARTNER_LOGO_ALLOW_UPSCALE:
            scale = min(scale, 1.0)

        rendered_width = max(1, int(round(source_width * scale)))
        rendered_height = max(1, int(round(source_height * scale)))

        partner_logo = partner_logo.resize(
            (rendered_width, rendered_height),
            Image.Resampling.LANCZOS,
        )

        output = BytesIO()
        partner_logo.save(output, format="PNG", optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        partner_uri = f"data:image/png;base64,{encoded}"

        return partner_uri, rendered_width, rendered_height

    # ------------------------------------------------------------------
    # ACHIEVEMENT TEXT (at a given vertical centre)
    # ------------------------------------------------------------------
    def _achievement_text_svg(self, badge: BadgeDetails,
                              ribbon_colour: str,
                              center_y=None,
                              font_size=None) -> str:
        if center_y is None:
            center_y = self.ACHIEVEMENT_Y
        if font_size is None:
            font_size = self.ACHIEVEMENT_FONT_SIZE
        achievement_name = escape(str(badge.achievement_name or ""))
        return (
            f'<text x="{self.CENTER_X}" y="{center_y}" '
            'text-anchor="middle" dominant-baseline="middle" '
            "font-family=\"'Segoe UI', Arial, sans-serif\" "
            f'font-size="{font_size}" '
            f'font-weight="{self.ACHIEVEMENT_FONT_WEIGHT}" '
            f'fill="{ribbon_colour}">{achievement_name}</text>'
        )

    # ------------------------------------------------------------------
    # PARTNER LOGO IMAGE (at a given vertical centre)
    # ------------------------------------------------------------------
    def _partner_logo_svg(self, partner_uri: str,
                          partner_width: int, partner_height: int,
                          center_y=None) -> str:
        if center_y is None:
            center_y = self.PARTNER_LOGO_CENTER_Y
        partner_x = self.PARTNER_LOGO_CENTER_X - partner_width / 2
        partner_y = center_y - partner_height / 2
        return (
            f'<image href="{partner_uri}" xlink:href="{partner_uri}" '
            f'x="{partner_x}" y="{partner_y}" '
            f'width="{partner_width}" height="{partner_height}" '
            'preserveAspectRatio="xMidYMid meet"/>'
        )

    # ------------------------------------------------------------------
    # SECONDARY ELEMENT  (partner logo and/or achievement text)
    #   • both present  -> stacked (logo on top, achievement below)
    #   • only one       -> centered
    # ------------------------------------------------------------------
    def _secondary_element_svg(self, badge: BadgeDetails,
                               ribbon_colour: str) -> str:
        achievement_name = str(
            getattr(badge, "achievement_name", "") or ""
        ).strip()
        has_achievement = bool(achievement_name)

        partner_logo_bytes = getattr(badge, "partner_logo_bytes", None)

        # ---------- CASE 1: BOTH present -> dedicated stacked layout ----------
        if partner_logo_bytes and has_achievement:
            partner_uri, partner_width, partner_height = (
                self._prepare_partner_logo(
                    partner_logo_bytes,
                    max_height=self.STACK_PARTNER_LOGO_MAX_HEIGHT,
                    max_width=self.STACK_PARTNER_LOGO_MAX_WIDTH,
                )
            )
            if partner_uri:
                stacked_achievement_size = self._fit_font_size(
                    achievement_name,
                    base=self.STACK_ACHIEVEMENT_FONT_SIZE,
                    usable=self.STACK_ACHIEVEMENT_USABLE,
                    weight=self.ACHIEVEMENT_FONT_WEIGHT,
                    min_size=self.STACK_ACHIEVEMENT_MIN,
                )
                return (
                    self._partner_logo_svg(
                        partner_uri, partner_width, partner_height,
                        center_y=self.STACK_PARTNER_CENTER_Y,
                    )
                    + self._achievement_text_svg(
                        badge, ribbon_colour,
                        center_y=self.STACK_ACHIEVEMENT_CENTER_Y,
                        font_size=stacked_achievement_size,
                    )
                )
            return self._achievement_text_svg(badge, ribbon_colour)

        # ---------- CASE 2: ONLY partner logo -> centered ----------
        if partner_logo_bytes:
            partner_uri, partner_width, partner_height = (
                self._prepare_partner_logo(partner_logo_bytes)
            )
            if partner_uri:
                return self._partner_logo_svg(
                    partner_uri, partner_width, partner_height,
                    center_y=self.PARTNER_LOGO_CENTER_Y,
                )
            # Fall through to achievement/empty if logo invalid.

        # ---------- CASE 3: ONLY achievement (or neither) -> centered ----
        return self._achievement_text_svg(badge, ribbon_colour)

    # ------------------------------------------------------------------
    # BADGE RENDERING
    # ------------------------------------------------------------------
    def render_badge(self, badge: BadgeDetails) -> Image.Image:

        outer_colour, ribbon_colour = self._resolve_circle_colours(badge)

        # --- Auto-fit font sizes ---
        # The PDF reference uses an all-uppercase top arc. Measure the exact
        # uppercase value that will be rendered so auto-fit stays accurate.
        activity_track_text = str(
            badge.activity_track_name or ""
        ).strip().upper()
        arc_font_size = self._fit_font_size(
            activity_track_text,
            base=self.ARC_TEXT_BASE,
            usable=self.ARC_TEXT_USABLE,
            weight=700,
            min_size=self.ARC_TEXT_MIN,
        )
        ribbon_font_size = self._fit_font_size(
            badge.program_category,
            base=self.RIBBON_TEXT_BASE,
            usable=self.RIBBON_TEXT_USABLE,
            weight=self.RIBBON_TEXT_WEIGHT,
            min_size=self.RIBBON_TEXT_MIN,
        )

        # --- Microsoft logo ---
        microsoft_logo_uri = self._embed_logo(str(self.logo_path))
        if microsoft_logo_uri:
            microsoft_logo_element = (
                f'<image href="{microsoft_logo_uri}" '
                f'xlink:href="{microsoft_logo_uri}" '
                f'x="{self.LOGO_X}" y="{self.LOGO_Y_TOP}" '
                f'width="{self.LOGO_WIDTH}" height="{self.LOGO_HEIGHT}" '
                'preserveAspectRatio="xMidYMid meet"/>'
            )
        else:
            microsoft_logo_element = ""

        # --- Achievement text and/or partner logo ---
        secondary_element = self._secondary_element_svg(badge, outer_colour)

        # --- Arc geometry ---
        arc_left = self.CENTER_X - self.ARC_TEXT_RADIUS
        arc_right = self.CENTER_X + self.ARC_TEXT_RADIUS

        bottom_arc_radius = self.DATE_ARC_RADIUS
        bottom_left = self.CENTER_X - bottom_arc_radius
        bottom_right = self.CENTER_X + bottom_arc_radius

        # --- Safe text values ---
        activity_track_name = escape(activity_track_text)
        program_category = escape(str(badge.program_category or ""))
        badge_date = escape(str(badge.date or ""))

        # --- SVG ---
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{self.WIDTH}" height="{self.HEIGHT}" viewBox="0 0 {self.WIDTH} {self.HEIGHT}">
    <defs>
        <path id="topArc" d="M {arc_left} {self.CENTER_Y} A {self.ARC_TEXT_RADIUS} {self.ARC_TEXT_RADIUS} 0 0 1 {arc_right} {self.CENTER_Y}"/>
        <path id="bottomArc" d="M {bottom_left} {self.CENTER_Y} A {bottom_arc_radius} {bottom_arc_radius} 0 0 0 {bottom_right} {self.CENTER_Y}"/>
        <clipPath id="ribbonClip">
            <circle cx="{self.CENTER_X}" cy="{self.CENTER_Y}" r="{self.WHITE_RING_RADIUS}"/>
        </clipPath>
        <filter id="ribbonShadow" x="-10%" y="-50%" width="120%" height="220%">
            <feGaussianBlur stdDeviation="0.65"/>
        </filter>
    </defs>

    <circle cx="{self.CENTER_X}" cy="{self.CENTER_Y}" r="{self.OUTER_RADIUS}" fill="{outer_colour}"/>

    <circle cx="{self.CENTER_X}" cy="{self.CENTER_Y}" r="{self.WHITE_RING_RADIUS}" fill="white" stroke="black" stroke-width="3.5"/>

    <circle cx="{self.CENTER_X}" cy="{self.CENTER_Y}" r="{self.INNER_RADIUS}" fill="white" stroke="black" stroke-width="3.5"/>

    <text font-family="'Segoe UI', Arial, sans-serif" font-size="{arc_font_size}" font-weight="700" letter-spacing="0.4" fill="black">
        <textPath href="#topArc" xlink:href="#topArc" startOffset="49.89%" text-anchor="middle">{activity_track_name}</textPath>
    </text>

    {microsoft_logo_element}

    {secondary_element}

    <rect x="0" y="{self.RIBBON_BOTTOM}" width="{self.WIDTH}" height="5"
          fill="#7A7A7A" fill-opacity="0.48" filter="url(#ribbonShadow)"
          clip-path="url(#ribbonClip)"/>
    <rect x="0" y="{self.RIBBON_TOP}" width="{self.WIDTH}" height="{self.RIBBON_BOTTOM - self.RIBBON_TOP}" fill="{ribbon_colour}" clip-path="url(#ribbonClip)"/>

    <text x="{self.CENTER_X}" y="{(self.RIBBON_TOP + self.RIBBON_BOTTOM) // 2}" text-anchor="middle" dominant-baseline="middle" font-family="'Segoe UI', Arial, sans-serif" font-size="{ribbon_font_size}" font-weight="{self.RIBBON_TEXT_WEIGHT}" fill="white">{program_category}</text>

    <text font-size="22" font-weight="700" font-family="'Segoe UI', Arial, sans-serif" fill="black">
        <textPath href="#bottomArc" xlink:href="#bottomArc" startOffset="50%" text-anchor="middle" dy="{self.DATE_DY}">{badge_date}</textPath>
    </text>
</svg>
"""

        png_bytes = cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            output_width=self.TARGET_SIZE,
            output_height=self.TARGET_SIZE,
        )

        image = Image.open(BytesIO(png_bytes)).convert("RGBA")
        return image
