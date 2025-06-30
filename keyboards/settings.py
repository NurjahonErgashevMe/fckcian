from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

def create_main_keyboard():
    """Создает главную клавиатуру меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Парсить")],
            [KeyboardButton(text="⚙️ Настройки парсинга")]
        ],
        resize_keyboard=True
    )

def create_rooms_keyboard(selected_rooms):
    """Создает клавиатуру для выбора комнат"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Создаем кнопки для каждой комнаты
    buttons_row = []
    for room in range(1, 7):
        # Добавляем галочку, если комната выбрана
        emoji = "✅" if room in selected_rooms else ""
        buttons_row.append(
            InlineKeyboardButton(
                text=f"{room} {emoji}",
                callback_data=f"room_{room}"
            )
        )
        
        # Каждые 3 кнопки начинаем новую строку
        if len(buttons_row) == 3:
            keyboard.inline_keyboard.append(buttons_row)
            buttons_row = []
    
    # Добавляем оставшиеся кнопки
    if buttons_row:
        keyboard.inline_keyboard.append(buttons_row)
    
    # Кнопка сохранения
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="💾 Сохранить настройки", callback_data="save_rooms")
    ])
    
    return keyboard

def create_floor_range_keyboard(min_value=0):
    """Клавиатура с диапазонами этажей с фильтрацией"""
    ranges = [
        ("1-10", 1, 10),
        ("11-20", 11, 20),
        ("21-30", 21, 30),
        ("31-40", 31, 40),
        ("41-50", 41, 50),
        ("51-60", 51, 60),
        ("61-70", 61, 70),
        ("71-80", 71, 80),
        ("81-90", 81, 90),
        ("91-100", 91, 100),
        ("Все этажи", 0, 0)
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    
    for name, start, end in ranges:
        # Фильтруем диапазоны: показываем только те, где верхняя граница >= min_value
        if min_value > 0 and end < min_value and name != "Все этажи":
            continue
            
        if name == "Все этажи":
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=name, callback_data=f"floor_range_all")
            ])
        else:
            row.append(InlineKeyboardButton(text=name, callback_data=f"floor_range_{start}_{end}"))
            if len(row) == 3:
                keyboard.inline_keyboard.append(row)
                row = []
    
    if row:
        keyboard.inline_keyboard.append(row)
    
    return keyboard

def create_floor_selection_keyboard(start, end, selected_floors, min_value=0):
    """Клавиатура для выбора конкретных этажей с фильтрацией"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    
    # Если выбран диапазон "Все этажи"
    if start == 0 and end == 0:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="✅ Все этажи выбраны", callback_data="floor_none")
        ])
    else:
        for floor in range(start, end + 1):
            # Пропускаем этажи меньше минимального значения
            if min_value > 0 and floor < min_value:
                continue
                
            emoji = "✅" if floor in selected_floors else ""
            row.append(
                InlineKeyboardButton(
                    text=f"{floor}{emoji}",
                    callback_data=f"floor_{floor}"
                )
            )
            if len(row) == 5:
                keyboard.inline_keyboard.append(row)
                row = []
    
    if row:
        keyboard.inline_keyboard.append(row)
    
    # Кнопки управления
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="✅ Выбрать все в диапазоне",
            callback_data="floor_select_all"
        )
    ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="💾 Сохранить выбор",
            callback_data="floor_save"
        )
    ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Назад к диапазонам",
            callback_data="floor_back"
        )
    ])
    
    return keyboard

def create_price_keyboard():
    """Создает клавиатуру для настроек цен"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬇️ Минимальная цена", callback_data="min_price_set")
        ],
        [
            InlineKeyboardButton(text="⬆️ Максимальная цена", callback_data="max_price_set")
        ],
        [
            InlineKeyboardButton(text="❌ Очистить цены", callback_data="clear_prices")
        ],
        [
            InlineKeyboardButton(text="💾 Сохранить настройки", callback_data="save_prices")
        ]
    ])

def create_author_types_keyboard(selected_types=None):
    """Создает клавиатуру для выбора типов авторов с чекбоксами"""
    if selected_types is None:
        selected_types = []
    
    author_types = [
        ('developer', '🏗️ Застройщики'),
        ('real_estate_agent', '🏢 Агентства'),
        ('homeowner', '🏠 Владельцы'),
        ('realtor', '👔 Риелторы')
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    
    for i, (auth_type, auth_name) in enumerate(author_types, 1):
        # Добавляем галочку для выбранных типов
        emoji = "✅" if auth_type in selected_types else ""
        btn = InlineKeyboardButton(
            text=f"{emoji} {auth_name}",
            callback_data=f"toggle_author_{auth_type}"
        )
        row.append(btn)
        
        # Размещаем по 2 кнопки в ряд
        if i % 2 == 0:
            keyboard.inline_keyboard.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки
    if row:
        keyboard.inline_keyboard.append(row)
    
    # Кнопки управления
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="💾 Сохранить выбор", callback_data="save_authors")
    ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_settings")
    ])
    
    return keyboard