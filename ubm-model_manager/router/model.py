import logging
import os
import uuid
from copy import deepcopy

import aiohttp as aiohttp
from aiohttp import FormData
from config import logger, config
from typing import List, Union
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Body, Form, BackgroundTasks
from pydantic import BaseModel, HttpUrl
import numpy as np

from db_manager.model_manager import update_model_in_project, create_model_in_project, create_model_file_in_project, \
    get_uuid_from_mf, upload_file_by_aiohttp, celery_app
from db_model.common import update, search_one_in_db, search_all_in_db, create_node_table, create_record_in_db, \
    update_one_in_db, create_records_in_db, create_records_reflect, SessionDispatcher, \
    search_all_by_name, search_all_by_id_list, search_one_in_db_by_filter, search_record_reflect, update_record_reflect
from db_model.slpk_model import Model, ModelFile, SublayerVersion, SublayerInfoVersion, NodepageVersion, LayerVersion
from dependence import get_authorization_header
from utils.common import split_page
from utils.parser import parse_path

router = APIRouter(
    prefix="/project",
    tags=["model"],
    # dependencies=[Depends(get_authorization_header)],   # 文档不能自动添加 header故先注释
    responses={404: {"description": "Not found"}},
)


class RAttribute(BaseModel):
    path: str
    data: dict


class RTaskStatus(BaseModel):
    status: str
    msg: str = None


class RTask(BaseModel):
    model_file_id: int


class RModelFileInfo(BaseModel):
    model_file_id: int


class RPosition(BaseModel):
    longitude: float
    latitude: float
    z: float


class RRotation(BaseModel):
    w: float
    x: float
    y: float
    z: float


class RTransform(BaseModel):
    position: RPosition
    rotation: RRotation = None


class RModel(BaseModel):
    # application_id: int = None
    name: str = None
    version: int = 1
    current_model_file_id: int = None
    attach_to_apps: List[int] = []
    remove_from_apps: List[int] = []


@router.post("/{project_id}/model")
@router.post("/{project_id}/model/{model_id}")
@router.put("/{project_id}/model/{model_id}")
async def create_model(r_model: RModel, project_id: int, model_id: int = None):
    """
    创建一个新模型或更新一个现有的模型信息

    如果传入 model_id 且 model_id 已存在则更新模型信息
    否则创建新模型

    **已完成**
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    model = search_one_in_db(session, Model, id=model_id)
    if model_id and model:
        new_record = {}
        default = RModel.dict(RModel())
        for k, v in r_model:
            if k and v != default[k]:
                new_record[k] = v
        new_record["app_id_list"] = list(
            set(model.app_id_list).union(r_model.attach_to_apps) - set(r_model.remove_from_apps))
        print(new_record)
        new_record = dict(filter(lambda item: item[0] in model.__dict__, new_record.items()))
        print(new_record)
        for k, v in new_record.items():
            setattr(model, k, v)
        session.add(model)

        if "current_model_file_id" in new_record:
            mf = search_one_in_db(session, ModelFile, id=new_record["current_model_file_id"])
            update_one_in_db(session, mf, False, model_id=model.id)
        session.commit()
        # update_one_in_db(session, model, True, **new_record)
    else:
        record = r_model.dict()
        record["id"] = model_id
        record["app_id_list"] = record["attach_to_apps"]
        del record["attach_to_apps"]   # TODO: 应该有更好的方案
        del record["remove_from_apps"]
        model = create_record_in_db(session, Model, autocommit=True, **record)
    session.remove()
    return {
        "code": 200,
        "data": model
    }


@router.post("/{project_id}/model/{model_id}/bind")
async def bind_model_file_with_model(project_id: int, model_id: int, model_file: RModelFileInfo):
    """
    将模型文件和模型关联

    **已完成**
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    model = search_one_in_db(session, Model, id=model_id)
    mf = search_one_in_db(session, ModelFile, id=model_file.model_file_id)
    if model and mf:
        update_one_in_db(session, model, False, current_model_file_id=model_file.model_file_id)
        update_one_in_db(session, mf, True, model_id=model_id)
        session.remove()
        return {
            "code": 200,
        }
    session.remove()
    return {
        "code": 400,
        "msg": "model or model file may not exist."
    }


