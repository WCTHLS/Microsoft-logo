import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Application configuration.
    """

    # ==========================================================
    # Logo Storage (local Microsoft logo asset, etc.)
    # ==========================================================

    LOGO_STORAGE_PATH = os.getenv(
        "LOGO_STORAGE_PATH",
        "services/badge/logo/microsoft_logo.png"
    )

    # ==========================================================
    # HTTP
    # ==========================================================

    HTTP_TIMEOUT = int(
        os.getenv("HTTP_TIMEOUT", "10")
    )

    # ==========================================================
    # Azure Blob Storage (Future)
    # ==========================================================

    AZURE_STORAGE_CONNECTION_STRING = os.getenv(
        "AZURE_STORAGE_CONNECTION_STRING"
    )

    AZURE_STORAGE_CONTAINER = os.getenv(
        "AZURE_STORAGE_CONTAINER",
        "badge-logos"
    )

    # ==========================================================
    # Badge Image Paths (static constants — same everywhere)
    # ==========================================================

    # Reference image used while building the badge
    BADGE_IMAGE_OUTPUT_PATH = os.getenv(
        "BADGE_IMAGE_OUTPUT_PATH",
        "input/doc_reference_images/badge.png"
    )

    # Final generated badge file name
    OUTPUT_FILE_NAME = os.getenv(
        "OUTPUT_FILE_NAME",
        "generated_badge.png"
    )

    # Output directory for all generated assets
    OUTPUT_DIR = os.getenv(
        "OUTPUT_DIR",
        "output"
    )

    # Template region image path (use .format(index) to fill the {})
    # e.g. Config.TEMPLATE_IMAGE.format(0) -> "output/template_region_0.png"
    TEMPLATE_IMAGE = f"{OUTPUT_DIR}/template_region_{{}}.png"
