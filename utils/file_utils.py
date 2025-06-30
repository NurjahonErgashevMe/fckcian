import os
import re
import json
from datetime import datetime, timedelta
import database

def ensure_output_dir(output_dir="output"):
    """Создает директорию для выходных файлов, если её нет."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

def get_region_file(output_dir="output"):
    return os.path.join(output_dir, "region_data.json")

def should_refresh_region_file(region_file, max_age_hours=24):
    """Проверяет, нужно ли обновить файл региона (старше max_age_hours часов)."""
    if not os.path.exists(region_file):
        return True
        
    file_time = datetime.fromtimestamp(os.path.getmtime(region_file))
    return datetime.now() - file_time > timedelta(hours=max_age_hours)

def remove_region_file(region_file):
    try:
        if os.path.exists(region_file):
            os.remove(region_file)
            return True
    except:
        pass
    return False

def start_parsing(lock_file="parsing.lock"):
    """Создает lock-файл, указывающий на выполнение парсинга."""
    with open(lock_file, 'w') as f:
        f.write(datetime.now().isoformat())

def finish_parsing(lock_file="parsing.lock"):
    """Удаляет lock-файл."""
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass

def is_parsing_in_progress(lock_file="parsing.lock"):
    """Проверяет, выполняется ли парсинг (существует lock-файл)."""
    return os.path.exists(lock_file)

def get_phones_file(output_dir="output"):
    return os.path.join(output_dir, "data.json")

def extract_urls_from_regions(region_file=None, author_type=None):
    """Извлекает URL объявлений из файла региона, с фильтром по типу автора."""
    if region_file is None:
        region_file = get_region_file()
        
    if not os.path.exists(region_file):
        return []
    
    with open(region_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    urls = []
    for item in data.get("data", []):
        if author_type is None or item.get("author_type") == author_type:
            url = item.get("url")
            if url:
                urls.append(url)
    
    return urls

def extract_id_from_url(url):
    """Извлекает ID объявления из URL."""
    match = re.search(r'/(\d+)/$', url)
    if match:
        return match.group(1)
    return None

def get_region_name():
    return database.get_setting('region', 'Тюмень')

def get_region_id():
    return database.get_setting('region_id', '4827')

def get_rooms():
    rooms_str = database.get_setting('rooms', '1,2,3,4')
    return [int(room) for room in rooms_str.split(',')] if rooms_str else []

def get_min_floor():
    min_floor = database.get_setting('min_floor')
    return [int(floor) for floor in min_floor.split(',')] if min_floor else []

def get_max_floor():
    max_floor = database.get_setting('max_floor')
    return [int(floor) for floor in max_floor.split(',')] if max_floor else []

def get_min_price():
    min_price = database.get_setting('min_price')
    return int(min_price) if min_price else None

def get_max_price():
    max_price = database.get_setting('max_price')
    return int(max_price) if max_price else None

def get_author_types():
    """Возвращает список выбранных типов авторов."""
    author_types_str = database.get_setting('author_types', 'developer,realtor,real_estate_agent,homeowner')
    return author_types_str.split(',') if author_types_str else ['developer']

def set_author_types(author_types: list):
    """Устанавливает выбранные типы авторов."""
    database.set_setting('author_types', ','.join(author_types))