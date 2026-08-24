import html
import re


class TextCleaner:
    """Clean individual values extracted from badge-form PDFs."""

    _LEADING_SEPARATORS = r"\s\-‐‑‒–—―:|•▪◦¢"

    @staticmethod
    def _normalize(text):
        if text is None:
            return None

        text = html.unescape(str(text))
        text = re.sub(r"<[^>]+>", "", text)

        for character in ("\xa0", "\u2007", "\u202f"):
            text = text.replace(character, " ")

        for character in ("\u200b", "\u200c", "\u200d", "\ufeff"):
            text = text.replace(character, "")

        text = text.replace("\r", " ")
        text = text.replace("\n", " ")
        text = text.replace("\t", " ")
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @staticmethod
    def _remove_leading_separators(text):
        if not text:
            return text

        return re.sub(
            rf"^[{TextCleaner._LEADING_SEPARATORS}]+",
            "",
            text,
        ).strip()

    @staticmethod
    def clean(text):
        """
        Clean a normal badge field.

        Examples:
            "- Skilled" -> "Skilled"
            "- Project Ready" -> "Project Ready"
            "-" -> None
        """

        text = TextCleaner._normalize(text)

        if not text:
            return None

        text = re.sub(
            r"\(\s*Character\s+limit\s*:?\s*\d*\s*\)",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\(\s*please\s+do\s+not\s+add\s+(?:the\s+)?month\s*\)",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = TextCleaner._remove_leading_separators(text)
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return None

        if re.fullmatch(
            rf"[{TextCleaner._LEADING_SEPARATORS}]+",
            text,
        ):
            return None

        return text

    @staticmethod
    def clean_date(text):
        """
        Return only a four-digit year.

        Examples:
            "- May 2026 Badge Template" -> "2026"
            "May 2026" -> "2026"
            "2025 (please do not add month)" -> "2025"
            "FY 26" -> "2026"
        """

        text = TextCleaner._normalize(text)

        if not text:
            return None

        text = re.sub(
            r"\(\s*please\s+do\s+not\s+add\s+(?:the\s+)?month\s*\)",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = TextCleaner._remove_leading_separators(text)

        fiscal_year = re.search(
            r"\bFY[\s\-‐‑‒–—―]?(\d{2})\b",
            text,
            flags=re.IGNORECASE,
        )

        if fiscal_year:
            return f"20{fiscal_year.group(1)}"

        year = re.search(
            r"(?<!\d)(?:19|20)\d{2}(?!\d)",
            text,
        )

        if year:
            return year.group(0)

        return None
