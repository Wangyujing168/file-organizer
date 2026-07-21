"""测试组织方案建议器"""

from pathlib import Path

from file_organizer.suggester import Suggester, Suggestion


class TestSuggester:
    """测试 Suggester 类"""

    def test_suggest_office(self, temp_dir):
        (temp_dir / "report.pdf").write_text("pdf")
        (temp_dir / "data.xlsx").write_text("xlsx")

        suggester = Suggester()
        suggestion = suggester.suggest(temp_dir)

        assert isinstance(suggestion, Suggestion)
        assert suggestion.scene in ("office", "engineering")

    def test_suggest_engineering(self, temp_dir):
        (temp_dir / "project.gbq").write_text("gbq")
        (temp_dir / "drawing.dwg").write_text("dwg")

        suggester = Suggester()
        suggestion = suggester.suggest(temp_dir)

        # 应该识别为 engineering
        assert suggestion.scene == "engineering"

    def test_suggest_has_structure(self, temp_dir):
        (temp_dir / "a.pdf").write_text("x")
        (temp_dir / "b.jpg").write_text("x")

        suggester = Suggester()
        suggestion = suggester.suggest(temp_dir)

        assert len(suggestion.proposed_structure) > 0
        assert len(suggestion.tips) > 0

    def test_suggest_file_moves(self, temp_dir):
        (temp_dir / "report.pdf").write_text("pdf")
        (temp_dir / "photo.jpg").write_text("jpg")

        suggester = Suggester()
        suggestion = suggester.suggest(temp_dir)

        assert suggestion.total_files_to_move > 0
        # 至少有一个 PDF 和一个 JPG 需要移动
        paths = [m["file"] for m in suggestion.file_moves]
        assert any(".pdf" in p for p in paths)
        assert any(".jpg" in p for p in paths)

    def test_suggest_empty_dir(self, temp_dir):
        suggester = Suggester()
        suggestion = suggester.suggest(temp_dir)

        assert suggestion.total_files_to_move == 0
        assert len(suggestion.tips) > 0
