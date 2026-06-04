from sqlalchemy import Column,Integer,String,DateTime
from sqlalchemy.sql import func
from database.db import Base

class Student(Base):

    __tablename__ = "students"

    id = Column(Integer,primary_key=True)
    roll_no = Column(String,unique=True,nullable=False)
    name = Column(String,nullable=False)
    department = Column(String,nullable=False)
    semester = Column(String,nullable=False)
    created_at = Column(DateTime(timezone=True),server_default=func.now())

# class Attendance(Base):
#     __tablename__ = "attendance"

#     id = Column(Integer,primary_key=True)
#     student_name = Column(String,nullable=False)
#     timestamp = Column(DateTime(timezone=True),server_default=func.now())
#     # session_id   = Column(String)
#     present      = Column(Integer, default=1)