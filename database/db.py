import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,declarative_base
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

connection = psycopg2.connect(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()