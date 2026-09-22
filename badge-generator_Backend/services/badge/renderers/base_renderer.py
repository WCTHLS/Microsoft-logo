import os
from abc import ABC, abstractmethod

from PIL import Image, ImageDraw, ImageFont


class BaseRenderer(ABC):

    @staticmethod
    def get_renderer(badge_shape: str):
        if not badge_shape:
            raise ValueError("Badge shape is required.")

        normalized_shape = badge_shape.lower()

        if normalized_shape == "circle":
            from services.badge.renderers.circle_renderer import CircleRenderer
            return CircleRenderer()

        if normalized_shape == "diamond":
            from services.badge.renderers.diamond_renderer import DiamondRenderer
            return DiamondRenderer()

        raise ValueError(
            f"Unsupported badge shape: {normalized_shape}"
        )

    # ------------------------------------------------------------------
    # FONTS
    # ------------------------------------------------------------------
    # Three weights are used to match the real badge:
    #   - regular   : thinner text (program category + activity)
    #   - semibold  : default / fallback
    #   - bold      : big title + date
    #
    # IMPORTANT: font files are looked up by trying a LIST of candidate
    # names/paths for each weight (bare filename first, then the standard
    # Windows Fonts folder). This is why the weights actually change now:
    # relying on the bare name alone can silently fall back to Semibold if
    # PIL doesn't resolve it, making every weight look identical.
    # ------------------------------------------------------------------
    _WIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

    FONT_CANDIDATES = {
        "regular": [
            "segoeui.ttf",
            os.path.join(_WIN, "segoeui.ttf"),
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
        ],
        "semibold": [
            "seguisb.ttf",
            os.path.join(_WIN, "seguisb.ttf"),
            "segoeuib.ttf",
            os.path.join(_WIN, "segoeuib.ttf"),
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "segoeui.ttf",
            "DejaVuSans.ttf",
        ],
        "bold": [
            "segoeuib.ttf",
            os.path.join(_WIN, "segoeuib.ttf"),
            "seguisb.ttf",
            os.path.join(_WIN, "seguisb.ttf"),
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
        ],
    }

    # Base (native-resolution) font sizes. The diamond renderer auto-fits
    # around these, so they act as sensible starting/max points.
    MICROSOFT_FONT_SIZE = 34
    PROGRAM_FONT_SIZE = 50
    ACTIVITY_FONT_SIZE = 64
    MAIN_TITLE_FONT_SIZE = 92
    DATE_FONT_SIZE = 46

    def __init__(self):
        self.width = 600
        self.height = 600

        self.microsoft_font = self.get_font(self.MICROSOFT_FONT_SIZE)
        self.program_font = self.get_font(self.PROGRAM_FONT_SIZE, weight="regular")
        self.activity_font = self.get_font(self.ACTIVITY_FONT_SIZE, weight="regular")
        self.main_title_font = self.get_font(self.MAIN_TITLE_FONT_SIZE, weight="bold")
        self.date_font = self.get_font(self.DATE_FONT_SIZE, weight="bold")

    # ------------------------------------------------------------------
    # Font loader: tries each candidate for the requested weight until one
    # loads. weight in {"regular", "semibold", "bold"}.
    # Also accepts the legacy bold=True/False argument.
    # ------------------------------------------------------------------
    def get_font(self, size, weight="semibold", bold=None):
        if bold is not None:
            weight = "bold" if bold else "semibold"

        candidates = self.FONT_CANDIDATES.get(weight, self.FONT_CANDIDATES["semibold"])
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def create_canvas(self):
        return Image.new(
            "RGBA",
            (self.width, self.height),
            "white",
        )

    def draw_centered_text(
        self,
        image,
        text,
        y,
        font,
        fill="black",
        stroke_width=0,
    ):
        if not text:
            return
        draw = ImageDraw.Draw(image)
        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=stroke_width,
        )
        image_width = image.width
        text_width = bbox[2] - bbox[0]
        x = (image_width - text_width) // 2
        draw.text(
            (x, y),
            text,
            fill=fill,
            font=font,
            stroke_width=stroke_width,
            stroke_fill=fill,
        )

    def draw_centered_spaced_text(
        self,
        image,
        text,
        y,
        font,
        fill="white",
        spacing=3,
    ):
        draw = ImageDraw.Draw(image)
        widths = []
        total_width = 0
        for ch in text:
            bbox = draw.textbbox((0, 0), ch, font=font)
            w = bbox[2] - bbox[0]
            widths.append(w)
            total_width += w
        total_width += spacing * (len(text) - 1)
        x = (image.width - total_width) / 2
        for ch, w in zip(text, widths):
            draw.text((x, y), ch, font=font, fill=fill)
            x += w + spacing

    def save(
        self,
        image,
        output_path,
    ):
        image.save(output_path)

    @abstractmethod
    def render_badge(
        self,
        badge,
    ):
        """
        Every renderer must implement this.
        """
        pass
