import os
import requests
import json
import csv

# Определяем путь к папке "downloads" в той же директории, где находится Python файл
current_dir = os.path.dirname(os.path.abspath(__file__))  # Получаем текущую директорию
folder_name = "downloads"  # Название папки
folder_path = os.path.join(current_dir, folder_name)

# Проверяем, существует ли папка, если нет — создаем
os.makedirs(folder_path, exist_ok=True)

# --- Скачиваем CSV файл ---

# Указываем путь к CSV файлу
csv_file_name = "tovary.csv"
csv_file_path = os.path.join(folder_path, csv_file_name)

# Загружаем файл с правильными заголовками
csv_url = "https://crm.wanmag-home.com/tovary.csv?rand=19785"
csv_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Выполняем запрос на скачивание CSV файла
csv_response = requests.get(csv_url, headers=csv_headers)

# Проверяем успешность загрузки CSV файла
if csv_response.status_code == 200:
    # Сохраняем CSV файл в указанную папку
    with open(csv_file_path, "wb") as file:
        file.write(csv_response.content)
    print(f"CSV файл успешно загружен в папку {csv_file_path}!")
else:
    print(f"Ошибка: {csv_response.status_code} - Не удалось загрузить CSV файл.")

# --- Получаем информацию о товарах через API ---

# Указываем путь к файлу для сохранения данных о товарах
products_file_name = "products_list.json"
products_file_path = os.path.join(folder_path, products_file_name)

# URL для GET-запроса
api_url = "https://my.prom.ua/api/v1/products/list"

# Заголовки с Bearer токеном для авторизации
api_headers = {
    "Authorization": "Bearer cac2f659837feb45cb18e8d0cf07e299cfe381b6",
    "Content-Type": "application/json"
}

# Выполняем GET-запрос
api_response = requests.get(api_url, headers=api_headers)

# Проверяем успешность загрузки данных о товарах
if api_response.status_code == 200:
    # Получаем данные в формате JSON
    data = api_response.json()
    
    # Сохраняем данные в файл JSON в папке downloads
    with open(products_file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    
    print(f"Информация о товарах успешно загружена и сохранена в {products_file_path}!")
else:
    print(f"Ошибка: {api_response.status_code} - Не удалось получить информацию о товарах.")

# --- Подготовка POST-запросов на основе данных из CSV и JSON ---

# Функция для чтения данных из CSV и создания словаря {sku: quantity_in_stock}
def read_csv(csv_file_path):
    with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        
        # Убираем BOM из названия колонки
        fieldnames = [name.strip('\ufeff"') for name in reader.fieldnames]
        reader.fieldnames = fieldnames
        sku_quantity_map = {}
        for row in reader:
            sku = row.get('Штрих-код')  # Теперь корректное название
            if sku:
                quantity = int(row['Кількість'])  # Поле для количества
                sku_quantity_map[sku] = quantity
    return sku_quantity_map

# Определяем путь к CSV файлу и загружаем данные
csv_file_path = os.path.join("downloads", "tovary.csv")
sku_quantity_map = read_csv(csv_file_path)

# Заголовки для POST-запроса
post_url = "https://my.prom.ua/api/v1/products/edit"  # Замените на правильный URL
headers = {
    "Authorization": "Bearer cac2f659837feb45cb18e8d0cf07e299cfe381b6",
    "Content-Type": "application/json"
}

# Читаем данные из products_list.json
products_file_path = os.path.join("downloads", "products_list.json")
with open(products_file_path, "r", encoding="utf-8") as f:
    products_data = json.load(f)

# Список для всех товаров
products_list = []

# Проходим по каждому продукту и собираем данные
for product in products_data.get('products', []):  # Замените 'products' на правильный ключ, если он другой
    product_id = product.get('id')
    sku = product.get('sku')
    quantity_in_stock = sku_quantity_map.get(sku, 0)

    # Определяем значения для полей "presence" и "in stock"
    presence = "unavailable" if quantity_in_stock < 5 else "available"
    in_stock = False if quantity_in_stock < 5 else True

    # Добавляем данные товара в список
    products_list.append({
        "id": product_id,
        "external_id": sku,
        "presence": presence,
        "in_stock": in_stock,
        "quantity_in_stock": quantity_in_stock
    })
print(products_list)
# Отправляем один POST-запрос с массивом товаров
response = requests.post(post_url, headers=headers, json=products_list)

# Проверяем статус ответа
if response.status_code == 200:
    print("Все товары успешно обновлены!")
    print(f"Ответ сервера: {response.json()}")  # Выводим JSON-ответ от сервера
else:
    print(f"Ошибка при обновлении товаров: {response.status_code}")
    print(f"Сообщение сервера: {response.text}")  # Выводим текст ответа от сервера
