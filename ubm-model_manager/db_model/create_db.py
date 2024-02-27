from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy_utils import database_exists, create_database
from config import config
from config import logger

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# TODO: 这个东西应该是一个统一的环境变量，而不是在每个文件创建一次
user = config["pg"]["user"]
pwd = config["pg"]["password"]
host = config["pg"]["host"]
port = config["pg"]["port"]
db_name = config["pg"]["db_name"]
url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
logger.debug(f"db url: {url}")
engine = create_engine(url)


class DatabaseExistError(Exception):
    pass


def create_application_tables(engine):
    from db_model.slpk_model import Base
    logger.debug("start create project tables.")
    Base.metadata.create_all(engine)


def create_project_tables(engine):
    from db_model.project import Base
    logger.debug("start create project tables.")
    Base.metadata.create_all(engine)


def init_db():  # create project manager db
    db_name = config["pg"]["db_name"]
    if not database_exists(engine.url):
        create_database(engine.url)
        create_project_tables(engine)
        logger.info(f"create db '{db_name}' success.")
    else:
        logger.info(f"db '{db_name}' already exist, skip create.")


# 项目表用于存储项目信息，同时需要为每个项目创建数据库，项目分库管理
def create_db(db_name):
    user = config["pg"]["user"]
    pwd = config["pg"]["password"]
    host = config["pg"]["host"]
    port = config["pg"]["port"]
    url = f'postgresql://{user}:{pwd}@{host}:{port}/{db_name}'
    logger.debug(f"db url: {url}")
    engine = create_engine(url)
    if not database_exists(engine.url):
        create_database(engine.url)
        create_application_tables(engine)
        logger.info(f"create db '{db_name}' success.")
    else:
        logger.warning(f"db '{db_name}' already exist, skip create.")
    return engine


if __name__ == "__main__":
    init_db()
