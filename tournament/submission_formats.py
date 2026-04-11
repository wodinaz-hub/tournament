from django import forms
from django.core.exceptions import ValidationError


BUILTIN_SUBMISSION_FIELDS = {
    "github_link": {
        "field_class": forms.URLField,
        "label": "Посилання на GitHub",
        "type": "url",
    },
    "video_link": {
        "field_class": forms.URLField,
        "label": "Посилання на відео",
        "type": "url",
    },
    "live_demo": {
        "field_class": forms.URLField,
        "label": "Посилання на live demo",
        "type": "url",
    },
    "description": {
        "field_class": forms.CharField,
        "label": "Короткий опис рішення",
        "type": "textarea",
    },
    "is_final": {
        "field_class": forms.BooleanField,
        "label": "Позначити як фінальну версію",
        "type": "checkbox",
    },
}

CUSTOM_FIELD_TYPE_CHOICES = {
    "text": forms.CharField,
    "textarea": forms.CharField,
    "email": forms.EmailField,
    "number": forms.IntegerField,
    "url": forms.URLField,
}

TASK_SUBMISSION_PRESETS = {
    "informatics": {
        "label": "Інформатика",
        "fields": [
            {"key": "github_link", "label": "Посилання на GitHub", "type": "url", "required": True, "builtin": True},
            {"key": "video_link", "label": "Посилання на відео", "type": "url", "required": True, "builtin": True},
            {"key": "live_demo", "label": "Посилання на live demo", "type": "url", "required": False, "builtin": True},
            {"key": "description", "label": "Короткий опис рішення", "type": "textarea", "required": False, "builtin": True},
            {"key": "is_final", "label": "Позначити як фінальну версію", "type": "checkbox", "required": False, "builtin": True},
        ],
    },
    "ukrainian_language": {
        "label": "Українська мова",
        "fields": [
            {"key": "essay_text", "label": "Текст відповіді", "type": "textarea", "required": True, "builtin": False},
            {"key": "sources_link", "label": "Посилання на додаткові матеріали", "type": "url", "required": False, "builtin": False},
            {"key": "description", "label": "Коментар до відповіді", "type": "textarea", "required": False, "builtin": True},
        ],
    },
    "mathematics": {
        "label": "Математика",
        "fields": [
            {"key": "answer_text", "label": "Хід розв'язання", "type": "textarea", "required": True, "builtin": False},
            {"key": "answer_link", "label": "Посилання на фото або файл розв'язання", "type": "url", "required": False, "builtin": False},
        ],
    },
    "generic": {
        "label": "Власний шаблон",
        "fields": [
            {"key": "answer_text", "label": "Відповідь", "type": "textarea", "required": True, "builtin": False},
        ],
    },
}


def submission_preset_choices():
    return [(key, value["label"]) for key, value in TASK_SUBMISSION_PRESETS.items()]


def normalize_submission_field_key(value, fallback_label=""):
    source = (value or fallback_label or "").strip().lower()
    normalized_chars = []
    for char in source:
        if char.isalnum():
            normalized_chars.append(char)
        elif char in {" ", "-", "."}:
            normalized_chars.append("_")
        elif char == "_":
            normalized_chars.append(char)

    normalized = "".join(normalized_chars).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized


def build_submission_fields_definition_for_preset(preset_key):
    preset = TASK_SUBMISSION_PRESETS.get(preset_key) or TASK_SUBMISSION_PRESETS["generic"]
    return [dict(item) for item in preset["fields"]]


def serialize_submission_fields_definition(config):
    lines = []
    for item in config or []:
        requirement = "required" if item.get("required") else "optional"
        lines.append(
            f"{item.get('key', '')}|{item.get('label', '')}|{item.get('type', 'text')}|{requirement}"
        )
    return "\n".join(lines)


def parse_submission_fields_definition(raw_value):
    config = []
    errors = []

    for index, raw_line in enumerate((raw_value or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            errors.append(f"Рядок {index}: потрібно щонайменше ключ поля і назва.")
            continue

        raw_key = parts[0]
        field_label = parts[1]
        field_type = (parts[2] if len(parts) > 2 and parts[2] else "text").lower()
        is_required = (parts[3] if len(parts) > 3 and parts[3] else "required").lower()

        builtin = raw_key in BUILTIN_SUBMISSION_FIELDS
        field_key = raw_key if builtin else normalize_submission_field_key(raw_key, field_label)

        if not field_key:
            errors.append(f"Рядок {index}: ключ поля може містити лише літери, цифри та _.")
            continue

        allowed_types = set(CUSTOM_FIELD_TYPE_CHOICES) | {"checkbox"}
        if field_type not in allowed_types:
            errors.append(
                f'Рядок {index}: невідомий тип "{field_type}". Доступно: text, textarea, email, number, url, checkbox.'
            )
            continue

        if builtin:
            builtin_type = BUILTIN_SUBMISSION_FIELDS[field_key]["type"]
            if field_type != builtin_type:
                errors.append(
                    f'Рядок {index}: вбудоване поле "{field_key}" повинно мати тип "{builtin_type}".'
                )
                continue

        if is_required not in {"required", "optional"}:
            errors.append(f"Рядок {index}: обов'язковість має бути required або optional.")
            continue

        if any(item["key"] == field_key for item in config):
            errors.append(f'Рядок {index}: ключ поля "{field_key}" вже використовується.')
            continue

        if not field_label:
            errors.append(f"Рядок {index}: вкажіть назву поля.")
            continue

        config.append(
            {
                "key": field_key,
                "label": field_label,
                "type": field_type,
                "required": is_required == "required",
                "builtin": builtin,
            }
        )

    if not config:
        errors.append("Потрібно додати хоча б одне поле формату відповіді.")

    if errors:
        raise ValidationError(errors)

    return config


def infer_submission_preset(config):
    if not config:
        return "informatics"

    normalized = [
        {
            "key": item.get("key"),
            "label": item.get("label"),
            "type": item.get("type"),
            "required": bool(item.get("required")),
            "builtin": bool(item.get("builtin")),
        }
        for item in config
    ]

    for preset_key, preset in TASK_SUBMISSION_PRESETS.items():
        if normalized == preset["fields"]:
            return preset_key
    return "generic"


def resolve_task_submission_fields_config(task):
    config = list(getattr(task, "submission_fields_config", []) or [])
    if config:
        return config
    return build_submission_fields_definition_for_preset("informatics")


def build_submission_response_items(submission):
    config = resolve_task_submission_fields_config(submission.task)
    form_answers = submission.form_answers or {}
    response_items = []

    for item in config:
        if item.get("builtin"):
            value = getattr(submission, item["key"], None)
        else:
            value = form_answers.get(item["key"])

        if item["type"] == "checkbox":
            value = "так" if value else "ні"
        elif value in (None, "", []):
            continue

        response_items.append(
            {
                "label": item["label"],
                "value": value,
                "is_link": item["type"] == "url" and bool(value),
            }
        )

    return response_items
