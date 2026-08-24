from datetime import datetime
import re


class ValidationService:

    FIELD_RULES = {
        "program_category": {
            "display": "Program Category",
            "required": True,
            "max_length": 35
        },
        "achievement_name": {
            "display": "Achievement Name",
            "required": False,
            "max_length": 16
        },
        "activity_track_name": {
            "display": "Activity Track Name",
            "required": True,
            "max_length": 35
        },
        "date": {
            "display": "Date",
            "required": True
        },
        "logo_name": {
            "display": "Logo Name",
            "required": True
        },
        "partner_logo": {
            "display": "Partner Logo",
            "required": False
        }
    }

    def validate(
        self,
        values,
        shape,
        outer_colour,
        inner_colour,
        badge_image
    ):

        self._validate_fields(values)

        self._validate_shape(shape, badge_image)

        self._validate_colour(
            outer_colour,
            inner_colour,
            badge_image
        )

        self._validate_date(
            values.get("date")
        )

        print("\nValidation Successful\n")

        return True

    def _validate_fields(
        self,
        values
    ):

        # ------------------------------------------------------
        # Achievement name and partner logo are mutually optional.
        # A badge must have AT LEAST ONE of them.
        # ------------------------------------------------------

        achievement_name = values.get("achievement_name")
        partner_logo = values.get("partner_logo")

        has_achievement = bool(
            achievement_name
            and str(achievement_name).strip() != ""
        )

        has_partner_logo = bool(
            partner_logo
            and str(partner_logo).strip() != ""
        )

        if not has_achievement and not has_partner_logo:

            raise ValueError(
                "Either Achievement Name or Partner Logo "
                "is required."
            )

        # ------------------------------------------------------
        # Standard field validation.
        # ------------------------------------------------------

        for field, rule in self.FIELD_RULES.items():

            value = values.get(field)

            if (
                rule["required"]
                and (
                    value is None
                    or str(value).strip() == ""
                )
            ):

                raise ValueError(
                    f"{rule['display']} is required."
                )

            if not value:
                continue

            value = str(value).strip()

            # Skip length validation when Achievement Name is a logo
            if field == "achievement_name":

                if (
                    "logo" in value.lower()
                    or "<" in value
                    or ">" in value
                ):
                    continue

            if (
                "max_length" in rule
                and len(value) > rule["max_length"]
            ):

                raise ValueError(
                    f"{rule['display']} exceeds "
                    f"{rule['max_length']} characters."
                )

    def _validate_shape(
        self,
        shape,
        badge_image
    ):
        if shape is None or str(shape).strip() == "":
            raise ValueError(
                "Unable to determine the badge shape. "
                "Please select Circle or Diamond in the UI."
            )
        normalized_shape = str(shape).strip().lower()
        if normalized_shape not in {"circle", "diamond"}:
            raise ValueError(
                "Badge shape must be Circle or Diamond."
            )

    def _validate_colour(
        self,
        outer_colour,
        inner_colour,
        badge_image
    ):

        # If badge image exists, generation service can infer colours.
        if badge_image:
            return

        if (
            outer_colour is None
            or str(outer_colour).strip() == ""
        ):
            raise ValueError(
                "Unable to determine the badge colours. "
                "Please highlight the badge or provide a badge image."
            )

        if (
            inner_colour is None
            or str(inner_colour).strip() == ""
        ):
            raise ValueError(
                "Unable to determine the badge colours. "
                "Please highlight the badge or provide a badge image."
            )

    def _validate_date(self, date):

        if date is None:
            raise ValueError("Date is required.")

        date = str(date)

        # Convert non-breaking spaces and line breaks to normal spaces.
        date = date.replace("\xa0", " ")
        date = date.replace("\n", " ")
        date = date.replace("\t", " ")

        # Remove HTML tags if extraction returned formatted content.
        date = re.sub(
            r"<[^>]+>",
            "",
            date
        )

        # Decode common HTML entities.
        date = (
            date.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )

        # Remove the date field label if it leaked into the value.
        date = re.sub(
            r"^\s*Date\s*[-:]?\s*Month\s*[/\- ]?\s*YYYY\s*[:\-]?\s*",
            "",
            date,
            flags=re.IGNORECASE
        )

        # Handle partial label text.
        date = re.sub(
            r"^\s*Month\s*[/\- ]?\s*YYYY\s*[:\-]?\s*",
            "",
            date,
            flags=re.IGNORECASE
        )

        date = re.sub(
            r"^\s*Date\s*[:\-]?\s*",
            "",
            date,
            flags=re.IGNORECASE
        )

        # Collapse repeated spaces.
        date = re.sub(
            r"\s+",
            " ",
            date
        )

        # Remove punctuation accidentally captured after the date.
        date = date.strip(" \t\r\n,.;:|")

        print(
            f"DEBUG >>> Normalized date used for validation: {date!r}",
            flush=True
        )

        if not date:
            raise ValueError("Date is required.")

        # YYYY, for example: 2026
        if re.fullmatch(r"\d{4}", date):
            return

        # Full month and year, for example: June 2026
        try:
            datetime.strptime(date, "%B %Y")
            return
        except ValueError:
            pass

        # Abbreviated month and year, for example: Jun 2026
        try:
            datetime.strptime(date, "%b %Y")
            return
        except ValueError:
            pass

        # FY 26 or FY26
        if re.fullmatch(
            r"FY\s?\d{2}",
            date,
            flags=re.IGNORECASE
        ):
            return

        raise ValueError(
            f"Invalid date value received: {date!r}. "
            "Date must be 'Month YYYY' "
            "(Example: June 2026), "
            "'YYYY' (Example: 2026), "
            "or 'FY 26'."
        )