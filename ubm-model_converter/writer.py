import json
import os
import shutil
import struct
import sys
import threading
import time
from typing import List
from wand import image
from .config import config
from .model.slpk_model.merged_node import MergedNode
from .model.slpk_model.node import Node
from .model.slpk_model.node_info import NodeInfo
from .model.slpk_model.slpk import SLPK
from loguru import logger
from .model.slpk_model.sublayer import Sublayer
from .model.ubm_model.attribute import Attribute
from .model.ubm_model.material import Material
from .utils.api_handler import upload_json_data, upload_bin, upload_bin_by_file
from .utils.path_handler import absolute_to_relative_path
from .utils.compress_file import build_slpk, compress_to_gz
from .utils.upload_file import upload, delete_file
from timeit import default_timer as timer
from concurrent.futures import ThreadPoolExecutor, as_completed

if getattr(sys, "frozen", False):
    work_path = os.path.dirname(sys.executable)
else:
    work_path = os.path.dirname(__file__)


class Writer:
    def __init__(self, slpk: SLPK):
        self.slpk_root = None
        self.slpk = slpk
        self.thread_pool = ThreadPoolExecutor(
            max_workers=config["model_manager"]["upload_worker"]
        )
        self.task_list = []
        self.image_cache = {}
        self.lock = threading.Lock()

    def to_file(self, fp: str):
        logger.debug(f"out put path: {fp}")
        self.create_dir()
        self.write_init_info()
        self.write_sublayers()
        self.finish()

    def to_db(self, fp: str, project_id: int, model_file_id: int):
        logger.debug(f"out put path: {fp}")
        self.create_dir()
        self.upload_init_info(project_id, model_file_id)
        as_completed(self.task_list)
        self.upload_sublayers(project_id, model_file_id)
        self.thread_pool.shutdown(wait=True)

    def create_dir(self):
        filename = os.path.splitext(self.slpk.name)[0]
        self.slpk_root = os.path.join(config["output_file_root"], filename)
        # create dir structure
        if not os.path.exists(self.slpk_root):
            os.makedirs(self.slpk_root)
            os.makedirs(os.path.join(self.slpk_root, "statistics"))
            os.makedirs(os.path.join(self.slpk_root, "sublayers"))
        else:
            logger.warning(f"目录 {self.slpk_root} 已存在, 正在删除...")
            shutil.rmtree(self.slpk_root)
            os.makedirs(self.slpk_root)
            os.makedirs(os.path.join(self.slpk_root, "statistics"))
            os.makedirs(os.path.join(self.slpk_root, "sublayers"))
            # raise FileExistsError

    def upload_init_info(self, project_id: int, model_file_id):
        self.task_list.append(
            self.thread_pool.submit(
                upload_json_data,
                project_id,
                model_file_id,
                f"project/{project_id}/model_file/{model_file_id}/layers/metadata",
                self.slpk.layer.meta,
            )
        )
        upload_json_data(
            project_id,
            model_file_id,
            f"project/{project_id}/model_file/{model_file_id}/layers/0",
            self.slpk.layer.to_dict())

    def upload_sublayers(self, project_id: int, model_file_id):
        # task_list = []
        # with ThreadPoolExecutor(max_workers=config["max_worker"]) as t:
        for idx, sublayer in enumerate(self.slpk.sublayers):
            sublayer_dir = os.path.join(self.slpk_root, f"sublayers", f"{idx}")
            res_sublayer_dir = f"project/{project_id}/model_file/{model_file_id}/sublayers/{idx}/"
            os.makedirs(sublayer_dir)
            # nodepages_dir = os.path.join(sublayer_dir, "nodepages")
            # os.makedirs(nodepages_dir)
            nodes_dir = os.path.join(sublayer_dir, "nodes")
            os.makedirs(nodes_dir)
            # 创建每层的metadata以及3dSceneLayer
            # task_list.append(
            self.thread_pool.submit(
                upload_json_data,
                project_id,
                model_file_id,
                os.path.join(res_sublayer_dir, "metadata"),
                sublayer.info.meta,
            )
            # )
            # task_list.append(
            self.thread_pool.submit(
                upload_json_data,
                project_id,
                model_file_id,
                os.path.join(res_sublayer_dir, "3dSceneLayer"),
                sublayer.info.scene_layer,
            )

            self.upload_nodepage(project_id, model_file_id, idx, sublayer)
            # )
            # 创建每个node的文件夹
            # 处理属性
            logger.debug(
                f"upload sublayer: {sublayer.info.scene_layer.get('name')}, node count: {len(sublayer.nodes)}"
            )
            for index, node in enumerate(sublayer.merged_nodes):
                node_dir = os.path.join(nodes_dir, f"{index}")
                # self.write_merged_nodes(node, node_dir, sublayer.attrnamelist)
                # task_list.append(
                self.thread_pool.submit(
                    self.upload_merged_nodes,
                    project_id,
                    model_file_id,
                    node,
                    node_dir,
                    index,
                    idx,
                )
                # )

        # as_completed(task_list)
        logger.info("upload sublayers complete.")

    def upload_nodepage(self, project_id, model_file_id, idx: int, sublayer: Sublayer):
        np = sublayer.nodepage
        self.thread_pool.submit(
            upload_json_data,
            project_id,
            model_file_id,
            f"project/{project_id}/model_file/{model_file_id}/sublayers/{idx}/nodepage",
            {"nodes": np.nodes},
        )

    def upload_merged_nodes(self, project_id, model_file_id, node: MergedNode, node_dir: str, index: int,
                            sublayer_idx: int):
        geometries_dir = os.path.join(node_dir, "geometries")
        os.makedirs(geometries_dir)
        # 创建texture且复制图片
        if node.has_texture:
            # logger.debug("开始处理纹理图片")
            texture_dir = os.path.join(node_dir, "textures")
            os.makedirs(texture_dir)
            oldmap = node.diffuse_map[0]
            if oldmap not in self.image_cache:
                logger.debug(f"图片纹理原路径：{oldmap}")
                if not os.path.isfile(oldmap):
                    logger.warning("图片不存在")
                else:
                    shutil.copy(oldmap, texture_dir + "\\" + f"{0}.jpg")  # 复制文件
                    with image.Image(filename=texture_dir + "\\" + f"{0}.jpg") as img:  # 转换为dds
                        img_size = img.size
                        logger.debug(f"origin size: {img_size}")
                        if img_size[0] != img_size[1]:
                            new_size = min(img_size)
                            img.transform(f"{new_size}x{new_size}", "100%")
                            for i in range(1, 20):
                                if (1 << i) < new_size < (1 << (i + 1)):  # TODO: here maybe cause some problems.
                                    new_size = 1 << i if abs((1 << i) - new_size) < abs(
                                        (1 << (i + 1)) - new_size) else 1 << (i + 1)
                                    logger.debug(f"new size: {new_size}")
                                    break
                            img.resize(new_size, new_size)
                        img.compression = "dxt3"
                        with self.lock:
                            self.image_cache[oldmap] = img.make_blob(format='dds')
                        # img.save(filename=texture_dir + f"\\{0}_{0}_1.bin.dds")
                        # blob_data = img.make_blob(format='dds')
                        # upload_bin_by_file(project_id, model_file_id, self.slpk_root, texture_dir + f"\\{0}_{0}_1.bin.dds")
            else:
                logger.debug(f"use cache：{oldmap}")
            blob_data = self.image_cache[oldmap]
            upload_bin(project_id, model_file_id,
                       absolute_to_relative_path(texture_dir + f"/0_0_1.bin.dds", self.slpk_root), blob_data)
        # 写属性
        # 线程里不能创建线程
        upload_json_data(project_id, model_file_id,
                         f"project/{project_id}/model_file/{model_file_id}/sublayers/{sublayer_idx}/nodes/{index}/attribute",
                         node.attribute)
        # self.thread_pool.submit(
        #     upload_json_data,
        #     project_id,
        #     model_file_id,
        #     f"{model_file_id}/sublayers/{sublayer_idx}/nodes/{index}/attribute",
        #     node.attribute,
        # )
        # 处理geometry 0.bin头文件
        # 生成geometry中的0.bin
        bindoc_dir = os.path.join(node_dir, "geometries\\0.bin")
        # 写入geometry 0.bin
        with open(os.path.join(geometries_dir, "0.bin"), "ab") as fp:
            fp.write(node.polymesh_header_data)
            for position in node.polymesh_position_bytes:
                fp.write(position)
            for uv in node.polymesh_uv_bytes:
                fp.write(uv)
            for normal in node.polymesh_normal_bytes:
                fp.write(normal)
            for color in node.polymesh_color_bytes:
                fp.write(color)
            # for uvregion in node.polymesh_uvregion_bytes:
            #     fp.write(uvregion)
            for feature_id in node.feature_id_bytes:
                fp.write(feature_id)
            for face_range in node.face_range_bytes:
                fp.write(face_range)
        # Draco压缩
        model = os.path.join(geometries_dir, "1.bin")
        draco_encoder = os.path.join(
            work_path,
            "../thirdparty/draco_encoder.exe",
        )
        # TODO: 直接获取压缩后的二进制数据

        res = Writer.exec_cmd(
            rf'"{draco_encoder}" -i "{bindoc_dir}" -o "{model}" --t {0}'
        )
        # print(res)
        if "Failed" in res:
            logger.warning(f"Failed to draco")
            return

        # upload geo 1.bin.gz
        upload_bin_by_file(project_id, model_file_id, self.slpk_root, model)

    def write_init_info(self):
        """
        总体的 3dSceneLayer.json
        metadata.json
        :return:
        """
        with open(
                os.path.join(self.slpk_root, "metadata.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(self.slpk.layer.meta, f, ensure_ascii=False)

        with open(
                os.path.join(self.slpk_root, "3dSceneLayer.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(self.slpk.layer.to_dict(), f, ensure_ascii=False)

    def write_sublayers(self):
        def to_file(path, data):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        task_list = []
        with ThreadPoolExecutor(max_workers=config["max_worker"]) as t:
            for idx, sublayer in enumerate(self.slpk.sublayers):
                sublayer_dir = os.path.join(self.slpk_root, f"sublayers/{idx}")
                os.makedirs(sublayer_dir)
                nodepages_dir = os.path.join(sublayer_dir, "nodepages")
                os.makedirs(nodepages_dir)
                nodes_dir = os.path.join(sublayer_dir, "nodes")
                os.makedirs(nodes_dir)
                # 创建每层的metadata以及3dSceneLayer
                task_list.append(
                    t.submit(
                        to_file,
                        os.path.join(sublayer_dir, "metadata.json"),
                        sublayer.info.meta,
                    )
                )
                task_list.append(
                    t.submit(
                        to_file,
                        os.path.join(sublayer_dir, "3dSceneLayer.json"),
                        sublayer.info.scene_layer,
                    )
                )
                self.write_nodepage(idx, sublayer)
                # 创建每个node的文件夹
                # 处理属性
                logger.info(
                    f"write sublayer: {sublayer.info.scene_layer.get('name')}, merged node count: {len(sublayer.merged_nodes)}, node count: {len(sublayer.nodes)}"
                )
                for index, node in enumerate(sublayer.merged_nodes):
                    node_dir = os.path.join(nodes_dir, f"{index}")
                    # self.write_merged_nodes(node, node_dir, sublayer.attrnamelist)
                    task_list.append(
                        t.submit(
                            self.write_merged_nodes,
                            node,
                            node_dir,
                            sublayer.attrnamelist,
                        )
                    )

        as_completed(task_list)
        logger.info("write sublayers complete.")

    def write_nodepage(self, idx: int, sublayer: Sublayer):
        np = sublayer.nodepage
        for i in range(0, len(np.nodes), config["nodepage_size"]):
            nodes = np.nodes[i: i + config["nodepage_size"]]
            with open(
                    os.path.join(self.slpk_root, SLPK.nodepage_path_tamp.format(idx, i // config["nodepage_size"]))
                    + ".json",
                    "w",
                    encoding="utf-8",
            ) as f:
                json.dump({"nodes": nodes}, f, ensure_ascii=False)

    def write_merged_nodes(self, node: MergedNode, node_dir: str, subattrnamelist: List[str]):
        attributes_dir = os.path.join(node_dir, "attributes")
        os.makedirs(attributes_dir)
        # features_dir = os.path.join(node_dir, "features")
        # os.makedirs(features_dir)
        geometries_dir = os.path.join(node_dir, "geometries")
        os.makedirs(geometries_dir)
        # 创建texture且复制图片
        if node.has_texture:
            # logger.debug("开始处理纹理图片")
            texture_dir = os.path.join(node_dir, "textures")
            os.makedirs(texture_dir)
            oldmap = node.diffuse_map[0]
            if oldmap not in self.image_cache:
                logger.debug(f"图片纹理原路径：{oldmap}")
                if not os.path.isfile(oldmap):
                    logger.warning("图片不存在")
                else:
                    shutil.copy(oldmap, texture_dir + "\\" + f"{0}.jpg")  # 复制文件
                    with image.Image(filename=texture_dir + "\\" + f"{0}.jpg") as img:  # 转换为dds
                        img_size = img.size
                        logger.debug(f"origin size: {img_size}")
                        if img_size[0] != img_size[1]:
                            new_size = min(img_size)
                            img.transform(f"{new_size}x{new_size}", "100%")
                            for i in range(1, 20):
                                if (1 << i) < new_size < (1 << (i + 1)):  # TODO: here maybe cause some problems.
                                    new_size = 1 << i if abs((1 << i) - new_size) < abs(
                                        (1 << (i + 1)) - new_size) else 1 << (i + 1)
                                    logger.debug(f"new size: {new_size}")
                                    break
                            img.resize(new_size, new_size)
                        img.compression = "dxt3"
                        with self.lock:
                            self.image_cache[oldmap] = img.make_blob(format='dds')
                        img.save(filename=texture_dir + f"\\{0}_{0}_1.bin.dds")
            else:
                # logger.debug(f"use cache：{oldmap}")
                with open(texture_dir + f"\\{0}_{0}_1.bin.dds", "wb") as fp:
                    fp.write(self.image_cache[oldmap])
                # self.image_cache[oldmap].save(filename=texture_dir + f"\\{0}_{0}_1.bin.dds")
        # 生成属性文件夹
        for idx, attrname in enumerate(subattrnamelist):
            attr_dir = os.path.join(attributes_dir, f"f_{idx}")
            os.makedirs(attr_dir)
        # 生成geometry中的0.bin
        bindoc_dir = os.path.join(node_dir, "geometries\\0.bin")
        # 写属性
        for idx, attr_bytes in enumerate(node.attribute_value_bytes_list):
            attr_dir = os.path.join(attributes_dir, f"f_{idx}")
            with open(os.path.join(attr_dir, "0.bin"), "wb") as fp:
                fp.write(node.node_count_bytes)
                if idx != 0:
                    fp.write(node.attribute_total_size_bytes[idx])
                    for attr_size_byte in node.attribute_size_bytes_list[idx]:
                        fp.write(attr_size_byte)
                for attr_byte in attr_bytes:
                    fp.write(attr_byte)
        # 处理geometry 0.bin头文件
        # 写入geometry 0.bin
        with open(os.path.join(geometries_dir, "0.bin"), "ab") as fp:
            fp.write(node.polymesh_header_data)
            for position in node.polymesh_position_bytes:
                fp.write(position)
            for normal in node.polymesh_normal_bytes:
                fp.write(normal)
            for uv in node.polymesh_uv_bytes:
                fp.write(uv)
            for color in node.polymesh_color_bytes:
                fp.write(color)
            for uvregion in node.polymesh_uvregion_bytes:
                fp.write(uvregion)
            for feature_id in node.feature_id_bytes:
                fp.write(feature_id)
            for face_range in node.face_range_bytes:
                fp.write(face_range)
        # Draco压缩
        model = os.path.join(geometries_dir, "1.bin")
        draco_encoder = os.path.join(
            work_path,
            "../thirdparty/draco_encoder.exe",
        )
        if config["use_deck"]:
            res = Writer.exec_cmd(
                rf'"{draco_encoder}" -i "{bindoc_dir}" -o "{model}" --t {0} --use-deck'
            )

        else:
            # pass  # TODO: 调整draco以适配arcgis前端，目前使用0.bin
            res = Writer.exec_cmd(
                rf'"{draco_encoder}" -i "{bindoc_dir}" -o "{model}" --t {1}'
            )
        # print(res)
        if "Failed" in res:
            logger.warning(f"Failed to draco")

    def finish(self):
        """
        打包为 slpk 文件
        :return: None
        """
        logger.info("start compress files.")
        task_list = []
        with ThreadPoolExecutor(max_workers=config["max_worker"]) as t:
            for root, ds, fs in os.walk(self.slpk_root):
                for f in fs:
                    task_list.append(t.submit(compress_to_gz, os.path.join(root, f)))
                # if f != "metadata.json":
                # compress_to_gz(os.path.join(root, f))
        # wait thread complete
        as_completed(task_list)

        if not config["server"]["is_server"]:
            logger.info("start build slpk file.")
            build_slpk(
                os.path.join(config["output_file_root"], f"{os.path.splitext(self.slpk.name)[0]}.slpk"),
                self.slpk_root,
            )
            logger.info(f"build slpk file success. output to : {self.slpk_root}.slpk")

    # for test, upload slpk file to test server.
    def upload(self):
        if not os.path.exists(f"{self.slpk_root}.slpk"):
            logger.error(f"no slpk file name {self.slpk.name}.slpk")
            raise FileNotFoundError

        if not delete_file(self.slpk.name):
            logger.warning("delete remote slpk failed, maybe file not exist")

        logger.info("start upload.")
        if upload(f"{self.slpk_root}.slpk"):
            logger.info("upload success.")
        else:
            logger.error("upload failed.")

    @staticmethod
    def exec_cmd(cmd):
        r = os.popen(cmd)
        text = r.read()
        r.close()
        return text