@router.post("/{project_id}/model-file/upload")
async def simple_upload(file: UploadFile, background_tasks: BackgroundTasks, project_id: int, model_id: int = None):
    """
     直接上传单个文件，如果传入model_id, 则与对应模型关联
     否则需手动关联模型

     **已完成**
    """
    if not file:
        return {
            "code": 400,
            "msg": "no file upload."
        }
    if file.filename.endswith(".jrvt"):
        data = await file.read()

        # file_path = os.path.join(config["model"]["upload_model_save_path"], f"{str(uuid.uuid4())}.jrvt")
        # with open(file_path, "wb") as f:
        #     f.write(data)
        # logger.debug(f"save file to: {file_path}")

        # create model_file
        uuid_ = str(uuid.uuid4())
        record = {
            "name": file.filename,
            "state": "transfer",
            "tmp_file_size": len(data),
            "uuid": uuid_,
        }
        session = SessionDispatcher().get_session(f"proj_{project_id}")
        model = search_one_in_db(session, Model, id=model_id)
        if model_id and model:
            record["model_id"] = model_id
        mf = create_model_file_in_project(project_id, record)
        if model:
            update_one_in_db(session, model, True, current_model_file_id=mf.get("id"), version=model.version + 1)
        logger.debug(f"create model file record success.")
        # upload to converter server
        url = config["model"]["converter_server_url"]
        filename = f"{uuid_}.jrvt"
        form_data = FormData()
        form_data.add_field('file', data, filename=filename)
        form_data.add_field('filename', filename)
        headers = {
            "x-project-id": str(project_id),
            "x-model-id": str(mf["id"])
        }
        background_tasks.add_task(upload_file_by_aiohttp, project_id, mf["id"], url, form_data, headers=headers)
        # update_one_in_db(session, search_one_in_db(session, ModelFile, id=mf["id"]), True, state="created")
        await file.close()
        session.remove()
        return {
            "code": 200,
            "data": {
                "filename": file.filename,
                "model_file_id": mf["id"]
            },
        }
    else:
        return {
            "code": 406,
            "msg": "not implement."
        }


@router.post("/{project_id}/model-file/multipart-upload")
@router.post("/{project_id}/model-file/{model_id}/multipart-upload")
async def create_multipart_upload():
    """
     创建分片上传，如果传入model_id, 则与对应模型关联
     否则需手动关联模型
    """
    pass


@router.post("/{project_id}/model-file/multipart-upload/{file_id}/{part_id}")
@router.get("/{project_id}/model-file/multipart-upload/{file_id}/{part_id}")
@router.get("/{project_id}/model-file/multipart-upload/{file_id}")
async def upload_multipart():
    """
    上传分片，获取分片状态
    获取分片状态时，如果传入part_id则返回单个part的上传状态，否则返回所有已上传的part_id
    """
    pass


@router.post("/{project_id}/model-file/multipart-upload/finish")
async def finish_multipart_upload():
    """
    完成分片上传
    """
    pass


