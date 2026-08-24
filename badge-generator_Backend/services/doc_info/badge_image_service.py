import fitz
import io

from PIL import Image

from utils.pdf_parser import PDFParser
from config import Config


class BadgeImageService:

    def __init__(self):

        self.parser = PDFParser()

    def extract_badge_image(
        self,
        pdf_path
    ):

        total_pages = (
            self.parser.get_total_pages(
                pdf_path
            )
        )

        target_page = None

        # ----------------------------------
        # Find the page containing the
        # LAST occurrence of "Choose".
        # ----------------------------------

        for page_number in range(total_pages):

            text = (
                self.parser.extract_text_from_page(
                    pdf_path,
                    page_number
                )
            )

            if (
                "Choose the badge" in text
                or
                "Choose the shape" in text
            ):
                target_page = page_number

        # No Choose found.
        if target_page is None:
            return None

        # ----------------------------------
        # Try extracting image from
        # LAST Choose page.
        # ----------------------------------

        image = (
            self.get_badge_image_from_page(
                pdf_path,
                target_page
            )
        )

        # No image found.
        if image is None:
            return None

        # ----------------------------------
        # Save badge image.
        # ----------------------------------

        image.save(
            Config.BADGE_IMAGE_OUTPUT_PATH,
            "PNG"
        )

        return Config.BADGE_IMAGE_OUTPUT_PATH
    
    def get_badge_image_from_page(
        self,
        pdf_path,
        page_number
    ):

        """
        Requirement:

        LAST Badge Template Creation Form
                    ↓
                LAST Choose
                    ↓
            Badge Image (optional)
                    ↓
        Program Category
                    ↓
            ISSUED BY
                    ↓
                STOP

        Extract image only if it lies between
        LAST Choose and ISSUED BY.
        """

        doc = fitz.open(
            pdf_path
        )

        page = doc[
            page_number
        ]

        blocks = page.get_text(
            "dict"
        )["blocks"]

        choose_y = None
        issued_by_y = None

        # ----------------------------------
        # Find Choose and ISSUED BY
        # ----------------------------------

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

                    block_text += span[
                        "text"
                    ]

            # ----------------------------------
            # LAST Choose section.
            # ----------------------------------

            if (
                "Choose the badge" in block_text
                or
                "Choose the shape" in block_text
            ):

                # bottom y-coordinate
                choose_y = block[
                    "bbox"
                ][3]

            # ----------------------------------
            # ISSUED BY section.
            # ----------------------------------

            if "ISSUED BY" in block_text:

                # top y-coordinate
                issued_by_y = block[
                    "bbox"
                ][1]

        # ----------------------------------
        # Mandatory checks.
        # ----------------------------------

        if choose_y is None:

            doc.close()
            return None

        if issued_by_y is None:

            doc.close()
            return None

        # ----------------------------------
        # Search image blocks.
        # ----------------------------------

        for block in blocks:

            if block["type"] != 1:
                continue

            image_top_y = block[
                "bbox"
            ][1]

            # ----------------------------------
            # Image must lie between:
            #
            # Choose
            #    ↓
            # Badge Image
            #    ↓
            # ISSUED BY
            # ----------------------------------

            if (
                choose_y
                <
                image_top_y
                <
                issued_by_y
            ):

                image_bytes = block[
                    "image"
                ]

                image = Image.open(
                    io.BytesIO(
                        image_bytes
                    )
                )

                doc.close()

                return image

        # ----------------------------------
        # No image found.
        # ----------------------------------

        doc.close()

        return None