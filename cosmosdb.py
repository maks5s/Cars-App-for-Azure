import os
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

load_dotenv()
COSMOS_DB_URL = os.getenv("COSMOS_DB_URL")  # URI Cosmos DB
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")  # Primary Key
DATABASE_NAME = "chinazesdb"
CONTAINER_NAME = "Cars"


def save_to_cosmos(car):
    """Зберігає інформацію про машину у Cosmos DB"""
    client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    car_doc = {
        "id": str(car.id),  # ID у Cosmos DB має бути str
        "brand": car.brand,
        "model": car.model,
        "manufacture_year": car.manufacture_year,
        "fuel_type": car.fuel_type
    }

    container.create_item(body=car_doc)


def delete_from_cosmos(car_id):
    """Видаляє машину з Cosmos DB"""
    client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    container.delete_item(item=str(car_id), partition_key=str(car_id))


def update_cosmos(car_id, car_data):
    """Оновлює дані машини в Cosmos DB"""
    client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    car_doc = container.read_item(item=str(car_id), partition_key=str(car_id))
    # car_doc.update(car_data)
    car_doc["brand"] = car_data["brand_name"]
    car_doc["model"] = car_data["model"]
    car_doc["manufacture_year"] = car_data["manufacture_year"]
    car_doc["fuel_type"] = car_data["fuel_type"]

    container.replace_item(item=str(car_id), body=car_doc)


def get_fuel_type_from_cosmos(car_id):
    """Отримує значення fuel_type з Cosmos DB"""
    client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    car_doc = container.read_item(item=str(car_id), partition_key=str(car_id))
    return car_doc.get("fuel_type", "")