import os

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

# ✅ Carga el archivo .env que contiene DATABASE_URL
load_dotenv()

# ✅ Función para obtener la hora de México
def mexico_now():
    return datetime.now(pytz.timezone("America/Mexico_City"))

# ✅ URL de la base de datos obtenida del entorno
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Crear el motor de SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ✅ MODELOS
class Quote(Base):
    __tablename__ = "quotes"
    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, index=True)
    date = Column(DateTime, default=mexico_now)

    client_name = Column(String)
    client_company = Column(String, nullable=True)
    client_email = Column(String, nullable=True)
    client_phone = Column(String, nullable=True)
    client_address = Column(String, nullable=True)

    currency = Column(String, default="MXN")
    tax_rate = Column(Float, default=0)
    discount_rate = Column(Float, default=0)
    notes = Column(String, nullable=True)

    validity = Column(String, nullable=True)
    payment_terms = Column(String, nullable=True)
    warranty = Column(String, nullable=True)

    subtotal = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    total = Column(Float, default=0)
    status = Column(String(50), nullable=True) 

    items = relationship("Item", back_populates="quote", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"))
    description = Column(String)
    quantity = Column(Float, default=1)
    unit = Column(String, nullable=True)
    unit_price = Column(Float, default=0)
    amount = Column(Float, default=0)
    quote = relationship("Quote", back_populates="items")

class Settings(Base):
    __tablename__ = "settings"  # ✅ se recomienda nombres en minúsculas
    id = Column(Integer, primary_key=True, index=True)
    business_name = Column(String, default="Tu empresa aquí")
    rfc_phone_email = Column(String, default="RFC / Teléfono / Email")
    address = Column(String, default="Dirección")

# ✅ Esto debes ejecutarlo solo una vez para crear las tablas
# Base.metadata.create_all(bind=engine)
