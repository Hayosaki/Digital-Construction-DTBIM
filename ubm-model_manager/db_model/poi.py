from sqlalchemy import Column, Integer, String, create_engine, cast, func, DateTime, Enum, DECIMAL, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.attributes import flag_modified
from db_model.common import ModelBase

Base = declarative_base(cls=ModelBase)
ValueType = Enum("int", "float", "string", "bool", name='FieldValueType')  # TODO: TO BE EXTEND


class PoiTemplate(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)


class PoiTemplateField(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, nullable=False)
    value_type = Column(ValueType, nullable=False)
    template_id = Column(Integer)


class Poi(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    additional_field = Column(JSONB)
    template_id = Column(Integer)
    position = Column(ARRAY(DECIMAL(25, 9)), nullable=False, default=[0, 0, 0])
    target_application = Column(Integer, nullable=False)
    target_model = Column(Integer, nullable=False)