@router.post("/{project_id}/model-file/convert")
def create_convert_task(task: RTask, project_id: int):
    """
    发起转换任务

    **已完成**
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    mf = search_one_in_db(session, ModelFile, id=task.model_file_id)
    if mf and (mf.state == "transfer" or mf.state == "processing"):
        return {
            "code": 400,
            "msg": f"model(id = {mf.id}) file state is {mf.state}, can not convert."
        }
    if mf:
        update_one_in_db(session, mf, True, state="waiting")
        celery_app.send_task("src.api.start_convert", args=[mf.uuid, project_id, task.model_file_id])
        session.remove()
        return {
            "code": 200,
        }
    else:
        session.remove()
        return {
            "code": 404,
            "msg": "no such model file."
        }


@router.get("/{project_id}/model-file/convert")
@router.get("/{project_id}/model-file/convert/{model_file_id}")
async def get_convert_task_state(project_id: int, model_file_id: int = None):
    """
    获取转换任务状态

    **已完成**
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    if model_file_id:
        mf = search_one_in_db(session, ModelFile, id=model_file_id)
        if mf:
            session.remove()
            return {
                "code": 200,
                "data": {
                    "model_file_id": mf.id,
                    "name": mf.name,
                    "state": mf.state,
                },
            }
        else:
            session.remove()
            return {
                "code": 404,
                "msg": "no such model file."
            }
    else:
        model_files = search_all_in_db(session, ModelFile)
        res = list(map(lambda record: {
            "model_file_id": record.id,
            "name": record.name,
            "state": record.state,
        }, model_files))
        session.remove()
        return {
            "code": 200,
            "data": res,
        }


@router.post("/{project_id}/model-file/{model_file_id}/bin")
async def save_attribute_to_file(project_id: int, model_file_id: int,
                                 path: str = Form(media_type="multipart/form-data"),
                                 bin_data: UploadFile = Form(media_type="multipart/form-data")):
    """
    将模型二进制属性(几何信息，材质信息)存入文件系统，内部调用

    **已完成，通过简单测试**
    """

    res = parse_path(path)
    output_file_root = config["model"]["slpk_root"]
    slpk_uuid = get_uuid_from_mf(project_id=project_id, model_file_id=model_file_id)
    if res["type"] == "node_text":
        # 当路径解析的结果为"node_text"时，仅接受后缀为.dds.gz的压缩文件
        print(bin_data.filename)
        if not bin_data.filename.endswith(".dds"):
            raise HTTPException(406, detail="Unacceptable file type")
        texture_path = os.path.join(Path(output_file_root), Path(slpk_uuid), Path(path))
        if not os.path.isfile(texture_path):
            dir_path = os.path.dirname(texture_path)
            os.makedirs(dir_path, exist_ok=True)
            # return {
            #     "code": 404,
            #     "msg": texture_path
            # }
        filebytes = await bin_data.read()
        f = open(texture_path, "wb")
        f.write(filebytes)
        f.close()
    elif res["type"] == "node_geom":
        # 当路径解析的结果为"node_geome"时，仅接受后缀为bin的二进制文件
        if not bin_data.filename.endswith(".bin"):
            raise HTTPException(406, detail="Unacceptable file type")
        geometry_path = os.path.join(Path(output_file_root), Path(slpk_uuid), Path(path))
        if not os.path.isfile(geometry_path):
            dir_path = os.path.dirname(geometry_path)
            os.makedirs(dir_path, exist_ok=True)
        #     print(geometry_path)
        #     return {
        #         "code": 404,
        #         "msg": geometry_path
        #     }
        filebytes = await bin_data.read()
        f = open(geometry_path, "wb")
        f.write(filebytes)
        f.close()
    else:
        raise NotImplemented
    return {
        "code": 200
    }


