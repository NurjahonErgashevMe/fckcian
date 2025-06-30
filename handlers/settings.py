import os
import json
import re
import asyncio
import cianparser
from datetime import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove
)
from utils import file_utils, log_utils
from keyboards.settings import (
    create_main_keyboard,
    create_rooms_keyboard,
    create_floor_range_keyboard,
    create_floor_selection_keyboard,
    create_price_keyboard,
    create_author_types_keyboard
)

router = Router()

class RegionState(StatesGroup):
    waiting_region_name = State()

class RoomState(StatesGroup):
    selecting_rooms = State()

class MinFloorState(StatesGroup):
    selecting_range = State()
    selecting_floors = State()

class MaxFloorState(StatesGroup):
    selecting_range = State()
    selecting_floors = State()

class PriceState(StatesGroup):
    min_price = State()
    max_price = State()

class AuthorTypesState(StatesGroup):
    selecting = State()

async def check_admin_access(user_id: int, message: types.Message = None, callback: types.CallbackQuery = None) -> bool:
    """Проверяет доступ пользователя к функциям бота"""
    if str(user_id) != os.getenv("TELEGRAM_ADMIN_ID"):
        if message:
            await message.answer("⛔ Доступ запрещен. Вы не администратор.")
        if callback:
            await callback.answer("⛔ Доступ запрещен. Вы не администратор.", show_alert=True)
        return False
    return True

@router.message(F.text == "🔙 Назад в меню")
async def back_to_menu(message: types.Message, state: FSMContext):
    """Обработчик кнопки возврата в меню"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=create_main_keyboard()
    )

@router.message(F.text == "⚙️ Настройки парсинга")
async def parsing_settings(message: types.Message):
    """Обработчик кнопки настроек парсинга"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    current_region = file_utils.get_region_name()
    region_id = file_utils.get_region_id()
    current_rooms = file_utils.get_rooms()
    current_min_floor = file_utils.get_min_floor()
    current_max_floor = file_utils.get_max_floor()
    current_min_price = file_utils.get_min_price()
    current_max_price = file_utils.get_max_price()
    auto_parse_enabled = file_utils.get_setting('auto_parse_enabled', '0') == '1'
    current_authors = file_utils.get_author_types()
    
    # Форматируем этажи
    min_floor_text = "не задано" if not current_min_floor else ", ".join(map(str, current_min_floor))
    max_floor_text = "не задано" if not current_max_floor else ", ".join(map(str, current_max_floor))
    
    # Форматируем цены
    min_price_text = "не задано" if not current_min_price else f"{current_min_price:,} ₽".replace(",", " ")
    max_price_text = "не задано" if not current_max_price else f"{current_max_price:,} ₽".replace(",", " ")
    
    # Форматируем типы авторов
    author_names = {
        'developer': '🏗️',
        'real_estate_agent': '🏢',
        'homeowner': '🏠',
        'realtor': '👔'
    }
    authors_text = ", ".join([f"{author_names.get(a, '❓')} {a}" for a in current_authors])
    
    # Обновленная клавиатура
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📍 Изменить регион"), 
                KeyboardButton(text="📋 Список регионов"), 
                KeyboardButton(text="🚪 Выбрать комнаты")
            ],
            [
                KeyboardButton(text="🏢 Настроить этажи"), 
                KeyboardButton(text="💰 Настроить цены"), 
                KeyboardButton(text="👥 Типы авторов")
            ],
            [
                KeyboardButton(text="🔄 Сбросить настройки"), 
                KeyboardButton(text="🔙 Назад в меню")
            ]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"⚙️ <b>Текущие настройки парсинга:</b>\n"
        f"• <b>Регион:</b> {current_region}\n"
        f"• <b>ID региона:</b> {region_id}\n"
        f"• <b>Комнаты:</b> {', '.join(map(str, current_rooms))}\n"
        f"• <b>Мин. этаж:</b> {min_floor_text}\n"
        f"• <b>Макс. этаж:</b> {max_floor_text}\n"
        f"• <b>Мин. цена:</b> {min_price_text}\n"
        f"• <b>Макс. цена:</b> {max_price_text}\n"
        f"• <b>Типы авторов:</b> {authors_text}\n"
        f"• <b>Автопарсинг:</b> {'✅ включен' if auto_parse_enabled else '❌ выключен'}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(F.text.endswith("Типы авторов"))
