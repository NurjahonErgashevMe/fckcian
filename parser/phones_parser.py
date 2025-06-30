import json
import time
import os
import re
import requests
from datetime import datetime
from requests.exceptions import RequestException
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from utils import file_utils, log_utils, format_utils
import config

class CianPhoneParser:
    def __init__(self, max_phones=None, log_callback=None, clear_existing=False, is_scheduled=False):
        file_utils.ensure_output_dir()
        self.parsed_data = {}
        self.max_phones = max_phones
        self.log_callback = log_callback
        self.current_headers = config.HEADERS.copy()
        self.current_payload_template = config.PAYLOAD_TEMPLATE.copy()
        self.is_scheduled = is_scheduled
        
        # Очистка старых файлов при необходимости
        if clear_existing:
            self._clear_existing_files()
            
        self.load_existing_data()
        self.start_time = datetime.now()
        
        # Получаем выбранные типы авторов
        self.author_types = file_utils.get_author_types()
        
        # Определяем название типа автора для логов
        author_names = {
            'developer': 'застройщики',
            'real_estate_agent': 'агенства недвижимостей',
            'homeowner': 'владельцы домов',
            'realtor': 'риелторы'
        }
        author_display = ", ".join([author_names.get(a, a) for a in self.author_types])
        
        self.log(f"[{self.start_time}] Начало парсинга телефонных номеров")
        self.log(f"🎯 Типы авторов: {author_display}")
        
        # Измененный вывод информации об ограничении
        if self.max_phones is None:
            self.log("📊 ОГРАНИЧЕНИЕ: Без ограничений (будут обработаны все найденные объявления)")
        else:
            self.log(f"📊 ОГРАНИЧЕНИЕ: Будет обработано не более {self.max_phones} номеров")
        
        if self.is_scheduled:
            self.log("⏰ АВТОМАТИЧЕСКИЙ ПАРСИНГ ПО РАСПИСАНИЮ")
        
        if clear_existing:
            self.log("🗑️ Старые файлы данных были удалены")
        
        # Выполняем активацию через браузер ТОЛЬКО если есть застройщики
        if 'developer' in self.author_types:
            self.log("🔧 Тип 'developer' присутствует - используем браузер + API")
            self._activate_browser()
        else:
            self.log("🔧 Тип 'developer' отсутствует - используем только HTML парсинг")

    def _activate_browser(self):
        """Активирует парсер через браузер ТОЛЬКО если есть застройщики"""
        self.log("🌐 Запуск браузера для активации парсера...")
        
        # Получаем список URL застройщиков для активации
        urls = file_utils.extract_urls_from_regions(author_type='developer')
        if not urls:
            url = "https://tyumen.cian.ru/sale/flat/307997699/"  # дефолтный URL
            self.log(f"❌ Нет URL застройщиков, используем дефолтный URL: {url}")
        else:
            url = urls[0]
            self.log(f"✅ Используем первый URL застройщика для активации: {url}")
        
        intercepted_headers = None
        intercepted_payload = None
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Перехватываем запросы к API
                def handle_request(route, request):
                    nonlocal intercepted_headers, intercepted_payload
                    if request.url == config.API_URL and request.method == "POST":
                        intercepted_headers = dict(request.headers)
                        intercepted_payload = request.post_data_json
                        self.log(f"📡 Перехвачен запрос на API: {request.url}")
                    route.continue_()
                
                page.route("**/*", handle_request)
                
                # Переходим на страницу объявления
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Кликаем кнопку контактов
                try:
                    page.wait_for_selector('[data-testid="contacts-button"]', state="visible", timeout=15000)
                    page.click('[data-testid="contacts-button"]')
                    self.log("✅ Кнопка контактов нажата")
                except Exception as e:
                    self.log(f"❌ Ошибка при клике на кнопку: {str(e)}")
                
                # Ждем появления номера
                try:
                    page.wait_for_selector('[data-testid="PhoneLink"], .phone-number', state="attached", timeout=10000)
                    self.log("📞 Номер телефона появился на странице")
                except:
                    self.log("⏰ Таймаут ожидания номера телефона")
                
                # Дополнительное время для перехвата
                page.wait_for_timeout(5000)
                browser.close()
        
        except Exception as e:
            self.log(f"❌ Ошибка при активации через браузер: {str(e)}")
        
        # Обновляем данные на основе перехваченных значений
        if intercepted_headers and intercepted_payload:
            self.log("🔄 Обновляем заголовки и payload на основе перехваченных данных")
            
            # Обновляем заголовки
            self.current_headers.update({
                "Cookie": intercepted_headers.get("cookie", self.current_headers.get("Cookie", "")),
                "Referer": intercepted_headers.get("referer", self.current_headers.get("Referer", "")),
                "Origin": intercepted_headers.get("origin", self.current_headers.get("Origin", ""))
            })
            
            # Обновляем payload
            self.current_payload_template.update({
                "blockId": intercepted_payload.get("blockId", self.current_payload_template.get("blockId", 0)),
                "platformType": intercepted_payload.get("platformType", self.current_payload_template.get("platformType", "")),
                "pageType": intercepted_payload.get("pageType", self.current_payload_template.get("pageType", "")),
                "placeType": intercepted_payload.get("placeType", self.current_payload_template.get("placeType", "")),
                "refererUrl": intercepted_payload.get("refererUrl", self.current_payload_template.get("refererUrl", "")),
                "utm": intercepted_payload.get("utm", self.current_payload_template.get("utm", ""))
            })
            
            self.log("✅ Данные успешно обновлены")
        else:
            self.log("⚠️ Не удалось перехватить данные, используем значения по умолчанию")

    def _clear_existing_files(self):
        """Удаляет существующие файлы данных, чтобы начать парсинг заново"""
        files_to_remove = [
            file_utils.get_phones_file(),  # data.json
            "output/phones.txt"       # файл экспорта
        ]
        
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.log(f"🗑️ Удален файл: {file_path}")
                except Exception as e:
                    self.log(f"❌ Ошибка при удалении файла {file_path}: {str(e)}")
    
    def log(self, message):
        log_utils.log_message(self.log_callback, message)
    
    def extract_domain(self, url):
        """Извлекает региональный поддомен из URL"""
        match = re.search(r'https?://([a-z]+)\.cian\.ru', url)
        return match.group(1) if match else "www"
    
    def load_existing_data(self):
        phones_file = file_utils.get_phones_file()
        try:
            if os.path.exists(phones_file):
                with open(phones_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.parsed_data = data.get("data", {})
                self.log(f"📂 Загружено {len(self.parsed_data)} существующих номеров")
            else:
                self.log("📂 Файл с номерами не найден, начинаем с чистого листа")
        except (FileNotFoundError, json.JSONDecodeError):
            self.log("❌ Файл с номерами не найден или поврежден, начинаем с чистого листа")
            self.parsed_data = {}
    
    def save_data(self):
        with open(file_utils.get_phones_file(), 'w', encoding='utf-8') as f:
            json.dump({"data": self.parsed_data}, f, ensure_ascii=False, indent=2)
        self.log(f"💾 [{datetime.now()}] Сохранено {len(self.parsed_data)} номеров")

    def parse_html_for_data(self, url, author_type):
        """Парсит HTML страницы для получения нужных данных в зависимости от типа автора"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            html_content = response.text
            
            if author_type == 'developer':
                # Для застройщиков ищем siteBlockId
                site_block_match = re.search(r'"siteBlockId":\s*(\d+)', html_content)
                if site_block_match:
                    site_block_id = int(site_block_match.group(1))
                    self.log(f"🏗️ Найден siteBlockId в HTML: {site_block_id}")
                    return {
                        "siteBlockId": site_block_id,
                        "type": "site_block"
                    }
                
                self.log(f"❌ siteBlockId не найден в HTML для {url}")
                return None
            else:
                # Для остальных типов ищем offerPhone
                offer_match = re.search(r'"offerPhone":\s*"([^"]+)"', html_content)
                if offer_match:
                    phone = offer_match.group(1)
                    formatted_phone = format_utils.format_phone(phone)
                    self.log(f"📞 Найден offerPhone в HTML: {formatted_phone}")
                    return {
                        "phone": formatted_phone,
                        "notFormattedPhone": re.sub(r'\D', '', phone),
                        "type": "direct_phone"
                    }
                
                self.log(f"❌ offerPhone не найден в HTML для {url}")
                return None
            
        except Exception as e:
            self.log(f"❌ Ошибка при парсинге HTML: {str(e)}")
            return None
    
    def fetch_phone_with_retry(self, announcement_id, url, site_block_id=None):
        """Получает телефонный номер через API с повторными попытками (ТОЛЬКО для застройщиков)"""
        domain = self.extract_domain(url)
        location_url = f"https://tyumen.cian.ru/sale/flat/{announcement_id}/"
        
        headers = format_utils.sanitize_payload(self.current_headers)
        payload = self.current_payload_template.copy()
        payload = format_utils.sanitize_payload(payload)
        
        # Используем siteBlockId как blockId для API запроса
        if site_block_id is not None:
            payload["blockId"] = int(site_block_id)
            self.log(f"🔗 Используем siteBlockId как blockId: {site_block_id}")
        
        payload.update({
            "announcementId": int(announcement_id),
            "locationUrl": location_url,
        })
        
        attempts = 0
        max_attempts = 6
        
        while attempts < max_attempts:
            try:
                response = requests.post(
                    config.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()
                
                if "phone" in data and data["phone"]:
                    # Форматируем телефон перед возвратом
                    data["phone"] = format_utils.format_phone(data["phone"])
                    return data
                else:
                    self.log(f"⚠️ Попытка {attempts+1}/{max_attempts}: Пустой ответ для ID {announcement_id}")
            
            except RequestException as e:
                self.log(f"❌ Попытка {attempts+1}/{max_attempts}: Ошибка запроса для ID {announcement_id}: {str(e)}")
            except json.JSONDecodeError:
                self.log(f"❌ Попытка {attempts+1}/{max_attempts}: Невалидный JSON для ID {announcement_id}")
            
            attempts += 1
            if attempts < max_attempts:
                time.sleep(2)
        
        # Если все попытки не удались, пробуем получить номер через браузер
        self.log(f"🌐 Все {max_attempts} попыток API не удались. Пробуем Playwright для ID {announcement_id}")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Переходим на страницу объявления
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Кликаем кнопку контактов
                try:
                    page.wait_for_selector('[data-testid="contacts-button"]', state="visible", timeout=10000)
                    page.click('[data-testid="contacts-button"]')
                except:
                    try:
                        page.evaluate('''() => {
                            const btn = document.querySelector('[data-testid="contacts-button"]');
                            if (btn) btn.click();
                        }''')
                    except:
                        pass
                
                # Ждем появления номера
                try:
                    page.wait_for_selector('[data-testid="PhoneLink"], .phone-number', state="attached", timeout=10000)
                except:
                    pass
                
                # Извлекаем номер
                phone_element = page.query_selector('[data-testid="PhoneLink"], .phone-number')
                if phone_element:
                    phone_text = phone_element.inner_text()
                    # Очищаем номер от лишних символов
                    phone_text = re.sub(r'[^\d+]', '', phone_text)
                    self.log(f"📞 Извлечен номер со страницы: {phone_text}")
                    
                    # Форматируем телефон
                    formatted_phone = format_utils.format_phone(phone_text)
                    return {
                        "phone": formatted_phone,
                        "notFormattedPhone": phone_text
                    }
                
                browser.close()
        except Exception as e:
            self.log(f"❌ Ошибка при получении номера через браузер: {str(e)}")
        
        return None

    def get_filename_suffix(self):
        """Генерирует суффикс для имени файла с регионом, типом автора и временем"""
        # Получаем регион (можно сделать динамически из конфигурации)
        region_id = file_utils.get_region_id() or "unknown"
        
        # Определяем тип автора
        author_types = self.author_types
        author_display = "_".join(author_types) if author_types else "all"
        
        # Форматируем время
        timestamp = self.start_time.strftime("%d.%m.%Y-%H-%M-%S")
        
        return f"_{region_id}_{author_display}_{timestamp}"

    def export_phones_to_txt(self):
        """Экспортирует номера в текстовый файл с улучшенным именованием"""
        suffix = self.get_filename_suffix()
        txt_file = f"output/phones{suffix}.txt"
        
        success_count = sum(1 for v in self.parsed_data.values() if v.get("phone") and v["phone"] != "не удалось получить")
        
        # Определяем название типа автора для отчета
        author_names = {
            'developer': 'Застройщики',
            'real_estate_agent': 'Агентства недвижимостей',
            'homeowner': 'Владельцы домов',
            'realtor': 'Риелторы'
        }
        author_display = ", ".join([author_names.get(a, a) for a in self.author_types])
        
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("📊 ОТЧЕТ О ПАРСИНГЕ ТЕЛЕФОННЫХ НОМЕРОВ\n")
            f.write("="*60 + "\n\n")
            f.write(f"📅 Дата парсинга: {self.start_time.strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write(f"🎯 Типы авторов: {author_display}\n")
            f.write(f"🌍 Регион: {file_utils.get_region_name()} (ID: {file_utils.get_region_id()})\n")
            f.write(f"📈 Обработано объявлений: {len(self.parsed_data)}\n")
            f.write(f"✅ Успешно полученных номеров: {success_count}\n")
            f.write(f"⏱️ Время выполнения: {datetime.now() - self.start_time}\n")
            
            # Измененный вывод информации об ограничении
            if self.max_phones is None:
                f.write(f"🎯 Ограничение на количество: без ограничений\n\n")
            else:
                f.write(f"🎯 Ограничение на количество: {self.max_phones}\n\n")
            
            f.write("📞 СПАРСЕННЫЕ НОМЕРА:\n")
            f.write("="*60 + "\n")
            
            for aid, data in self.parsed_data.items():
                phone = data.get("phone", "не удалось получить")
                source = data.get("source", "unknown")
                source_emoji = {
                    "direct": "📋",
                    "api": "🔗",
                    "html": "🌐",
                    "failed": "❌"
                }.get(source, "❓")
                
                f.write(f"🆔 ID: {aid}\n")
                f.write(f"📞 Телефон: {phone}\n")
                f.write(f"{source_emoji} Источник: {source}\n")
                f.write("-"*50 + "\n")
        
        self.log(f"📄 Номера экспортированы в {txt_file}")
        self.log(f"✅ Успешных номеров: {success_count}/{len(self.parsed_data)}")
        return txt_file
    
    def parse(self):
        # Собираем URL для всех выбранных типов авторов
        urls = []
        for auth_type in self.author_types:
            type_urls = file_utils.extract_urls_from_regions(author_type=auth_type)
            urls.extend(type_urls)
        
        if not urls:
            author_names = {
                'developer': 'застройщики',
                'real_estate_agent': 'агенства недвижимостей',
                'homeowner': 'владельцы домов',
                'realtor': 'риелторы'
            }
            selected_names = [author_names.get(a, a) for a in self.author_types]
            self.log(f"❌ Нет URL для обработки! Не найдено объявлений от типов: {', '.join(selected_names)}")
            return None
        
        total_urls = len(urls)
        request_count = 0
        success_count = 0
        processed_count = 0
        
        author_names = {
            'developer': 'застройщики',
            'real_estate_agent': 'агенства недвижимостей',
            'homeowner': 'владельцы домов',
            'realtor': 'риелторы'
        }
        selected_names = [author_names.get(a, a) for a in self.author_types]
        
        self.log(f"📊 Всего URL для обработки: {total_urls}")
        self.log(f"🎯 Типы авторов: {', '.join(selected_names)}")
        
        # Измененный вывод информации об ограничении
        if self.max_phones is None:
            self.log("📈 Ограничение на количество номеров: без ограничений")
        else:
            self.log(f"📈 Ограничение на количество номеров: {self.max_phones}")
        
        for idx, url in enumerate(urls, 1):
            # Проверяем ограничение ТОЛЬКО если max_phones задан
            if self.max_phones is not None and processed_count >= self.max_phones:
                self.log(f"\n🎯 Достигнуто ограничение в {self.max_phones} номеров. Парсинг остановлен.")
                break
            
            aid = file_utils.extract_id_from_url(url)
            if not aid:
                self.log(f"❌ Не удалось извлечь ID из URL: {url}")
                continue
            
            if aid in self.parsed_data:
                self.log(f"⏭️ [{idx}/{total_urls}] Пропуск существующего ID: {aid}")
                continue
            
            # Определяем тип автора для текущего URL
            author_type = None
            for a_type in self.author_types:
                if any(a_type in u for u in [url]):  # Упрощенная проверка
                    author_type = a_type
                    break
            
            if not author_type:
                self.log(f"⚠️ Не удалось определить тип автора для URL: {url}")
                author_type = 'unknown'
            
            self.log(f"🔍 [{idx}/{total_urls}] Запрос для ID: {aid} (Тип: {author_type})")
            
            # ЛОГИКА ОБРАБОТКИ В ЗАВИСИМОСТИ ОТ ТИПА АВТОРА
            if author_type == 'developer':
                # Для застройщиков - парсим HTML чтобы получить siteBlockId, затем делаем API запрос
                html_result = self.parse_html_for_data(url, author_type)
                
                if html_result and html_result.get("type") == "site_block":
                    site_block_id = html_result["siteBlockId"]
                    
                    # Теперь делаем API запрос с полученным siteBlockId
                    api_result = self.fetch_phone_with_retry(aid, url, site_block_id)
                    request_count += 1
                    processed_count += 1
                    
                    if api_result and "phone" in api_result and api_result["phone"]:
                        self.parsed_data[aid] = {
                            "phone": api_result["phone"],
                            "notFormattedPhone": api_result.get("notFormattedPhone", re.sub(r'\D', '', api_result["phone"])),
                            "source": "api",
                            "siteBlockId": site_block_id
                        }
                        success_count += 1
                        self.log(f"✅ Успешно через API (siteBlockId={site_block_id}): {aid} => {api_result['phone']}")
                    else:
                        self.parsed_data[aid] = {
                            "phone": "не удалось получить",
                            "notFormattedPhone": "",
                            "source": "failed",
                            "siteBlockId": site_block_id
                        }
                        self.log(f"❌ Не удалось получить номер через API для {aid} (siteBlockId={site_block_id})")
                else:
                    # Если не нашли siteBlockId в HTML
                    processed_count += 1
                    self.parsed_data[aid] = {
                        "phone": "не удалось получить",
                        "notFormattedPhone": "",
                        "source": "failed"
                    }
                    self.log(f"❌ Не найден siteBlockId в HTML для {aid}")
            else:
                # Для НЕ застройщиков - парсим HTML чтобы получить offerPhone напрямую
                html_result = self.parse_html_for_data(url, author_type)
                processed_count += 1
                
                if html_result and html_result.get("type") == "direct_phone":
                    self.parsed_data[aid] = {
                        "phone": html_result["phone"],
                        "notFormattedPhone": html_result.get("notFormattedPhone", ""),
                        "source": "html"
                    }
                    success_count += 1
                    self.log(f"✅ Успешно через HTML: {aid} => {html_result['phone']}")
                else:
                    self.parsed_data[aid] = {
                        "phone": "не удалось получить",
                        "notFormattedPhone": "",
                        "source": "failed"
                    }
                    self.log(f"❌ Не удалось получить номер из HTML для {aid}")
            
            # Сохраняем прогресс
            if idx % 5 == 0:
                self.save_data()
            
            # Задержка между запросами
            if author_type == 'developer' and request_count % 50 == 0:
                self.log(f"⏸️ Выполнено {request_count} запросов. Ожидание 15 секунд...")
                time.sleep(15)
            else:
                time.sleep(1)  # Небольшая задержка для HTML парсинга
        
        self.save_data()
        
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        self.log("\n" + "="*60)
        self.log(f"🏁 Парсинг завершен: {end_time.strftime('%d.%m.%Y %H:%M:%S')}")
        self.log(f"⏱️ Общее время выполнения: {duration}")
        
        # Измененный вывод информации об обработанных номерах
        if self.max_phones is None:
            self.log(f"📊 Обработано номеров: {processed_count}")
        else:
            self.log(f"📊 Обработано номеров: {processed_count}/{self.max_phones}")
        
        self.log(f"✅ Успешных номеров: {success_count}/{processed_count}")
        if 'developer' in self.author_types:
            self.log(f"🔗 API запросов выполнено: {request_count}")
        self.log("="*60 + "\n")
        
        return self.export_phones_to_txt()