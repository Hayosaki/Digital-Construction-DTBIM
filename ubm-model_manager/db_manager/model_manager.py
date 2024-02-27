"""
为slpk文件提供增删改查的支持函数
"""

from aiohttp import FormData, ClientSession
from celery import Celery

from config import logger, config

from db_model.common import create_record_in_db, search_one_in_db, SessionDispatcher, update_one_in_db
from db_model.slpk_model import Model, ModelFile


celery_app = Celery("celery_app",
                    broker=config["celery"]["broker"],
                    backend=config["celery"]["backend"])
session_dispatcher = SessionDispatcher.get_instance()


def create_model_in_project(
        project_id: int,
        new_record: dict
) -> dict:
    # do some check
    pass

    def filter_func(item):
        if item[1] and item[0] in Model.__dict__:
            return True

    new_record = dict(filter(filter_func, new_record.items()))
    sd = SessionDispatcher()
    session = sd.get_session(f"proj_{project_id}")
    res = create_record_in_db(session, Model, True, **new_record)
    return res


def update_model_in_project(
        project_id: int,
        m_id: int,
        new_record: dict
) -> Model:

    sd = SessionDispatcher()
    session = sd.get_session(f"proj_{project_id}")
    model = search_one_in_db(session, Model, id=m_id)
    assert model

    def filter_func(item):
        if item[1] and item[0] in Model.__dict__:
            return True

    new_record = dict(filter(filter_func, new_record.items()))

    for k, v in new_record.items():
        setattr(model, k, v)

    session.add(model)
    session.commit()
    logger.debug(f"update model `{model.name}` success")
    return model


def create_model_file_in_project(
        project_id: int,
        new_record: dict
):

    def filter_func(item):
        if item[1] and item[0] in ModelFile.__dict__:
            return True

    sd = SessionDispatcher()
    session = sd.get_session(f"proj_{project_id}")
    new_record = dict(filter(filter_func, new_record.items()))
    record = create_record_in_db(session, ModelFile, True, **new_record)
    new_record["id"] = record.id
    return new_record


def get_uuid_from_mf(project_id: int, model_file_id: int) -> str:
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    mf = search_one_in_db(session, ModelFile, id=model_file_id)
    slpk_uuid = mf.uuid
    session.close()
    return slpk_uuid


async def upload_file_by_aiohttp(project_id: int, mf_id: int, url: str, data: FormData, headers: dict = None):
    async with ClientSession() as session:
        async with session.post(url, data=data, headers=headers) as response:
            print(await response.text())
            s = SessionDispatcher().get_session(f"proj_{project_id}")
            update_one_in_db(s, search_one_in_db(s, ModelFile, id=mf_id), True, state="created")
            return response.status


if __name__ == "__main__":
    # create_model_in_project(1, {
    #     "name": "hhh",
    #     "ddsf": "asdfgag",
    #     "version": 22,
    #     "current_model_file_id": 12,
    #     "app_id_list": [1, 2, 3]})
    update_model_in_project(1, 6, {"name": "xxxx", "ddsf": "asdfgag", "version": 34})