async def author_types_settings(message: types.Message, state: FSMContext):
    """Обработчик кнопки настройки типов авторов"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
    
    # Получаем текущие настройки
    current_types = file_utils.get_author_types()
    
    await state.set_state(AuthorTypesState.selecting)
    await message.answer(
        "👥 Выберите типы авторов для парсинга:",
        reply_markup=create_author_types_keyboard(current_types)
    )

@router.callback_query(AuthorTypesState.selecting, F.data.startswith("toggle_author_"))
async def toggle_author_type(callback: types.CallbackQuery, state: FSMContext):
    """Переключение типа автора"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    auth_type = callback.data.split("_")[-1]
    data = await state.get_data()
    selected_types = data.get("selected_types", file_utils.get_author_types())
    
    if auth_type in selected_types:
        selected_types.remove(auth_type)
    else:
        selected_types.append(auth_type)
    
    await state.update_data(selected_types=selected_types)
    await callback.message.edit_reply_markup(
        reply_markup=create_author_types_keyboard(selected_types)
    )
    await callback.answer()

@router.callback_query(AuthorTypesState.selecting, F.data == "save_authors")
async def save_author_types(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение выбранных типов авторов"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    data = await state.get_data()
    selected_types = data.get("selected_types", file_utils.get_author_types())
    
    # Сохраняем настройки
    file_utils.set_author_types(selected_types)
    
    # Форматируем для сообщения
    author_names = {
        'developer': 'застройщики',
        'real_estate_agent': 'агентства',
        'homeowner': 'владельцы',
        'realtor': 'риелторы'
    }
    selected_names = [author_names.get(a, a) for a in selected_types]
    
    await callback.answer(f"✅ Сохранены типы авторов: {', '.join(selected_names)}")
    await state.clear()
    await parsing_settings(callback.message)

@router.callback_query(AuthorTypesState.selecting, F.data == "back_to_settings")
async def back_to_settings_from_authors(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в настройки без сохранения"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    await callback.answer("❌ Изменения не сохранены")
    await state.clear()
    await parsing_settings(callback.message)

@router.message(F.text.endswith("Изменить регион"))
async def change_region(message: types.Message, state: FSMContext):
    """Обработчик кнопки изменения региона"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    await state.set_state(RegionState.waiting_region_name)
    
    # Отправляем подсказку с популярными регионами
    popular_regions = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
        "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону"
    ]
    
    regions_text = "\n".join([f"• {region}" for region in popular_regions])
    
    await message.answer(
        "Введите название региона:\n\n"
        "🔹 <b>Популярные регионы:</b>\n"
        f"{regions_text}\n\n"
        "Для полного списка регионов нажмите кнопку 'Список регионов'",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )

@router.message(F.text.endswith("Список регионов"))
async def send_regions_list(message: types.Message):
    """Отправляет список доступных регионов в виде файла"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    try:
        # Генерируем файл со списком регионов
        regions = cianparser.list_locations()
        regions.sort(key=lambda x: x[0].lower())
        
        filename = "available_regions.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("Список доступных регионов для парсинга:\n")
            f.write("=" * 50 + "\n\n")
            for region in regions:
                f.write(f"• {region[0]} (ID: {region[1]})\n")
        
        file = FSInputFile(filename)
        
        # Отправляем файл
        await message.answer_document(
            document=file,
            caption="📋 <b>Полный список доступных регионов:</b>\n\n"
                    "Используйте точное название региона при вводе.",
            parse_mode="HTML"
        )
        
        # Удаляем файл через 30 секунд
        asyncio.create_task(file_utils.delete_file_after_delay(filename, 30))
        
        # Предлагаем ввести регион
        await message.answer(
            "Введите название региона:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Назад в настройки")]],
                resize_keyboard=True
            )
        )
    except Exception as e:
        await message.answer(f"❌ Не удалось сгенерировать список регионов: {str(e)}")

