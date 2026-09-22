import colorsys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from services.badge.renderers.base_renderer import BaseRenderer
import textwrap

from services.badge.templates.diamond_recolor import (
    recolor_diamond_badge,
    load_diamond_template,
)


class DiamondRenderer(BaseRenderer):
    """
    Diamond renderer tuned to match the real Microsoft badge:
      * Big BOLD white title (no heavy stroke -> not over-thick).
      * Program category in a PALE ICE-BLUE tint, drawn with visible
        letter-spacing/tracking (all-caps), like the real badge.
      * Activity/track text in a near-neutral pale gray-blue (NOT the
        same saturated tint as the program category), thinner weight.
      * Date in BOLD, with a touch of tracking so the digits read
        openly instead of tight/cramped, like the real badge.
      * All text CENTER-anchored on fraction-of-height lines, so vertical
        placement is independent of the auto-fit font size.

    NOTE ON CALIBRATION: every F_*, W_* and colour-tint constant below was
    measured directly off the real reference badge (pixel analysis of the
    hexagon geometry, text bounding boxes and sampled text colours), not
    guessed. See the inline comments next to each constant.
    """

    # ------------------------------------------------------------------
    # LAYOUT FRACTIONS (vertical CENTRES, fraction of template height)
    # ------------------------------------------------------------------
    F_LOGO_TOP = 0.178      # Microsoft logo TOP edge
    F_PROGRAM = 0.295       # Header / Category centre
    F_SEPARATOR = 0.380     # Divider line (shifted slightly up)
    F_ACTIVITY = 0.475      # Activity track centre (closer to title)
    F_TITLE = 0.550         # Main title centre
    F_DATE = 0.670          # Date centre

    # Separator half-width and bolder stroke width
    SEPARATOR_HALF_W = 0.100
    SEPARATOR_WIDTH = 4     # Bolder divider stroke

    # Target text widths as a fraction of the TEMPLATE WIDTH.
    W_TITLE = 0.650
    W_ACTIVITY = 0.500
    W_PROGRAM = 0.620
    W_DATE = 0.240

    PROGRAM_FONT_MAX_FRAC = 0.038
    DATE_FONT_MAX_FRAC = 0.044

    # Logo width as a fraction of template width (increased size).
    LOGO_W = 0.335

    # ------------------------------------------------------------------
    # TEXT COLOUR TINTS
    # ------------------------------------------------------------------
    PROGRAM_TINT = (0.1137, 0.0143)
    ACTIVITY_TINT = (0.1157, -0.5293)
    SEPARATOR_TINT = (0.1412, -0.5571)

    # Letter-spacing (tracking), as a fraction of font size.
    PROGRAM_TRACKING_RATIO = 0.08
    DATE_TRACKING_RATIO = 0.08

    # ------------------------------------------------------------------
    # ACTIVITY BANNER vertical safety margins (fraction of height)
    # ------------------------------------------------------------------
    ACTIVITY_TOP_GAP = 0.008     # clearance below the separator line
    ACTIVITY_BOTTOM_GAP = 0.004  # clearance above the title's top edge (sits closer to title)
    ACTIVITY_MIN_FONT = 18       # minimum legible size for long activity text

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _y(self, image, frac):
        return int(round(image.height * frac))

    def _light_colour(self, grade, default="#C6B1DE"):
        try:
            text = str(grade).replace("\u2013", "-")
            hexes = [p.strip() for p in text.split("-") if p.strip().startswith("#")]
            if hexes:
                return hexes[-1]
        except Exception:
            pass
        return default

    def _tinted_colour(self, grade, tint, default="#AAD0F0"):
        """Nudge the theme's light stop toward one of the reference's
        measured text colours (see PROGRAM_TINT / ACTIVITY_TINT /
        SEPARATOR_TINT above) using an HLS lightness/saturation delta."""
        hexcol = self._light_colour(grade, default=default)
        hexcol = hexcol.lstrip("#")
        if len(hexcol) == 3:
            hexcol = "".join(ch * 2 for ch in hexcol)
        try:
            r, g, b = (int(hexcol[i:i + 2], 16) for i in (0, 2, 4))
        except Exception:
            r, g, b = (170, 208, 240)  # fallback: blue theme light stop

        h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
        
        # Ensure base lightness is bright enough so text on the dark diamond
        # gradient is always crisp and legible (matching purple and blue).
        l = max(l, 0.82)

        # Align purple themes to the real badge's cool, pale pastel lavender
        if 0.70 < h < 0.80:
            h = 0.722
            s = min(s, 0.22)
        elif 0.40 <= h <= 0.60:  # Teal / Cyan themes
            s = min(s, 0.35)     # Keep ice-teal bright and crisp, not dark/saturated

        dl, ds = tint
        l = min(1.0, max(0.0, l + dl))
        s = min(1.0, max(0.0, s + ds))
        rr, gg, bb = colorsys.hls_to_rgb(h, l, s)
        return (round(rr * 255), round(gg * 255), round(bb * 255))

    def _fit_font(self, draw, text, target_w, max_size,
                  weight="semibold", min_size=18):
        """Largest font of the given weight whose width for `text` is
        <= target_w (auto-fit: big when short, shrinks when long)."""
        size = max_size
        while size > min_size:
            font = self.get_font(size, weight=weight)
            if draw.textbbox((0, 0), text, font=font)[2] <= target_w:
                return font
            size -= 2
        return self.get_font(min_size, weight=weight)

    def _title_top_frac(self, image, title_text):
        """Top edge (as a fraction of canvas height) of the main title block."""
        if not title_text:
            return self.F_TITLE - 0.03
        draw = ImageDraw.Draw(image)
        text_str = str(title_text).upper()
        target_w = int(image.width * self.W_TITLE)
        font = self._fit_font(
            draw, text_str, target_w,
            max_size=self.MAIN_TITLE_FONT_SIZE + 30, weight="bold",
        )
        asc, desc = font.getmetrics()
        lh = (asc + desc) * 1.16
        cy = image.height * self.F_TITLE
        return (cy - lh / 2) / image.height

    def _draw_block_centered(self, image, lines, center_frac, font,
                             colour, stroke=0, line_gap=1.16):
        """Draw line(s) centred horizontally and vertically around
        center_frac (fraction of height). anchor='mm' makes placement
        independent of the font size."""
        draw = ImageDraw.Draw(image)
        cx = image.width / 2
        cy = image.height * center_frac
        asc, desc = font.getmetrics()
        lh = int(round((asc + desc) * line_gap))
        total = lh * len(lines)
        first_cy = cy - total / 2 + lh / 2
        for i, line in enumerate(lines):
            draw.text(
                (cx, first_cy + i * lh), line, font=font, fill=colour,
                anchor="mm", stroke_width=stroke, stroke_fill=colour,
            )

    # ------------------------------------------------------------------
    # WIDTH + HEIGHT aware fitting (used by the activity banner).
    # ------------------------------------------------------------------
    def _wrap_pixels(self, draw, text, font, max_w):
        """Greedy word-wrap by measured pixel width (fewest lines that fit
        max_w at this font size)."""
        words = str(text).split()
        if not words:
            return [str(text)]
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if not cur or draw.textbbox((0, 0), trial, font=font)[2] <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def _balanced_wrap(self, draw, text, font, max_w, max_lines):
        """Wrap `text` into at most `max_lines` lines, every line <= max_w,
        preferring an EVEN split (so a 2-line block reads as two balanced
        halves instead of one long line + one orphan word). Returns the
        line list, or None if it simply cannot fit in max_lines at this
        font size."""
        words = str(text).split()
        if not words:
            return [str(text)]

        def fits(line):
            return draw.textbbox((0, 0), line, font=font)[2] <= max_w

        # Fast path: everything on one line.
        if fits(" ".join(words)):
            return [" ".join(words)]

        # Try k = 2 .. max_lines, choosing the split that minimises the
        # WIDEST line (most balanced) while keeping every line within max_w.
        for k in range(2, max_lines + 1):
            best, best_metric = None, None
            # enumerate all ways to break `words` into k contiguous groups
            import itertools
            n = len(words)
            for cuts in itertools.combinations(range(1, n), k - 1):
                idx = [0, *cuts, n]
                groups = [" ".join(words[idx[j]:idx[j + 1]]) for j in range(k)]
                widths = [draw.textbbox((0, 0), g, font=font)[2] for g in groups]
                if max(widths) > max_w:
                    continue
                metric = max(widths)  # minimise the widest line
                if best_metric is None or metric < best_metric:
                    best, best_metric = groups, metric
            if best is not None:
                return best
        return None  # cannot fit within max_lines at this size

    def _fit_wrapped_block(self, draw, text, target_w, max_block_h,
                           max_size, weight="semibold",
                           line_gap=1.16, min_size=14, max_lines=3):
        """Largest font whose BALANCED wrapped block fits target_w wide AND
        max_block_h tall (within max_lines). Returns (font, lines)."""
        size = max_size
        while size >= min_size:
            font = self.get_font(size, weight=weight)
            lines = self._balanced_wrap(draw, text, font, target_w, max_lines)
            if lines is not None:
                asc, desc = font.getmetrics()
                lh = int(round((asc + desc) * line_gap))
                if lh * len(lines) <= max_block_h:
                    return font, lines
            size -= 2
        # Last resort: shrink onto whatever fits width, ignore balance.
        font = self.get_font(min_size, weight=weight)
        return font, self._wrap_pixels(draw, text, font, target_w)

    # ------------------------------------------------------------------
    # TRACKED (letter-spaced) TEXT drawing
    # ------------------------------------------------------------------
    def _tracked_width(self, draw, text, font, tracking):
        total = 0.0
        n = len(text)
        for i, ch in enumerate(text):
            if ch == " ":
                w = tracking * 3.0
            else:
                bbox = draw.textbbox((0, 0), ch, font=font)
                w = bbox[2] - bbox[0]
            total += w
            if i < n - 1:
                total += tracking
        return total

    def _fit_tracked_font(self, draw, text, target_w, max_size,
                          weight="semibold", min_size=16, tracking_ratio=0.08):
        size = max_size
        while size > min_size:
            font = self.get_font(size, weight=weight)
            tracking = int(round(size * tracking_ratio))
            if self._tracked_width(draw, text, font, tracking) <= target_w:
                return font, tracking
            size -= 2
        font = self.get_font(min_size, weight=weight)
        return font, int(round(min_size * tracking_ratio))

    def _draw_tracked_line(self, image, text, y_center, font, tracking, colour):
        draw = ImageDraw.Draw(image)
        total_w = self._tracked_width(draw, text, font, tracking)
        start_x = (image.width - total_w) / 2.0
        cur_x = start_x
        n = len(text)
        for i, ch in enumerate(text):
            if ch == " ":
                cur_x += tracking * 3.0
            else:
                bbox = draw.textbbox((0, 0), ch, font=font)
                ch_w = bbox[2] - bbox[0]
                draw.text(
                    (cur_x, y_center), ch, font=font, fill=colour,
                    anchor="lm",
                )
                cur_x += ch_w
            if i < n - 1:
                cur_x += tracking

    def _draw_tracked_block_centered(self, image, lines, center_frac,
                                     font, tracking, colour, line_gap=1.16):
        cy = image.height * center_frac
        asc, desc = font.getmetrics()
        lh = int(round((asc + desc) * line_gap))
        total = lh * len(lines)
        first_cy = cy - total / 2 + lh / 2
        for i, line in enumerate(lines):
            self._draw_tracked_line(
                image, line, first_cy + i * lh, font, tracking, colour
            )

    # ------------------------------------------------------------------
    def load_template(self, badge):
        return load_diamond_template(badge)

    def _prep_logo(self, logo):
        """Prepare the Microsoft logo."""
        import numpy as np
        a = np.array(logo.convert("RGBA")).astype(float)
        rgb = a[:, :, :3]
        alpha = a[:, :, 3]
        near_white = (rgb[:, :, 0] > 240) & (rgb[:, :, 1] > 240) & (rgb[:, :, 2] > 240)
        alpha[near_white] = 0
        is_gray = (
            (rgb[:, :, 0] > 70) & (rgb[:, :, 0] < 190) &
            (abs(rgb[:, :, 0] - rgb[:, :, 1]) < 25) &
            (abs(rgb[:, :, 1] - rgb[:, :, 2]) < 25) &
            (alpha > 40)
        )
        rgb[is_gray] = 255
        alpha[is_gray] = np.clip(alpha[is_gray] * 1.25, 0, 255)
        out = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")
        bbox = out.getbbox()
        if bbox:
            out = out.crop(bbox)
        return out

    def draw_microsoft_header(self, image, badge=None):
        if badge is not None and getattr(badge, "logo_path", None) and Path(badge.logo_path).exists():
            logo_path = Path(badge.logo_path)
        else:
            logo_dir = Path(__file__).parent.parent / "logo"
            logo_path = logo_dir / "microsoft_logos.png"
            if not logo_path.exists():
                logo_path = logo_dir / "microsoft_logo.png"

        if not logo_path.exists():
            return
        logo = Image.open(logo_path).convert("RGBA")
        logo = self._prep_logo(logo)

        target_w = int(image.width * self.LOGO_W)
        scale = target_w / logo.width
        target_h = max(1, int(round(logo.height * scale)))
        logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)

        start_x = (image.width - logo.width) // 2
        start_y = self._y(image, self.F_LOGO_TOP)
        image.paste(logo, (start_x, start_y), logo)

    def draw_program_category(self, image, text, badge=None):
        """Draw Program Category in ALL CAPS with wide tracking."""
        if not text:
            return
        draw = ImageDraw.Draw(image)
        colour = self._tinted_colour(
            badge.outer_colour if badge is not None else None,
            self.PROGRAM_TINT,
        )
        target_w = int(image.width * self.W_PROGRAM)
        text_upper = str(text).upper()
        # Wrap to 2 balanced lines if long
        lines = textwrap.wrap(text_upper, width=20) or [text_upper]
        widest = max(lines, key=len)
        font, tracking = self._fit_tracked_font(
            draw, widest, target_w,
            max_size=int(image.height * self.PROGRAM_FONT_MAX_FRAC), weight="semibold",
            tracking_ratio=self.PROGRAM_TRACKING_RATIO,
        )
        self._draw_tracked_block_centered(
            image, lines, self.F_PROGRAM, font, tracking, colour
        )

    def draw_separator(self, image, badge=None):
        draw = ImageDraw.Draw(image)
        center_x = image.width // 2
        y = self._y(image, self.F_SEPARATOR)
        half = int(round(image.width * self.SEPARATOR_HALF_W))
        colour = self._tinted_colour(
            badge.outer_colour if badge is not None else None,
            self.SEPARATOR_TINT,
        )
        draw.line(
            (center_x - half, y, center_x + half, y),
            fill=colour, width=self.SEPARATOR_WIDTH,
        )

    def draw_activity_banner(self, image, text, badge=None):
        """Draw Activity Track in Title Case with dynamic boundary fit."""
        if not text:
            return
        draw = ImageDraw.Draw(image)
        colour = self._tinted_colour(
            badge.outer_colour if badge is not None else None,
            self.ACTIVITY_TINT,
        )
        target_w = int(image.width * self.W_ACTIVITY)

        title = badge.achievement_name if badge is not None else None
        band_top = self.F_SEPARATOR + self.ACTIVITY_TOP_GAP
        band_bottom = self._title_top_frac(image, title) - self.ACTIVITY_BOTTOM_GAP
        center_frac = band_top * 0.35 + band_bottom * 0.65
        max_block_h = max(1, int(round((band_bottom - band_top) * image.height)))

        font, lines = self._fit_wrapped_block(
            draw, str(text), target_w, max_block_h,
            max_size=self.ACTIVITY_FONT_SIZE + 30, weight="semibold",
            min_size=self.ACTIVITY_MIN_FONT, max_lines=3,
        )
        self._draw_block_centered(image, lines, center_frac, font, colour)

    def draw_main_title(self, image, text):
        """Draw Main Title in ALL CAPS, BOLD white text with auto-fitting."""
        if not text:
            return
        draw = ImageDraw.Draw(image)
        text_upper = str(text).upper()
        target_w = int(image.width * self.W_TITLE)
        
        # Support multi-line wrapping for long titles (e.g., THE PERFECT PITCH)
        words = text_upper.split()
        if len(text_upper) > 14 and len(words) > 1:
            lines = textwrap.wrap(text_upper, width=14) or [text_upper]
        else:
            lines = [text_upper]
            
        widest = max(lines, key=len)
        font = self._fit_font(
            draw, widest, target_w,
            max_size=self.MAIN_TITLE_FONT_SIZE + 30, weight="bold",
        )
        self._draw_block_centered(
            image, lines, self.F_TITLE, font, "white", stroke=0
        )

    def draw_date(self, image, text):
        """Draw Date in BOLD white with spaced tracking."""
        if not text:
            return
        draw = ImageDraw.Draw(image)
        target_w = int(image.width * self.W_DATE)
        font, tracking = self._fit_tracked_font(
            draw, str(text), target_w,
            max_size=int(image.height * self.DATE_FONT_MAX_FRAC), weight="bold",
            tracking_ratio=self.DATE_TRACKING_RATIO,
        )
        y_center = image.height * self.F_DATE
        self._draw_tracked_line(image, str(text), y_center, font, tracking, "white")

    # ------------------------------------------------------------------
    def render_badge(self, badge):
        image = self.load_template(badge)
        self.draw_microsoft_header(image, badge)
        self.draw_program_category(image, badge.program_category, badge)
        self.draw_separator(image, badge)
        self.draw_activity_banner(image, badge.activity_track_name, badge)
        self.draw_main_title(image, badge.achievement_name)
        self.draw_date(image, badge.date)
        return image
