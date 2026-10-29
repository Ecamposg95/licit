from sqlalchemy import JSON, Column, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import OrgScoped


class Product(OrgScoped, Base):
    __tablename__ = "products"

    name = Column(String(255), nullable=False)
    family = Column(String(100), nullable=False, index=True)
    brand = Column(String(255))
    manufacturer = Column(String(255))        # fabricante declarado
    description = Column(Text)
    data_kind = Column(String(12), nullable=False, index=True)
    review_status = Column(String(20), nullable=False, default="pendiente")
    line = Column(String(80))
    subfamily = Column(String(200))
    external_ref = Column(String(200), index=True)       # id de la ficha en el catálogo de origen
    source_url = Column(String(1000))
    checked_on = Column(Date)
    attribution = Column(String(255))
    images = Column(JSON, nullable=False, default=list)
    features = Column(JSON, nullable=False, default=list)
    data_quality_notes = Column(JSON, nullable=False, default=list)
    # Atributos de la ficha, cada uno {value, unit, source_text} con la cita literal de la página.
    attributes = Column(JSON, nullable=False, default=dict, server_default="{}")

    variants = relationship("Variant", back_populates="product", cascade="all, delete-orphan",
                            order_by="Variant.sku", lazy="selectin")


class Variant(OrgScoped, Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("organization_id", "sku"),)

    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(60), nullable=False)
    name = Column(String(255), nullable=False)
    # Atributos técnicos; null = no declarado (nunca se infiere del nombre comercial).
    attributes = Column(JSON, nullable=False, default=dict)
    unit = Column(String(30), nullable=False)
    price = Column(Numeric(14, 2))
    currency = Column(String(3))
    stock_demo = Column(Integer)
    regulatory_reference = Column(String(120))
    data_kind = Column(String(12), nullable=False, index=True)
    review_status = Column(String(20), nullable=False, default="pendiente")
    side = Column(String(20))                            # izquierda | derecha | null
    source_text = Column(Text)
    field_provenance = Column(JSON, nullable=False, default=dict)

    product = relationship("Product", back_populates="variants")
