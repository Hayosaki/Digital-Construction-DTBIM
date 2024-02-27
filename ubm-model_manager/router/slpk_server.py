from config import logger
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, HttpUrl
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import (
    text,
    create_engine,
    MetaData,
    Table
)
from sqlalchemy.orm import sessionmaker

from utils.common import split_page
from db_model.common import SessionDispatcher, search_record_reflect, update_one_in_db, \
    create_record_in_db, update_record_reflect, search_all_by_id_list, search_one_in_db
from db_model.slpk_model import ModelFile, LayerVersion, MetaVersion, \
    SublayerVersion, SublayerInfoVersion, NodepageVersion, SublayerMetaVersion, MaterialAttributeVersion
from db_manager.model_manager import get_uuid_from_mf
from dependence import get_authorization_header
from config import config


router = APIRouter(
    prefix="/project",
    tags=["slpk server"],
    # dependencies=[Depends(get_authorization_header)],   # 文档不能自动添加 header故先注释
    responses={404: {"description": "Not found"}},
)


class RMaterialAttributeVersion(BaseModel):
    version: int = 0
    attribute: dict = None
    old_version_list: List[int] = None


# 模型分发相关 api (slpk server)
# TODO: 点云、斜摄的api支持
@router.get("/{project_id}/slpk/{model_file_id}/SceneServer")
async def get_scene_server(model_file_id: int, project_id: int, response: Response):
    """
    获取一个转换后的slpk模型文件server

    *已完成，未测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    slpk_scenelayer = session.query(LayerVersion).filter_by(id=slpk_model.layer_version_id).first()
    if not slpk_scenelayer:
        raise HTTPException(
            status_code=404,
            detail=f"No server identified by id: {model_file_id}"
        )

    # building service
    server = dict()
    server["serviceName"] = " "
    server["name"] = " "
    server["currentVersion"] = " "
    server["serviceVersion"] = " "
    server["supportedBuildings"] = ["REST"]
    server["layers"] = [slpk_scenelayer.layer]
    session.close()
    response.headers["content-encoding"] = "gzip"
    session.remove()
    return server


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/0")
async def get_scene_layer(model_file_id: int, project_id: int, response: Response):
    """
    获取一个转换后的slpk模型文件主层的3dSceneLayer.json

    **已完成，未测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    slpk_scenelayer = session.query(LayerVersion).filter_by(id=slpk_model.layer_version_id).first()
    if not slpk_scenelayer:
        raise HTTPException(
            status_code=404,
            detail=f"No scene layer identified by id: {model_file_id}"
        )

    response.headers["content-encoding"] = "gzip"
    session.remove()
    return slpk_scenelayer.layer


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/MaterialAttribute")
async def get_material_attribute(model_file_id: int, project_id: int, response: Response,
                                 material_attribute_id: int = None, page_size: int = 10, page_num: int = 1,
                                 sort_by: str = "create_time", desc: bool = True):
    """
    获取一个转换后的slpk模型文件的所有材质信息，如果传入query参数则根据参数筛选，同时也支持路径参数

    以下参数用来设置分页：
    - page_size 分页大小
    - page_num  第几页
    **已完成，通过简单测试**

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    id_list = slpk_model.material_attribute_version_id_list
    if not id_list:
        raise HTTPException(
            status_code=404,
            detail=f"No MaterialAttribute in ModelFile identified: {model_file_id}"
        )
    if material_attribute_id and material_attribute_id in id_list:
        slpk_attribute: MaterialAttributeVersion = session.query(MaterialAttributeVersion). \
            filter(id=material_attribute_id).first()
        if not slpk_attribute:
            raise HTTPException(
                status_code=404,
                detail=f"No material attribute identified by MaterialAttribute id: {model_file_id}"
            )
        response.headers["content-encoding"] = "gzip"
        session.remove()
        return slpk_attribute.attribute

    material_attributes = search_all_by_id_list(session, MaterialAttributeVersion, id_list)
    total, res = split_page(list(material_attributes), page_size, page_num, sort_by, desc)
    return {
        "code": 200,
        "data": {
            "total": total,
            "data": res,
        }
    }


@router.post("/{project_id}/slpk/{model_file_id}/MaterialAttribute")
@router.post("/{project_id}/slpk/{model_file_id}/MaterialAttribute/{material_attribute_id}")
@router.put("/{project_id}/slpk/{model_file_id}/MaterialAttribute/{material_attribute_id}")
async def create_material_attribute(model_file_id: int, project_id: int,
                                    r_materialAttribute: RMaterialAttributeVersion, material_attribute_id: int = None):
    """
    为一个转换后的slpk模型文件创建材质属性信息
    可使用路径参数或查询参数指定创建的材质属性表的ID
    若指定的ID已存在对应属性表，则为模型文件绑定该材质属性

    修改一个转换后的slpk模型文件的材质信息
    根据传入的路径参数或查询查询，更新对应的材质属性信息
    *已完成，未测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model: ModelFile = search_one_in_db(session, ModelFile, id=model_file_id)
    id_list = list(slpk_model.material_attribute_version_id_list) if slpk_model.material_attribute_version_id_list else []
    if material_attribute_id:
        materialAttribute: MaterialAttributeVersion = session.query(MaterialAttributeVersion). \
            filter_by(id=material_attribute_id).first()
        if materialAttribute:
            if material_attribute_id in id_list:
                # 若指定ID已存在对应属性表，且已绑定到模型文件，则执行更新逻辑
                new_record = {}
                default = RMaterialAttributeVersion.dict(RMaterialAttributeVersion())
                for k, v in r_materialAttribute:
                    if k and v != default[k]:
                        new_record[k] = v
                update_one_in_db(session, materialAttribute, autocommit=True, **new_record)
                print(materialAttribute.id)
                session.remove()
                return {
                    "code": 200,
                    "detail": f"An existing  material attribute identified by "
                              f"`{materialAttribute.id}` updated successfully.",
                    "data": materialAttribute
                }
            else:
                # 若指定ID已存在对应属性表，且未绑定到模型文件，则为模型文件绑定该材质属性
                id_list.append(material_attribute_id)
                slpk_model.material_attribute_version_id_list = tuple(id_list)
                return {
                    "code": 200,
                    "detail": f"An existing  material attribute identified by "
                              f"`{materialAttribute.id}` bound with model file `{model_file_id}` successfully.",
                    "data": {
                        "model_file_id": model_file_id,
                        "materialAttribute": materialAttribute
                    }
                }
        else:
            # 若ModelFile无对应材质属性信息，则根据RMaterialAttribute创建MaterialAttributeVersion
            id_list.append(material_attribute_id) if material_attribute_id not in id_list else None
            slpk_model.material_attribute_version_id_list = tuple(id_list)
            materialAttribute = create_record_in_db(
                session,
                MaterialAttributeVersion,
                autocommit=True,
                id=material_attribute_id,
                version=r_materialAttribute.version,
                attribute=r_materialAttribute.attribute,
                old_version_list=r_materialAttribute.old_version_list
            )
            session.remove()
            return {
                "code": 200,
                "data": materialAttribute
            }
    else:
        # 若未指定MaterialAttributeVersion的ID，则自增ID创建Mat表
        materialAttribute = create_record_in_db(
            session,
            MaterialAttributeVersion,
            autocommit=True,
            version=r_materialAttribute.version,
            attribute=r_materialAttribute.attribute,
            old_version_list=r_materialAttribute.old_version_list
        )
        session.remove()
        return {
            "code": 200,
            "data": materialAttribute
        }


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/{layer_index}/sublayers/{sublayer_index}")
async def get_sublayer(model_file_id: int, sublayer_index: int, project_id: int, response: Response):
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    sublayer_id_list = slpk_model.sublayer_version_id
    sublayer = session.query(SublayerVersion). \
        filter(SublayerVersion.id.in_(sublayer_id_list)).filter_by(sublayer_index=sublayer_index).first()
    if sublayer:
        session.remove()
        sublayer_info = session.query(SublayerInfoVersion).filter_by(id=sublayer.sublayer_version_id).first()
        response.headers["content-encoding"] = "gzip"
        return sublayer_info.sublayer

    session.remove()
    raise HTTPException(
        status_code=404,
        detail=f"Sublayer indexed {sublayer_index} in model {model_file_id} Not Found"
    )


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/{layer_index}/sublayers/{sublayer_index}/ClassAttribute")
async def get_class_attribute(model_file_id: int, sublayer_index: int, project_id: int,
                              response: Response):
    """
    获取一个转换后的slpk模型文件子层的类属性信息

    *已完成，通过简单测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    sublayer_id_list = slpk_model.sublayer_version_id
    sublayer = session.query(SublayerVersion). \
        filter(SublayerVersion.id.in_(sublayer_id_list)).filter_by(sublayer_index=sublayer_index).first()
    sublayer_info: SublayerInfoVersion = session.query(SublayerInfoVersion).filter_by(
        id=sublayer.sublayer_version_id).first()
    if sublayer_info and sublayer_info.sublayer_attribute:
        session.remove()
        response.headers["content-encoding"] = "gzip"
        return sublayer_info.sublayer_attribute

    session.remove()
    raise HTTPException(
        status_code=404,
        detail=f"Sublayer attribute indexed {sublayer_index} in model {model_file_id} Not Found"
    )


@router.post("/{project_id}/slpk/{model_file_id}/SceneServer/layers/{layer_index}/sublayers/{sublayer_index}/ClassAttribute")
@router.put("/{project_id}/slpk/{model_file_id}/SceneServer/layers/{layer_index}/sublayers/{sublayer_index}/ClassAttribute")
async def update_class_attribute(model_file_id: int, sublayer_index: int, project_id: int,
                                 _sublayerAttribute: dict):
    """
    更新一个转换后的slpk模型文件子层的类属性信息

    *已完成，通过简单测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    sublayer_id_list = slpk_model.sublayer_version_id
    sublayer = session.query(SublayerVersion). \
        filter(SublayerVersion.id.in_(sublayer_id_list)).filter_by(sublayer_index=sublayer_index).first()
    sublayer_info: SublayerInfoVersion = session.query(SublayerInfoVersion).filter_by(
        id=sublayer.sublayer_version_id).first()
    if sublayer_info:
        sublayer_info.sublayer_attribute = _sublayerAttribute
        session.add(sublayer_info)
        session.commit()
        print(sublayer_info.sublayer_attribute)
        session.remove()

        return {
            "code": 200,
            "data": sublayer_info.sublayer_attribute
        }
    session.remove()
    raise HTTPException(
        status_code=404,
        detail=f"Sublayer attribute indexed {sublayer_index} in model {model_file_id} Not Found"
    )


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
            "{layer_index}/sublayers/{sublayer_index}/nodepages/{nodepage_index}")
