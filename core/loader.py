#这是debugtaik加载器，将设计的函数加载
import importlib.util
import inspect
import os
import sys
from typing import Any, Callable, Dict, Text

from loguru import logger


class ProjectMeta:
    """项目元数据：承载 debugtalk.py 中定义的函数和环境信息"""

    def __init__(self, debugtalk_path: Text = "", functions: Dict[Text, Callable] = None):
        # debugtalk.py 文件绝对路径
        self.debugtalk_path = debugtalk_path
        # 从 debugtalk.py 提取的公共函数映射
        self.functions = functions or {}
        # 环境变量（预留扩展）
        self.env = {}


def load_debugtalk(project_root: Text = None) -> ProjectMeta:
    """从项目根目录加载 debugtalk.py，提取其中所有公共可调用对象

    Args:
        project_root: 项目根目录，默认为当前工作目录

    Returns:
        ProjectMeta: 包含 functions 映射的项目元数据
    """
    # 默认使用当前工作目录
    if project_root is None:
        project_root = os.getcwd()

    debugtalk_path = os.path.join(project_root, "debugtalk.py")

    # debugtalk.py 不存在时返回空 meta（不报错，保持向后兼容）
    if not os.path.isfile(debugtalk_path):
        logger.debug(f"未找到 debugtalk.py: {debugtalk_path}，跳过加载自定义函数")
        return ProjectMeta(debugtalk_path="", functions={})

    logger.info(f"加载 debugtalk.py: {debugtalk_path}")

    # 动态导入 debugtalk 模块（避免与已加载模块冲突，使用唯一模块名）
    module_name = "_debugtalk_loaded"
    spec = importlib.util.spec_from_file_location(module_name, debugtalk_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 debugtalk.py: {debugtalk_path}")

    module = importlib.util.module_from_spec(spec)
    # 注册到 sys.modules 以支持模块内相对引用
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        # 加载失败时清理已注册模块
        sys.modules.pop(module_name, None)
        raise ImportError(f"执行 debugtalk.py 失败: {e}") from e

    # 提取模块中所有公共可调用对象（排除模块自身、内置属性）
    functions = {}
    for name, obj in inspect.getmembers(module, callable):
        # 跳过下划线开头的私有成员
        if name.startswith("_"):
            continue
        # 跳过导入的模块/类/类型，只保留函数和方法
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            functions[name] = obj

    logger.info(f"debugtalk.py 加载完成，共提取 {len(functions)} 个函数: {list(functions.keys())}")

    return ProjectMeta(debugtalk_path=debugtalk_path, functions=functions)


def get_project_root(start_path: Text = None) -> Text:
    """从给定路径向上查找项目根目录（包含 debugtalk.py 的目录）

    Args:
        start_path: 起始查找路径，默认为 runner.py 所在目录的上级

    Returns:
        Text: 项目根目录绝对路径
    """
    if start_path is None:
        # core/ 的上一级即项目根目录
        start_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    current = os.path.abspath(start_path)
    while current != os.path.dirname(current):
        if os.path.isfile(os.path.join(current, "debugtalk.py")):
            return current
        current = os.path.dirname(current)

    # 未找到则返回起始路径作为兜底
    return os.path.abspath(start_path)
