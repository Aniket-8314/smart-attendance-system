"""Initialize or upgrade the Smart Attendance database."""

from database import models
from database.db import engine
from database.schema import initialize_database

if __name__ == "__main__":
    initialize_database(engine, models.Base)
    print("Database initialized successfully")