@router.message(F.text.endswith("Выбрать комнаты"))
async def select_rooms(message: types.Message, state: FSMContext):
    """Обработчик кнопки выбора комнат"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    current_rooms = file_utils.get_rooms()
    keyboard = create_rooms_keyboard(current_rooms)
    
    await message.answer(
        "Выберите количество комнат для парсинга:\n\n"
        "Нажмите на комнату, чтобы добавить/удалить её из выборки. "
        "Значок ✅ означает, что комната выбрана.\n\n"
        "После выбора нажмите '💾 Сохранить настройки'.",
        reply_markup=keyboard
    )
    
    # Сохраняем текущий выбор в состояние
    await state.set_data({"selected_rooms": current_rooms})
    await state.set_state(RoomState.selecting_rooms)

@router.message(F.text.endswith("Настроить этажи"))
async def setup_floors(message: types.Message, state: FSMContext):
    """Запуск настройки этажей"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    await state.set_state(MinFloorState.selecting_range)
    await message.answer(
        "Выберите диапазон для МИНИМАЛЬНОГО этажа:",
        reply_markup=create_floor_range_keyboard()
    )

@router.message(F.text.endswith("Настроить цены"))
async def setup_prices(message: types.Message, state: FSMContext):
    """Запуск настройки цен"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    current_min_price = file_utils.get_min_price()
    current_max_price = file_utils.get_max_price()
    
    min_price_text = "не задано" if not current_min_price else f"{current_min_price:,} ₽".replace(",", " ")
    max_price_text = "не задано" if not current_max_price else f"{current_max_price:,} ₽".replace(",", " ")
    
    await message.answer(
        f"💰 <b>Текущие настройки цен:</b>\n"
        f"• Минимальная цена: {min_price_text}\n"
        f"• Максимальная цена: {max_price_text}\n\n"
        "Выберите действие:",
        reply_markup=create_price_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "min_price_set")
async def set_min_price(callback: types.CallbackQuery, state: FSMContext):
    """Запрос минимальной цены"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    await callback.message.edit_text(
        "⬇️ Введите минимальную цену в рублях (например: 5000000):\n\n"
        "Цена должна быть целым числом без пробелов и других символов.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Без ограничений", callback_data="min_price_clear")
        ]])
    )
    await state.set_state(PriceState.min_price)

@router.callback_query(F.data == "max_price_set")
async def set_max_price(callback: types.CallbackQuery, state: FSMContext):
    """Запрос максимальной цены"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    await callback.message.edit_text(
        "⬆️ Введите максимальную цену в рублях (например: 10000000):\n\n"
        "Цена должна быть целым числом без пробелов и других символов.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Без ограничений", callback_data="max_price_clear")
        ]])
    )
    await state.set_state(PriceState.max_price)

@router.callback_query(F.data.startswith(("min_price_clear", "max_price_clear")))
async def clear_price(callback: types.CallbackQuery, state: FSMContext):
    """Очистка цены"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    price_type = "min_price" if callback.data.startswith("min_price") else "max_price"
    
    if price_type == "min_price":
        file_utils.set_min_price(None)
    else:
        file_utils.set_max_price(None)
    
    await callback.answer(f"✅ {price_type.replace('_', ' ').capitalize()} очищена")
    await setup_prices(callback.message, state)

