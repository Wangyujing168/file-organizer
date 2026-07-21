"""全局配置与常量"""

# 默认哈希算法
DEFAULT_HASH_ALGORITHM = "xxh3_128"

# 大文件阈值（超过此大小使用部分哈希策略以提升性能）
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB

# 部分哈希的头部/尾部读取大小
PARTIAL_HASH_HEAD_BYTES = 8192
PARTIAL_HASH_TAIL_BYTES = 8192

# 默认日期格式
DEFAULT_DATE_PATTERN = "{year}/{month:02d}"

# 撤销日志目录
UNDO_LOG_DIR = "~/.fileorg/undo_logs"

# 图片文件扩展名（按扩展名判定，不需要实际解析 EXIF）
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".tiff", ".tif", ".webp", ".heic", ".heif",
    ".raw", ".cr2", ".nef", ".arw", ".dng",
}

# 有 EXIF 的文件扩展名
EXIF_EXTENSIONS = {
    ".jpg", ".jpeg", ".tiff", ".tif",
    ".raw", ".cr2", ".nef", ".arw", ".dng",
}
