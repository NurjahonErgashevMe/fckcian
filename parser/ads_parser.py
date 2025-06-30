import cianparser
import json
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from utils import file_utils, log_utils, format_utils

def get_block_id_and_phone(url, author_type, log_callback=None):
    """Извлекает blockId и/или телефон из HTML страницы объявления в зависимости от типа автора"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
        
        block_id = None
        phone = None
        
        # ЛОГИКА В ЗАВИСИМОСТИ ОТ ТИПА АВТОРА
        if author_type == 'developer':
            # ДЛЯ ЗАСТРОЙЩИКОВ: ищем ТОЛЬКО siteBlockId
            match = re.search(r'"siteBlockId":\s*(\d+)', html_content)
            if match:
                block_id = match.group(1)
                msg = f"✅ Найден siteBlockId для застройщика: {block_id} для {url}"
                log_utils.log_message(log_callback, msg)
            else:
                msg = f"❌ siteBlockId НЕ найден для застройщика на странице {url}"
                log_utils.log_message(log_callback, msg)
        else:
            # ДЛЯ ОСТАЛЬНЫХ: ищем ТОЛЬКО offerPhone
            offer_match = re.search(r'"offerPhone":\s*"([^"]+)"', html_content)
            if offer_match:
                phone = offer_match.group(1)
                msg = f"✅ Найден готовый номер offerPhone: {phone} для {url}"
                log_utils.log_message(log_callback, msg)
            else:
                # Если offerPhone не найден, пытаемся извлечь его напрямую из HTML
                soup = BeautifulSoup(html_content, 'html.parser')
                phone_element = soup.select_one('[data-testid="PhoneLink"], .phone-number')
                if phone_element:
                    phone = phone_element.get_text(strip=True)
                    # Очищаем номер от лишних символов
                    phone = re.sub(r'[^\d+]', '', phone)
                    msg = f"✅ Найден прямой телефон из HTML: {phone} для {url}"
                    log_utils.log_message(log_callback, msg)
                else:
                    msg = f"❌ offerPhone НЕ найден для НЕ-застройщика на странице {url}"
                    log_utils.log_message(log_callback, msg)
        
        return block_id, phone
    
    except Exception as e:
        msg = f"❌ Ошибка при получении данных: {str(e)}"
        log_utils.log_message(log_callback, msg)
        return None, None

def parse_cian_ads(log_callback=None):
    """Парсит объявления с CIAN и сохраняет в regions.json"""
    log_utils.log_message(log_callback, f"[{datetime.now()}] Начало парсинга объявлений...")
    file_utils.ensure_output_dir()
    
    try:
        # Проверяем возраст файла региона
        region_file = file_utils.get_region_file()
        if file_utils.should_refresh_region_file(region_file):
            log_utils.log_message(log_callback, "⚠️ Данные региона устарели (>1 дня). Удаляем и обновляем...")
            file_utils.remove_region_file(region_file)
        
        # Создаем lock-файл
        file_utils.start_parsing()
        
        # Получаем регион из настроек
        region_name = file_utils.get_region_name()
        region_id = file_utils.get_region_id()
        rooms = file_utils.get_rooms()
        min_floor = file_utils.get_min_floor()
        max_floor = file_utils.get_max_floor()
        min_price = file_utils.get_min_price()
        max_price = file_utils.get_max_price()
        
        # Получаем выбранные типы авторов
        author_types = file_utils.get_author_types()
        log_utils.log_message(log_callback, f"👥 Выбранные типы авторов: {', '.join(author_types)}")
        
        log_utils.log_message(log_callback, f"📍 Парсинг объявлений для региона: {region_name} (ID: {region_id})")
        log_utils.log_message(log_callback, f"🏠 Выбранные комнаты: {', '.join(map(str, rooms))}")
        
        if min_floor:
            log_utils.log_message(log_callback, f"⬇️ Мин. этаж: {min_floor}")
        if max_floor:
            log_utils.log_message(log_callback, f"⬆️ Макс. этаж: {max_floor}")
        if min_price:
            log_utils.log_message(log_callback, f"💰 Мин. цена: {format_utils.format_price(min_price)}")
        if max_price:
            log_utils.log_message(log_callback, f"💰 Макс. цена: {format_utils.format_price(max_price)}")
        
        # Формируем дополнительные настройки
        additional_settings = {
            "start_page": 1,
            "end_page": 200,
        }
        
        if min_floor:
            additional_settings["min_floor"] = min_floor
        if max_floor:
            additional_settings["max_floor"] = max_floor
        if min_price:
            additional_settings["min_price"] = min_price
        if max_price:
            additional_settings["max_price"] = max_price
        
        # Парсим данные
        # Внимание: Для работы этой части нужен установленный пакет cianparser
        # pip install cianparser
        parser = cianparser.CianParser(location=region_name)
        data = parser.get_flats(deal_type="sale", rooms=tuple(rooms), additional_settings=additional_settings)
        
        # Фильтруем данные по выбранным типам авторов
        filtered_data = [item for item in data if item.get('author_type') in author_types]
        data = filtered_data
        
        # Проверяем и корректируем URL
        for item in data:
            if 'url' in item and not item['url'].startswith('http'):
                item['url'] = f"https://www.cian.ru{item['url']}"
        
        # Получаем blockId и телефон для ВСЕХ объявлений В ЗАВИСИМОСТИ ОТ ТИПА АВТОРА
        for item in data:
            url = item.get('url')
            author_type = item.get('author_type')
            
            if url and author_type:
                block_id, phone = get_block_id_and_phone(url, author_type, log_callback)
                
                if author_type == 'developer':
                    # Для застройщиков сохраняем blockId, phone остается None
                    item['blockId'] = block_id
                    item['directPhone'] = None
                else:
                    # Для остальных сохраняем phone, blockId остается None
                    item['blockId'] = None
                    item['directPhone'] = phone
                
                # Задержка, чтобы не нагружать сервер
                time.sleep(1.5)
            else:
                item['blockId'] = None
                item['directPhone'] = None
        
        # Формируем данные для сохранения с метаданными
        result_data = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "region": {
                "name": region_name,
                "id": region_id
            },
            "rooms": rooms,
            "min_floor": min_floor,
            "max_floor": max_floor,
            "min_price": min_price,
            "max_price": max_price,
            "data": data
        }
        
        # Сохраняем ВСЕ данные
        with open(region_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        # Считаем статистику по типам авторов
        author_stats = {}
        phones_found = 0
        block_ids_found = 0
        
        for item in data:
            author_type = item.get('author_type', 'unknown')
            if author_type not in author_stats:
                author_stats[author_type] = {'total': 0, 'with_phone': 0, 'with_blockid': 0}
            
            author_stats[author_type]['total'] += 1
            
            if item.get('directPhone'):
                author_stats[author_type]['with_phone'] += 1
                phones_found += 1
            
            if item.get('blockId'):
                author_stats[author_type]['with_blockid'] += 1
                block_ids_found += 1
        
        # Логируем статистику
        log_utils.log_message(log_callback, f"[{datetime.now()}] Успешно! Сохранено {len(data)} объявлений в {region_file}")
        
        log_utils.log_message(log_callback, "\n📊 СТАТИСТИКА ПО ТИПАМ АВТОРОВ:")
        for author_type, stats in author_stats.items():
            if author_type == 'developer':
                log_utils.log_message(log_callback, f"  🏢 {author_type}: {stats['total']} объявлений, {stats['with_blockid']} с blockId (для API)")
            else:
                log_utils.log_message(log_callback, f"  👤 {author_type}: {stats['total']} объявлений, {stats['with_phone']} с готовыми телефонами")
        
        log_utils.log_message(log_callback, f"\n📞 Всего найдено готовых номеров (НЕ застройщики): {phones_found}")
        log_utils.log_message(log_callback, f"🔗 Всего найдено blockId (застройщики): {block_ids_found}")
        
        return True, len(data)
    
    except Exception as e:
        log_utils.log_message(log_callback, f"[{datetime.now()}] Ошибка парсинга: {str(e)}")
        return False, 0
    finally:
        # Всегда удаляем lock-файл
        file_utils.finish_parsing()