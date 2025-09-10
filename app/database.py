from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from decouple import config

DATABASE_URL = f"postgresql://{config('DB_USER')}:{config('DB_PASS')}@{config('DB_HOST')}:{config('DB_PORT')}/{config('DB_NAME')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
