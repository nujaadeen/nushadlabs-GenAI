"""
db.py — SQLAlchemy connection layer for the ERP PostgreSQL database.

Connection string is read from the DATABASE_URL environment variable:
    export DATABASE_URL="postgresql://erp_user:erp_pass@localhost:5432/erp_db"

The default value matches the docker-compose.yml credentials so the prototype
works out of the box with no configuration.
"""

import os

from sqlalchemy import Column, DateTime, Integer, Numeric, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://erp_user:erp_pass@localhost:5433/erp_db",
)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id           = Column(Integer, primary_key=True)
    tenant_id    = Column(Integer, nullable=False)
    name         = Column(Text, nullable=False)
    description  = Column(Text, nullable=False, default="")
    price        = Column(Numeric(10, 2), nullable=False)
    discount_pct = Column(Numeric(5, 2), nullable=False, default=0)
    category     = Column(Text, nullable=False, default="")
    created_at   = Column(DateTime(timezone=True), nullable=False)
    updated_at   = Column(DateTime(timezone=True), nullable=False)
    demand_score = Column(Numeric(4, 2), nullable=False, default=0)
    stock        = Column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Product id={self.id} tenant={self.tenant_id} name={self.name!r}>"


def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def get_session_factory(engine=None) -> sessionmaker:
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
