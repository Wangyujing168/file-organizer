"""测试重复文件查找器模块"""

from file_organizer.duplicate_finder import DuplicateFinder


class TestDuplicateFinder:
    """测试 DuplicateFinder 类"""

    def test_find_duplicates(self, sample_files):
        temp_dir, files = sample_files
        finder = DuplicateFinder(min_size=1)
        duplicates = finder.find(temp_dir, recursive=False)

        # hello.txt 和 hello_copy.txt 是重复的
        assert len(duplicates) >= 1

    def test_find_no_duplicates_all_unique(self, temp_dir):
        d = temp_dir
        (d / "a.txt").write_text("aaa")
        (d / "b.txt").write_text("bbb")
        (d / "c.txt").write_text("ccc")

        finder = DuplicateFinder(min_size=1)
        duplicates = finder.find(d, recursive=False)
        assert len(duplicates) == 0

    def test_find_with_min_size(self, sample_files):
        temp_dir, files = sample_files
        finder = DuplicateFinder(min_size=999999)
        duplicates = finder.find(temp_dir, recursive=False)
        assert len(duplicates) == 0

    def test_find_recursive(self, sample_dirs):
        finder = DuplicateFinder(min_size=1)
        duplicates = finder.find(sample_dirs, recursive=True)

        # sub1/a.txt 和 sub2/c.txt 内容相同 (both "aaa")
        assert len(duplicates) >= 1

    def test_clean_keep_oldest(self, sample_files):
        temp_dir, files = sample_files
        finder = DuplicateFinder(min_size=1)
        duplicates = finder.find(temp_dir, recursive=False)

        result = finder.clean(duplicates, keep="oldest", dry_run=False, confirm=True)
        assert result["deleted"] > 0

    def test_clean_dry_run(self, sample_files):
        temp_dir, files = sample_files
        finder = DuplicateFinder(min_size=1)
        duplicates = finder.find(temp_dir, recursive=False)

        count_before = len(list(temp_dir.iterdir()))
        result = finder.clean(duplicates, keep="oldest", dry_run=True)
        count_after = len(list(temp_dir.iterdir()))

        # Dry run 不应删除文件
        assert count_before == count_after
        assert result["deleted"] > 0

    def test_nonexistent_directory(self):
        from pathlib import Path
        finder = DuplicateFinder()
        duplicates = finder.find(Path("/nonexistent/path"))
        assert duplicates == {}
