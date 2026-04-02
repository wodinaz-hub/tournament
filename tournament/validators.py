import re

from django.core.exceptions import ValidationError


SCHOOL_REQUIRED_MESSAGE = "Вкажіть, будь ласка, свій навчальний заклад."
SCHOOL_INVALID_MESSAGE = "Такого навчального закладу не знайдено, будь ласка, напишіть правильно."

EDUCATION_KEYWORDS = (
    "школ",
    "ліцей",
    "лицей",
    "гімназ",
    "гимназ",
    "коледж",
    "college",
    "school",
    "lyceum",
    "gymnasium",
    "універс",
    "универс",
    "university",
    "інститут",
    "институт",
    "institute",
    "академ",
    "academy",
    "ззсо",
    "нвк",
    "хл",
)

GENERIC_EDUCATION_NAMES = {
    "школа",
    "school",
    "ліцей",
    "лицей",
    "гімназія",
    "гимназия",
    "гімназія",
    "коледж",
    "college",
    "університет",
    "университет",
    "university",
    "інститут",
    "институт",
    "academy",
    "академія",
    "академия",
}


def validate_school_name(value):
    school = (value or "").strip()
    if not school:
        raise ValidationError(SCHOOL_REQUIRED_MESSAGE)

    normalized = re.sub(r"\s+", " ", school)
    lower_value = normalized.lower()
    has_letter = bool(re.search(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]", normalized))
    has_digit = bool(re.search(r"\d", normalized))
    tokens = [token for token in re.split(r"[\s,]+", normalized) if token]
    has_keyword = any(keyword in lower_value for keyword in EDUCATION_KEYWORDS)
    is_generic_name_only = lower_value in GENERIC_EDUCATION_NAMES
    looks_like_acronym_with_number = bool(
        re.search(r"\b[А-ЯІЇЄҐA-Z]{2,}\b", normalized) and has_digit
    )

    is_valid = (
        has_letter
        and (
            looks_like_acronym_with_number
            or (has_keyword and not is_generic_name_only)
        )
    )

    if not is_valid:
        raise ValidationError(SCHOOL_INVALID_MESSAGE)

    return normalized
