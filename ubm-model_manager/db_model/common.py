import asyncio
import os
import re
import threading
from typing import List
from sqlalchemy import (
    Column,
    String,
    DateTime,
    func,
    create_engine,
    MetaData,
    Table,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy_utils import database_exists
from config import config
from config import logger


# TODO: 改成异步形式
# user = config["pg"]["user"]
# pwd = config["pg"]["password"]
# host = config["pg"]["host"]
# port = config["pg"]["port"]
# db_name = config["pg"]["db_name"]
# url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
# logger.debug(f"db url: {url}")
# engine = create_engine(url)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# session = SessionLocal()


def synchronized(func):
    func.__lock__ = threading.Lock()

    def lock_func(*args, **kwargs):
        with func.__lock__:
            return func(*args, **kwargs)

    return lock_func


class SessionDispatcher:
    port = None
    host = None
    pwd = None
    user = None
    instance = None
    session_mapper = dict()
    lock = asyncio.Lock()

    @synchronized
    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
            cls.instance.init()
        return cls.instance

    @classmethod
    @synchronized
    async def get_instance(cls):
        if cls.instance is None:
            async with cls.lock:
                if cls.instance is None:
                    cls.instance = super().__new__(cls)
                    cls.instance.init()
        return cls.instance

    # @synchronized
    @classmethod
    def init(cls):
        from db_model.project import Project
        cls.user = config["pg"]["user"]
        cls.pwd = config["pg"]["password"]
        cls.host = config["pg"]["host"]
        cls.port = config["pg"]["port"]
        cls.add_session(config["pg"]["db_name"])
        # add exist db in session map
        session = cls.get_session(config["pg"]["db_name"])
        projects = session.query(Project).all()
        for p in projects:
            cls.add_session(f"proj_{p.id}")

    # @synchronized
    @classmethod
    def add_session(cls, db_name):
        # print(f"call from add_session(),added by session: {cls.instance}")
        url = f"postgresql://{cls.user}:{cls.pwd}@{cls.host}:{cls.port}/{db_name}"
        logger.debug(f"db adder: {url}")
        engine = create_engine(url, pool_size=100)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = scoped_session(SessionLocal)
        cls.session_mapper[db_name] = SessionLocal
        # self.session_mapper[db_name] = session

    # @synchronized
    @classmethod
    def get_session(cls, db_name=config["pg"]["db_name"]):
        # print(f"call from add_session(),got by session: {cls.instance}")
        if db_name not in cls.session_mapper:
            if database_exists(f"postgresql://{cls.user}:{cls.pwd}@{cls.host}:{cls.port}/{db_name}"):
                cls.add_session(db_name)
            else:
                raise OperationalError(f"Database '{db_name}' does not exist.", params={}, orig=None)
        # return self.session_mapper[db_name]
        return scoped_session(cls.session_mapper[db_name])


class ModelBase:
    @declared_attr
    def __tablename__(self):
        snake_case = re.sub(r"(?P<key>[A-Z])", r"_\g<key>", self.__name__)
        return snake_case.lower().strip("_")

    create_by = Column(String, nullable=False, default="anonymous")
    create_time = Column(DateTime, nullable=False, server_default=func.now())
    update_by = Column(String, nullable=False, default="anonymous")
    update_time = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


def create_record_in_db(session, db_model, autocommit: bool, **kvargs):
    # sd = SessionDispatcher()
    # session = sd.get_session(db_name)
    record = db_model(**kvargs)
    session.add(record)
    # session.flush()
    if autocommit:
        session.commit()
    else:
        session.flush()
    logger.debug(f"create record success: {db_model.__tablename__} | {record} {record.id}")
    return record


def create_records_in_db(session, db_model, autocommit: bool, keys, values):
    assert len(keys) > 0
    assert len(values) > 0
    assert all(map(lambda l: len(l) == len(keys), values))
    # sd = SessionDispatcher()
    # session = sd.get_session(db_name)
    record_id = []
    for row_v in values:
        t = dict(zip(keys, row_v))
        record = db_model(**t)
        session.add(record)
        record_id.append(record)
    # session.flush()
    if autocommit:
        session.commit()
    else:
        session.flush()
    # record_id = list(map(lambda i: i.id, record_id))
    logger.debug(f"create record success: {db_model.__tablename__} | {record_id}")
    return record_id


def search_one_in_db(session, db_model, **kvargs):
    # sd = SessionDispatcher()
    # session = sd.get_session(db_name)
    return session.query(db_model).filter_by(**kvargs).first()


def search_one_in_db_by_filter(session, db_model, **kvargs):
    # sd = SessionDispatcher()
    # session = sd.get_session(db_name)
    return session.query(db_model).filter_by(**kvargs).all()


def search_all_in_db(session, db_model):
    # sd = SessionDispatcher()
    # session = sd.get_session(db_name)
    return session.query(db_model).all()


def search_all_by_name(session, db_model, name):
    assert hasattr(db_model, "name")
    res = session.query(db_model).filter(db_model.name.like(f'%{name}%')).all()
    return res


def search_all_by_id_list(session, db_model, id_list):
    assert hasattr(db_model, "id")
    res = session.query(db_model).filter(db_model.id.in_(id_list)).all()
    return res


def update_one_in_db(session, record, autocommit: bool, **kvargs):
    # sd = SessionDispatcher()
    # session = sd.get_session(db_name)

    def filter_func(item):
        # print(record.__dict__)
        if item[1] and item[0] in record.__dict__:
            return True
        # print(item)

    # print(kvargs.items())
    res = dict(filter(filter_func, kvargs.items()))
    # print(record, res)
    for k, v in res.items():
        setattr(record, k, v)
    session.add(record)
    if autocommit:
        session.commit()
    logger.debug(f"update record `{record}` success.")


def create(Model, **kvargs):
    p = Model(**kvargs)
    sd = SessionDispatcher()
    session = sd.get_session()
    session.add(p)
    session.commit()
    logger.debug(f"create record success: {Model.__tablename__} | {p}")
    return p


def update(record, **kvargs):
    def filter_func(item):
        if item[1] and item[0] in record.__dict__:
            return True

    res = dict(filter(filter_func, kvargs.items()))
    for k, v in res.items():
        setattr(record, k, v)

    sd = SessionDispatcher()
    session = sd.get_session()
    session.add(record)
    session.commit()
    session.remove()
    logger.debug(f"update record `{record}` success.")


# TODO: 支持filter用法，支持 and or 语法
def search_one(Model, **kvargs):
    sd = SessionDispatcher()
    session = sd.get_session()
    res = session.query(Model).filter_by(**kvargs).first()
    session.remove()
    return res


def search_all(Model, **kvargs):
    pass


def delete(Model, **kvargs):
    pass


def create_node_table(db_name, table_name):
    user = config["pg"]["user"]
    pwd = config["pg"]["password"]
    host = config["pg"]["host"]
    port = config["pg"]["port"]
    url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
    engine = create_engine(url)
    meta = MetaData()
    table_name = Table(
        table_name,
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("node_index", Integer),
        Column("version", Integer),
        Column("material_ids", ARRAY(Integer)),
        Column("category_id", Integer),
        Column("attribute", JSONB),
        Column("custom_attribute", JSONB),
        Column("old_version_list", ARRAY(Integer)),
        Column("create_by", String, nullable=False, server_default="anonymous"),
        Column("create_time", DateTime, nullable=False, server_default=func.now()),
        Column("update_by", String, nullable=False, server_default="anonymous"),
        Column("update_time", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    )
    meta.create_all(engine)
    logger.debug(f"create table `{table_name}` in `{db_name}` success.")


def create_records_reflect(db_name, table_name, data):
    user = config["pg"]["user"]
    pwd = config["pg"]["password"]
    host = config["pg"]["host"]
    port = config["pg"]["port"]
    url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
    engine = create_engine(url)
    conn = engine.connect()
    meta = MetaData(engine)
    table = Table(table_name, meta, autoload=True, autoload_with=engine)
    ins = table.insert()
    conn.execute(ins, data)


def search_record_reflect(db_name, table_name, search_one=True, **filter_by):
    user = config["pg"]["user"]
    pwd = config["pg"]["password"]
    host = config["pg"]["host"]
    port = config["pg"]["port"]
    url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
    engine = create_engine(url)
    meta = MetaData(engine)
    table = Table(table_name, meta, autoload=True, autoload_with=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    if search_one:
        result = session.query(table).filter_by(**filter_by).first()
    else:
        result = session.query(table).filter_by(**filter_by).all()
    session.close()
    # return list(map(row_to_dict, result))
    return result


def update_record_reflect(db_name, table_name, data, **filter_by):
    """
    根据条件查询并更新数据，需要保证查询条件返回结果唯一，即只更新一条记录
    :param db_name:
    :param table_name:
    :param data:
    :param filter_by:
    :return:
    """
    user = config["pg"]["user"]
    pwd = config["pg"]["password"]
    host = config["pg"]["host"]
    port = config["pg"]["port"]
    url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
    engine = create_engine(url)
    meta = MetaData(engine)
    table = Table(table_name, meta, autoload=True, autoload_with=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    record = session.query(table).filter_by(**filter_by)

    def filter_func(item):
        # print(record.__dict__)
        if item[1] and item[0] in record.one()._asdict():
            return True

    data = dict(filter(filter_func, data.items()))
    record.update(data)
    # session.add(record)
    session.commit()
    session.close()


def attribute_encode(attribute_id: int, values: List[str], byte_counts: List[int]):
    count = len(byte_counts)
    binary_response: List[bytes] = []
    if attribute_id != 0:
        size = sum(byte_counts)
        binary_response.append(count.to_bytes(4, "little", signed=False))
        binary_response.append(size.to_bytes(4, "little", signed=False))
        for byte_count in byte_counts:
            binary_byte_count = byte_count.to_bytes(4, "little", signed=False)
            binary_response.append(binary_byte_count)
        for value in values:
            if value is not None:
                binary_response.append(value.encode())
            binary_response.append(0x00.to_bytes(1, "little", signed=False))
    elif attribute_id == 0:
        binary_response.append(count.to_bytes(4, "little", signed=False))
        values: List[int]
        for value in values:
            binary_response.append(value.to_bytes(4, "little", signed=False))
    content_length = 0
    for i in binary_response:
        content_length += i.__len__()
    return binary_response


if __name__ == "__main__":  # for test
    from db_model.slpk_model import ModelFile

    # r = search_record_reflect("proj_1", "1_0_NODE_VERSION", id=1)
    # print(r)
    update_record_reflect("proj_1", "1_0_NODE_VERSION", {"version": 12}, id=1)

    # r = search_one(Project, id=1)
    # update(r, name="", owner="")
    # update(r, name="", goodbye="asdsdf")
    # update(r, name="heheheheh", goodbye="asdsdf")
    # create_table("proj_2", "test_table_name1")
    # SessionDispatcher()
    # SessionDispatcher()
    # SessionDispatcher()
    # print(search_all_in_db("proj_1", Model))
    # session = SessionDispatcher().get_session("proj_1")
    # ids = create_records_in_db(session, SublayerVersion, True, ["sublayer_index", "model_file_id"], [[66, 2]])
    # ids = list(map(lambda i: i.id, ids))
    # print(ids)
    # session = SessionDispatcher().get_session("proj_1")
    # mf = search_one_in_db(session, MetaVersion, id=1)
    # update_one_in_db(session, mf, False, meta={"fuck": "test"})
    # session.commit()
    # print(create_record_in_db("proj_1", Model, name="sss"))
    # t = search_one_in_db("slpk_local", Template, id=2)
    # update_one_in_db("slpk_local", t, name="aaaaaaa")

    # model = search_one_in_db(f"proj_1", Model, id=2)
    # update_one_in_db(f"proj_1", model, current_model_file_id="6")
    # create_node_records("proj_1", "1_0_NODE_VERSION", [{
    #     "node_index": 0,
    #     "attribute": {"aa": 11},
    #     "create_by": "me",
    #     "update_by": "me"
    # }])
    # mf = search_one_in_db(f"proj_1", ModelFile, id=14)
    # print(mf.__dict__)
    # record_id = create_record_in_db(f"proj_1", LayerVersion, layer={})
    # print(mf.__dict__)
    # print(record_id, type(record_id))
    # update_one_in_db(f"proj_1", mf, layer_version_id=record_id)
    # update_one_in_db_tmp((f"proj_1", ModelFile, {"id": 14}), f"proj_1", layer_version_id=record_id)
