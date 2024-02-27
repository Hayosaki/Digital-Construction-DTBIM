import asyncio
import os
import time

import pytest
from numpy import uint

from .utils.api import traverse_files_with_extension, create_application_test, create_project_test, \
    create_model_attached_to_application_test, upload_model_file_test, convert_model_file_test, \
    get_convert_state, print_long_info, get_whole_model_test, edit_class_attribute_test, \
    edit_material_attribute_test, edit_custom_attribute_test, create_material_attribute_test


@pytest.mark.run(order=1)
def test_init(test_files_root_path, data):
    print_long_info("SMOKE TEST START")
    print(f"\nTest Files Root Path: {test_files_root_path}")

    paths = traverse_files_with_extension(test_files_root_path, tuple('.jrvt'))
    print("\nTest Files:")
    data["model_num"] = len(paths)
    for index in range(data["model_num"]):
        print(f"File {index} Path: {paths[index]}")
    data["model_paths"] = paths


@pytest.mark.run(order=2)
def test_create_project_and_application(config_model_manager, data):
    print_long_info("CREATE PROJECT AND APPLICATION TEST START")
    host, port = config_model_manager
    url = f"http://{host}:{port}"

    project_json = create_project_test(url)
    project_id = project_json["data"]["id"]
    data["project_id"] = project_id
    print(f"\nProject {project_id} Created Successfully, Project Info :\n{project_json}")

    application_json = create_application_test(url, project_id, "test")
    application_id = application_json["data"]["id"]
    data["application_id"] = application_id
    print(f"\nApplication {application_id} Created Successfully, Application Info :\n{application_json}")
    print_long_info("CREATE PROJECT AND APPLICATION TEST END")


@pytest.mark.run(order=3)
def test_upload_models(config_model_manager, data):
    host, port = config_model_manager
    url = f"http://{host}:{port}"
    project_id = data["project_id"]
    application_id = data["application_id"]
    paths = data["model_paths"]
    num = data["model_num"]
    model_ids = []
    model_file_ids = []

    print_long_info("UPLOAD MODEL FILE TEST START")

    for index in range(num):
        attach_response = create_model_attached_to_application_test(url, project_id, application_id)
        model_id = attach_response["data"]["id"]
        model_ids.append(model_id)
    data["model_ids"] = model_ids
    print(f"\nAll Models Created And Attached to Application Successfully")

    for index in range(num):
        print(f"\nModel {model_ids[index]} Start to Upload, Filename : {os.path.basename(paths[index])}")
        upload_response = upload_model_file_test(url, project_id, model_ids[index], paths[index])
        model_file_id = upload_response["data"]["model_file_id"]
        model_file_ids.append(model_file_id)

    data["model_file_ids"] = model_file_ids
    print("\nALL MODELS UPLOADING IN BACKGROUND")
    print_long_info("UPLOAD MODEL FILE TEST END")


@pytest.mark.run(order=4)
@pytest.mark.asyncio
async def test_convert_models(config_model_manager, data):
    host, port = config_model_manager
    url = f"http://{host}:{port}"
    project_id = data["project_id"]
    model_file_ids = data["model_file_ids"]
    num = data["model_num"]
    uploaded_models = [i for i in range(num)]

    print_long_info("CONVERT MODEL FILE TEST START")

    async def polling():
        print("Polling For Uploaded Models")
        while True:
            for index in uploaded_models:
                state = get_convert_state(url, project_id, model_file_ids[index])
                if state == "created":
                    print(f"\nModel {model_file_ids[index]} Uploaded Successfully")
                    uploaded_models.remove(index)
                    await convert_model_file_test(url, project_id, model_file_ids[index])
                    print(f"\nModel {model_file_ids[index]} Start to Convert")
                elif state == "transfer":
                    await asyncio.sleep(1)
                else:
                    print_long_info("UNACCEPTED CONDITION: MODEL ALREADY UPLOADED")
                    raise NotImplemented
            if not uploaded_models:
                print(f"\nAll ModelFiles Uploaded Successfully\n")
                return

    await polling()
    print_long_info("CONVERT MODEL FILE TEST END")


@pytest.mark.run(order=5)
@pytest.mark.asyncio
async def test_model_get(config_model_manager, data):
    host, port = config_model_manager
    url = f"http://{host}:{port}"
    project_id = data["project_id"]
    model_file_ids = data["model_file_ids"]
    num = data["model_num"]
    uploaded_models = [i for i in range(num)]

    print_long_info("GET MODEL TEST START")

    async def polling():
        print("\nPolling For Converted Models")
        while True:
            for index in uploaded_models:
                state = get_convert_state(url, project_id, model_file_ids[index])
                if state == "success":
                    print(f"\nModel {model_file_ids[index]} Converted Successfully")
                    uploaded_models.remove(index)
                    await get_whole_model_test(url, project_id, model_file_ids[index])
                elif state == "fail":
                    print_long_info(f"MODEL {model_file_ids[index]} FAILED TO CONVERT,TEST DISCONTINUE")
                    raise NotImplemented
                elif state == "processing" or "waiting":
                    await asyncio.sleep(1)
                else:
                    raise NotImplemented
            if not uploaded_models:
                print(f"\nAll ModelFiles Converted Successfully")
                return

    await polling()
    for index in range(num):
        await get_whole_model_test(url, project_id, model_file_ids[index])
    print_long_info("GET MODEL TEST END")


# 这里的修改属性可以单独测试，默认取所有的第一个可编辑对象进行编辑，后续对测试用例及测试逻辑进行优化
@pytest.mark.run(order=6)
@pytest.mark.asyncio
async def test_attribute_edit(config_model_manager, data, config_test_cases):
    """
    默认编辑 id为1的模型文件的材质属性，id为1的子层的类属性及1_0_NODEVERSION的自定义属性
    """
    host, port = config_model_manager
    url = f"http://{host}:{port}"
    project_id = 114

    print_long_info("EDIT ATTRIBUTE TEST START")

    print("\nLoad Attribute Test Cases")

    material_attribute_cases = config_test_cases["materialAttributeCases"]
    class_attribute_cases = config_test_cases["classAttributeCases"]
    custom_attribute_cases = config_test_cases["customAttributeCases"]

    print(f"\nMaterial Attribute Cases:\n{material_attribute_cases}")
    print(f"\nClass Attribute Cases:\n{material_attribute_cases}")
    print(f"\nCustom Attribute Cases:\n{material_attribute_cases}")

    material_attribute = await create_material_attribute_test(
        url=url,
        project_id=project_id,
        model_file_id=1,
        material_attribute=material_attribute_cases["materialAttributeForCreate"]
    )
    print(f"\nMaterialAttribute Created Successfully, MaterialAttribute Info: {material_attribute}")

    bind_response = await edit_material_attribute_test(
        url=url,
        project_id=project_id,
        model_file_id=1,
        material_attribute_id=material_attribute["data"]["id"],
        material_attribute=None
    )
    print(f"\nMaterialAttribute Bound With ModelFile {1} Successfully. Info: {bind_response}")

    update_response = await edit_material_attribute_test(
        url=url,
        project_id=project_id,
        model_file_id=1,
        material_attribute_id=material_attribute["data"]["id"],
        material_attribute=material_attribute_cases["materialAttributeForEdit"]
    )
    print(f"MaterialAttribute Updated Successfully, ClassAttribute Info: {update_response}")

    class_attribute = await edit_class_attribute_test(
        url=url,
        project_id=project_id,
        model_file_id=1,
        sublayer_index=0,
        class_attribute=class_attribute_cases
    )
    print(f"ClassAttribute Updated Successfully, ClassAttribute Info: {class_attribute}")