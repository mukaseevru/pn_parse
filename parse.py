import os
import time
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

# Основные настройки
BASE_URL = "https://pamyat-naroda.ru/heroes/"
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'heroes_data.xlsx')
DATA_FILE_UNIQUE = os.path.join(os.path.dirname(__file__), 'data', 'heroes_data_unique.xlsx')
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'progress.txt')
FAILED_LINKS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'failed_hero_links.txt')

# Настройка опций Chrome
options = webdriver.ChromeOptions()
# options.add_argument('--headless')  # раскомментируйте, если нужен headless режим
options.add_argument('--window-size=1920x1080')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--start-maximized')
options.add_argument('--disable-infobars')
options.add_argument('--disable-extensions')

# Для удалённого запуска (например, через Selenium Grid)
server = 'http://localhost:4444'  # адрес Selenium Grid


# Функция инициализации драйвера
def initialize_driver():
    global driver
    driver = webdriver.Remote(command_executor=server, options=options)
    # For unix:
    # driver = webdriver.Chrome(service=Service(executable_path='/usr/bin/chromedriver'), options=options)
    # For macOS:
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    # Устанавливаем увеличенный таймаут загрузки страницы
    driver.set_page_load_timeout(30)
    return driver


# Инициализируем драйвер
initialize_driver()


# Функция для корректного завершения и повторной инициализации драйвера
def reinitialize_driver():
    global driver
    try:
        driver.quit()
    except Exception as e:
        print("Ошибка при закрытии драйвера:", e)
    print("Переинициализация драйвера...")
    initialize_driver()


# Функция для загрузки URL с ожиданием появления нужного элемента.
# При неудаче (например, TimeoutException) происходит повторная инициализация драйвера и повтор загрузки.
def load_url(url, expected_locator=None, timeout=30, retry=5):
    for attempt in range(retry):
        try:
            driver.get(url)
            if expected_locator:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located(expected_locator)
                )
            return True
        except TimeoutException:
            print(f"TimeoutException при загрузке {url} (Попытка {attempt + 1}/{retry}).")
            reinitialize_driver()
        except Exception as e:
            print(f"Ошибка при загрузке {url}: {e} (Попытка {attempt + 1}/{retry}).")
            reinitialize_driver()
    print(f"Не удалось загрузить {url} после {retry} попыток.")
    return False


# При запуске скрипта загружаем номер последней обработанной страницы (если файл существует)
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as pf:
        last_page = int(pf.read().strip())
    start_page = last_page + 1
    print(f"Возобновляем парсинг с страницы {start_page}...")
else:
    start_page = 1

# Если ранее были собраны данные, загружаем их
if os.path.exists(DATA_FILE):
    all_data = pd.read_excel(DATA_FILE).to_dict(orient="records")
    all_data_links = set(hero['Ссылка'] for hero in all_data)
else:
    all_data = []  # Создаем пустой список для данных
    all_data_links = set()  # Создаем пустой сет для уникальности ссылок


# Используем текущий сет all_data_links для проверки уникальности
def hero_already_in_data(short_url):
    return short_url in all_data_links


# Функция для получения ссылок на страницы героев с указанной страницы списка
def get_hero_links(page):
    url = (
        f"{BASE_URL}?lager=Шталаг%20337&group=all"
        "&types=pamyat_commander:nagrady_nagrad_doc:nagrady_uchet_kartoteka:"
        "nagrady_ubilein_kartoteka:pdv_kart_in:pdv_kart_in_inostranec:pamyat_voenkomat:"
        "potery_vpp:pamyat_zsp_parts:kld_ran:kld_bolezn:kld_polit:kld_upk:kld_vmf:"
        "kld_partizan:potery_doneseniya_o_poteryah:potery_hospitali:potery_utochenie_poter:"
        "potery_spiski_zahoroneniy:potery_voennoplen:potery_iskluchenie_iz_spiskov:"
        "potery_kartoteki:potery_rvk_extra:potery_isp_extra:same_doroga:same_rvk:same_guk:"
        "potery_knigi_pamyati"
        f"&page={page}&grouppersons=1"
    )

    # Ожидаем, что на странице появятся ссылки с указанным классом
    if not load_url(url, expected_locator=(By.CLASS_NAME, "heroes-list-item-name"), timeout=30, retry=5):
        return []

    hero_links = []
    try:
        links = driver.find_elements(By.CLASS_NAME, "heroes-list-item-name")
        for link in links:
            href = link.get_attribute("href")
            if href:
                hero_links.append(href)
    except Exception as e:
        print(f"Ошибка при поиске ссылок на героях на странице {page}: {e}")

    return hero_links


