import asyncio
import math

import aiohttp
import requests
import os


def print_long_info(info: str, info_len: int = 81):
    """
    Used to print long information with separation '-'

    :param info: information to be printed
    :param info_len: whole length of information and separator , default value 81
    :return:
    """
    if info_len < info.__len__():
        raise NotImplemented
    else:
        sep_num = info_len - info.__len__()
        separator = sep_num * '-'
        print(" " + separator[:sep_num // 2] + info + separator[sep_num // 2 + 1:])


def traverse_files_with_extension(folder_path, extension: tuple[str, ...] = ".jrvt"):
    """
    traverse model files with specific extension

    :param folder_path: the model folder path
    :param extension: model extension, default extension: .jrvt
    :return: the model filenames list
    """
    model_files = []
    # 获取文件夹中的所有文件和文件夹名称
    file_names = os.listdir(folder_path)
    # 遍历文件夹中的所有文件
    for file_name in file_names:
        file_path = os.path.join(folder_path, file_name)  # 文件的完整路径
        # 判断是否为文件
        if os.path.isfile(file_path) and file_name.endswith(extension):
            # 将模型文件加入到待处理的模型列表中
            model_files.append(file_path)

    return model_files


def create_project_test(url) -> dict:
    """
    Create project in the indicated project for test

    :param url: model manager's url
    :return: project http response json
    """
    response = requests.post(
        url=f"{url}/project/",
        json={
            "name": "smoke"
        })
    if response.status_code == 200:
        return response.json()


def create_application_test(url, project_id, application_name=None) -> dict:
    """
    Create application in the indicated project for test

    :param url: model_manager url
    :param project_id: the projection id for test
    :param application_name: application name
    :return: application http response json
    """
    response = requests.post(
        url=f"{url}/project/{project_id}/application",
        json={"name": application_name}
    )
    if response.status_code == 200:
        return response.json()


def create_model_attached_to_application_test(url, project_id, application_id) -> dict:
    response = requests.post(
        url=f"{url}/project/{project_id}/model",
        json={
            "name": "string",
            "version": 1,
            "current_model_file_id": 0,
            "attach_to_apps": [],
            "remove_from_apps": []
        }
    )
    if response.status_code == 200:
        response_json = response.json()
        attached_model_id = response.json()["data"]["id"]
        print(f"\nModel {attached_model_id} Created Successfully, Model Info : {response_json}")
    else:
        raise NotImplemented
    response = requests.post(
        url=f"{url}/project/{project_id}/application/{application_id}/attach?attached_model_id={attached_model_id}")
    if response.status_code == 200:
        print(f"\nModel {attached_model_id} Successfully Attached To Application {application_id}")
        return response_json


def upload_model_file_test(url, project_id, model_id, file_path) -> dict:
    with open(file_path, "rb") as f:
        response = requests.post(
            url=f"{url}/project/{project_id}/model-file/upload?model_file_id={model_id}",
            files={"file": f}
        )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"\nModel {model_id} Fail to Upload, Upload Info : {response.json()} ")
        raise NotImplemented


def get_convert_state(url, project_id, model_file_id):
    response = requests.get(
        url=f"{url}/project/{project_id}/model-file/convert/{model_file_id}")
    if response.status_code == 200:
        convert_state = response.json()["data"]["state"]
        return convert_state
    else:
        raise NotImplemented


async def convert_model_file_test(url, project_id, model_file_id):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{url}/project/{project_id}/model-file/convert",
                json={"model_file_id": model_file_id}) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented


