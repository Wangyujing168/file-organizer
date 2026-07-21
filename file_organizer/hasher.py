"""哈希器模块——文件哈希计算，支持全文件和部分哈希策略"""

import hashlib
from pathlib import Path

import xxhash

from file_organizer.config import (
    DEFAULT_HASH_ALGORITHM,
    LARGE_FILE_THRESHOLD,
    PARTIAL_HASH_HEAD_BYTES,
    PARTIAL_HASH_TAIL_BYTES,
)


class FileHasher:
    """文件哈希计算器，默认使用 xxh3_128 快速哈希"""

    def __init__(self, algorithm: str = DEFAULT_HASH_ALGORITHM):
        self.algorithm = algorithm

    def hash_file(self, path: Path) -> str:
        """
        计算文件的哈希值。
        对大文件（>100MB）自动使用部分哈希策略以提升性能。
        """
        try:
            size = path.stat().st_size
        except OSError:
            return ""

        if size >= LARGE_FILE_THRESHOLD:
            return self._hash_file_partial(path, size)
        return self._hash_file_full(path)

    def hash_file_full(self, path: Path) -> str:
        """计算整个文件的哈希"""
        return self._hash_file_full(path)

    def _hash_file_full(self, path: Path) -> str:
        """读整个文件计算哈希"""
        if self.algorithm.startswith("xxh"):
            hasher = self._new_xxhash()
        else:
            hasher = hashlib.new(self.algorithm)

        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    hasher.update(chunk)
        except (OSError, PermissionError):
            return ""
        return hasher.hexdigest()

    def _hash_file_partial(self, path: Path, size: int) -> str:
        """
        部分哈希策略：对头部 + 尾部 + 文件大小做哈希。
        这对于检测大文件重复已经足够准确。
        """
        hasher = self._new_xxhash()
        # 把文件大小也纳入哈希，确保不同大小不碰撞
        hasher.update(str(size).encode())

        try:
            with open(path, "rb") as f:
                # 读头部
                head = f.read(PARTIAL_HASH_HEAD_BYTES)
                hasher.update(head)

                # 跳到尾部
                tail_start = max(0, size - PARTIAL_HASH_TAIL_BYTES)
                if tail_start > PARTIAL_HASH_HEAD_BYTES:
                    f.seek(tail_start)
                tail = f.read(PARTIAL_HASH_TAIL_BYTES)
                hasher.update(tail)
        except (OSError, PermissionError):
            return ""
        return hasher.hexdigest()

    def _new_xxhash(self):
        """创建 xxhash 实例"""
        if self.algorithm == "xxh3_128":
            return xxhash.xxh3_128()
        if self.algorithm == "xxh64":
            return xxhash.xxh64()
        if self.algorithm == "xxh32":
            return xxhash.xxh32()
        raise ValueError(f"不支持的 xxhash 算法: {self.algorithm}")


def compute_file_md5(path: Path) -> str:
    """计算文件的 MD5 哈希（备用方案）"""
    hasher = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
    except (OSError, PermissionError):
        return ""
    return hasher.hexdigest()
