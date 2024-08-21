from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from db import models, crud, database
from sqlalchemy.orm import Session
import json
import requests
import logging
import os
import time
import asyncio


# Убедитесь, что папка для логов существует
log_directory = "/root/webhook/combine_project"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Настройка логирования в файл в папке логов
log_file_path = os.path.join(log_directory, 'app.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Убедитесь, что папка для сохранения полученных JSON файлов существует
upload_directory = "/root/webhook/combine_project/order_data"
if not os.path.exists(upload_directory):
    os.makedirs(upload_directory)

# Глобальная переменная для хранения токена
global_token = ""

app = FastAPI()


# Определение функции для получения заказа по order_id
def get_order_from_horoshop(order_id, global_token):
    url = "https://wanmag-home.online/api/orders/get/"
    
    # Формирование тела запроса
    data = {
        "token": global_token,
        "ids[]": [order_id],  # Массив с одним order_id
        "additionalData": True
    }

    try:
        # Отправка PUT запроса
        response = requests.put(url, json=data)
        
        # Проверка ответа
        if response.status_code == 200:
            order_data = response.json()
            logger.info(f"Order data received: {order_data}")
            return order_data
        else:
            logger.error(f"Failed to get order data. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Exception occurred while getting order data: {str(e)}")
        return None


# Функция для обновления токена
async def update_token():
    global global_token
    while True:
        try:
            url = "https://wanmag-home.online/api/auth/"
            headers = {"Content-Type": "application/json"}
            data = {
                "login": "owner",
                "password": "hahrlnpqx"
            }

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                response_data = response.json()
                if response_data["status"] == "OK":
                    global_token = response_data["response"]["token"]
                    logger.info(f"Token updated successfully: {global_token}")
                else:
                    logger.error("Failed to update token: Invalid status in response")
            else:
                logger.error(f"Failed to update token: {response.status_code}")
        except Exception as e:
            logger.error(f"Exception occurred while updating token: {str(e)}")

        # Ждем 4 минуты перед следующим запросом
        await asyncio.sleep(240)

# Запуск фоновой задачи для обновления токена
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(update_token())


def transform_payload(first_order, payload, db: Session):
    logger.info("Transforming payload...")

    # Ищем пользователя по email
    user = crud.get_user_by_email(db, payload.get("delivery_email", ""))
    source_id = user.id if user else None

    transformed = {
        "source_id": source_id,  # Используем найденный id
        "source_uuid": str(payload.get("order_id", "")),
        "buyer_comment": payload.get("comment", ""),
        "manager_id": 1,  # fixed value
        "manager_comment": payload.get("manager_comment", ""),
        "promocode": payload.get("coupon_code", ""),
        "discount_percent": payload.get("discount_percent", 0),
        "discount_amount": payload.get("discount_value", 0),
        "shipping_price": payload.get("delivery_price", 0),
        "wrap_price": 0,  # fixed value
        "gift_message": "",  # fixed value
        "is_gift": False,  # fixed value
        "gift_wrap": False,  # fixed value
        "taxes": 0,  # fixed value
        "ordered_at": payload.get("stat_created", ""),
        "buyer": {
            "full_name": payload.get("dropshipping_details", {}).get("dropshiper", {}).get("name", ""),
            "email": payload.get("delivery_email", ""),
            "phone": payload.get("delivery_phone", "")
        },
        "shipping": {
            "delivery_service_id": 1,  # fixed value
            "tracking_code": payload.get("delivery_data", {}).get("tnNumber", ""),
            "shipping_service": payload.get("delivery_type", {}).get("title", ""),
            "shipping_address_city": payload.get("delivery_city", ""),
            "shipping_address_country": "Ukraine",  # fixed value
            "shipping_address_region": "",
            "shipping_address_zip": "",
            "shipping_secondary_line": "string",  # fixed value
            "shipping_receive_point": payload.get("delivery_address", ""),
            "recipient_full_name": payload.get("delivery_name", ""),
            "recipient_phone": payload.get("delivery_phone", ""),
            "warehouse_ref": payload.get("delivery_data", {}).get("destination", {}).get("address", {}).get("geoObject", {}).get("id", ""),
            "shipping_date": ""
        },
        "marketing": {
            "utm_source": payload.get("utm_source", ""),
            "utm_medium": payload.get("utm_medium", ""),
            "utm_campaign": payload.get("utm_campaign", ""),
            "utm_term": payload.get("utm_term", ""),
            "utm_content": payload.get("utm_content", "")
        },
        "products": [
            {
                "sku": product.get("article", ""),
                "price": product.get("price", 0),
                "purchased_price": 0,
                "discount_percent": 0,
                "discount_amount": 0,
                "quantity": product.get("quantity", 0),
                "unit_type": "шт.",
                "name": product.get("title", ""),
                "comment": "product comment",
                "picture": f"https://cdn.shopify.com/s/files/1/0808/3800/0942/files/{product.get('article', '')}.jpg",
                "properties": [
                    {
                        "name": "",
                        "value": ""
                    }
                ]
            } for product in payload.get("products", [])
        ] + [
            {
                "sku": "1000001",
                "price": payload.get("dropshipping_details", {}).get("recipient_payment_price", 250),
                "purchased_price": 0,
                "discount_percent": 0,
                "discount_amount": payload.get("total_sum", 0),
                "quantity": 1,
                "unit_type": "шт",
                "name": "Dropshipping fee",
                "comment": "product comment 3",
                "picture": "https://cdn.shopify.com/s/files/1/0808/3800/0942/files/dropshipping-icon.jpg?v=1722782581"
            }
        ],
        "payments": [
            {
                "payment_method_id": 11,  # fixed value
                "payment_method": "Оплата карткою онлайн (Apple Pay, Google Pay)",
                "amount": payload.get("total_sum", 0),
                "description": "payment_description",  # fixed value
                "payment_date": payload.get("stat_created", ""),
                "status": "paid" if first_order.get("payed", 0) == 1 else "not_paid"

            }
        ]
    }
    logger.info("Payload transformed successfully.")
    return transformed

@app.put("/webhook")
async def upload_json(request: Request, file: UploadFile = File(None), data: str = Form(None), db: Session = Depends(database.get_db)):
    try:
        logger.info("Receiving JSON data...")

        if file:
            logger.info(f"File filename: {file.filename}")
            logger.info(f"File content_type: {file.content_type}")
            contents = await file.read()
            logger.info(f"File contents: {contents}")
            payload = json.loads(contents)
        elif data:
            logger.info(f"Form data: {data}")
            payload = json.loads(data)
        else:
            body = await request.body()
            logger.info(f"Raw body: {body}")
            payload = json.loads(body.decode('utf-8'))
        
        logger.info(f"Received payload: {payload}")

        # Сохранение полученных данных в файл
        with open(os.path.join(upload_directory, "received_webhook_order_data.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)
        logger.info("Received payload saved to JSON file successfully.")
        logger.info("=" * 50)  # Разделительная линия

        # Ждем три минуты
        logger.info("Waiting for 3 minutes before rechecking payment status...")
        time.sleep(60)

        # Получаем обновленные данные заказа
        token = global_token  # Используем сохраненный токен
        order_id = payload.get("order_id", "")
        order_data = get_order_from_horoshop(order_id, token)

        # Извлечение статуса оплаты из order_data
        orders = order_data.get('response', {}).get('orders', [])
        if not orders:
            raise HTTPException(status_code=400, detail="No orders found in the response.")

        first_order = orders[0]  # Берем первый заказ из списка
        payed_status = first_order.get("payed", 0)
        logger.info(f"Payed status from order_data: {payed_status}")

        # Используем payed_status для определения статуса оплаты
        payment_status = "paid" if payed_status == 1 else "not_paid"
        logger.info(f"Determined payment status: {payment_status}")

       # if order_data:
       #     # Обновляем статус оплаты на основании данных из Horoshop
       #     new_payment_status = order_data.get("payed", 0)
       #     if new_payment_status == 1:
       #         payload["payed"] = 1
       #     else:
       #         payload["payed"] = 0

        # Преобразование данных
        transformed_data = transform_payload(first_order, payload, db)

        # Сохранение преобразованных данных в другой файл
        with open(os.path.join(upload_directory, "transformed_webhook_order_data.json"), "w", encoding="utf-8") as f:
            json.dump(transformed_data, f, ensure_ascii=False, indent=4)
        logger.info("Transformed data saved to JSON file successfully.")
        logger.info("=" * 50)  # Разделительная линия

        # Отправка преобразованных данных на указанный URL
        url = "https://openapi.keycrm.app/v1/order"
        headers = {
            "Authorization": "Bearer MjQ1ZmE0Mzc2OTMyZWY4MjMxMzZiNmFlMDJhNzliNWM3ZWVlYTUzZQ",
            "Content-Type": "application/json"
        }
        response = requests.post(url, headers=headers, json=transformed_data)

        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Text: {response.text}")

        if response.status_code == 200 or response.status_code == 201:
            logger.info("Data successfully sent to KeyCRM API.")
        else:
            logger.error(f"Failed to send data to KeyCRM API. Status code: {response.status_code}, Response: {response.text}")
        logger.info("=" * 50)  # Разделительная линия

        return JSONResponse(status_code=200, content={
            "message": "JSON data received, transformed and sent successfully",
            "api_response": response.json()
        })
    except Exception as e:
        logger.error(f"Error occurred while processing JSON data: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# Создание таблиц
models.Base.metadata.create_all(bind=database.engine)

# Pydantic модель для входящих данных
class UserCreate(BaseModel):
    id: int
    email: str

class UserDelete(BaseModel):
    id: int
    email: str

@app.delete("/db_delete_user", response_model=UserDelete)
def delete_user(user: UserDelete, db: Session = Depends(database.get_db)):
    success = crud.delete_user(db=db, user_id=user.id, email=user.email)
    if success:
        return {"message": "User deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.post("/db_add_user", response_model=UserCreate)
def create_user(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = crud.create_user(db=db, user_id=user.id, email=user.email)
    return db_user


@app.middleware("http")
async def ignore_get_requests(request: Request, call_next):
    if request.method == "GET":
        return JSONResponse(status_code=405, content={"message": "Fuck you!!!!"})
    response = await call_next(request)
    return response
