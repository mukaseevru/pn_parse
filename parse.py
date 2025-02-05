import os
from selenium import webdriver
from selenium.webdriver.common.by import By
# from selenium.webdriver.support.wait import WebDriverWait
# from selenium.webdriver.support import expected_conditions as ec
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time

BASE_URL = "https://pamyat-naroda.ru/heroes/"

# Путь к файлам сохранения данных и прогресса
DATA_FILE = "heroes_data.xlsx"
PROGRESS_FILE = "progress.txt"

# Настройки Chrome
options = webdriver.ChromeOptions()
# options.add_argument('--headless')  # Запуск без отображения окна браузера
options.add_argument('--window-size=1920x1080')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--start-maximized')
options.add_argument('--disable-infobars')
options.add_argument('--disable-extensions')

# For unix
# driver = webdriver.Chrome(service=Service(executable_path='/usr/bin/chromedriver'), options=options)

# For macOS
# driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Для удалённого запуска (например, через Selenium Grid)
server = 'http://localhost:4444'
driver = webdriver.Remote(command_executor=server, options=options)
driver.set_page_load_timeout(30)  # время в секундах

# Загружаем номер последней обработанной страницы (если файл существует)
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as pf:
        last_page = int(pf.read().strip())
    start_page = last_page + 1
    print(f"Возобновляем с страницы {start_page}...")
else:
    start_page = 1

# Загружаем ранее собранные данные (если файл существует)
if os.path.exists(DATA_FILE):
    all_data = pd.read_excel(DATA_FILE).to_dict(orient="records")
else:
    all_data = []

# Функция для загрузки и парсинга страницы списка героев
def get_hero_links(page):
    url = f"{BASE_URL}?adv_search=y&poslednee_mesto_sluzhbi=158%20сд&group=all&types=pamyat_commander:nagrady_nagrad_doc:nagrady_uchet_kartoteka:nagrady_ubilein_kartoteka:pdv_kart_in:pdv_kart_in_inostranec:pamyat_voenkomat:potery_vpp:pamyat_zsp_parts:kld_ran:kld_bolezn:kld_polit:kld_upk:kld_vmf:kld_partizan:potery_doneseniya_o_poteryah:potery_hospitali:potery_utochenie_poter:potery_spiski_zahoroneniy:potery_voennoplen:potery_iskluchenie_iz_spiskov:potery_kartoteki:potery_rvk_extra:potery_isp_extra:same_doroga:same_rvk:same_guk:potery_knigi_pamyati&page={page}&grouppersons=1"
    driver.get(url)
    time.sleep(2)  # Ожидание загрузки страницы

    hero_links = []
    links = driver.find_elements(By.XPATH, "//a[contains(@href, 'person-hero')]")
    for link in links:
        hero_links.append(link.get_attribute("href"))

    return hero_links

# Функция для парсинга страницы героя
def parse_hero_page(url):
    driver.get(url)
    time.sleep(2)
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
        "Место захоронения": "",
        "Ссылка": short_url
    }

    try:
        data["ФИО"] = driver.find_element(By.CLASS_NAME, "hero-card-panel-head__name").text.strip()
    except Exception as e:
        # print(f"Ошибка получения ФИО: {e}")
        pass

    details = driver.find_elements(By.XPATH, "//dl[@class='heroes_person_details_list']/dt")
    for detail in details:
        try:
            key = detail.text.strip()
            value = detail.find_element(By.XPATH, "following-sibling::dd").text.strip()
            if "Дата рождения" in key:
                data["Дата рождения"] = value
            elif "Место рождения" in key:
                data["Место рождения"] = value
            elif "Место призыва" in key:
                data["Место призыва"] = value
            elif "Дата призыва" in key:
                data["Дата призыва"] = value
            elif "Воинское звание" in key:
                data["Воинское звание"] = value
            elif "Воинская часть" in key:
                data["Воинская часть"] = value
            elif "Награды" in key:
                data["Награды"] = value
            elif "Место выбытия" in key:
                data["Место выбытия"] = value
            elif "Место захоронения" in key:
                data["Место захоронения"] = value
        except Exception as e:
            # print(f"Ошибка обработки деталей: {e}")
            pass

    return data

# Главный цикл парсинга
TOTAL_PAGES = 3647  # общее количество страниц
for page in range(start_page, TOTAL_PAGES + 1):
    print(f"Парсинг страницы {page}...")
    hero_links = get_hero_links(page)

    for hero_url in hero_links:
        hero_data = parse_hero_page(hero_url)
        if hero_data:
            all_data.append(hero_data)

    # Сохраняем номер последней обработанной страницы
    with open(PROGRESS_FILE, "w") as pf:
        pf.write(str(page))

    # Сохраняем данные в Excel
    df = pd.DataFrame(all_data)
    df.to_excel(DATA_FILE, index=False)
    print(f"Страница {page} обработана. Данные сохранены в {DATA_FILE}")

    time.sleep(1)

driver.quit()
