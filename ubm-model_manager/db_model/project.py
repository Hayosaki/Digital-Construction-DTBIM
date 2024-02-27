from sqlalchemy import Column, Integer, String, create_engine, cast, func, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.attributes import flag_modified
from db_model.common import ModelBase

Base = declarative_base(cls=ModelBase)
ValueType = Enum("int", "float", "string", "bool", name='FieldValueType')  # TODO: TO BE EXTEND


class Project(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False, default="anonymous")  # TODO: 实现/接入用户管理后，改为 USER ID
    template_id = Column(Integer)
    additional_field = Column(JSONB)
    cover_image = Column(String)

    def __str__(self):
        return f"Project <id={self.id}, name={self.name}>"


class Template(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)


class TemplateField(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, nullable=False)  # 字段名为field_key
    value_type = Column(ValueType, nullable=False)  # field_value_type
    template_id = Column(Integer)
