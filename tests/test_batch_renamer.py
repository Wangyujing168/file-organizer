"""测试批量重命名器模块"""

from pathlib import Path

from file_organizer.batch_renamer import (
    AddPrefix,
    AddSuffix,
    BatchRenamer,
    CaseConvert,
    ReplaceSpaces,
    SearchReplace,
    SequentialNumber,
)


class TestOperations:
    """测试各个重命名操作"""

    def test_search_replace(self):
        op = SearchReplace("IMG_", "Photo_")
        assert op.apply("IMG_001.jpg") == "Photo_001.jpg"

    def test_search_replace_regex(self):
        op = SearchReplace(r"\d{4}-\d{2}-\d{2}", "DATE", use_regex=True)
        assert op.apply("report-2024-01-15.pdf") == "report-DATE.pdf"

    def test_add_prefix(self):
        op = AddPrefix("vacation_")
        assert op.apply("photo.jpg") == "vacation_photo.jpg"

    def test_add_suffix(self):
        op = AddSuffix("_final")
        assert op.apply("document.pdf") == "document_final.pdf"

    def test_sequential_number(self):
        op = SequentialNumber(start=1, padding=3)
        assert op.apply("photo.jpg") == "001.jpg"
        assert op.apply("photo.jpg") == "002.jpg"
        assert op.apply("photo.jpg") == "003.jpg"

    def test_sequential_number_with_prefix(self):
        op = SequentialNumber(start=10, step=5, padding=2, prefix="img-")
        assert op.apply("x.jpg") == "img-10.jpg"
        assert op.apply("x.jpg") == "img-15.jpg"

    def test_case_convert_lower(self):
        op = CaseConvert(mode="lower")
        assert op.apply("My File.TXT") == "my file.txt"

    def test_case_convert_upper(self):
        op = CaseConvert(mode="upper")
        assert op.apply("hello.txt") == "HELLO.TXT"

    def test_case_convert_title(self):
        op = CaseConvert(mode="title")
        assert op.apply("hello world.txt") == "Hello World.txt"

    def test_replace_spaces(self):
        op = ReplaceSpaces("_")
        assert op.apply("my document file.pdf") == "my_document_file.pdf"


class TestBatchRenamer:
    """测试 BatchRenamer 类"""

    def test_rename_prefix_dry_run(self, temp_dir):
        (temp_dir / "a.txt").write_text("a")
        (temp_dir / "b.txt").write_text("b")

        renamer = BatchRenamer()
        op = AddPrefix("test_")
        result = renamer.rename(temp_dir, [op], dry_run=True)

        # 文件不应被重命名
        assert (temp_dir / "a.txt").exists()
        assert (temp_dir / "b.txt").exists()

    def test_rename_prefix(self, temp_dir):
        (temp_dir / "a.txt").write_text("a")

        renamer = BatchRenamer()
        op = AddPrefix("test_")
        result = renamer.rename(temp_dir, [op], dry_run=False)

        assert not (temp_dir / "a.txt").exists()
        assert (temp_dir / "test_a.txt").exists()

    def test_rename_with_filter(self, temp_dir):
        (temp_dir / "photo.jpg").write_text("p")
        (temp_dir / "doc.txt").write_text("d")

        renamer = BatchRenamer()
        op = AddPrefix("img_")
        result = renamer.rename(temp_dir, [op], filter_pattern="*.jpg", dry_run=False)

        assert (temp_dir / "img_photo.jpg").exists()
        assert (temp_dir / "doc.txt").exists()  # 未被改动

    def test_rename_nonexistent_path(self):
        renamer = BatchRenamer()
        op = AddPrefix("x")
        result = renamer.rename(Path("/nonexistent"), [op])
        assert result == []
