import re

def format_phone(phone):
    """Форматирует номер телефона в единый формат."""
    if not phone:
        return ""
    # Удаляем все нецифровые символы, кроме плюса
    cleaned = re.sub(r'[^\d+]', '', phone)
    if cleaned.startswith('8'):
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7'):
        cleaned = '+7' + cleaned[1:]
    return cleaned

def format_price(price):
    """Форматирует цену для отображения"""
    return f"{price:,} ₽".replace(",", " ") if price else "не задано"

def sanitize_payload(payload):
    """Рекурсивно удаляет из словаря все ключи с пустыми значениями."""
    if not isinstance(payload, dict):
        return payload
    return {k: sanitize_payload(v) for k, v in payload.items() if v not in [None, ""]}