import sys
import uvicorn
from uvicorn import Config, Server
from fastapi import FastAPI
from db_model.create_db import init_db
# import init  # 必须存在，确保使用控制台启动服务时初始化数据库成功
from config import config
from db_model.common import SessionDispatcher
from router import project, model, slpk_server, global_scope
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

tags_metadata = [
    {
        "name": "global scope",
        "description": "所有跨项目查询的api",
    },
    {
        "name": "project",
    },
    {
        "name": "model",
    },
    {
        "name": "slpk server",
    },
]

app = FastAPI(
    openapi_tags=tags_metadata,
    # openapi_url="/fastapi-dev/data_manger.json",
    # docs_url="/fastapi-dev/docs",
    # redoc_url="/fastapi-dev/redoc"
)
app.include_router(project.router)
app.include_router(model.router)
app.include_router(slpk_server.router)
app.include_router(global_scope.router)
app.add_middleware(GZipMiddleware, minimum_size=10)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    # 执行一些初始化操作
    init_db()
    instance = SessionDispatcher()


@app.get("/")
async def root():
    return {"message": "Hello World"}


if __name__ == "__main__":
    # 不使用控制台命令，直接运行 main.py

    if sys.platform == "win32":
        from asyncio import ProactorEventLoop, get_event_loop

        # server = Server(config=Config(app=app, loop=ProactorEventLoop(), host="0.0.0.0", port=10100, workers=4, reload=True, reload_dirs=["../"]))
        uvicorn.run("main:app", host="0.0.0.0", port=10100, workers=2)
    elif sys.platform == "linux":
        uvicorn.run("main:app", host="0.0.0.0", port=10100, workers=2)
    # server = Server(config=Config(app=app, loop=ProactorEventLoop(), host="0.0.0.0", port=10100, workers=4, reload=True, reload_dirs=["../"]))
    # get_event_loop().run_until_complete(server.serve())
