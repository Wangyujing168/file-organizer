"""元数据模块——从文件中提取日期信息，优先使用 EXIF 拍摄日期"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from file_organizer.config import EXIF_EXTENSIONS

# 延迟导入 Pillow，只在需要时加载
_EXIF_TAGS = [
    "DateTimeOriginal",   # 拍摄日期（最优先）
    "DateTimeDigitized",  # 数字化日期
    "DateTime",           # 修改日期
]

# EXIF 日期格式
_EXIF_DATE_FORMATS = [
    "%Y:%m:%d %H:%M:%S",
    "%Y:%m:%d %H:%M",
    "%Y:%m:%d",
]


def extract_date(file_path: Path) -> Optional[datetime]:
    """
    从文件中提取日期，优先级：
    1. EXIF DateTimeOriginal（照片拍摄日期）
    2. EXIF DateTimeDigitized
    3. EXIF DateTime
    4. 文件创建时间（Windows ctime / macOS birthtime）
    5. 文件修改时间（mtime）
    """
    # 1-3. 尝试 EXIF
    ext = file_path.suffix.lower()
    if ext in EXIF_EXTENSIONS:
        exif_date = _extract_exif_date(file_path)
        if exif_date:
            return exif_date

    # 4. 文件创建时间
    ctime = _get_creation_time(file_path)
    if ctime:
        return ctime

    # 5. 文件修改时间
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime)
    except OSError:
        return None


def extract_all_dates(file_path: Path) -> dict[str, Optional[datetime]]:
    """
    提取文件的所有可能的日期信息（调试用）。
    返回一个字典，包含各来源的日期。
    """
    result: dict[str, Optional[datetime]] = {}

    ext = file_path.suffix.lower()
    if ext in EXIF_EXTENSIONS:
        try:
            from PIL import Image, ExifTags
            img = Image.open(file_path)
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                        result[f"EXIF.{tag_name}"] = _parse_exif_date_str(value)
            img.close()
        except Exception:
            pass

    result["ctime"] = _get_creation_time(file_path)
    try:
        result["mtime"] = datetime.fromtimestamp(os.path.getmtime(file_path))
    except OSError:
        result["mtime"] = None

    return result


def _extract_exif_date(file_path: Path) -> Optional[datetime]:
    """从 EXIF 中提取拍摄日期"""
    try:
        from PIL import Image, ExifTags

        img = Image.open(file_path)
        exif_data = img._getexif()
        img.close()

        if not exif_data:
            return None

        # 构建 tag_name → value 的映射
        exif = {}
        for tag_id, value in exif_data.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            exif[tag_name] = value

        # 按优先顺序查找日期
        for tag in _EXIF_TAGS:
            value = exif.get(tag)
            if value:
                date = _parse_exif_date_str(value)
                if date:
                    return date
    except Exception:
        pass

    return None


def _parse_exif_date_str(date_str: str) -> Optional[datetime]:
    """解析 EXIF 日期字符串，支持多种格式"""
    if not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    for fmt in _EXIF_DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _get_creation_time(file_path: Path) -> Optional[datetime]:
    """
    获取文件的创建时间。
    Windows: ctime 是创建时间
    macOS: st_birthtime 是创建时间
    Linux: ctime 是状态变更时间，不适用
    """
    try:
        stat = file_path.stat()
        # macOS 特有属性
        if hasattr(stat, "st_birthtime"):
            return datetime.fromtimestamp(stat.st_birthtime)
        # Windows: ctime 是创建时间
        return datetime.fromtimestamp(stat.st_ctime)
    except (OSError, ValueError):
        return None
