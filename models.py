import os
import typing
from datetime import datetime
from sqlmodel import Field, SQLModel, create_engine, Relationship
from dotenv import load_dotenv

load_dotenv()
sql_url = os.getenv("AZURE_POSTGRESQL_CONNECTIONSTRING")

engine = create_engine(sql_url)


def create_db_and_tables():
    return SQLModel.metadata.create_all(engine)


def drop_all():
    SQLModel.metadata.drop_all(engine)


class Car(SQLModel, table=True):
    id: typing.Optional[int] = Field(default=None, primary_key=True)
    brand: str = Field(max_length=50)
    model: str = Field(max_length=50)
    manufacture_year: int = Field()
    fuel_type: str = Field(max_length=50)

    reviews: typing.List["Review"] = Relationship(back_populates="car", cascade_delete=True)

    def __str__(self):
        return f"{self.brand}"


class Review(SQLModel, table=True):
    id: typing.Optional[int] = Field(default=None, primary_key=True)
    car_id: int = Field(foreign_key="car.id")
    user_name: str = Field(max_length=50)
    rating: typing.Optional[int]
    review_text: str = Field(max_length=500)
    review_date: datetime

    car: "Car" = Relationship(back_populates="reviews")

    def __str__(self):
        return f"{self.user_name}"
