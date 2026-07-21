"""组织方案建议器——根据文件类型模式建议文件夹结构"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from file_organizer.analyzer import Analyzer, AnalysisReport
from file_organizer.reporter import console, print_dry_run_notice, print_info
from file_organizer.scanner import FileScanner


# 预设文件夹模板
SCENE_TEMPLATES = {
    "engineering": {
        "keywords": [".gbq", ".gad", ".gtj", ".dwg", ".bak", "造价", "结算", "审核", "合同", "招标"],
        "name": "造价/工程目录",
        "structure": [
            "Projects/",        # 项目文件
            "Reports/",         # 审核报告、结算报告
            "Drawings/",        # CAD 图纸
            "Contracts/",       # 合同文件
            "Calculations/",    # 算量文件
            "Archive/",         # 历史归档
        ],
    },
    "office": {
        "keywords": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt"],
        "name": "通用办公",
        "structure": [
            "Documents/",
            "Spreadsheets/",
            "Presentations/",
            "PDFs/",
            "Images/",
            "Archive/",
        ],
    },
    "photos": {
        "keywords": [".jpg", ".jpeg", ".png", ".gif", ".heic", ".raw", ".cr2"],
        "name": "照片目录",
        "structure": [
            "2024/", "2025/", "2026/",
            "Unsorted/",
        ],
    },
    "downloads": {
        "keywords": [".dmg", ".exe", ".msi", ".zip", ".rar", ".tar", ".gz"],
        "name": "下载目录",
        "structure": [
            "Documents/",
            "Images/",
            "Installers/",
            "Archives/",
            "ToSort/",
        ],
    },
    "code": {
        "keywords": [".py", ".js", ".ts", ".java", ".go", ".rs", ".git", "package.json"],
        "name": "项目代码",
        "structure": [
            "src/",
            "docs/",
            "tests/",
            "assets/",
            "archive/",
        ],
    },
}

# 通用类型→文件夹映射
TYPE_TO_FOLDER = {
    # 文档
    ".pdf": "Documents/PDFs/",
    ".doc": "Documents/Word/", ".docx": "Documents/Word/",
    ".xls": "Documents/Excel/", ".xlsx": "Documents/Excel/",
    ".ppt": "Documents/Presentations/", ".pptx": "Documents/Presentations/",
    ".txt": "Documents/Text/", ".csv": "Documents/Data/",
    # 图片
    ".jpg": "Images/", ".jpeg": "Images/", ".png": "Images/",
    ".gif": "Images/", ".bmp": "Images/", ".svg": "Images/",
    ".webp": "Images/", ".heic": "Images/",
    # 视频
    ".mp4": "Videos/", ".mov": "Videos/", ".avi": "Videos/",
    ".mkv": "Videos/",
    # 音频
    ".mp3": "Audio/", ".wav": "Audio/", ".flac": "Audio/",
    # 压缩包
    ".zip": "Archives/", ".rar": "Archives/", ".7z": "Archives/",
    ".tar": "Archives/", ".gz": "Archives/",
    # 安装包
    ".exe": "Installers/", ".msi": "Installers/", ".dmg": "Installers/",
    # 工程文件
    ".dwg": "Drawings/", ".dxf": "Drawings/",
    ".gbq": "Cost/", ".gad": "Cost/Calculations/", ".gtj": "Cost/Models/",
    ".bak": "Temp/",
    # 代码
    ".py": "Code/Python/", ".js": "Code/JavaScript/", ".ts": "Code/TypeScript/",
    ".html": "Code/Web/", ".css": "Code/Web/",
}


@dataclass
class Suggestion:
    """组织建议"""
    scene: str                    # 场景名称
    proposed_structure: list[str] # 建议的文件夹结构
    file_moves: list[dict]        # 建议的文件移动: {file, target_folder, reason}
    tips: list[str]               # 维护建议
    total_files_to_move: int


class Suggester:
    """根据文件内容模式建议文件夹结构"""

    def suggest(self, path: Path) -> Suggestion:
        """
        分析目录并生成组织建议。

        返回：Suggestion
        """
        path = path.resolve()
        console.print(f"🧠 分析 [cyan]{path}[/cyan] 并生成建议...")

        # 1. 先用 Analyzer 获取文件类型分布
        analyzer = Analyzer(recursive=False)
        report = analyzer.analyze(path)

        # 2. 匹配场景模板
        scene = self._match_scene(report)
        template = SCENE_TEMPLATES.get(scene)

        # 3. 生成文件移动建议
        file_moves = self._suggest_moves(path, report)

        # 4. 维护建议
        tips = self._generate_tips(scene, report)

        return Suggestion(
            scene=scene,
            proposed_structure=template["structure"] if template else [],
            file_moves=file_moves,
            tips=tips,
            total_files_to_move=len(file_moves),
        )

    def _match_scene(self, report: AnalysisReport) -> str:
        """根据文件类型匹配场景模板"""
        scores = {}
        for scene_id, template in SCENE_TEMPLATES.items():
            score = 0
            for ext_info in list(report.file_types.items())[:20]:
                ext, info = ext_info
                for kw in template["keywords"]:
                    if kw.startswith("."):
                        if ext == kw:
                            score += info["count"] * 3
                    else:
                        score += info["count"]  # 关键词匹配给额外加分
            scores[scene_id] = score

        if not scores or max(scores.values()) == 0:
            return "office"  # 默认
        return max(scores, key=scores.get)

    def _suggest_moves(self, path: Path, report: AnalysisReport) -> list[dict]:
        """根据文件类型建议移动方案"""
        moves = []
        scanner = FileScanner(recursive=False)
        root_files = scanner.scan(path)

        for file_path in root_files:
            ext = file_path.suffix.lower()
            target = TYPE_TO_FOLDER.get(ext)
            if target:
                moves.append({
                    "file": str(file_path),
                    "target_folder": target.rstrip("/"),
                    "reason": f"{ext} 类型文件归类",
                })

        return moves

    def _generate_tips(self, scene: str, report: AnalysisReport) -> list[str]:
        """生成维护建议"""
        tips = ["每月清理一次临时文件和空目录"]

        if scene == "engineering":
            tips.append("每个项目独立建文件夹，包含 Reports/Drawings/Calculations 子目录")
            tips.append("项目完成后归档到 Archive/ 中")
        elif scene == "office":
            tips.append("按项目/客户名称建立子文件夹")
            tips.append("定期检查重复文件：fileorg dup find ./")
        elif scene == "downloads":
            tips.append("每周整理一次下载文件夹")
            tips.append("安装包在安装后可以删除")
        elif scene == "photos":
            tips.append("使用 fileorg date sort 按拍摄日期自动归档")
            tips.append("定期备份照片到云存储")

        return tips


def print_suggestion(suggestion: Suggestion, dry_run: bool = False) -> None:
    """打印组织建议"""
    from rich.panel import Panel
    from rich.table import Table

    if dry_run:
        print_dry_run_notice()

    console.print()
    console.print(Panel.fit(
        f"[bold]🏗️  组织方案: {suggestion.scene}[/bold]",
        border_style="cyan",
    ))

    # 建议结构
    if suggestion.proposed_structure:
        console.print("\n[bold]📁 建议的文件夹结构:[/bold]")
        for folder in suggestion.proposed_structure:
            console.print(f"  ├── {folder}")

    # 文件移动建议
    if suggestion.file_moves:
        console.print(f"\n[bold]📦 建议移动的文件 ({suggestion.total_files_to_move} 个):[/bold]")
        table = Table()
        table.add_column("文件", style="yellow")
        table.add_column("目标文件夹", style="green")
        table.add_column("原因", style="dim")
        for m in suggestion.file_moves[:15]:
            fname = Path(m["file"]).name
            table.add_row(fname, m["target_folder"], m["reason"])
        console.print(table)
        if suggestion.total_files_to_move > 15:
            console.print(f"  ... 还有 {suggestion.total_files_to_move - 15} 个")

    # 维护建议
    if suggestion.tips:
        console.print("\n[bold]💡 维护建议:[/bold]")
        for tip in suggestion.tips:
            console.print(f"  • {tip}")
