# 模型管理后台

## 环境搭建

1. 安装 postgresQL 15.0.1
2. (选)创建数据库用户
3. clone 本项目到本地，如需使用转换器，还需clone子项目(添加 `--recursive`参数)
4. 创建虚拟环境
5. 安装依赖(同时需要安装`submodule`中的依赖)`pip install -r requirements.txt`
   1. 需要安装`ImageMagick-7.1.0-45-Q16-HDRI-x64-dll.exe`
   2. 确认所需的各种dll
   3. 确保huey已安装
6. 使用`huey_consumer.py model_converter.src.api.huey`启动任务队列
7. 使用`uvicorn main:app --reload`运行项目

## 部分文件目录说明

### router/

路由部分，暴露给前端的接口；根据不同的资源组成不同的文件。

通过`APIRouter`可以设置同一资源下的共用设置，如前缀，具体可参考[更大的应用-多个文件-FastAPI (tiangolo.com)](https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/#_2)

### db_model/

数据模型，直接对应数据库

### db_manager/

对模型层的数据处理进行封装，为router提供接口

### main.py

程序入口

### dependence.py

依赖项，如何用户验证

### config.py

配置文件

## Change Log

### v1.0.1

bug fix:

- 修复并发太大导致session pool耗尽的问题

model converter:

- 调整玻璃的sublayer顺序

feat:

- 新增查询接口
- 添加分页功能

### 2023-01-05

实现基本功能：

- 创建项目
- 上传模型(单文件上传，格式为jrvt)
- 发起转化任务
- 分发slpk文件(前端需修改一下路由)
- 修改模型位置(不包括旋转)

已知问题：

- 大量请求可能会耗尽数据库连接池造成500错误

- 前端点击显示属性的部分，似乎变的更难点中，原因需要排查

  