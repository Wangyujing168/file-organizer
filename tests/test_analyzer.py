"""测试目录分析器"""

from pathlib import Path

from file_organizer.analyzer import Analyzer, AnalysisReport


class TestAnalyzer:
    """测试 Analyzer 类"""

    def test_analyze_basic(self, sample_files):
        temp_dir, files = sample_files
        analyzer = Analyzer(recursive=False)
        report = analyzer.analyze(temp_dir)

        assert isinstance(report, AnalysisReport)
        assert report.total_files == 5
        assert report.total_size > 0
        assert len(report.file_types) > 0
        assert report.scan_time != ""

    def test_analyze_recursive(self, sample_dirs):
        analyzer = Analyzer(recursive=True)
        report = analyzer.analyze(sample_dirs)

        assert report.total_files == 4
        assert report.total_dirs >= 2  # sub1, sub2

    def test_analyze_empty_dir(self, temp_dir):
        analyzer = Analyzer(recursive=False)
        report = analyzer.analyze(temp_dir)

        assert report.total_files == 0
        assert report.total_size == 0

    def test_analyze_nonexistent(self):
        analyzer = Analyzer()
        report = analyzer.analyze(Path("/nonexistent"))

        assert len(report.issues) > 0

    def test_report_to_dict(self, sample_files):
        temp_dir, files = sample_files
        analyzer = Analyzer(recursive=False)
        report = analyzer.analyze(temp_dir)
        d = report.to_dict()

        assert d["total_files"] == 5
        assert "total_size_human" in d
        assert isinstance(d["file_types"], dict)

    def test_detect_duplicate_names(self, sample_files):
        temp_dir, files = sample_files
        # hello.txt and hello_copy.txt have different names so they won't be caught
        # Let's create actual same-name files
        (temp_dir / "sub").mkdir(exist_ok=True)
        (temp_dir / "sub" / "hello.txt").write_text("different content")

        analyzer = Analyzer(recursive=True)
        report = analyzer.analyze(temp_dir)
        # Should find at least "hello.txt" appearing in 2 places
        dup_names = {d["name"] for d in report.top_duplicate_names}
        assert "hello.txt" in dup_names

    def test_top_largest(self, sample_files):
        temp_dir, files = sample_files
        analyzer = Analyzer(recursive=False)
        report = analyzer.analyze(temp_dir, top_n=3)

        assert len(report.top_largest) <= 3
        assert report.top_largest[0]["size"] >= report.top_largest[-1]["size"]

    def test_date_range(self, sample_files):
        temp_dir, files = sample_files
        analyzer = Analyzer(recursive=False)
        report = analyzer.analyze(temp_dir)

        assert "oldest" in report.date_range
        assert "newest" in report.date_range
