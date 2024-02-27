from sqlalchemy import (
    Column,
    Integer,
    String,
    create_engine,
    cast,
    func,
    DateTime,
    Enum,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.declarative import declared_attr
from .common import ModelBase

Base = declarative_base(cls=ModelBase)
ValueType = Enum(
    "int", "float", "string", "bool", name="FieldValueType"
)  # TODO: TO BE EXTEND


# class ApplicationTemplate(Base):
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     name = Column(String, nullable=False)
#
#
# class ApplicationTemplateField(Base):
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     key = Column(String, nullable=False)
#     value_type = Column(ValueType, nullable=False)
#     template_id = Column(Integer)


class Application(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    plugin_list = Column(ARRAY(Integer))
    additional_field = Column(JSONB)
    template_id = Column(Integer)
    model_id_list = Column(ARRAY(Integer))


class Plugin(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin_path = Column(String, nullable=False)


class Model(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="未命名模型")
    version = Column(Integer, default=1)
    current_model_file_id = Column(Integer)
    app_id_list = Column(ARRAY(Integer))

    def __repr__(self):
        return f"<Model id={self.id} name={self.name}>"


class ModelFile(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    origin_file_path = Column(String)
    origin_file_name = Column(String)
    origin_file_type = Column(String)
    origin_file_size = Column(Integer)  # 单位 bytes
    name = Column(String, nullable=False)
    # version = Column(Integer, default=1)
    model_id = Column(Integer)
    slpk_path = Column(String)
    duration = Column(Integer)
    state = Column(String, nullable=False)
    use_lod = Column(Boolean, nullable=False, default=False)
    tmp_file_size = Column(Integer)
    tmp_file_path = Column(String)
    uuid = Column(String, nullable=False)
    # app_id_list = Column(ARRAY(Integer))
    meta_version_id = Column(Integer)
    layer_version_id = Column(Integer)
    sublayer_version_id = Column(ARRAY(Integer))
    material_attribute_version_id_list = Column(ARRAY(Integer))


class MaterialAttributeVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    attribute = Column(JSONB)
    old_version_list = Column(ARRAY(Integer))


class MetaVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    meta = Column(JSONB)
    old_version_list = Column(ARRAY(Integer))


class LayerVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    layer = Column(JSONB)
    old_version_list = Column(ARRAY(Integer))


class SublayerVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    sublayer_index = Column(Integer)
    model_file_id = Column(Integer)
    nodepage_version_id = Column(Integer)
    sublayer_version_id = Column(Integer)
    sublayer_meta_version_id = Column(Integer)
    __table_args__ = (UniqueConstraint("model_file_id", "sublayer_index"),)  # 联合唯一


class SublayerMetaVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    meta = Column(JSONB)
    old_version_list = Column(ARRAY(Integer))


class NodepageVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    nodepage = Column(JSONB)
    old_version_list = Column(ARRAY(Integer))


class SublayerInfoVersion(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, default=1)
    sublayer = Column(JSONB)  # 子层的数据
    old_version_list = Column(ARRAY(Integer))
    sublayer_attribute = Column(JSONB)
