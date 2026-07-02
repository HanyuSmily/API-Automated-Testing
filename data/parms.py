#这个文件是从 data/ 目录加载数据，支持类型转换（解决 CSV 全字符串问题）
import os
from typing import Any, Dict, List, Text

from utils.data_loader import DataLoader


# 数据文件根目录（data/ 所在路径）
DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load_params(file_name: Text, converters: Dict[Text, Any] = None) -> List[Dict[Text, Any]]:
    """从 data/ 目录加载数据文件并返回参数化数据列表

    Args:
        file_name: 数据文件名（相对 data/ 目录，如 "test_users.csv"）
        converters: 字段类型转换器，如 {"user_id": int, "expect_status": int}
                    用于解决 CSV 默认全部为字符串的问题

    Returns:
        List[Dict]: 参数化数据列表，每条为一个字典

    示例:
        data = load_params("test_users.csv", converters={"user_id": int, "expect_status": int})
    """
    # 拼接完整路径
    file_path = os.path.join(DATA_DIR, file_name)
    # 加载数据
    data = DataLoader.load(file_path)

    # 应用类型转换
    if converters:
        for row in data:
            for field, converter in converters.items():
                if field in row and row[field] is not None:
                    row[field] = converter(row[field])

    return data


def load_params_tuples(file_name: Text, converters: Dict[Text, Any] = None) -> List[tuple]:
    """加载并转换为 pytest.mark.parametrize 友好的 tuple 列表

    用法:
        @pytest.mark.parametrize("params", load_params_tuples("test_users.csv"))
        def test_xxx(params): ...
    """
    data_list = load_params(file_name, converters)
    return [(item,) for item in data_list]
