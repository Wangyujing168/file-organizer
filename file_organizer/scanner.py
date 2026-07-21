"""文件扫描器——三个功能共用的文件发现引擎"""

import fnmatch
import os
from pathlib import Path
from typing import Iterator, Optional


class FileScanner:
    """通用的文件扫描器，支持递归、模式过滤、大小过滤"""

    def __init__(
        self,
        recursive: bool = True,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        min_size: int = 0,
        max_size: Optional[int] = None,
    ):
        """
        参数：
            recursive: 是否递归扫描子目录
            include_patterns: 文件匹配模式列表（glob 风格，如 ["*.jpg", "*.png"]）
            exclude_patterns: 排除模式列表
            min_size: 最小文件大小（字节）
            max_size: 最大文件大小（字节），None 表示不限制
        """
        self.recursive = recursive
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.min_size = min_size
        self.max_size = max_size

    def iter_files(self, source: Path) -> Iterator[Path]:
        """递归或非递归遍历目录，返回文件路径迭代器"""
        if self.recursive:
            for root, dirs, files in os.walk(source):
                # 跳过隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                root_path = Path(root)
                for filename in files:
                    if filename.startswith("."):
                        continue
                    file_path = root_path / filename
                    if self._should_include(file_path):
                        yield file_path
        else:
            for entry in source.iterdir():
                if entry.is_file() and not entry.name.startswith("."):
                    if self._should_include(entry):
                        yield entry

    def scan(self, source: Path) -> list[Path]:
        """扫描并返回匹配的文件列表（排序后）"""
        files = list(self.iter_files(source))
        files.sort()
        return files

    def scan_by_size(self, source: Path) -> dict[int, list[Path]]:
        """
        按文件大小分组扫描（供重复文件查找使用）。
        返回：{文件大小（字节）: [文件路径列表]}
        只返回大小组内文件数 >= 2 的组（单个文件不可能是重复）。
        """
        size_map: dict[int, list[Path]] = {}
        for file_path in self.iter_files(source):
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            if size < self.min_size:
                continue
            if size not in size_map:
                size_map[size] = []
            size_map[size].append(file_path)

        # 只保留大小组内有至少 2 个文件的组
        return {size: paths for size, paths in size_map.items() if len(paths) >= 2}

    def _should_include(self, file_path: Path) -> bool:
        """检查文件是否应该被包含"""
        try:
            stat = file_path.stat()
        except OSError:
            return False

        # 大小过滤
        if stat.st_size < self.min_size:
            return False
        if self.max_size is not None and stat.st_size > self.max_size:
            return False

        # 模式过滤
        if self.include_patterns:
            matched = any(
                fnmatch.fnmatch(file_path.name.lower(), pat.lower())
                for pat in self.include_patterns
            )
            if not matched:
                return False

        if self.exclude_patterns:
            excluded = any(
                fnmatch.fnmatch(file_path.name.lower(), pat.lower())
                for pat in self.exclude_patterns
            )
            if excluded:
                return False

        return True


def count_files(source: Path, recursive: bool = True) -> int:
    """快速统计目录下的文件数量"""
    scanner = FileScanner(recursive=recursive)
    return len(scanner.scan(source))
