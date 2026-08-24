import fitz
import io

from PIL import Image


class PDFParser:

    def extract_complete_pdf_text(
            self,
            pdf_path
    ):

        doc = fitz.open(pdf_path)

        text = ""

        for page in doc:
            text += page.get_text()
            text += "\n"

        doc.close()

        return text

    def get_total_pages(
            self,
            pdf_path
    ):

        doc = fitz.open(pdf_path)

        total_pages = len(doc)

        doc.close()

        return total_pages

    def extract_text_from_page(
            self,
            pdf_path,
            page_number
    ):

        doc = fitz.open(pdf_path)

        page = doc[page_number]

        text = page.get_text()

        doc.close()

        return text

    def extract_page_blocks(
            self,
            pdf_path,
            page_number
    ):

        doc = fitz.open(pdf_path)

        page = doc[page_number]

        blocks = page.get_text(
            "dict"
        )["blocks"]

        doc.close()

        return blocks

    def extract_images_from_page(
            self,
            pdf_path,
            page_number
    ):

        doc = fitz.open(pdf_path)

        page = doc[page_number]

        image_list = page.get_images(
            full=True
        )

        images = []

        for image in image_list:

            xref = image[0]

            base_image = doc.extract_image(
                xref
            )

            image_bytes = base_image[
                "image"
            ]

            pil_image = Image.open(
                io.BytesIO(
                    image_bytes
                )
            )

            images.append(
                pil_image
            )

        doc.close()

        return images

    def save_image(
            self,
            image,
            output_path
    ):

        image.save(
            output_path,
            "PNG"
        )