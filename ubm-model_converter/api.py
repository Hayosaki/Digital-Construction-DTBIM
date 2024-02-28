import ntpath
import os
import sys
import traceback

import requests
from loguru import logger
# from huey import SqliteHuey, RedisHuey
from celery import Celery
from .model.slpk_model.slpk import SLPK
from .reader import Reader
from .my_parser.parser import Parser
from .utils.type_definition import ApiConfig, TaskStatus
from .writer import Writer
from timeit import default_timer as timer
from .config import config

# if not config.get("model_manager", {}).get("redis_host"):
#     huey = SqliteHuey()
# else:
#     huey = RedisHuey("model-manager-task", host=config.get("model_manager", {}).get("redis_host"),\
#     port=config.get("model_manager", {}).get("redis_port"))

celery_app = Celery("convert_app",
                    broker=config["celery"]["broker"],
                    backend=config["celery"]["backend"])


def report_status(
        project_id: int, model_file_id: int, status: TaskStatus, msg: str = ""
):
    base_url = config["model_manager"]["url"]
    headers = {
        "accept": "application/json",
        # 'Content-Type': 'application/json',
    }

    json_data = {
        "status": status.value,
        "msg": msg,
    }
    try:
        response = requests.post(
            f"{base_url}/project/{project_id}/model-file/convert/{model_file_id}/status",
            headers=headers,
            json=json_data,
        )
        status_code = response.json().get("code")
        if status_code != 200:
            logger.error(
                f"fail to upload data, status code: {status_code}, model_file_id: {model_file_id}, status: {status}"
            )
        # print(response.json())
        return True
    except Exception as e:
        print(e)
        logger.error(f"fail to report status, model_file_id: {model_file_id}")
        return False


@celery_app.task()
def start_convert(uuid: str, project_id: int, model_file_id: int):
    input_file_path = f"{config['jrvt_file_root']}/{uuid}.jrvt"  # TODO: maybe rename to a more common suffix?
    config["input_file_path"] = input_file_path
    # config["model_manager"]["model_id"] = model_id
    tic = timer()
    try:
        report_status(project_id, model_file_id, TaskStatus.processing)
        jrvt = Reader(config)
        parser = Parser(jrvt)
        slpkm = SLPK(parser.to_ubm(ntpath.basename(input_file_path)))
        writer = Writer(slpkm)
        writer.to_db(config["output_file_root"], project_id, model_file_id)
        # if not config["server"]["is_server"]:
        #     writer.upload()
        toc = timer()
        report_status(
            project_id, model_file_id, TaskStatus.success, f"{int(toc - tic)}"
        )
    except Exception as e:
        print(e)
        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        print("Traceback:\n", traceback_str)
        toc = timer()
        report_status(project_id, model_file_id, TaskStatus.fail, f"{int(toc - tic)}")

    logger.info(f"总用时: {toc - tic}")


if __name__ == "__main__":
    # report_status(1, 2, TaskStatus.processing)
    # import asyncio
    #
    # if os.path.exists("../api_running.log"):
    #     os.remove("../api_running.log")  # refresh log file
    #
    # logger.add("../api_running.log", level="DEBUG")
    # # loop = asyncio.get_event_loop()
    # asyncio.run(start_convert(r"C:\Users\admin\Desktop\deckglTest\slpk_server\jrvt\270af921-bf41-43e3-ae81-3f58d40246a4.jrvt", 1, 2))
    # # loop.run_until_complete()
    # # cProfile.run('main()', sort="cumulative")
    # logger.debug("finish.")

    # import yappi
    #
    # yappi.clear_stats()
    # yappi.set_clock_type("cpu")
    # # yappi.set_clock_type("wall")
    # yappi.start(builtins=True)  # track builtins
    #
    start_convert(
        r"C:\Users\admin\Desktop\deckglTest\slpk_server\jrvt\d09e86af-c50c-428b-85f7-fadf4eeb1b13.jrvt",
        1,
        2,
    )
    #
    # yappi.stop()
    #
    # yappi.get_func_stats().save("./api_test.pstats", type="callgrind")
    # yappi.get_thread_stats().print_all()

