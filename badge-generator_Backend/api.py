"""
================================================================================
 api.py - FastAPI backend for the Badge Generator React UI
================================================================================
Run with:
    uvicorn api:app --reload --port 8000
================================================================================
"""

import base64
import io
import os
import tempfile
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from models.badge_details import BadgeDetails
from services.badge.badge_generation_service import BadgeGenerationService
from services.doc_info.badge_image_service import BadgeImageService
from services.doc_info.badge_text_service import BadgeTextService
from services.doc_info.highlighted_text_service import HighlightedTextService
from services.validation_service import ValidationService


CIRCLE_COLOR_MAP = {
    "teal": {"outer": "#1399A2", "inner": "#0E7379"},
    "blue": {"outer": "#3487C7", "inner": "#2A6C9F"},
    "purple": {"outer": "#6B3F9E", "inner": "#532982"},
}

DIAMOND_COLOR_MAP = {
    "teal": {
        "outer": "#18BFCA - #A6E9ED",
        "inner": "#001D1F - #00666D",
    },
    "blue": {
        "outer": "#3487C7 - #BFDDF5",
        "inner": "#091823 - #20547C",
    },
    "purple": {
        "outer": "#6B3F9E - #C6B1DE",
        "inner": "#0F0717 - #532982",
    },
}

SHAPE_MAP = {
    "circle": "circle",
    "diamond": "diamond",
}

OUTPUT_SIZE = 2048


def resolve_color(
    name: Optional[str],
    shape: Optional[str],
    role: str,
) -> Optional[str]:
    if not name:
        return None

    color_name = name.strip().lower()
    normalized_shape = str(shape or "").strip().lower()
    color_map = (
        DIAMOND_COLOR_MAP
        if normalized_shape == "diamond"
        else CIRCLE_COLOR_MAP
    )
    color_values = color_map.get(color_name)
    if not color_values:
        return None
    return color_values.get(role)


def resolve_shape(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return SHAPE_MAP.get(name.strip().lower())


def fit_to_square(image, size=OUTPUT_SIZE):
    if isinstance(image, (str, Path)):
        image_path = Path(image)
        if not image_path.exists():
            raise FileNotFoundError(
                f"Generated badge was not found: {image_path}"
            )
        with Image.open(image_path) as source:
            image = source.convert("RGBA")
    elif isinstance(image, Image.Image):
        image = image.convert("RGBA")
    else:
        raise TypeError(
            "Generated badge must be a PIL image or a valid image file path."
        )

    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        image = image.crop(bbox)

    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("The generated badge image is empty.")

    scale = min(size / width, size / height)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))

    image = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset_x = (size - new_width) // 2
    offset_y = (size - new_height) // 2
    canvas.paste(image, (offset_x, offset_y), image)

    return canvas


def json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, memoryview):
        return f"<memoryview: {len(value)} bytes>"
    if isinstance(value, (bytes, bytearray)):
        return f"<bytes: {len(value)} bytes>"
    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return str(value)


def build_debug_values(
    values,
    ocr_values,
    shape,
    outer_colour,
    inner_colour,
    badge_image,
    partner_logo=None,
    partner_logo_bytes=None,
):
    values = values or {}
    ocr_values = ocr_values or {}

    return {
        "text_values": json_safe(values),
        "ocr_values": json_safe(ocr_values),
        "resolved": {
            "program_category": json_safe(values.get("program_category")),
            "achievement_name": json_safe(values.get("achievement_name")),
            "activity_track_name": json_safe(
                values.get("activity_track_name")
            ),
            "date": json_safe(values.get("date")),
            "logo_name": json_safe(values.get("logo_name")),
            "partner_logo": json_safe(values.get("partner_logo")),
            "shape": json_safe(shape),
            "outer_colour": json_safe(outer_colour),
            "inner_colour": json_safe(inner_colour),
            "badge_image": json_safe(badge_image),
            "partner_logo_uploaded_from_ui": (
                partner_logo.filename
                if partner_logo is not None
                else None
            ),
            "partner_logo_uploaded_bytes": (
                len(partner_logo_bytes)
                if partner_logo_bytes is not None
                else 0
            ),
        },
    }


def print_debug_values(title, debug_values):
    print(f"\nDEBUG >>> {title}", flush=True)
    for section_name, section_value in debug_values.items():
        print(
            f"DEBUG >>> {section_name}: {section_value!r}",
            flush=True,
        )
    print(f"DEBUG >>> END {title}\n", flush=True)