@router.message(PriceState.min_price, F.text)
async def process_min_price(message: types.Message, state: FSMContext):
    """Обработка минимальной цены"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    if message.text == "❌ Без ограничений":
        file_utils.set_min_price(None)
        await message.answer("✅ Минимальная цена очищена")
    else:
        try:
            price = int(message.text)
            file_utils.set_min_price(price)
            await message.answer(f"✅ Минимальная цена установлена: {price:,} ₽".replace(",", " "))
        except ValueError:
            await message.answer("❌ Неверный формат цены. Введите целое число (например: 5000000)")
    
    await state.clear()
    await setup_prices(message, state)

@router.message(PriceState.max_price, F.text)
async def process_max_price(message: types.Message, state: FSMContext):
    """Обработка максимальной цены"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    if message.text == "❌ Без ограничений":
        file_utils.set_max_price(None)
        await message.answer("✅ Максимальная цена очищена")
    else:
        try:
            price = int(message.text)
            file_utils.set_max_price(price)
            await message.answer(f"✅ Максимальная цена установлена: {price:,} ₽".replace(",", " "))
        except ValueError:
            await message.answer("❌ Неверный формат цены. Введите целое число (например: 10000000)")
    
    await state.clear()
    await setup_prices(message, state)

@router.callback_query(F.data == "clear_prices")
async def clear_all_prices(callback: types.CallbackQuery, state: FSMContext):
    """Очистка всех цен"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    file_utils.set_min_price(None)
    file_utils.set_max_price(None)
    await callback.answer("✅ Все цены очищены")
    await setup_prices(callback.message, state)

@router.callback_query(F.data == "save_prices")
async def save_prices(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение настроек цен"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    await callback.answer("✅ Настройки цен сохранены!")
    await parsing_settings(callback.message)

@router.message(F.text.endswith("Сбросить настройки"))
async def reset_settings(message: types.Message):
    """Сброс всех настроек к значениям по умолчанию"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    # Сбрасываем настройки
    file_utils.reset_settings()
    
    await message.answer(
        "✅ Все настройки сброшены к значениям по умолчанию:\n"
        "• Регион: Тюмень\n"
        "• Комнаты: 1, 2, 3, 4\n"
        "• Минимальный этаж: не задано\n"
        "• Максимальный этаж: не задано\n"
        "• Минимальная цена: не задано\n"
        "• Максимальная цена: не задано\n"
        "• Типы авторов: 🏗️ developer, 🏢 real_estate_agent, 🏠 homeowner, 👔 realtor\n"
        "• Автопарсинг: ❌ выключен",
        reply_markup=create_main_keyboard()
    )

