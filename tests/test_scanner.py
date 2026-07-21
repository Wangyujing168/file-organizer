"""测试文件扫描器模块"""

from pathlib import Path

from file_organizer.scanner import FileScanner, count_files


class TestFileScanner:
    """测试 FileScanner 类"""

    def test_scan_non_recursive(self, sample_files):
        temp_dir, files = sample_files
        scanner = FileScanner(recursive=False)
        result = scanner.scan(temp_dir)
        assert len(result) == 5
        assert all(isinstance(f, Path) for f in result)

    def test_scan_recursive(self, sample_dirs):
        scanner = FileScanner(recursive=True)
        result = scanner.scan(sample_dirs)
        # 4 files total: a.txt, b.txt, c.txt, d.txt
        assert len(result) == 4

    def test_scan_with_include_pattern(self, sample_files):
        temp_dir, files = sample_files
        scanner = FileScanner(recursive=False, include_patterns=["*.txt"])
        result = scanner.scan(temp_dir)
        assert len(result) == 5  # all are .txt

    def test_scan_with_include_pattern_no_match(self, sample_files):
        temp_dir, files = sample_files
        scanner = FileScanner(recursive=False, include_patterns=["*.jpg"])
        result = scanner.scan(temp_dir)
        assert len(result) == 0

    def test_scan_with_exclude_pattern(self, sample_files):
        temp_dir, files = sample_files
        scanner = FileScanner(recursive=False, exclude_patterns=["empty*"])
        result = scanner.scan(temp_dir)
        assert len(result) == 4

    def test_scan_with_min_size(self, sample_files):
        temp_dir, files = sample_files
        scanner = FileScanner(recursive=False, min_size=100)
        result = scanner.scan(temp_dir)
        # Only big.txt (10000 bytes) > 100
        names = [f.name for f in result]
        assert "big.txt" in names
        assert "empty.txt" not in names

    def test_scan_by_size(self, sample_files):
        temp_dir, files = sample_files
        scanner = FileScanner(recursive=False, min_size=1)
        size_map = scanner.scan_by_size(temp_dir)
        # hello.txt and hello_copy.txt have same size (same content)
        found_dup = False
        for size, paths in size_map.items():
            if len(paths) >= 2:
                found_dup = True
        assert found_dup

    def test_count_files(self, sample_files):
        temp_dir, files = sample_files
        count = count_files(temp_dir, recursive=False)
        assert count == 5

    def test_nonexistent_directory(self):
        scanner = FileScanner()
        result = scanner.scan(Path("/nonexistent/path"))
        assert result == []
