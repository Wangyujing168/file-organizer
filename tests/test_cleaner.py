"""测试杂乱清理器"""

import os
import time
from pathlib import Path

from file_organizer.cleaner import (
    ClutterFinder,
    ClutterReport,
    clean_empty_dirs,
    clean_temp_files,
)


class TestClutterFinder:
    """测试 ClutterFinder 类"""

    def test_find_old_files(self, temp_dir):
        # 创建一个"旧"文件
        old = temp_dir / "old.txt"
        old.write_text("old")
        # 设置修改时间为很久以前
        old_time = time.time() - 365 * 24 * 3600  # 1 year ago
        os.utime(str(old), (old_time, old_time))

        finder = ClutterFinder(recursive=False)
        result = finder.find_old_files(temp_dir, months=6)

        assert len(result) >= 1
        assert any("old.txt" in f["path"] for f in result)

    def test_find_old_files_none(self, temp_dir):
        (temp_dir / "new.txt").write_text("new")

        finder = ClutterFinder(recursive=False)
        result = finder.find_old_files(temp_dir, months=6)

        assert len(result) == 0

    def test_find_temp_files(self, temp_dir):
        (temp_dir / "test.tmp").write_text("tmp")
        (temp_dir / "drawing.dwl").write_text("dwl")
        (temp_dir / "normal.txt").write_text("normal")

        finder = ClutterFinder(recursive=False)
        result = finder.find_temp_files(temp_dir)

        assert len(result) == 2
        assert any(".tmp" in f for f in result)
        assert any(".dwl" in f for f in result)

    def test_find_empty_dirs(self, temp_dir):
        empty = temp_dir / "empty"
        empty.mkdir()
        not_empty = temp_dir / "not_empty"
        not_empty.mkdir()
        (not_empty / "file.txt").write_text("x")

        finder = ClutterFinder()
        result = finder.find_empty_dirs(temp_dir)

        assert str(empty) in result
        assert str(not_empty) not in result

    def test_find_large_files(self, temp_dir):
        (temp_dir / "small.txt").write_text("small")
        big = temp_dir / "big.txt"
        big.write_text("X" * 10000)

        finder = ClutterFinder(recursive=False)
        result = finder.find_large_files(temp_dir, min_size=1000)

        assert len(result) >= 1
        assert any("big.txt" in f["path"] for f in result)

    def test_full_scan(self, temp_dir):
        (temp_dir / "test.tmp").write_text("tmp")
        (temp_dir / "normal.txt").write_text("normal")

        finder = ClutterFinder()
        report = finder.full_scan(temp_dir, old_months=12, large_threshold=1024*1024)

        assert isinstance(report, ClutterReport)
        assert len(report.temp_files) == 1

    def test_clean_temp_files_dry_run(self, temp_dir):
        (temp_dir / "test.tmp").write_text("tmp")

        deleted = clean_temp_files([str(temp_dir / "test.tmp")], dry_run=True)
        assert deleted == 1
        assert (temp_dir / "test.tmp").exists()  # 未被真正删除

    def test_clean_temp_files_real(self, temp_dir):
        (temp_dir / "test.tmp").write_text("tmp")

        deleted = clean_temp_files([str(temp_dir / "test.tmp")], dry_run=False)
        assert deleted == 1
        assert not (temp_dir / "test.tmp").exists()

    def test_clean_empty_dirs(self, temp_dir):
        empty = temp_dir / "empty"
        empty.mkdir()

        deleted = clean_empty_dirs(str(temp_dir), empty_dirs=[str(empty)], dry_run=False)
        assert deleted == 1
        assert not empty.exists()
