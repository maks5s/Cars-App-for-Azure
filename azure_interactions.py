import os
from datetime import datetime, timedelta
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from fastapi import UploadFile
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

load_dotenv()
COSMOS_DB_URL = os.getenv("COSMOS_DB_URL")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")
DATABASE_NAME = "chinazesdb"
CONTAINER_NAME = "Cars"

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER_NAME = "fileupload"


def delete_file_from_container(blob_name: str):
    """Видаляє файл з контейнера Blob"""
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(AZURE_BLOB_CONTAINER_NAME)
    blob_client = container_client.get_blob_client(blob_name)
    print(blob_name)
    try:
        blob_client.delete_blob()
        print(f"Blob {blob_name} deleted successfully.")
    except Exception as e:
        print(f"Error deleting blob {blob_name}: {e}")


def upload_file_to_container(file: UploadFile, blob_name: str):
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(AZURE_BLOB_CONTAINER_NAME)
    blob_client = container_client.get_blob_client(blob_name)

    blob_client.upload_blob(file.file, overwrite=True)

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=AZURE_BLOB_CONTAINER_NAME,
        blob_name=blob_name,
        account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(days=100)
    )

    image_url = f"{blob_client.url}?{sas_token}"
    return image_url


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
        "fuel_type": car.fuel_type,
        "image_url": ""
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

    if "image_url" in car_data:
        car_doc["image_url"] = car_data["image_url"]

    container.replace_item(item=str(car_id), body=car_doc)


def get_fuel_type_from_cosmos(car_id):
    """Отримує значення fuel_type з Cosmos DB"""
    client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    car_doc = container.read_item(item=str(car_id), partition_key=str(car_id))
    return car_doc.get("fuel_type", "")