@router.post("/{project_id}/model-file/{model_file_id}/attribute")
async def save_attribute_to_db(project_id: int, model_file_id: int, r_attr: RAttribute):
    """
    将模型非几何信息存入数据库，内部调用

    **已完成**
    """

    def create_sublayer(session, layer_json):
        sublayers = layer_json.get("sublayers")
        # TODO: 为兼容性考虑，递归遍历sublayers
        sublayers = list(filter(lambda item: item["layerType"] == "3DObject", sublayers))
        keys = ("sublayer_index", "model_file_id")
        values = []
        for i in range(len(sublayers)):
            values.append((i, model_file_id))
            create_node_table(f"proj_{project_id}", f"{model_file_id}_{i}_NODE_VERSION")
        # session = SessionDispatcher().get_session(f"proj_{project_id}")
        ids = create_records_in_db(session, SublayerVersion, False, keys, values)
        ids = list(map(lambda i: i.id, ids))
        # add association with model file
        print(f"ids: {ids}")
        return ids

    session = SessionDispatcher().get_session(f"proj_{project_id}")
    res = parse_path(r_attr.path)
    mf = search_one_in_db(session, ModelFile, id=model_file_id)
    if res["type"] == "layer":
        _, model = res["data"]
        record_id = create_record_in_db(session, model, False, layer=r_attr.data)
        logger.debug(f"type: layer, new record id: {record_id.id}")
        ids = create_sublayer(session, r_attr.data)
        update_one_in_db(session, mf, False, sublayer_version_id=ids, layer_version_id=record_id.id)
    elif res["type"] == "metadata":
        _, model = res["data"]
        record_id = create_record_in_db(session, model, False, meta=r_attr.data)
        logger.debug(f"type: metadata, new record id: {record_id.id}")
        update_one_in_db(session, mf, False, meta_version_id=record_id.id)
    elif res["type"] == "sublayer":
        sublayer_idx, model = res["data"]
        sublayer = search_one_in_db(session, SublayerVersion, model_file_id=model_file_id, sublayer_index=sublayer_idx)
        if sublayer:
            record_id = create_record_in_db(session, model, False, sublayer=r_attr.data)
            logger.debug(f"type: sublayer, new record id: {record_id.id}")
            update_one_in_db(session, sublayer, False, sublayer_version_id=record_id.id)
        else:
            logger.error(f"model_file_id: {model_file_id}, sublayer_idx: {sublayer_idx} sublayer records not exists.")
            session.remove()
            return {
                "code": 400,
                "msg": f"model_file_id: {model_file_id}, sublayer_idx: {sublayer_idx} sublayer records not exists."
            }
    elif res["type"] == "nodepage":
        sublayer_idx, model = res["data"]
        sublayer = search_one_in_db(session, SublayerVersion, model_file_id=model_file_id, sublayer_index=sublayer_idx)
        if sublayer:
            record_id = create_record_in_db(session, model, False, nodepage=r_attr.data)
            update_one_in_db(session, sublayer, False, nodepage_version_id=record_id.id)
        else:
            logger.error(f"model_file_id: {model_file_id}, sublayer_idx: {sublayer_idx} sublayer records not exists.")
            session.remove()
            return {
                "code": 400,
                "msg": f"model_file_id: {model_file_id}, sublayer_idx: {sublayer_idx} sublayer records not exists."
            }
    elif res["type"] == "sublayer_meta":
        sublayer_idx, model = res["data"]
        sublayer = search_one_in_db(session, SublayerVersion, model_file_id=model_file_id, sublayer_index=sublayer_idx)
        if sublayer:
            record_id = create_record_in_db(session, model, False, meta=r_attr.data)
            update_one_in_db(session, sublayer, False, sublayer_meta_version_id=record_id.id)
        else:
            logger.error(f"model_file_id: {model_file_id}, sublayer_idx: {sublayer_idx} sublayer records not exists.")
            session.remove()
            return {
                "code": 400,
                "msg": f"model_file_id: {model_file_id}, sublayer_idx: {sublayer_idx} sublayer records not exists."
            }
    elif res["type"] == "node_attr":
        sublayer_idx, node_idx = res["data"]
        has_table = search_record_reflect(f"proj_{project_id}", f"{model_file_id}_{sublayer_idx}_NODE_VERSION", node_index=node_idx)
        # 若路径解析为attribute且对应node_idx已存在，则执行更新逻辑
        if has_table:
            update_record_reflect(f"proj_{project_id}", f"{model_file_id}_{sublayer_idx}_NODE_VERSION", {
                "attribute": r_attr.data,
                "version": 1,
            }, node_index=node_idx)
        else:
            create_records_reflect(f"proj_{project_id}", f"{model_file_id}_{sublayer_idx}_NODE_VERSION", [{
                "node_index": node_idx,
                "attribute": r_attr.data,
                "version": 1,
            }])
    else:
        raise NotImplemented
    session.commit()
    session.remove()
    return {
        "code": 200,  # 需要返回状态码用于转换器判断数据是否正确存储
        # "data": {
        #     "model_id": model_file_id,
        #     "data": r_attr,
        # }
    }