async def get_nodepage(model_file_id: int, layer_index: int, sublayer_index: int, nodepage_index: int, project_id: int,
                       response: Response):
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    sublayer_id_list = slpk_model.sublayer_version_id
    sublayer = session.query(SublayerVersion). \
        filter(SublayerVersion.id.in_(sublayer_id_list)).filter_by(sublayer_index=sublayer_index).first()

    if sublayer:
        nodes_range = [nodepage_index * 64, (nodepage_index + 1) * 64]
        integrated_nodepage = session.query(NodepageVersion).filter_by(id=sublayer.nodepage_version_id).first()
        nodepage_json_data = integrated_nodepage.nodepage
        # 此处遍历可优化
        # for item in nodepage_json_data["nodes"]:
        #     for i in range(nodes_range[0], nodes_range[1]):
        #         if i == item["index"]:
        #             nodes.append(item)
        #             break
        nodes = nodepage_json_data["nodes"][nodes_range[0]:nodes_range[1]]
        response.headers["content-encoding"] = "gzip"
        session.remove()
        return {"nodes": nodes}

    session.remove()
    raise HTTPException(
        status_code=404,
        detail="Nodepage Not Found"
    )


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
            "{layer_index}/sublayers/{sublayer_index}/nodes/{node_index}/geometries/{geometry_index}")
