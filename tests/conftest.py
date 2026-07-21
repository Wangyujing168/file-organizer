"""测试共享 Fixtures"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_dir():
    """创建一个临时目录，测试结束后自动清理"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_files(temp_dir):
    """创建一组测试文件"""
    files = {}

    # 两个相同内容的文件（将成为重复）
    f1 = temp_dir / "hello.txt"
    f1.write_text("Hello World")
    files["hello1"] = f1

    f2 = temp_dir / "hello_copy.txt"
    f2.write_text("Hello World")
    files["hello2"] = f2

    # 另一个不同内容的文件
    f3 = temp_dir / "unique.txt"
    f3.write_text("Unique content here")
    files["unique"] = f3

    # 一个空文件
    f4 = temp_dir / "empty.txt"
    f4.write_text("")
    files["empty"] = f4

    # 一个大一点的文件
    f5 = temp_dir / "big.txt"
    f5.write_text("X" * 10000)
    files["big"] = f5

    return temp_dir, files


@pytest.fixture
def sample_dirs(temp_dir):
    """创建带子目录的测试结构"""
    sub1 = temp_dir / "sub1"
    sub1.mkdir()
    sub2 = temp_dir / "sub2"
    sub2.mkdir()

    (sub1 / "a.txt").write_text("aaa")
    (sub1 / "b.txt").write_text("bbb")
    (sub2 / "c.txt").write_text("aaa")  # 与 a.txt 重复
    (temp_dir / "d.txt").write_text("ddd")

    return temp_dir