@router.callback_query(RoomState.selecting_rooms, F.data.startswith("room_"))
async def toggle_room(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик переключения комнаты"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    room_num = int(callback.data.split("_")[1])
    state_data = await state.get_data()
    selected_rooms = state_data.get("selected_rooms", [])
    
    if room_num in selected_rooms:
        selected_rooms.remove(room_num)
    else:
        selected_rooms.append(room_num)
        selected_rooms.sort()
    
    # Обновляем состояние
    await state.update_data(selected_rooms=selected_rooms)
    
    # Обновляем клавиатуру
    keyboard = create_rooms_keyboard(selected_rooms)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(RoomState.selecting_rooms, F.data == "save_rooms")
async def save_rooms(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик сохранения выбранных комнат"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    state_data = await state.get_data()
    selected_rooms = state_data.get("selected_rooms", [])
    
    # Сохраняем настройки
    file_utils.set_rooms(selected_rooms)
    
    await callback.answer("✅ Настройки комнат сохранены!")
    await callback.message.delete()
    await state.clear()
    
    # Возвращаем в меню настроек
    await parsing_settings(callback.message)

@router.callback_query(MinFloorState.selecting_range, F.data.startswith("floor_range_"))
async def min_floor_range_selected(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора диапазона этажей"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    data = callback.data.split("_")
    if data[2] == "all":
        await state.update_data(range_start=0, range_end=0, range_name="Все этажи")
        file_utils.set_min_floor([])
        await callback.answer("Минимальный этаж: без ограничений")
        await state.set_state(MaxFloorState.selecting_range)
        await callback.message.answer(
            "Выберите диапазон для МАКСИМАЛЬНОГО этажа:",
            reply_markup=create_floor_range_keyboard()
        )
        return
    else:
        start = int(data[2])
        end = int(data[3])
        await state.update_data(range_start=start, range_end=end, range_name=f"{start}-{end}")
    
    await state.set_state(MinFloorState.selecting_floors)
    current_floors = file_utils.get_min_floor()
    
    state_data = await state.get_data()
    await callback.message.edit_text(
        f"Выберите МИНИМАЛЬНЫЕ этажи в диапазоне {state_data['range_name']}:\n"
        "(Нажмите на этаж, чтобы выбрать/отменить)",
        reply_markup=create_floor_selection_keyboard(
            state_data['range_start'],
            state_data['range_end'],
            current_floors
        )
    )

@router.callback_query(MinFloorState.selecting_floors, F.data.startswith("floor_"))
async def min_floor_selected(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора конкретного этажа"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    data_parts = callback.data.split("_")
    action = data_parts[1]
    state_data = await state.get_data()
    current_floors = file_utils.get_min_floor()
    
    if action == "select":  # Выбрать все
        new_floors = list(range(state_data['range_start'], state_data['range_end'] + 1))
        file_utils.set_min_floor(new_floors)
        await callback.answer("Все этажи в диапазоне выбраны!") 
    elif action == "save":  # Сохранить
        # Сохраняем минимальные этажи
        current_min_floors = file_utils.get_min_floor()
        
        # Вычисляем минимальное значение для максимального этажа
        min_value_for_max = max(current_min_floors) if current_min_floors else 0
        
        await callback.answer("Выбор сохранён")
        await state.set_state(MaxFloorState.selecting_range)
        await callback.message.answer(
            "Выберите диапазон для МАКСИМАЛЬНОГО этажа:",
            reply_markup=create_floor_range_keyboard(min_value=min_value_for_max)
        )
        return
    elif action == "back":  # Назад
        await state.set_state(MinFloorState.selecting_range)
        await callback.message.edit_text(
            "Выберите диапазон для МИНИМАЛЬНОГО этажа:",
            reply_markup=create_floor_range_keyboard()
        )
        return
    else:  # Выбор конкретного этажа
        floor = int(action)
        if floor in current_floors:
            current_floors.remove(floor)
        else:
            current_floors.append(floor)
        file_utils.set_min_floor(current_floors)
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=create_floor_selection_keyboard(
            state_data['range_start'],
            state_data['range_end'],
            file_utils.get_min_floor()
        )
    )
    await callback.answer()

@router.callback_query(MaxFloorState.selecting_range, F.data.startswith("floor_range_"))
async def max_floor_range_selected(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора диапазона этажей"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    data = callback.data.split("_")
    state_data = await state.get_data()
    current_min_floors = file_utils.get_min_floor()
    min_value_for_max = max(current_min_floors) if current_min_floors else 0
    
    if data[2] == "all":
        await state.update_data(range_start=0, range_end=0, range_name="Все этажи")
        file_utils.set_max_floor([])
        await callback.answer("Максимальный этаж: без ограничений")
        await save_floors_settings(callback.message, state)
        return
    else:
        start = int(data[2])
        end = int(data[3])
        await state.update_data(range_start=start, range_end=end, range_name=f"{start}-{end}")
    
    await state.set_state(MaxFloorState.selecting_floors)
    current_floors = file_utils.get_max_floor()
    
    state_data = await state.get_data()
    await callback.message.edit_text(
        f"Выберите МАКСИМАЛЬНЫЕ этажи в диапазоне {state_data['range_name']}:\n"
        "(Нажмите на этаж, чтобы выбрать/отменить)",
        reply_markup=create_floor_selection_keyboard(
            state_data['range_start'],
            state_data['range_end'],
            current_floors,
            min_value=min_value_for_max
        )
    )

@router.callback_query(MaxFloorState.selecting_floors, F.data.startswith("floor_"))
async def max_floor_selected(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора конкретного этажа"""
    if not await check_admin_access(callback.from_user.id, callback=callback):
        return
        
    data_parts = callback.data.split("_")
    action = data_parts[1]
    state_data = await state.get_data()
    current_floors = file_utils.get_max_floor()
    current_min_floors = file_utils.get_min_floor()
    min_value_for_max = max(current_min_floors) if current_min_floors else 0
    
    if action == "select":  # Выбрать все
        # Фильтруем этажи по минимальному значению
        new_floors = [
            f for f in range(state_data['range_start'], state_data['range_end'] + 1) 
            if f >= min_value_for_max
        ]
        file_utils.set_max_floor(new_floors)
        await callback.answer("Все этажи в диапазоне выбраны!")
    elif action == "save":  # Сохранить
        await save_floors_settings(callback.message, state)
        return
    elif action == "back":  # Назад
        await state.set_state(MaxFloorState.selecting_range)
        await callback.message.edit_text(
            "Выберите диапазон для МАКСИМАЛЬНОГО этажа:",
            reply_markup=create_floor_range_keyboard(min_value=min_value_for_max)
        )
        return
    else:  # Выбор конкретного этажа
        floor = int(action)
        # Проверяем, что этаж не меньше минимального значения
        if min_value_for_max > 0 and floor < min_value_for_max:
            await callback.answer("Этаж должен быть больше минимального значения!")
            return
            
        if floor in current_floors:
            current_floors.remove(floor)
        else:
            current_floors.append(floor)
        file_utils.set_max_floor(current_floors)
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=create_floor_selection_keyboard(
            state_data['range_start'],
            state_data['range_end'],
            file_utils.get_max_floor(),
            min_value=min_value_for_max
        )
    )
    await callback.answer()

async def save_floors_settings(message: types.Message, state: FSMContext):
    """Сохранение настроек этажей и завершение"""
    min_floors = file_utils.get_min_floor()
    max_floors = file_utils.get_max_floor()
    
    min_text = "не задано" if not min_floors else ", ".join(map(str, min_floors))
    max_text = "не задано" if not max_floors else ", ".join(map(str, max_floors))
    
    await state.clear()
    await message.answer(
        f"✅ Настройки этажей сохранены:\n"
        f"• Минимальный этаж: {min_text}\n"
        f"• Максимальный этаж: {max_text}\n\n"
        "Старые данные парсинга удалены.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Назад в настройки")]],
            resize_keyboard=True
        )
    )

@router.message(RegionState.waiting_region_name)
async def process_region_name(message: types.Message, state: FSMContext):
    """Обработчик ввода названия региона"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    # Проверяем, если пользователь хочет вернутьс
    if message.text == "Назад в настройки":
        await state.clear()
        await parsing_settings(message)
        return
        
    region_name = message.text.strip()
    locations = cianparser.list_locations()
    
    # Ищем точное совпадение
    found = None
    for loc in locations:
        if loc[0].lower() == region_name.lower():
            found = loc
            break
    
    if found:
        region_id = found[1]
        file_utils.set_region(region_name, region_id)
        await state.clear()
        
        await message.answer(
            f"✅ <b>Регион изменен</b>\n"
            f"• <b>Новый регион:</b> {region_name}\n"
            f"• <b>ID региона:</b> {region_id}\n\n"
            f"Теперь все парсинги будут выполняться для этого региона.",
            reply_markup=create_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        # Попробуем найти похожие
        similar = []
        for loc in locations:
            if region_name.lower() in loc[0].lower():
                similar.append(loc[0])
                if len(similar) >= 5:  # Ограничим 5 вариантами
                    break
        
        if similar:
            suggestions = "\n".join([f"• {name}" for name in similar])
            await message.answer(
                f"❌ <b>Регион не найден</b>\n\n"
                f"Возможно вы имели в виду:\n"
                f"{suggestions}\n\n"
                "Пожалуйста, введите название точно:",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Регион не найден. Пожалуйста, введите название точно:"
            )

@router.message(F.text == "Назад в настройки")
async def back_to_settings(message: types.Message, state: FSMContext):
    """Обработчик кнопки возврата в настройки"""
    if not await check_admin_access(message.from_user.id, message=message):
        return
        
    await state.clear()
    await parsing_settings(message)
    