@router.get("/{project_id}/model-file/{model_file_id}/object/{object_id}/extended-attribute")
async def get_object_extended_attribute():
    """
    获取某一个构件的扩展信息
    """


@router.post("/{project_id}/model-file/{model_file_id}/object/{object_id}/extended-attribute")
async def edit_object_extended_attribute():
    """
    编辑某一个构件的扩展信息
    """


@router.get("/{project_id}/model")
async def get_model(project_id: int, application_id: int = None, model_name: str = None, page_size: int = 10,
                    page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    获取当前项目的所有模型，如果传入model_name则根据model_name筛选，
    如果传入application_id则根据application_id筛选，
    二者可同时生效。
    - model_name: 应用名
    - page_size:  分页大小
    - page_num:  第几页，从1开始
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    if model_name:
        models = search_all_by_name(session, Model, model_name)
    else:
        models = search_all_in_db(session, Model)
    if application_id:
        models = list(filter(lambda m: application_id in m.app_id_list if m.app_id_list else [], models))
    session.remove()
    total, res = split_page(list(models), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.get("/{project_id}/model/{model_id}")
async def get_model_info_by_id(project_id: int, model_id: int):
    """
    根据id获取模型信息
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    res = search_one_in_db(session, Model, id=model_id)
    if res:
        return {
            "code": 200,
            "data": res
        }
    else:
        return {
            "code": 404,
            "msg": "model not found."
        }


@router.get("/{project_id}/model-file")
async def get_modelfile(project_id: int, modelfile_name: str = None, model_id: int = None, page_size: int = 10,
                        page_num: int = 1, sort_by: str = "create_time", desc: bool = True):
    """
    获取当前项目的所有模型，如果传入model_name则根据model_name筛选.
    - model_id: 模型id
    - page_size:  分页大小
    - page_num:  第几页，从1开始
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    if model_id:
        model = search_one_in_db(session, Model, id=model_id)
        modelfiles = search_one_in_db_by_filter(session, ModelFile, model_id=model.id)
    else:
        modelfiles = search_all_in_db(session, ModelFile)
    if modelfile_name:
        modelfiles = filter(lambda mf: modelfile_name in mf.name, modelfiles)

    session.remove()
    total, res = split_page(list(modelfiles), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.get("/{project_id}/model-file/{modelfile_id}")
async def get_modelfile_info_by_id(project_id: int, modelfile_id: int):
    """
    根据id获取模型信息
    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    res = search_one_in_db(session, ModelFile, id=modelfile_id)
    if res:
        return {
            "code": 200,
            "data": res
        }
    else:
        return {
            "code": 404,
            "msg": "modelfile not found."
        }


@router.post("/{project_id}/model-file/convert/{model_file_id}/status")
async def report_convert_status_by_converter(project_id: int, model_file_id: int, r_status: RTaskStatus):
    """
    converter 上报模型转化状态
    当转化完成时，变更模型状态
    状态定义：

    ```
    class TaskStatus(Enum):
        # report convert status to model manager
        transfer = "transfer"  # 转移到converter服务器
        created = "created"  # 已上传，未发起转换
        waiting = "waiting"  # 已发起转换，加入到任务队列
        processing = "processing"  # 开始处理
        success = "success"
        fail = "fail"
    ```

    **已完成**
    """
    # print(r_status)
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    mf = search_one_in_db(session, ModelFile, id=model_file_id)
    if r_status.status == "processing":
        update_one_in_db(session, mf, True, state="processing")
    elif r_status.status == "success":
        duration = int(r_status.msg)
        update_one_in_db(session, mf, True, state="success", duration=duration)
    elif r_status.status == "fail":
        update_one_in_db(session, mf, True, state="fail")
    elif r_status.status == "created":
        if mf.state == "transfer":
            update_one_in_db(session, mf, True, state="created")
        else:
            logging.error("Model file created only when uploaded!")
            raise NotImplementedError
    else:
        session.remove()
        raise NotImplementedError
    session.remove()
    return {
        "code": 200,  # 需要返回状态码用于转换器判断数据是否正确存储
        "data": {
            "model_file_id": model_file_id,
            "data": r_status,
        }
    }


@router.post("/{project_id}/model-file/{model_file_id}/attribute/transform")
async def set_model_transform(project_id: int, model_file_id: int, new_transform: RTransform):
    """
    设置模型位置
    new_pos: 经纬度及高度
    """
    # TODO: change store extent
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    mf = search_one_in_db(session, ModelFile, id=model_file_id)
    if not mf:
        session.remove()
        return {
            "code": 404,
            "msg": "model file not found."
        }
    layer = search_one_in_db(session, LayerVersion, id=mf.layer_version_id)
    origin_model_center = np.array(layer.layer["ubm"]["model_center"])
    new_model_center = np.array([
        new_transform.position.longitude,
        new_transform.position.latitude,
        new_transform.position.z
    ])

    sublayer_ids = mf.sublayer_version_id
    for sid in sublayer_ids:
        sublayer = search_one_in_db(session, SublayerVersion, id=sid)
        assert sublayer
        # change sublayer fullextend and nodepage's obb
        sublayer_info = search_one_in_db(session, SublayerInfoVersion, id=sublayer.sublayer_version_id)
        nodepage = search_one_in_db(session, NodepageVersion, id=sublayer.nodepage_version_id)
        assert sublayer_info
        assert nodepage
        sublayer_info_data = deepcopy(sublayer_info.sublayer)
        origin_extent = sublayer_info_data.get("fullExtent")
        extent_center = np.array([
            (origin_extent["xmin"] + origin_extent["xmax"]) / 2,
            (origin_extent["ymin"] + origin_extent["ymax"]) / 2,
            (origin_extent["zmin"] + origin_extent["zmax"]) / 2,
        ])
        new_extent = deepcopy(origin_extent)
        delta_extent_center = extent_center - origin_model_center
        new_extent_center = new_model_center + delta_extent_center
        new_extent["xmin"] = new_extent_center[0] + origin_extent["xmin"] - extent_center[0]
        new_extent["ymin"] = new_extent_center[1] + origin_extent["ymin"] - extent_center[1]
        new_extent["xmax"] = new_extent_center[0] + origin_extent["xmax"] - extent_center[0]
        new_extent["ymax"] = new_extent_center[1] + origin_extent["ymax"] - extent_center[1]
        new_extent["zmin"] = new_extent_center[2] + origin_extent["zmin"] - extent_center[2]
        new_extent["zmax"] = new_extent_center[2] + origin_extent["zmax"] - extent_center[2]
        sublayer_info_data["fullExtent"] = new_extent
        update_one_in_db(session, sublayer_info, False, sublayer=sublayer_info_data)

        nodepage_data = deepcopy(nodepage.nodepage.get("nodes"))
        for node in nodepage_data:
            node_pos = np.array(node["obb"]["center"]) - origin_model_center + new_model_center
            node["obb"]["center"] = list(node_pos)
        update_one_in_db(session, nodepage, False, nodepage={"nodes": nodepage_data})
    new_layer = deepcopy(layer.layer)
    new_layer["ubm"]["model_center"] = list(new_model_center)
    print(new_layer["ubm"])
    update_one_in_db(session, layer, False, layer=new_layer)
    session.commit()
    session.remove()
    return {
        "code": 200,
    }