async def get_node_geometry(model_file_id: int, layer_index: int, sublayer_index: int, node_index: int,
                            geometry_index: int, project_id: int, response: Response):
    """
    有改动，待测试
    """
    slpk_uuid = get_uuid_from_mf(project_id=project_id, model_file_id=model_file_id)
    slpk_root = config["model"]["slpk_root"]
    geometry_path = os.path.join(slpk_root, slpk_uuid, "sublayers", f"{sublayer_index}",
                                 "nodes", f"{node_index}", "geometries", f"{geometry_index}.bin")
    response.headers["content-encoding"] = "gzip"
    return FileResponse(geometry_path, filename=f"{geometry_index}.bin")


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
            "{layer_index}/sublayers/{sublayer_index}/nodes/{node_index}/textures/0_0_1")
async def get_node_texture(model_file_id: int, layer_index: int, sublayer_index: int, node_index: int,
                           project_id: int, response: Response):
    """
    有改动，待测试
    """
    slpk_uuid = get_uuid_from_mf(project_id=project_id, model_file_id=model_file_id)
    slpk_root = config["model"]["slpk_root"]
    texture_path = os.path.join(slpk_root, slpk_uuid, "sublayers", f"{sublayer_index}",
                                "nodes", f"{node_index}", "textures", "0_0_1.bin.dds")
    response.headers["content-encoding"] = "gzip"
    return FileResponse(texture_path, filename=f"0_0_1.bin.dds")


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
            "{layer_index}/sublayers/{sublayer_index}/nodes/{node_index}/attributes/{attributes_key}/0")
