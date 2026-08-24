from typing import Optional


class BadgeDetails:
    """
    Stores all information required for badge generation.
    """

    def __init__(self):

        # ==========================================================
        # OCR Extracted Fields
        # ==========================================================

        self.program_category: Optional[str] = None
        self.achievement_name: Optional[str] = None
        self.activity_track_name: Optional[str] = None
        self.date: Optional[str] = None

        self.logo_name: Optional[str] = None
        self.partner_logo: Optional[str] = None

        self.badge_shape: Optional[str] = None
        self.outer_colour: Optional[str] = None
        self.inner_colour: Optional[str] = None

        # ==========================================================
        # Microsoft Logo
        # ==========================================================

        self.logo_path: Optional[str] = None

        # Partner logo uploaded with the generation request.
        self.partner_logo_bytes = None

    def __repr__(self):

        return (
            f"BadgeDetails("
            f"program_category={self.program_category}, "
            f"achievement_name={self.achievement_name}, "
            f"activity_track_name={self.activity_track_name}, "
            f"date={self.date}, "
            f"logo_name={self.logo_name}, "
            f"partner_logo={self.partner_logo}, "
            f"badge_shape={self.badge_shape}, "
            f"outer_colour={self.outer_colour}, "
            f"inner_colour={self.inner_colour}, "
            f"logo_path={self.logo_path})"
        )