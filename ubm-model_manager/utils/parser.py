import re
from db_model.slpk_model import *


def parse_path(path: str):
    """
    根据路径解析出对应的数据库
    :param path:
    :return: 数据库名
    """
    layer = re.search("/layers/\d+", path)
    sublayer_meta = re.search("sublayers/\d+/metadata", path)
    sublayer = re.search("sublayers/\d+/3dSceneLayer", path)
    nodepage = re.search("sublayers/\d+/nodepage", path)
    node_attr = re.search("sublayers/\d+/nodes/\d+/attribute", path)
    node_text = re.search("sublayers/\d+/nodes/\d+/textures", path)
    node_geom = re.search("sublayers/\d+/nodes/\d+/geometries", path)
    # print(path)
    # project_id = re.findall("project/\d+/", path)[0].strip("project/")
    # model_file_id = re.findall("model_file/\d+/", path)[0].strip("model_file/")
    # print(project_id)
    # print(model_file_id)
    res: dict = {}
    if layer:
        res["type"] = "layer"
        res["data"] = int(layer.group(0).replace("/layers/", "")), LayerVersion
    elif "/layers/metadata" in path:
        res["type"] = "metadata"
        res["data"] = 0, MetaVersion  # FIXME
    elif sublayer_meta:
        res["type"] = "sublayer_meta"
        res["data"] = int(re.findall("\d+", sublayer_meta.group(0))[0]), SublayerMetaVersion
    elif sublayer:
        res["type"] = "sublayer"
        res["data"] = int(re.findall("\d+", sublayer.group(0))[0]), SublayerInfoVersion
    elif nodepage:
        res["type"] = "nodepage"
        res["data"] = int(re.findall("\d+", nodepage.group(0))[0]), NodepageVersion
    elif node_attr:
        sublayer_idx, node_idx = re.findall("\d+", node_attr.group(0))
        res["type"] = "node_attr"
        res["data"] = int(sublayer_idx), int(node_idx)
    elif node_text:
        sublayer_idx, node_idx = re.findall("\d+", node_text.group(0))
        res["type"] = "node_text"
        res["data"] = int(sublayer_idx), int(node_idx)
    elif node_geom:
        sublayer_idx, node_idx = re.findall("\d+", node_geom.group(0))
        res["type"] = "node_geom"
        res["data"] = int(sublayer_idx), int(node_idx)
    else:
        raise NotImplemented
    return res


if __name__ == "__main__":
    print(parse_path("project/1/model_file/1/sublayers/2/nodes/3/attribute"))
