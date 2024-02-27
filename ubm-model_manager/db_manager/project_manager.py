from config import logger
from sqlalchemy.sql.expression import select
from typing import List, Dict
from db_model.common import create, search_one, SessionDispatcher, search_one_in_db, search_all_in_db, \
    create_record_in_db
from db_model.create_db import create_db
from db_model.project import Project, Template, TemplateField
from db_model.slpk_model import Application


def create_project(p_name: str,
                   *,
                   p_id: int = None,
                   owner: str = None,
                   template_id: int = None,
                   additional_field: dict = None,
                   cover_image: str = None
                   ) -> Project:
    record = {"name": p_name}
    if p_id:
        record["id"] = p_id
    if owner:
        record["owner"] = owner
    if template_id:
        record["template_id"] = template_id
    if additional_field:
        record["additional_field"] = additional_field
    if cover_image:
        record["cover_image"] = cover_image

    res = create(Project, **record)
    # 为每个项目创建独立的数据库
    sd = SessionDispatcher()
    sd.add_session(f"proj_{res.id}")
    create_db(f"proj_{res.id}")
    return res


def get_project_by_id(pid: int) -> Project:
    res = search_one(Project, id=pid)
    return res


def get_project_by_name(pname: str) -> List[Project]:
    sd = SessionDispatcher()
    session = sd.get_session()
    res = session.query(Project).filter(Project.name.like(f'%{pname}%')).all()
    return res


def create_template(t_name: str,
                    *,
                    t_id: int = None,
                    field_list: List[Dict[str, str]] = None,
                    ) -> Template:
    record = {"name": t_name}

    if t_id:
        record["id"] = t_id

    res = create(Template, **record)
    return res


def get_template_by_id(tid: int) -> Template:
    res = search_one(Template, id=tid)
    return res


def create_template_field(f_key: str, f_vt: int, t_id: int, f_id: int = None) -> TemplateField:
    record = {
        "key": f_key,
        "value_type": f_vt,
        "template_id": t_id,
        "id": f_id
    }
    res = create(TemplateField, **record)
    return res


def create_application(session, **record) -> Application:
    res = create_record_in_db(session, Application, autocommit=True, **record)
    return res


def get_application_by_id(application_id: int, session) -> Application:
    res = search_one_in_db(session, Application, id=application_id)
    return res


def get_applications(session) -> List[Application]:
    res = search_all_in_db(session, Application)
    return res


def get_applications_from_all_project() -> List[Application]:
    session = SessionDispatcher().get_session()
    res = []
    for project in search_all_in_db(session, Project):
        s = SessionDispatcher().get_session(f"proj_{project.id}")
        res.extend(get_applications(s))
        s.remove()
    session.remove()
    return res


if __name__ == "__main__":
    print(get_applications_from_all_project())
