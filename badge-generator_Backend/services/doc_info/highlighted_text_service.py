import os

import fitz
import cv2
import numpy as np
import pytesseract
import re
from PIL import Image
from config import Config


class HighlightedTextService:

    def extract_values(
        self,
        pdf_path
    ):

        doc = fitz.open(pdf_path)

        start_page = None
        start_y = None

        end_page = None
        end_y = None

        # ---------------------------------------------------------
        # Scan entire PDF
        # ---------------------------------------------------------

        for page_number, page in enumerate(doc):

            blocks = page.get_text("dict")["blocks"]

            for block in blocks:

                if block["type"] != 0:
                    continue

                block_text = ""

                for line in block.get(
                    "lines",
                    []
                ):

                    for span in line.get(
                        "spans",
                        []
                    ):

                        block_text += span["text"] + " "

                block_text = block_text.strip()

                if (
                    start_page is None
                    and
                    "Badge Template Creation Form" in block_text
                ):

                    start_page = page_number
                    start_y = block["bbox"][1]


                if (
                    end_page is None
                    and
                    "ISSUED BY" in block_text
                ):

                    end_page = page_number
                    end_y = block["bbox"][1]

                

        if (
            start_page is None
            or
            end_page is None
        ):

            doc.close()

            print(
                "Template region not found."
            )

            return {
                "partner_logo": None,
                "shape": None,
                "colour": None
            }

        # ---------------------------------------------------------
        # Export cropped images to memory for OCR highlight detection
        # ---------------------------------------------------------

        template_image = None

        for page_number in range(
            start_page,
            end_page + 1
        ):

            page = doc[page_number]

            if start_page == end_page:

                clip = fitz.Rect(
                    0,
                    start_y,
                    page.rect.width,
                    end_y
                )

            elif page_number == start_page:

                clip = fitz.Rect(
                    0,
                    start_y,
                    page.rect.width,
                    page.rect.height
                )

            elif page_number == end_page:

                clip = fitz.Rect(
                    0,
                    0,
                    page.rect.width,
                    end_y
                )

            else:

                clip = page.rect

            pix = page.get_pixmap(
                matrix=fitz.Matrix(
                    3,
                    3
                ),
                clip=clip
            )

            image = Image.frombytes(
                "RGB",
                (
                    pix.width,
                    pix.height
                ),
                pix.samples
            )

            if template_image is None:
                template_image = cv2.cvtColor(
                    np.array(image),
                    cv2.COLOR_RGB2BGR
                )

        doc.close()


        # ----------------------------------------
        # OCR Highlight Detection
        # ----------------------------------------

        if template_image is None:
            return {
                "partner_logo": None,
                "shape": None,
                "outer_colour": None,
                "inner_colour": None
            }

        crops = self.detect_highlighted_regions(
            template_image
        )

        texts = self.extract_highlight_text(
            crops
        )

        return self.parse_highlighted_values(
            texts
        )

    def detect_highlighted_regions(
    self,
        image_source
    ):

        if isinstance(image_source, str):
            image = cv2.imread(image_source)
            if image is None:
                print(f"Unable to read image: {image_source}")
                return []

        elif isinstance(image_source, np.ndarray):
            image = image_source

        else:
            try:
                image = np.array(image_source)
                if image.dtype == np.uint8 and len(image.shape) == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            except Exception:
                print("Invalid image source for highlight detection.")
                return []

        if image is None:
            print("Unable to read image for highlight detection.")
        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV
        )

        lower_yellow = np.array(
            [20, 80, 80]
        )

        upper_yellow = np.array(
            [40, 255, 255]
        )

        mask = cv2.inRange(
            hsv,
            lower_yellow,
            upper_yellow
        )

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        crops = []

        for contour in contours:

            x, y, w, h = cv2.boundingRect(
                contour
            )

            if w < 30 or h < 10:
                continue

            padding = 5

            crop = image[
                max(0, y - padding):y + h + padding,
                max(0, x - padding):x + w + padding
            ]

            crops.append(crop)

        return crops

    def extract_highlight_text(
    self,
    crops
    ):

        extracted_text = []

        for crop in crops:

            # -----------------------------------
            # Upscale image for better OCR
            # -----------------------------------

            crop = cv2.resize(
                crop,
                None,
                fx=2,
                fy=2,
                interpolation=cv2.INTER_CUBIC
            )

            # -----------------------------------
            # Convert to grayscale
            # -----------------------------------

            gray = cv2.cvtColor(
                crop,
                cv2.COLOR_BGR2GRAY
            )

            # -----------------------------------
            # Denoise
            # -----------------------------------

            gray = cv2.GaussianBlur(
                gray,
                (3, 3),
                0
            )

            # -----------------------------------
            # Adaptive Threshold
            # -----------------------------------

            thresh = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                15
            )

            # -----------------------------------
            # OCR
            # -----------------------------------

            text = pytesseract.image_to_string(
                thresh,
                config="--oem 3 --psm 6"
            )

            text = text.strip()

            if text:

                extracted_text.append(text)
        return extracted_text

    def parse_highlighted_values(
    self,
    texts
    ):

        shape = None
        partner_logo = None

        outer_colour = None
        inner_colour = None

        for text in texts:

            # ----------------------------------
            # Shape
            # ----------------------------------

            shape_match = re.search(
                r"\b(Circle|Diamond|Hexagon|Star|Shield)\b",
                text,
                re.IGNORECASE
            )

            if shape_match:
                shape = shape_match.group(1).title()

            # ----------------------------------
            # Partner Logo
            # ----------------------------------

            logo_match = re.search(
                r"([A-Za-z0-9& ]+)\s+Logo",
                text,
                re.IGNORECASE
            )

            if logo_match:
                partner_logo = logo_match.group(1).strip()

            # ----------------------------------
            # Circle
            #
            # Example:
            # Circle teal- #18BFCA
            # ----------------------------------

            if shape == "Circle":

                hex_codes = re.findall(
                    r"#[0-9A-Fa-f]{6}",
                    text
                )

                colour_match = re.search(
                    r"Circle\s+([A-Za-z]+)",
                    text,
                    re.IGNORECASE
                )

                # Circle with two colors
                # Example:
                # Circle Purple (Pitch Perfect only)
                # Light Purple: #6B3F9E & Dark Purple: #532982
                if len(hex_codes) >= 2:

                    outer_colour = hex_codes[0]
                    inner_colour = hex_codes[1]

                # Circle with one color
                # Example:
                # Circle teal- #18BFCA
                elif len(hex_codes) == 1:

                    if colour_match:
                        outer_colour = colour_match.group(1).title()

                    inner_colour = hex_codes[0]

                # Circle with no hex color
                elif colour_match:

                    outer_colour = colour_match.group(1).title()

            # ----------------------------------
            # Diamond
            #
            # Example:
            #
            # Light Blue Grade:
            # #3487C7 - #BFDDF5
            #
            # Dark Blue Grade:
            # #091823 - #20547
            # ----------------------------------

            elif shape == "Diamond":

                light_match = re.search(
                    r"Light.*?:\s*(#[0-9A-Fa-f]{6}\s*-\s*#[0-9A-Fa-f]{5,8})",
                    text,
                    re.IGNORECASE | re.DOTALL
                )

                dark_match = re.search(
                    r"Dark.*?:\s*(#[0-9A-Fa-f]{6}\s*-\s*#[0-9A-Fa-f]{5,8})",
                    text,
                    re.IGNORECASE | re.DOTALL
                )

                if light_match:

                    outer_colour = re.sub(
                        r"\s+",
                        " ",
                        light_match.group(1)
                    ).strip()

                    outer_colour = re.sub(
                        r"\s*-\s*",
                        " - ",
                        outer_colour
                    )

                if dark_match:

                    inner_colour = re.sub(
                        r"\s+",
                        " ",
                        dark_match.group(1)
                    ).strip()

                    inner_colour = re.sub(
                        r"\s*-\s*",
                        " - ",
                        inner_colour
                    )

        return {

            "partner_logo": partner_logo,
            "shape": shape,
            "outer_colour": outer_colour,
            "inner_colour": inner_colour

        }