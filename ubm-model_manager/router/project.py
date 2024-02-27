from config import logger
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, HttpUrl

from db_manager import project_manager
from db_manager.project_manager import get_project_by_id, get_project_by_name, get_template_by_id, \
    get_application_by_id, get_applications, get_applications_from_all_project
from db_model.common import update, SessionDispatcher, search_all_in_db, search_one_in_db, update_one_in_db
from db_model.project import Project
from db_model.slpk_model import Model

from dependence import get_authorization_header
from utils.common import split_page

router = APIRouter(
    prefix="/project",
    tags=["project"],
    # dependencies=[Depends(get_authorization_header)],   # 文档不能自动添加 header故先注释
    responses={404: {"description": "Not found"}},
)


class RProject(BaseModel):
    name: str = "未命名项目"
    template_id: int = None
    additional_field: dict = None
    image_url: HttpUrl = None
    owner: str = None

    class Config:
        schema_extra = {
            "example": {
                "name": ""
            }
        }


class RApplication(BaseModel):
    name: str
    # project_id: int
    template_id: int = None
    additional_field: dict = None
    plugin_list: List[int] = None
    model_id_list: List[int] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "",
                # "project_id": 0
            }
        }


class RTemplateField(BaseModel):
    key: str
    value_type: str


class RTemplate(BaseModel):
    name: str
    field_list: List[RTemplateField]

    class Config:
        schema_extra = {
            "example": {
                "field_list": []
            }
        }


@router.get("/")
@router.get("/{project_id}")
async def get_project(project_id: int = None, project_name: str = None, page_size: int = 10, page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    获取项目列表，如果传入query参数则根据参数筛选，同时也支持路径参数

    可以使用的参数列表，一下参数只能选择其一：
    - project_id
    - project_name

    以下参数用来设置分页：
    - page_size 分页大小
    - page_num  第几页
    **已完成**
    """
    if project_id and project_name:
        raise HTTPException(
            status_code=400,
            detail="Not allowed parameter!"
        )

    if project_id:
        project = get_project_by_id(project_id)
        if project:
            return {
                "code": 200,
                "data": project
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No project identified by id: {project_id}"
            )

    if project_name:
        project = get_project_by_name(project_name)
        if project:
            total, res = split_page(list(project), page_size, page_num, sort_by, desc)
            return {
                "code": 200,
                "data": {
                    "total": total,
                    "data": res,
                }
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No project identified by name: {project_name}"
            )

    session = SessionDispatcher().get_session()
    projects = search_all_in_db(session, Project)
    total, res = split_page(list(projects), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.post("/")
@router.post("/{project_id}")
@router.put("/{project_id}")
async def create_project(r_project: RProject, project_id: int = None):
    """
    创建一个新项目或更新一个现有的项目

    可选参数：
    - template_id 用于指定使用哪个模板创建
    - additional_field 根据选定的模板，传入对应的json数据

    **已完成**
    """
    if project_id:
        session = SessionDispatcher().get_session()
        project = search_one_in_db(session, Project, id=project_id)
        # project = get_project_by_id(int(project_id))
        if project:
            new_record = {}
            default = RProject.dict(RProject())
            for k, v in r_project:
                if k and v != default[k]:
                    new_record[k] = v
            update_one_in_db(session, project, True, **new_record)
            session.remove()
            return {
                "code": 200,
                "detail": f"An existing project `{project.name}` updated successfully.",
                "data": project
            }
        else:
            return {
                "code": 404,
                "msg": "no project found."
            }

    project = project_manager.create_project(
        r_project.name,
        owner=r_project.owner,
        p_id=project_id,
        template_id=r_project.template_id,
        additional_field=r_project.additional_field,
        cover_image=r_project.image_url
    )
    return {
        "code": 200,
        "detail": "A new project created automatically.",
        "data": project
    }


@router.post("/template/")
@router.post("/template/{template_id}")
@router.put("/template/{template_id}")
async def create_template(r_template: RTemplate, template_id: int = None):
    """
    创建一个新项目模板或更新一个现有的项目模板

    **未完成**

    """

    template = get_template_by_id(int(template_id))
    # 若模板已存在，则根据请求体中给出的参数更新模板的名字及对应字段
    if template:
        update(
            template,
            name=r_template.name
        )
        return {
            "code": 200,
            "detail": f"Update record template `{template.id}` success.",
            "data": template
        }

    # 若无对应模板，则根据给出参数创建模板及对应模板字段
    template = project_manager.create_template(
        t_name=r_template.name,
        t_id=template_id
    )
    return {
        "code": 200,
        "detail": f"No project identified by id:{template_id}, create one.",
        "data": {
            "template": template,
            "field_list": r_template.field_list
        }
    }


@router.get("/{project_id}/application")
@router.get("/{project_id}/application/{application_id}")
async def get_application(project_id: int, application_id: int = None, application_name: str = None, page_size: int = 10, page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    获取对应项目的应用列表；如果传入application_id，则查询单个应用

    如果不传入如果传入application_id，且传入application_name，则会根据名称搜索

    同时传入application_id和application_name，只有application_id会生效

    **已完成**
    """
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"No project identified by id: {project_id}"
        )
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    if application_id:
        application = get_application_by_id(application_id, session)
        return {
            "code": 200,
            "data": application,
        }

    application = get_applications(session)
    if application_name:
        application = list(filter(lambda app: application_name in app.name, application))  # TODO: FIX ME
    total, res = split_page(list(application), page_size, page_num, sort_by, desc)
    session.remove()
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.post("/{project_id}/application")
@router.post("/{project_id}/application/{application_id}")
@router.put("/{project_id}/application/{application_id}")
async def create_application(r_application: RApplication, project_id: int, application_id: int = None):
    """
    创建一个新应用或更新一个现有的应用

    **已完成**

    """
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"No project identified by id: {project_id}"
        )

    session = SessionDispatcher().get_session(f"proj_{project_id}")
    application_dict = r_application.dict()
    if application_id:
        application = get_application_by_id(application_id, session)
        if application:
            new_record = {}
            default = RApplication.dict(RApplication())
            for k, v in r_application:
                if k and v != default[k]:
                    new_record[k] = v
            update_one_in_db(session, project, True, **new_record)
            session.remove()
            return {
                "code": 200,
                "detail": f"Update record application `{application_id}` success.",
            }

    application_dict["id"] = application_id
    application_dict["project_id"] = project_id
    application = project_manager.create_application(session, **application_dict)
    session.remove()
    return {
        "code": 200,
        "data": application,
        "detail": "A new application automatically created",
    }


@router.post("/{project_id}/application/{application_id}/attach")
async def attach_model_to_application(project_id: int, application_id: int, attached_model_id: int):
    """
    为应用添加模型

    **已完成**

    """
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"No project identified by id: {project_id}"
        )

    session = SessionDispatcher().get_session(f"proj_{project_id}")
    application = get_application_by_id(application_id, session)
    model = search_one_in_db(session, Model, id=attached_model_id)
    if not application or not model:
        session.remove()
        raise HTTPException(
            status_code=404,
            detail=f"No application identified by id: {application_id}"
        )

    model_id_list = set(application.model_id_list) if application.model_id_list else set()
    model_id_list.add(attached_model_id)
    application.model_id_list = tuple(model_id_list)
    session.add(application)

    app_id_list = set(model.app_id_list) if model.app_id_list else set()
    app_id_list.add(application_id)
    update_one_in_db(session, model, False, app_id_list=app_id_list)
    session.commit()
    session.remove()
    return {
        "code": 200,
        "detail": f"Attach model `{attached_model_id}` to application `{application_id}` success"
    }
