import json

import pytest
from configparser import ConfigParser


def pytest_addoption(parser):
    parser.addoption(
        "--path", action="store", default=None,
        help="Please input the model directory path"
    )


@pytest.fixture
def test_files_root_path(request):
    return request.config.getoption("--path")


@pytest.fixture
def config_model_manager():
    config = ConfigParser()
    config.read('config.ini')
    return config.get('ModelManager', 'host'), config.get('ModelManager', 'port')


@pytest.fixture
def config_test_cases():
    with open('tests/testcases/edit_attribute.json', 'r', encoding='utf-8') as file:
        test_cases = json.load(file)
    return test_cases


# 用于用例之间传递数据
test_data = {}


@pytest.fixture
def data():
    """
    用于测试执行时不同用例传递参数

    :return:
    """
    return test_data
