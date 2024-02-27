from math import ceil
from collections.abc import Iterable, Sized
from typing import List

from loguru import logger


def split_page(lst: List, page_size, page_num, sort_by="create_time", desc=True):
    # TODO: 独立处理sort by 和 desc
    # print(sort_by, desc, type(desc), type(l[0]))
    assert isinstance(lst, Iterable)
    assert isinstance(lst, Sized)
    total = len(lst)
    if total <= 0:
        return total, lst
    try:
        if hasattr(lst[0], '__dict__') and sort_by in lst[0].__dict__:  # TODO: 使用更加通用的判断方法
            lst = sorted(lst, key=lambda x: x.__dict__[sort_by], reverse=desc)
        elif isinstance(lst[0], dict) and sort_by in lst[0]:
            lst = sorted(lst, key=lambda x: x[sort_by], reverse=desc)
        else:
            logger.error(f"some condition not catch.")
    except KeyError:
        logger.error(f"key `{sort_by}` not found.")
        if desc:
            lst = lst[::-1]

    number_of_page = ceil(total / page_size)
    page_num = min(number_of_page, page_num)
    page_num = max(page_num, 1)
    left = (page_num - 1) * page_size
    right = page_num * page_size
    return total, lst[left:right]


if __name__ == "__main__":
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 0))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 1))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 2))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 3))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 4))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 5))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 6))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 7))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 8))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 9))
    print(split_page([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 10))
