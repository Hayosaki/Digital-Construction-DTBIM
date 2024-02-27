from functools import partial

from config import logger

from fastapi import APIRouter, Depends, HTTPException, Response
from db_manager.project_manager import get_applications_from_all_project, get_applications
from db_model.common import SessionDispatcher, search_all_in_db
from db_model.project import Project
from db_model.slpk_model import Model, ModelFile

from dependence import get_authorization_header
from utils.common import split_page

router = APIRouter(
    prefix="/global",
    tags=["global scope"],
    # dependencies=[Depends(get_authorization_header)],   # 文档不能自动添加 header故先注释
    responses={404: {"description": "Not found"}},
)


@router.get("/application")
async def get_all_application(application_name: str = None, page_size: int = 10, page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    从所有项目中获取所有application，传入application_name将进行查询

    - application_name: 应用名
    - page_size:  分页大小
    - page_num:  第几页，从1开始
    """
    applications = get_applications_from_all_project()
    if application_name:
        applications = list(filter(lambda app: application_name in app.name, applications))  # TODO: FIX ME

    total, res = split_page(list(applications), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.get("/projects/tree")
async def get_project_tree(sort_by: str = "create_time", desc: bool = True):
    """
    获取`项目`-`应用`的树状结构
    """
    session = SessionDispatcher().get_session()
    res = []
    for project in search_all_in_db(session, Project):
        s = SessionDispatcher().get_session(f"proj_{project.id}")
        d = project.__dict__
        temp = get_applications(s)
        d["applications"] = sorted(temp, key=lambda x: x.__dict__[sort_by], reverse=desc)
        res.append(d)
        s.remove()
    session.remove()
    res = sorted(res, key=lambda x: x[sort_by], reverse=desc)
    return {
        "code": 200,
        "data": res,
    }


@router.get("/model")
async def get_all_model(page_size: int = 10, page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    获取所有模型
    """
    session = SessionDispatcher().get_session()
    res = []
    for project in search_all_in_db(session, Project):
        s = SessionDispatcher().get_session(f"proj_{project.id}")
        models = search_all_in_db(s, Model)
        models = map(partial(add_project_id_to_record, project.id), models)
        res.extend(models)
        s.remove()
    session.remove()
    total, res = split_page(list(res), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.get("/model-file")
async def get_all_modelfile(page_size: int = 10, page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    获取所有模型文件
    """
    session = SessionDispatcher().get_session()
    res = []
    for project in search_all_in_db(session, Project):
        s = SessionDispatcher().get_session(f"proj_{project.id}")
        models = search_all_in_db(s, ModelFile)
        models = map(partial(add_project_id_to_record, project.id), models)
        res.extend(models)
        s.remove()
    session.remove()
    total, res = split_page(list(res), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


def add_project_id_to_record(project_id, record):
    res = record.__dict__
    res["project_id"] = project_id
    return res