# Функция для парсинга страницы конкретного героя
def parse_hero_page(url):
    if not load_url(url, expected_locator=(By.CLASS_NAME, "hero-card-panel-head__name"), timeout=30, retry=5):
        print(f"Пропускаем страницу героя {url} из-за ошибки загрузки.")
        with open(FAILED_LINKS_FILE, "a") as f:
            f.write(url + "\n")
        return {}

    short_url = url.split("?")[0]
    data = {
        "ФИО": "",
        "Дата рождения": "",
        "Место рождения": "",
        "Место призыва": "",
        "Дата призыва": "",
        "Воинское звание": "",
        "Воинская часть": "",
        "Награды": "",
        "Место выбытия": "",
        "Дата выбытия": "",
        "Причина выбытия": "",
        "Место захоронения": "",
        "Место пленения": "",
        "Лагерь": "",
        "Лагерный номер": "",
        "Дата пленения": "",
        "Биография": "",
        "Источник информации": "",
        "Фонд ист. информации": "",
        "Опись ист. информации": "",
        "Дело ист. информации": "",
        "Ссылка": url.split("?")[0]
    }

    try:
        fio_element = driver.find_element(By.CLASS_NAME, "hero-card-panel-head__name")
        data["ФИО"] = fio_element.get_attribute('textContent').strip()
    except Exception as e:
        print(f"Ошибка получения ФИО на {url}: {e}")

    # Парсим основной блок информации
    try:
        details_list = driver.find_elements(By.XPATH, "//dl[@class='heroes_person_details_list']/dt")
        for detail in details_list:
            key = detail.text.strip()
            value = detail.find_element(By.XPATH, "following-sibling::dd").text.strip()
            if key in data:
                data[key] = value
    except Exception as e:
        print(f"Ошибка парсинга основного блока деталей на {url}: {e}")

    # Дополнительные поля (из раздела документов о плене и пр.)
    try:
        doc_info_items = driver.find_elements(By.CLASS_NAME, "hero-card-docs-item__info")
        for item in doc_info_items:
            try:
                key_element = item.find_element(By.TAG_NAME, "b")
                key = key_element.text.strip(": ")
                value = item.text.replace(key_element.text, "").strip()
                if key in data and not data[key]:  # Заполняем, только если поле еще не заполнено
                    data[key] = value
            except Exception as inner_e:
                print(f"Ошибка получения элемента детальной информации на {url}: {inner_e}")
    except Exception as e:
        print(f"Ошибка получения данных из блока '.hero-card-docs-item__info' на {url}: {e}")

    # Биография (если доступна)
    try:
        bio_elements = driver.find_elements(By.CLASS_NAME, "hero-card__bio__item")
        bio_text = " ".join([el.text.strip() for el in bio_elements if el.text.strip()])
        data["Биография"] = bio_text
    except Exception as e:
        print(f"Ошибка получения биографии на {url}: {e}")

    # Информация об архиве (если доступна)
    try:
        archive_button = driver.find_element(By.CLASS_NAME, "hero-card-docs-item-archive-button")
        driver.execute_script("arguments[0].click();", archive_button)
        time.sleep(1)  # дать время раскрыться
        archive_info_elements = driver.find_elements(By.CLASS_NAME, "hero-card-docs-item__info")
        for element in archive_info_elements:
            key_element = element.find_element(By.TAG_NAME, "b")
            key = key_element.text.strip(": ")
            value = element.text.replace(key_element.text, "").strip()
            if key in data and not data[key]:
                data[key] = value
    except Exception as e:
        print(f"Ошибка получения архивной информации на {url}: {e}")

    return data


# Функция для повторной обработки неудачных ссылок
def attempt_failed_links():
    if not os.path.exists(FAILED_LINKS_FILE):
        print("Файл неудачных ссылок не найден. Нет ссылок для повторной обработки.")
        return

    with open(FAILED_LINKS_FILE, "r") as f:
        failed_urls = [line.strip() for line in f if line.strip()]

    if not failed_urls:
        print("Нет неудачных ссылок для повторной обработки.")
        return

    print("\nНачинается повторная попытка обработки неудачных ссылок.")
    remaining_failed_urls = []
    for url in failed_urls:
        short_url = url.split("?")[0]
        # Проверяем, если герой уже есть в all_data, пропускаем
        if hero_already_in_data(short_url):
            continue
        print(f"\nПовторная обработка героя {url}")
        hero_data = parse_hero_page(url)
        if hero_data:
            all_data.append(hero_data)
        else:
            remaining_failed_urls.append(url)

    # Обновляем файл неудачных ссылок
    if remaining_failed_urls:
        with open(FAILED_LINKS_FILE, "w") as f:
            for url in remaining_failed_urls:
                f.write(url + "\n")
        print(f"После повторной попытки осталось неудачных ссылок: {len(remaining_failed_urls)}")
    else:
        os.remove(FAILED_LINKS_FILE)
        print("Все неудачные ссылки обработаны успешно.")


TOTAL_PAGES = 93  # общее число страниц

# Основной цикл парсинга
for page in range(start_page, TOTAL_PAGES + 1):
    print(f"\nОбработка страницы {page}...")
    hero_links = get_hero_links(page)

    for hero_url in hero_links:
        short_url = hero_url.split("?")[0]
        # Проверяем, если герой уже добавлен, пропускаем его (сравнение по короткой версии ссылки)
        if hero_already_in_data(short_url):
            continue
        else:
            print(f"\nОбработка нового героя {hero_url}")
            hero_data = parse_hero_page(hero_url)
            if hero_data:
                all_data.append(hero_data)
                all_data_links.add(hero_data['Ссылка'])

    # Обновляем номер последней обработанной страницы (малозатратная операция)
    with open(PROGRESS_FILE, "w") as pf:
        pf.write(str(page))

    # Сохраняем накопленные данные только каждые 100 страниц или если это последняя страница
    if page % 10 == 0 or page == TOTAL_PAGES:
        df = pd.DataFrame(all_data)
        df.to_excel(DATA_FILE, index=False)
        df_unique = df.drop_duplicates()
        df_unique.to_excel(DATA_FILE_UNIQUE, index=False)
        print(f"Страница {page} обработана. Данные сохранены в {DATA_FILE}")
    else:
        print(f"Страница {page} обработана.")

    # Небольшая задержка между страницами
    time.sleep(1)

# Повторная попытка обработки неудачных ссылок
attempt_failed_links()

# После повторной попытки сохраняем обновленные данные
df = pd.DataFrame(all_data)
df.to_excel(DATA_FILE, index=False)
df_unique = df.drop_duplicates()
df_unique.to_excel(DATA_FILE_UNIQUE, index=False)
print("Обработка неудачных ссылок завершена. Данные обновлены.")

driver.quit()
