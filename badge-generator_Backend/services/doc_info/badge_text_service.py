import html
import re

from utils.pdf_parser import PDFParser
from utils.text_cleaner import TextCleaner


class BadgeTextService:
    """Extract and clean values from the final badge request form."""

    def __init__(self):
        self.parser = PDFParser()

    def extract_values(self, pdf_path):
        full_text = self.parser.extract_complete_pdf_text(pdf_path)
        full_text = self._normalize_pdf_text(full_text)
        form_text = self.extract_required_section(full_text)

        # IMPORTANT: extract raw values first, then clean every field.
        raw_program_category = self.get_program_category(form_text)
        raw_achievement_name = self.get_achievement_name(form_text)
        raw_activity_name = self.get_activity_name(form_text)
        raw_date = self.get_date(form_text)
        raw_logo_name = self.get_logo_name(full_text)
        raw_partner_logo = self.get_partner_logo(form_text)
        raw_colour = self.get_colour(form_text)

        values = {
            "program_category": TextCleaner.clean(
                raw_program_category
            ),
            "achievement_name": TextCleaner.clean(
                raw_achievement_name
            ),
            "activity_track_name": TextCleaner.clean(
                raw_activity_name
            ),
            "date": TextCleaner.clean_date(raw_date),
            "logo_name": TextCleaner.clean(raw_logo_name),
            "partner_logo": TextCleaner.clean(raw_partner_logo),
            "colour": TextCleaner.clean(raw_colour),
        }

        print(
            "DEBUG >>> BadgeTextService raw values: "
            f"{self._debug_raw_values(raw_program_category, raw_achievement_name, raw_activity_name, raw_date, raw_logo_name, raw_partner_logo, raw_colour)!r}",
            flush=True,
        )
        print(
            f"DEBUG >>> BadgeTextService cleaned values: {values!r}",
            flush=True,
        )

        return values

    @staticmethod
    def _debug_raw_values(
        program_category,
        achievement_name,
        activity_track_name,
        date,
        logo_name,
        partner_logo,
        colour,
    ):
        return {
            "program_category": program_category,
            "achievement_name": achievement_name,
            "activity_track_name": activity_track_name,
            "date": date,
            "logo_name": logo_name,
            "partner_logo": partner_logo,
            "colour": colour,
        }

    @staticmethod
    def _normalize_pdf_text(text):
        if text is None:
            return ""

        text = html.unescape(str(text))
        text = text.replace("\xa0", " ")
        text = text.replace("\u200b", "")
        text = text.replace("\ufeff", "")
        text = text.replace("\r", "\n")
        text = text.replace("\t", " ")
        text = re.sub(r"[ ]+", " ", text)
        text = re.sub(r"\n[ ]+", "\n", text)
        text = re.sub(r"[ ]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def extract_required_section(self, text):
        if not text:
            return ""

        # Prefer the last Badge Template Creation Form when present.
        creation_form_matches = list(
            re.finditer(
                r"Badge\s+Template\s+Creation\s+Form",
                text,
                flags=re.IGNORECASE,
            )
        )

        if creation_form_matches:
            text = text[creation_form_matches[-1].end():]

        # From that area, use the final actual form starting with Choose.
        choose_matches = list(
            re.finditer(
                r"Choose\s+the\s+(?:shape\s+of\s+the\s+)?badge\s+to\s+be\s+created",
                text,
                flags=re.IGNORECASE,
            )
        )

        if choose_matches:
            text = text[choose_matches[-1].start():]

        # Stop before template metadata. Do not let "Badge Template" enter Date.
        stop = re.search(
            r"\b(?:Badge\s+Template|ISSUED\s+BY|Badge\s+Name)\b",
            text,
            flags=re.IGNORECASE,
        )

        if stop:
            text = text[:stop.start()]

        return text.strip()

    def get_program_category(self, text):
        return self.get_value(
            text,
            (
                r"Program\s+or\s+achievement\s+category"
                r"\s*-?"
                r"\s*(?:\(\s*Character\s+limit\s*35\s*\))?"
                r"\s*(.*?)"
                r"(?=\s*Achievement\s+Name\b)"
            ),
        )

    def get_achievement_name(self, text):
        value = self.get_value(
            text,
            (
                r"Achievement\s+Name"
                r"\s*-?"
                r"\s*(?:\(\s*Character\s+limit\s*\d+\s*\))?"
                r"\s*(.*?)"
                r"(?=\s*(?:Activity\s+Track\s+Name|Activity\s+Name)\b)"
            ),
        )

        if value is None:
            return None

        decoded = html.unescape(value)
        decoded = re.sub(
            r"<\s*.+?\s*logo\s*>",
            "",
            decoded,
            flags=re.IGNORECASE,
        )

        return decoded

    def get_activity_name(self, text):
        patterns = (
            (
                r"Activity\s+Track\s+Name"
                r"\s*-?"
                r"\s*(?:\(\s*Character\s+limit\s*\d+\s*\))?"
                r"\s*(.*?)"
                r"(?=\s*Partner\s+Logo\b)"
            ),
            (
                r"Activity\s+Track\s+Name"
                r"\s*-?"
                r"\s*(?:\(\s*Character\s+limit\s*\d+\s*\))?"
                r"\s*(.*?)"
                r"(?=\s*Date\b)"
            ),
            (
                r"Activity\s+Name"
                r"\s*-?"
                r"\s*(?:\(\s*Character\s+limit\s*\d+\s*\))?"
                r"\s*(.*?)"
                r"(?=\s*Date\b)"
            ),
        )

        for pattern in patterns:
            value = self.get_value(text, pattern)
            if value is not None:
                return value

        return None

    def get_date(self, text):
        # The required section already stops before Badge Template.
        # Extract everything after Date, then clean_date() obtains only YYYY.
        patterns = (
            r"Date\s*-?\s*Month\s+YYYY\s*(.*)$",
            r"Date\s+Month\s+YYYY\s*(.*)$",
            r"Date\s*(.*)$",
        )

        for pattern in patterns:
            value = self.get_value(text, pattern)
            if value is not None:
                return value

        return None

    @staticmethod
    def get_value(text, pattern):
        if not text:
            return None

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if not match:
            return None

        value = match.group(1).strip()
        return value if value else None

    def get_logo_name(self, text):
        match = re.search(
            r"ISSUED\s+BY\s+([^\n\r<]+)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        value = TextCleaner.clean(match.group(1))
        return value.split()[0] if value else None

    def get_partner_logo(self, text):
        value = self.get_value(
            text,
            r"Partner\s+Logo\s*(.*?)(?=\s*Date\b)",
        )

        partner = self._extract_partner_from_logo_text(value)
        if partner:
            return partner

        if value is not None:
            return value

        achievement_section = self.get_value(
            text,
            (
                r"Achievement\s+Name"
                r"\s*-?"
                r"\s*(?:\(\s*Character\s+limit\s*\d+\s*\))?"
                r"\s*(.*?)"
                r"(?=\s*(?:Activity\s+Track\s+Name|Activity\s+Name)\b)"
            ),
        )

        return self._extract_partner_from_logo_text(achievement_section)

    @staticmethod
    def _extract_partner_from_logo_text(text):
        if not text:
            return None

        matches = re.findall(
            r"<\s*(.+?)\s*logo\s*>",
            html.unescape(str(text)),
            flags=re.IGNORECASE,
        )

        for name in matches:
            cleaned = TextCleaner.clean(name)
            if cleaned and cleaned.lower() != "microsoft":
                return cleaned

        return None

    def get_colour(self, text):
        for pattern in (
            r"Colour\s*(.*?)\s*(?:Badge\s+Template|ISSUED\s+BY|$)",
            r"Color\s*(.*?)\s*(?:Badge\s+Template|ISSUED\s+BY|$)",
        ):
            value = self.get_value(text, pattern)
            if value is not None:
                return value

        return None