async def get_node_attribute(model_file_id: int, layer_index: int, sublayer_index: int, node_index: int,
                             attributes_key: str, project_id: int, response: Response):
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    model_file = search_one_in_db(session, ModelFile, id=model_file_id)
    # TODO: FIXME 可被注入，但是使用反射会对性能造成很大影响，需重新考虑实现
    sql = f"SELECT attribute FROM \"{model_file.id}_{sublayer_index}_NODE_VERSION\" WHERE node_index = {node_index}"
    attribute = session.execute(text(sql)).fetchall()[0]["attribute"]
    # attribute = search_record_reflect(
    #     f"proj_{project_id}",
    #     f"{model_file.id}_{sublayer_index}_NODE_VERSION",
    #     node_index=node_index
    # )["attribute"]
    attribute_id = int(attributes_key.split("_", 1)[1])
    values: List[str] = attribute["value"][attribute_id]
    byte_counts: List[int] = attribute["size_bytes"][attribute_id]
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
    response.headers["content-encoding"] = "gzip"
    content_length = 0
    for i in binary_response:
        content_length += i.__len__()
    response.headers["content-length"] = f"{content_length}"
    session.remove()
    return StreamingResponse(
        binary_response.__iter__(),
        media_type="application/octet-stream"
    )


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
            "{layer_index}/sublayers/{sublayer_index}/nodes/{node_index}/CustomAttribute")
async def get_custom_attribute(model_file_id: int, sublayer_index: int, node_index: int,
                               project_id: int, response: Response):
    """
    获取一个节点的自定义属性

    *已完成，未测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    model_file = search_one_in_db(session, ModelFile, id=model_file_id)
    sql = f"SELECT custom_attribute FROM " \
          f"\"{model_file.id}_{sublayer_index}_NODE_VERSION\"" \
          f" WHERE node_index = {node_index} "
    custom_attribute = session.execute(text(sql)).fetchall()[0]["custom_attribute"]
    response.headers["content-encoding"] = "gzip"
    session.remove()
    return {
        "code": 200,
        "data": custom_attribute
    }


@router.post("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
             "{layer_index}/sublayers/{sublayer_index}/nodes/{node_index}/CustomAttribute")
@router.put("/{project_id}/slpk/{model_file_id}/SceneServer/layers/"
            "{layer_index}/sublayers/{sublayer_index}/nodes/{node_index}/CustomAttribute")
async def update_custom_attribute(model_file_id: int, sublayer_index: int, node_index: int,
                                  project_id: int, _customAttribute: dict = None):
    """
    修改一个节点的自定义属性

    *已完成，通过简单测试*

    """
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    model_file = search_one_in_db(session, ModelFile, id=model_file_id)
    select_sql = f"SELECT custom_attribute FROM " \
                 f"\"{model_file.id}_{sublayer_index}_NODE_VERSION\"" \
                 f" WHERE node_index = {node_index}"
    custom_attribute = session.execute(text(select_sql)).fetchall()[0]["custom_attribute"]
    update_sql_prefix = f"UPDATE \"{model_file.id}_{sublayer_index}_NODE_VERSION\" SET custom_attribute = "
    update_sql_postfix = f"WHERE node_index = {node_index}"
    for k, v in _customAttribute.items():
        if v and k in custom_attribute:
            print(f"{k},{v}")
            # 目前只能更新基本数据类型，且全部转换为string
            update_sql = update_sql_prefix + f"(jsonb_set(custom_attribute,'{{{k}}}','\"{v}\"'))" + update_sql_postfix
            session.execute(text(update_sql))
    session.commit()
    print(custom_attribute)
    session.remove()
    return {
        "code": 200,
        "data": custom_attribute
    }


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/{layer_index}/sublayers/{sublayer_index}/metadata")
async def get_sublayer_meta(model_file_id: int, layer_index: int, sublayer_index: int, project_id: int,
                            response: Response):
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    sublayer_id_list = slpk_model.sublayer_version_id
    sublayer = session.query(SublayerVersion). \
        filter(SublayerVersion.id.in_(sublayer_id_list)).filter_by(sublayer_index=sublayer_index).first()
    sublayer_meta = session.query(SublayerMetaVersion).filter_by(id=sublayer.sublayer_meta_version_id).first()
    response.headers["content-encoding"] = "gzip"
    session.remove()
    return sublayer_meta.meta


@router.get("/{project_id}/slpk/{model_file_id}/SceneServer/layers/{layer_index}/metadata")
async def get_scene_layer_meta(model_file_id: int, layer_index: int, project_id: int, response: Response):
    session = SessionDispatcher().get_session(f"proj_{project_id}")
    slpk_model = search_one_in_db(session, ModelFile, id=model_file_id)
    metadata = session.query(MetaVersion).filter_by(id=slpk_model.meta_version_id).first()
    response.headers["content-encoding"] = "gzip"
    session.remove()
    return metadata.meta