app = FastAPI(title="Badge Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/generate")
async def generate(
    file: UploadFile = File(...),
    outer_color: Optional[str] = Form(None),
    inner_color: Optional[str] = Form(None),
    badge_shape: Optional[str] = Form(None),
    partner_logo: Optional[UploadFile] = File(None),
):
    pdf_path = None
    debug_values = None

    try:
        pdf_bytes = await file.read()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf",
        ) as temp_file:
            temp_file.write(pdf_bytes)
            pdf_path = temp_file.name

        text_service = BadgeTextService()
        image_service = BadgeImageService()
        highlighted_service = HighlightedTextService()
        validation_service = ValidationService()
        generator = BadgeGenerationService()

        values = text_service.extract_values(pdf_path) or {}
        badge_image = image_service.extract_badge_image(pdf_path)
        ocr_values = highlighted_service.extract_values(pdf_path) or {}

        shape = ocr_values.get("shape")
        if badge_shape:
            resolved_shape = resolve_shape(badge_shape)
            if resolved_shape is None:
                return _bad_shape(badge_shape)
            shape = resolved_shape
        outer_colour = ocr_values.get("outer_colour")
        inner_colour = ocr_values.get("inner_colour")

        if outer_color:
            resolved_outer = resolve_color(outer_color, shape, "outer")
            if resolved_outer is None:
                return _bad_color(outer_color)
            outer_colour = resolved_outer

        if inner_color:
            resolved_inner = resolve_color(inner_color, shape, "inner")
            if resolved_inner is None:
                return _bad_color(inner_color)
            inner_colour = resolved_inner

        partner_logo_bytes = None

        if partner_logo is not None:
            partner_logo_bytes = await partner_logo.read()

            # IMPORTANT: Validation checks values["partner_logo"].
            # A logo selected in the React UI must therefore populate this
            # value before validation runs.
            uploaded_partner_name = Path(
                partner_logo.filename or "partner_logo"
            ).stem.strip()

            if uploaded_partner_name:
                values["partner_logo"] = uploaded_partner_name

            print(
                "DEBUG >>> Partner logo received from UI: "
                f"{partner_logo.filename!r}, "
                f"{len(partner_logo_bytes)} bytes",
                flush=True,
            )
            print(
                "DEBUG >>> Partner logo used for validation: "
                f"{values.get('partner_logo')!r}",
                flush=True,
            )
        else:
            print(
                "DEBUG >>> No partner logo uploaded from UI",
                flush=True,
            )

        debug_values = build_debug_values(
            values=values,
            ocr_values=ocr_values,
            shape=shape,
            outer_colour=outer_colour,
            inner_colour=inner_colour,
            badge_image=badge_image,
            partner_logo=partner_logo,
            partner_logo_bytes=partner_logo_bytes,
        )

        print_debug_values("VALUES BEFORE VALIDATION", debug_values)

        try:
            validation_service.validate(
                values,
                shape,
                outer_colour,
                inner_colour,
                badge_image,
            )
        except ValueError as validation_error:
            debug_values = build_debug_values(
                values=values,
                ocr_values=ocr_values,
                shape=shape,
                outer_colour=outer_colour,
                inner_colour=inner_colour,
                badge_image=badge_image,
                partner_logo=partner_logo,
                partner_logo_bytes=partner_logo_bytes,
            )

            print_debug_values(
                "VALUES AFTER VALIDATION FAILURE",
                debug_values,
            )

            return {
                "valid": False,
                "needs_colors": (
                    outer_colour is None
                    or inner_colour is None
                ),
                "needs_shape": shape is None,
                "message": f"Validation failed: {validation_error}",
                "debug_values": debug_values,
            }

        debug_values = build_debug_values(
            values=values,
            ocr_values=ocr_values,
            shape=shape,
            outer_colour=outer_colour,
            inner_colour=inner_colour,
            badge_image=badge_image,
            partner_logo=partner_logo,
            partner_logo_bytes=partner_logo_bytes,
        )

        print_debug_values(
            "VALUES AFTER VALIDATION SUCCESS",
            debug_values,
        )

        badge_details = BadgeDetails()
        badge_details.program_category = values.get("program_category")
        badge_details.achievement_name = values.get("achievement_name")
        badge_details.activity_track_name = values.get(
            "activity_track_name"
        )
        badge_details.date = values.get("date")
        badge_details.logo_name = values.get("logo_name")
        badge_details.partner_logo = values.get("partner_logo")
        badge_details.partner_logo_bytes = partner_logo_bytes
        badge_details.badge_image = badge_image
        badge_details.badge_shape = shape
        badge_details.outer_colour = outer_colour
        badge_details.inner_colour = inner_colour

        generated_badge = generator.generate_badge(
            badge=badge_details,
        )
        generated_badge = fit_to_square(
            generated_badge,
            size=OUTPUT_SIZE,
        )

        os.makedirs("output", exist_ok=True)
        output_path = "output/badge_generated.png"
        generated_badge.save(output_path, "PNG")

        output_buffer = io.BytesIO()
        generated_badge.save(output_buffer, format="PNG")
        image_base64 = base64.b64encode(
            output_buffer.getvalue()
        ).decode("utf-8")

        return {
            "valid": True,
            "message": "Validation Successful",
            "debug_values": debug_values,
            "image_base64": image_base64,
        }

    except Exception as error:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "valid": False,
                "message": f"Server error: {error}",
                "debug_values": debug_values,
            },
        )

    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)


def _bad_shape(name: str):
    return JSONResponse(
        status_code=400,
        content={
            "valid": False,
            "needs_shape": True,
            "message": (
                f"Unknown badge shape '{name}'. "
                f"Allowed: {', '.join(SHAPE_MAP)}"
            ),
        },
    )


def _bad_color(name: str):
    return JSONResponse(
        status_code=400,
        content={
            "valid": False,
            "needs_colors": True,
            "message": (
                f"Unknown color '{name}'. "
                f"Allowed: {', '.join(CIRCLE_COLOR_MAP)}"
            ),
        },
    )


STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {
            "status": "ok",
            "message": "Badge Generator API is running.",
        }
