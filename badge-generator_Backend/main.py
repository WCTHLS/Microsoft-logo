import os
import tempfile
from pathlib import Path

import streamlit as st
from PIL import Image

from models.badge_details import BadgeDetails
from services.doc_info.badge_text_service import BadgeTextService
from services.doc_info.badge_image_service import BadgeImageService
from services.doc_info.highlighted_text_service import HighlightedTextService
from services.validation_service import ValidationService
from services.badge.badge_generation_service import (
    BadgeGenerationService,
)
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("badge")


# ==========================================================
# FIT TO SQUARE
# Exact square output with no badge distortion
# ==========================================================

OUTPUT_SIZE = 2048


def fit_to_square(image, size=OUTPUT_SIZE):
    """
    Return an exact size x size RGBA image.

    The image is cropped only to its visible alpha bounds,
    resized while preserving its aspect ratio, and centered
    on a transparent square canvas.
    """

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
            "Generated badge must be a PIL image "
            "or a valid image file path."
        )

    # Trim transparent padding.
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()

    if bbox:
        image = image.crop(bbox)

    width, height = image.size

    if width <= 0 or height <= 0:
        raise ValueError(
            "The generated badge image is empty."
        )

    # Scale to fit inside the square.
    scale = min(size / width, size / height)

    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))

    image = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    # Center on transparent square canvas.
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    offset_x = (size - new_width) // 2
    offset_y = (size - new_height) // 2

    canvas.paste(image, (offset_x, offset_y), image)

    return canvas


# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Badge Generator",
    page_icon="🏅",
    layout="wide",
)


# ==========================================================
# PAGE TITLE
# ==========================================================

st.title("🏅 Badge Generator")

st.write(
    "Upload a badge PDF to extract its information "
    "and generate the final badge."
)

st.divider()


# ==========================================================
# PDF UPLOAD
# ==========================================================

uploaded_file = st.file_uploader(
    "Upload Badge PDF",
    type=["pdf"],
)


# ==========================================================
# GENERATE BUTTON
# ==========================================================

generate_button = st.button(
    "Generate Badge",
    type="primary",
    use_container_width=True,
    disabled=uploaded_file is None,
)


# ==========================================================
# MAIN PROCESS
# ==========================================================

if generate_button:

    pdf_path = None

    if uploaded_file is None:
        st.warning("Please upload a PDF first.")
        st.stop()

    # Save uploaded PDF temporarily
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf",
    ) as temp_file:

        temp_file.write(uploaded_file.getbuffer())
        pdf_path = temp_file.name

    try:

        # ==================================================
        # SERVICES
        # ==================================================

        text_service = BadgeTextService()
        image_service = BadgeImageService()
        highlighted_service = HighlightedTextService()
        validation_service = ValidationService()
        generator = BadgeGenerationService()

        # ==================================================
        # EXTRACT TEXT VALUES
        # ==================================================

        with st.spinner("Extracting badge information..."):
            values = text_service.extract_values(pdf_path)

        # ==================================================
        # EXTRACT BADGE IMAGE
        # ==================================================

        with st.spinner("Extracting badge image..."):
            badge_image = image_service.extract_badge_image(pdf_path)

        # ==================================================
        # OCR EXTRACTION
        # ==================================================

        with st.spinner("Analyzing badge design..."):
            ocr_values = highlighted_service.extract_values(pdf_path)

        # ==================================================
        # SHAPE AND COLOURS
        # ==================================================

        shape = ocr_values.get("shape")
        outer_colour = ocr_values.get("outer_colour")
        inner_colour = ocr_values.get("inner_colour")

        # ==================================================
        # PARTNER LOGO
        # ==================================================

        partner_name = values.get("partner_logo")

        if not partner_name:
            partner_name = ocr_values.get("partner_logo")
            

        values["partner_logo"] = partner_name

        # ==================================================
        # VALIDATION
        # ==================================================

        with st.spinner("Validating badge..."):
            validation_service.validate(
                values,
                shape,
                outer_colour,
                inner_colour,
                badge_image,
            )

        # ==================================================
        # DISPLAY EXTRACTED INFORMATION
        # ==================================================

        st.success("Badge information extracted successfully.")
        st.divider()
        st.subheader("📋 Extracted Badge Information")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Program Category:**", values["program_category"])
            st.write("**Achievement Name:**", values["achievement_name"])
            st.write("**Activity Track Name:**", values["activity_track_name"])
            st.write("**Date:**", values["date"])
            st.write("**Logo Name:**", values["logo_name"])

        with col2:
            st.write("**Partner Logo:**", values["partner_logo"])
            st.write("**Badge Shape:**", shape)
            st.write("**Outer Colour:**", outer_colour)
            st.write("**Inner Colour:**", inner_colour)

        # ==================================================
        # BADGE DETAILS
        # ==================================================

        badge_details = BadgeDetails()

        badge_details.program_category = values["program_category"]
        badge_details.achievement_name = values["achievement_name"]
        badge_details.activity_track_name = values["activity_track_name"]
        badge_details.date = values["date"]
        badge_details.logo_name = values["logo_name"]
        badge_details.partner_logo = values["partner_logo"]
        badge_details.badge_image = badge_image
        badge_details.badge_shape = shape
        badge_details.outer_colour = outer_colour
        badge_details.inner_colour = inner_colour

        # ==================================================
        # BADGE DETAILS DEBUG
        # ==================================================

        st.divider()
        st.subheader("🐞 BADGE DETAILS DEBUG")

        st.write("program_category:", badge_details.program_category)
        st.write("achievement_name:", badge_details.achievement_name)
        st.write("activity_track_name:", badge_details.activity_track_name)
        st.write("date:", badge_details.date)
        st.write("logo_name:", badge_details.logo_name)
        st.write("partner_logo:", badge_details.partner_logo)
        st.write("badge_shape:", badge_details.badge_shape)
        st.write("outer_colour:", badge_details.outer_colour)
        st.write("inner_colour:", badge_details.inner_colour)

        # ==================================================
        # BADGE GENERATION
        # ==================================================

        with st.spinner("Generating badge..."):
            generated_badge = generator.generate_badge(
                badge=badge_details,
            )

        # ==================================================
        # FIT TO EXACT SQUARE
        # ==================================================

        with st.spinner("Finalizing badge..."):
            generated_badge = fit_to_square(
                generated_badge,
                size=OUTPUT_SIZE,
            )

        # ==================================================
        # SAVE GENERATED BADGE
        # ==================================================

        os.makedirs("output", exist_ok=True)
        output_path = "output/badge_generated.png"
        generated_badge.save(output_path, "PNG")

        # ==================================================
        # SUCCESS MESSAGE
        # ==================================================

        st.success("✅ Badge generated successfully!")

        # ==================================================
        # DISPLAY IMAGES
        # ==================================================

        st.divider()
        st.subheader("🖼 Badge Images")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Extracted Badge**")

            if badge_image and os.path.exists(badge_image):
                st.image(badge_image, use_container_width=True)
            else:
                st.warning("Extracted badge image was not found.")

        with col2:
            st.markdown("**Generated Badge**")
            st.image(generated_badge, use_container_width=True)

            with open(output_path, "rb") as file:
                st.download_button(
                    label="⬇ Download Generated Badge",
                    data=file.read(),
                    file_name="badge_generated.png",
                    mime="image/png",
                    use_container_width=True,
                )

    except ValueError as e:
        st.error(f"Validation failed: {e}")

    except Exception as e:
        st.error("An error occurred while processing the badge.")
        st.exception(e)

    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
