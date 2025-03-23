from datetime import datetime

from fastapi import FastAPI, Request, Depends, Form, status, HTTPException
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, delete
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
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

    return RedirectResponse(url=app.url_path_for("details", id=car.id), status_code=status.HTTP_303_SEE_OTHER)


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

    return templates.TemplateResponse(
        "details.html", {"request": request, "car": car_dict, "reviews": reviews}
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

    return RedirectResponse(url=app.url_path_for("index"), status_code=status.HTTP_303_SEE_OTHER)
