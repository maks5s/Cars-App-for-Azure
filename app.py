import os
from datetime import datetime

import requests
from fastapi import FastAPI, Request, Depends, Form, status, HTTPException
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, delete
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from cosmosdb import save_to_cosmos, delete_from_cosmos, update_cosmos, get_fuel_type_from_cosmos
from models import create_db_and_tables, drop_all, engine, Car, Review
from sqlalchemy.sql import func


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
    # drop_all()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.globals["url_for"] = app.url_path_for


def get_db_session():
    with Session(engine) as session:
        yield session


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: Session = Depends(get_db_session)):
    statement = (
        select(Car, func.avg(Review.rating).label("avg_rating"), func.count(Review.id).label("review_count"))
        .outerjoin(Review, Review.car_id == Car.id)
        .group_by(Car.id)
    )
    results = session.exec(statement).all()

    cars = []
    for car, avg_rating, review_count in results:
        car_dict = car.dict()
        car_dict["avg_rating"] = avg_rating
        car_dict["review_count"] = review_count
        car_dict["stars_percent"] = round((float(avg_rating) / 5.0) * 100) if review_count > 0 else 0
        cars.append(car_dict)

    return templates.TemplateResponse("index.html", {"request": request, "cars": cars})


@app.get("/create", response_class=HTMLResponse)
async def create_car(request: Request):
    return templates.TemplateResponse("create_car.html", {"request": request})


@app.post("/add", response_class=RedirectResponse)
async def add_car(
    request: Request, brand_name: str = Form(...), model: str = Form(...), manufacture_year: int = Form(...), fuel_type: str = Form(...),
    session: Session = Depends(get_db_session)
):
    car = Car()
    car.brand = brand_name
    car.model = model
    car.manufacture_year = int(manufacture_year)
    car.fuel_type = fuel_type
    session.add(car)
    session.commit()
    session.refresh(car)

    # Записуємо машину у Cosmos DB
    try:
        save_to_cosmos(car)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cosmos DB error: {e}")

    # Викликаємо Azure Function для отримання повідомлення
    azure_function_url = os.getenv("AZURE_FUNCTION_URL")
    params = {"brand": car.brand, "model": car.model, "year": car.manufacture_year, "fuel": car.fuel_type}
    try:
        response = requests.get(azure_function_url, params=params)
        response.raise_for_status()  # Перевірка на помилки
        message = response.json().get("message", "")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Azure Function error: {e}")

    return RedirectResponse(
        url=app.url_path_for("details", id=car.id) + f"?message={message}",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.get("/details/{id}", response_class=HTMLResponse)
async def details(request: Request, id: int, session: Session = Depends(get_db_session)):
    car = session.exec(select(Car).where(Car.id == id)).first()
    reviews = session.exec(select(Review).where(Review.car_id == id)).all()

    review_count = len(reviews)

    avg_rating = 0
    if review_count > 0:
        avg_rating = sum(review.rating for review in reviews if review.rating is not None) / review_count

    car_dict = car.dict()
    car_dict["avg_rating"] = avg_rating
    car_dict["review_count"] = review_count
    car_dict["stars_percent"] = round((float(avg_rating) / 5.0) * 100) if review_count > 0 else 0
    car_dict["brand_model"] = car.brand + " " + car.model

    # Отримуємо fuel_type із Cosmos DB
    try:
        car_dict["fuel_type"] = get_fuel_type_from_cosmos(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cosmos DB fetch error: {e}")

    message = request.query_params.get("message", "")

    return templates.TemplateResponse(
        "details.html", {"request": request, "car": car_dict, "reviews": reviews, "message": message}
    )


@app.post("/review/{id}", response_class=RedirectResponse)
async def add_review(
    request: Request,
    id: int,
    user_name: str = Form(...),
    rating: str = Form(...),
    review_text: str = Form(...),
    session: Session = Depends(get_db_session),
):
    review = Review()
    review.car_id = id
    review.review_date = datetime.now()
    review.user_name = user_name
    review.rating = int(rating)
    review.review_text = review_text
    session.add(review)
    session.commit()

    return RedirectResponse(url=app.url_path_for("details", id=id), status_code=status.HTTP_303_SEE_OTHER)


@app.delete("/delete_car/{id}", response_class=RedirectResponse)
async def delete_car(id: int, session: Session = Depends(get_db_session)):
    car = session.exec(select(Car).where(Car.id == id)).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    session.delete(car)
    session.commit()

    # Видаляємо авто з Cosmos DB
    try:
        delete_from_cosmos(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cosmos DB delete error: {e}")

    return RedirectResponse(url=app.url_path_for("index"), status_code=status.HTTP_303_SEE_OTHER)



@app.delete("/delete_review/{review_id}", response_class=RedirectResponse)
async def delete_review(review_id: int, session: Session = Depends(get_db_session)):
    review = session.exec(select(Review).where(Review.id == review_id)).first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    session.delete(review)
    session.commit()

    return RedirectResponse(url=app.url_path_for("details", id=review.car_id), status_code=status.HTTP_303_SEE_OTHER)


@app.put("/edit_car/{id}", response_class=RedirectResponse)
async def edit_car(id: int, car_data: dict, session: Session = Depends(get_db_session)):
    car = session.exec(select(Car).where(Car.id == id)).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    car.brand = car_data['brand_name']
    car.model = car_data['model']
    car.manufacture_year = car_data['manufacture_year']
    car.fuel_type = car_data['fuel_type']
    session.commit()

    # Оновлюємо авто в Cosmos DB
    try:
        update_cosmos(id, car_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cosmos DB update error: {e}")

    return RedirectResponse(url=app.url_path_for("index"), status_code=status.HTTP_303_SEE_OTHER)