async def get_whole_model_test(url, project_id, model_file_id):
    """
    Imitate the frontend to post requests to get whole slpk model by sequence traversal

    :param url: Model Manger's URL
    :param project_id:
    :param model_file_id:
    :return:
    """

    async def get_layer(project_id: int, model_file_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0") as response:
                if response.status == 200:
                    layer_json = await response.json()
                    return layer_json
                else:
                    raise NotImplemented

    async def get_layer_meta(project_id: int, model_file_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/metadata") as response:
                if response.status == 200:
                    layer_meta_json = await response.json()
                    return layer_meta_json
                else:
                    raise NotImplemented

    async def get_sublayers(project_id: int, model_file_id: int, layer_json: dict):
        sublayers = list(filter(lambda item: item["layerType"] == "3DObject", layer_json.get("sublayers")))
        sublayers_list = list()
        for sublayer in sublayers:
            sublayer_index = sublayer["id"]
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers/"
                        f"{sublayer_index}") as response:
                    if response.status == 200:
                        sublayer_json = await response.json()
                        sublayers_list.append(sublayer_json)
                    else:
                        raise NotImplemented
        return sublayers_list

    async def get_sublayer_meta(project_id: int, model_file_id: int, sublayer_index: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer"
                                   f"/layers/0/sublayers/{sublayer_index}/metadata") as response:
                if response.status == 200:
                    sublayer_meta_json = await response.json()
                    return sublayer_meta_json
                else:
                    raise NotImplemented

    async def get_nodepages(project_id: int, model_file_id: int, sublayer_index: int, nodes_per_page: int = 64):
        sublayer_meta_json = await get_sublayer_meta(project_id, model_file_id, sublayer_index)
        nodes_count = sublayer_meta_json["nodeCount"]
        nodepages_count = math.ceil(nodes_count / nodes_per_page)
        nodepages_list = list()
        async with aiohttp.ClientSession() as session:
            for nodepage_index in range(nodepages_count):
                async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers"
                                       f"/{sublayer_index}/nodepages/{nodepage_index}") as response:
                    if response.status == 200:
                        nodepage_json = await response.json()
                        nodepages_list.append(nodepage_json)
                    else:
                        raise NotImplemented
        return nodepages_list

    async def get_node(project_id: int, model_file_id: int, sublayer_index: int, node_index: int,
                       attributes_keys: list):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers/"
                                   f"{sublayer_index}/nodes/{node_index}/geometries/1") as response:
                if response.status == 200:
                    pass
                else:
                    raise NotImplemented
            for attributes_key in attributes_keys:
                async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers"
                                       f"/{sublayer_index}/nodes/{node_index}/"
                                       f"attributes/{attributes_key}/0") as response:
                    if response.status == 200:
                        pass
                    else:
                        raise NotImplemented

    layer_json = await get_layer(project_id, model_file_id)

    print_long_info("LAYER JSON START")
    print(f"\n{layer_json}\n")
    print_long_info("LAYER JSON END")

    layer_meta_json = await get_layer_meta(project_id, model_file_id)

    print_long_info("LAYER METADATA JSON START")
    print(f"\n{layer_meta_json}\n")
    print_long_info("LAYER METADATA JSON END")

    sublayers_list = await get_sublayers(project_id, model_file_id, layer_json)
    for sublayer_json in sublayers_list:
        sublayer_index = sublayer_json["id"]

        print_long_info(f"SUBLAYER {sublayer_index} JSON START")
        print(f"\n{sublayer_json}\n")
        print_long_info(f"SUBLAYER {sublayer_index} JSON END")

        sublayer_meta_json = await get_sublayer_meta(project_id, model_file_id, sublayer_index)

        print_long_info(f"SUBLAYER {sublayer_index} METADATA JSON START")
        print(f"\n{sublayer_meta_json}\n")
        print_long_info(f"SUBLAYER {sublayer_index} METADATA JSON END")

        attribute_storage_info = sublayer_json["attributeStorageInfo"]
        keys = list()
        for storage in attribute_storage_info:
            keys.append(storage["key"])

        nodepages_list = await get_nodepages(project_id, model_file_id, sublayer_index)
        for nodepage_json in nodepages_list:

            print_long_info(f"SUBLAYER {sublayer_index} NODEPAGE {nodepages_list.index(nodepage_json)} JSON START")
            print(f"\n{nodepage_json}\n")
            print_long_info(f"SUBLAYER {sublayer_index} NODEPAGE {nodepages_list.index(nodepage_json)} JSON END")

            for node_json in nodepage_json["nodes"]:
                node_index = node_json["index"]
                if node_index == 0 and "parentIndex" not in node_json:
                    pass
                else:
                    await get_node(project_id, model_file_id, sublayer_index, node_index - 1, keys)


async def create_material_attribute_test(url, project_id, model_file_id, material_attribute):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{url}/project/{project_id}/slpk/{model_file_id}/MaterialAttribute",
                json={"attribute": material_attribute}) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented


async def edit_material_attribute_test(url, project_id, model_file_id, material_attribute_id, material_attribute):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{url}/project/{project_id}/slpk/{model_file_id}/MaterialAttribute/{material_attribute_id}",
                json={"attribute": material_attribute}) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented


async def get_class_attribute_test(url, project_id, model_file_id, sublayer_index):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers/"
                               f"{sublayer_index}/ClassAttribute") as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented


async def edit_class_attribute_test(url, project_id, model_file_id, sublayer_index, class_attribute):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers/"
                                f"{sublayer_index}/ClassAttribute",
                                json=class_attribute) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented


async def get_custom_attribute_test(url, project_id, model_file_id, sublayer_index, node_index):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers/"
                               f"{sublayer_index}/nodes/{node_index}/CustomAttribute") as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented


async def edit_custom_attribute_test(url, project_id, model_file_id, sublayer_index, node_index, custom_attribute):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url}/project/{project_id}/slpk/{model_file_id}/SceneServer/layers/0/sublayers/"
                               f"{sublayer_index}/nodes/{node_index}/CustomAttribute",
                               json=custom_attribute) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise NotImplemented
