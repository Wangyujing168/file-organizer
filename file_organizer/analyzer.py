"""目录结构分析器——扫描目录，生成诊断报告"""

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from file_organizer.reporter import (
    console,
    create_progress,
    print_info,
    print_warning,
    _format_size,
)
from file_organizer.scanner import FileScanner


@dataclass
class AnalysisReport:
    """分析报告数据类"""

    path: str
    total_files: int = 0
    total_dirs: int = 0
    total_size: int = 0
    file_types: dict[str, dict] = field(default_factory=dict)  # ext -> {count, size}
    size_distribution: dict[str, int] = field(default_factory=dict)
    date_range: dict[str, Optional[str]] = field(default_factory=dict)
    top_largest: list[dict] = field(default_factory=list)
    top_duplicate_names: list[dict] = field(default_factory=list)
    empty_dirs: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    scan_time: str = ""

    def to_dict(self) -> dict:
        """转为字典（JSON 输出用）"""
        return {
            "path": self.path,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_size": self.total_size,
            "total_size_human": _format_size(self.total_size),
            "file_types": self.file_types,
            "size_distribution": self.size_distribution,
            "date_range": self.date_range,
            "top_largest": self.top_largest,
            "top_duplicate_names": self.top_duplicate_names,
            "empty_dirs": self.empty_dirs[:20],
            "issues": self.issues,
            "scan_time": self.scan_time,
        }


class Analyzer:
    """目录结构分析器"""

    def __init__(self, recursive: bool = True):
        self.recursive = recursive

    def analyze(self, path: Path, top_n: int = 10) -> AnalysisReport:
        """
        分析目录并生成诊断报告。

        参数：
            path: 目标目录路径
            top_n: 报告中展示的前 N 名

        返回：AnalysisReport
        """
        path = path.resolve()
        report = AnalysisReport(path=str(path))
        report.scan_time = datetime.now().isoformat()

        if not path.exists():
            report.issues.append(f"目录不存在: {path}")
            return report

        # 收集统计
        file_types: dict[str, dict] = defaultdict(lambda: {"count": 0, "size": 0})
        size_dist = {
            "0-1KB": 0, "1KB-100KB": 0, "100KB-1MB": 0,
            "1MB-10MB": 0, "10MB-100MB": 0, "100MB-1GB": 0, ">1GB": 0,
        }
        all_files: list[dict] = []
        name_map: dict[str, list[str]] = defaultdict(list)
        all_mtimes: list[float] = []
        dir_count = 0

        console.print(f"📊 分析 [cyan]{path}[/cyan] ...")

        scanner = FileScanner(recursive=self.recursive)
        files = scanner.scan(path)
        report.total_files = len(files)

        # 统计目录数
        if self.recursive:
            for root, dirs, _ in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                dir_count += len(dirs)
        report.total_dirs = dir_count

        # 分析每个文件
        progress = create_progress()
        task = progress.add_task("分析中...", total=len(files))

        with progress:
            for file_path in files:
                try:
                    stat = file_path.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime

                    report.total_size += size
                    all_mtimes.append(mtime)

                    # 文件类型
                    ext = file_path.suffix.lower() or "(无扩展名)"
                    file_types[ext]["count"] += 1
                    file_types[ext]["size"] += size

                    # 大小分布
                    if size < 1024:
                        size_dist["0-1KB"] += 1
                    elif size < 102400:
                        size_dist["1KB-100KB"] += 1
                    elif size < 1048576:
                        size_dist["100KB-1MB"] += 1
                    elif size < 10485760:
                        size_dist["1MB-10MB"] += 1
                    elif size < 104857600:
                        size_dist["10MB-100MB"] += 1
                    elif size < 1073741824:
                        size_dist["100MB-1GB"] += 1
                    else:
                        size_dist[">1GB"] += 1

                    # 全部文件信息（用于排序）
                    all_files.append({
                        "path": str(file_path),
                        "size": size,
                        "mtime": mtime,
                        "mtime_str": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
                    })

                    # 同名检测
                    name_map[file_path.name.lower()].append(str(file_path))

                except (OSError, PermissionError):
                    pass

                progress.update(task, advance=1)

        # 日期范围
        if all_mtimes:
            report.date_range = {
                "oldest": datetime.fromtimestamp(min(all_mtimes)).strftime("%Y-%m-%d"),
                "newest": datetime.fromtimestamp(max(all_mtimes)).strftime("%Y-%m-%d"),
            }

        # 最大的文件
        all_files.sort(key=lambda f: f["size"], reverse=True)
        report.top_largest = all_files[:top_n]

        # 同名文件（>=2 个即报告）
        dup_names = [
            {"name": name, "count": len(paths), "paths": paths[:5]}
            for name, paths in sorted(name_map.items(), key=lambda x: len(x[1]), reverse=True)
            if len(paths) >= 2
        ]
        report.top_duplicate_names = dup_names[:top_n]

        # 空目录
        report.empty_dirs = self._find_empty_dirs(path)

        # 文件类型排名（按数量排）
        report.file_types = dict(
            sorted(file_types.items(), key=lambda x: x[1]["count"], reverse=True)
        )

        # 大小分布
        report.size_distribution = size_dist

        # 自动发现的问题
        report.issues = self._detect_issues(report)

        return report

    def _find_empty_dirs(self, path: Path) -> list[str]:
        """查找空目录"""
        empty = []
        if self.recursive:
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if not dirs and not files:
                    empty.append(root)
        return empty

    def _detect_issues(self, report: AnalysisReport) -> list[str]:
        """自动检测问题"""
        issues = []

        # 大量同名文件
        total_dup = sum(d["count"] - 1 for d in report.top_duplicate_names)
        if total_dup > 10:
            issues.append(f"发现 {total_dup}+ 个同名文件，可能存在重复")

        # 某类型文件占比 > 50%
        if report.file_types:
            top_ext = list(report.file_types.keys())[0]
            top_count = report.file_types[top_ext]["count"]
            if report.total_files > 0 and top_count / report.total_files > 0.5:
                issues.append(f"「{top_ext}」类型文件占比超过 50%，建议分类存放")

        # 根目录文件过多
        try:
            root_files = sum(1 for f in Path(report.path).iterdir() if f.is_file())
            if root_files > 30:
                issues.append(f"根目录下有 {root_files} 个文件，建议归类到子文件夹")
        except (OSError, PermissionError):
            pass

        # 空目录
        if report.empty_dirs:
            issues.append(f"存在 {len(report.empty_dirs)} 个空目录")

        # 无扩展名文件
        no_ext = report.file_types.get("(无扩展名)", {}).get("count", 0)
        if no_ext > 5:
            issues.append(f"存在 {no_ext} 个无扩展名文件")

        return issues


def print_report(report: AnalysisReport, issues_only: bool = False) -> None:
    """用 Rich 美化打印分析报告"""
    from rich.panel import Panel
    from rich.table import Table

    if not issues_only:
        console.print()
        console.print(Panel.fit(
            f"[bold]📊 分析报告: {report.path}[/bold]",
            border_style="cyan",
        ))

    # 问题优先展示
    if report.issues:
        console.print("\n[bold yellow]⚠️  发现的问题:[/bold yellow]")
        for issue in report.issues:
            console.print(f"  • {issue}")
    else:
        console.print("\n[bold green]✅ 未发现明显问题[/bold green]")

    if issues_only:
        return

    # 概况表格
    console.print()
    overview = Table(title="概况", title_style="bold")
    overview.add_column("指标", style="cyan")
    overview.add_column("数值", style="green")
    overview.add_row("文件总数", f"{report.total_files:,}")
    overview.add_row("目录总数", f"{report.total_dirs:,}")
    overview.add_row("总大小", _format_size(report.total_size))
    if report.date_range:
        overview.add_row("最早文件", report.date_range["oldest"])
        overview.add_row("最新文件", report.date_range["newest"])
    console.print(overview)

    # 文件类型分布
    if report.file_types:
        console.print()
        type_table = Table(title="文件类型 Top 10", title_style="bold")
        type_table.add_column("扩展名", style="cyan")
        type_table.add_column("数量", justify="right")
        type_table.add_column("大小", justify="right")
        for ext, info in list(report.file_types.items())[:10]:
            type_table.add_row(ext, f"{info['count']:,}", _format_size(info["size"]))
        console.print(type_table)

    # 大小分布
    console.print()
    size_table = Table(title="大小分布", title_style="bold")
    size_table.add_column("区间", style="cyan")
    size_table.add_column("文件数", justify="right")
    for interval, count in report.size_distribution.items():
        if count > 0:
            size_table.add_row(interval, f"{count:,}")
    console.print(size_table)

    # 最大的文件
    if report.top_largest:
        console.print()
        console.print("[bold]🔝 最大的文件:[/bold]")
        for f in report.top_largest[:5]:
            console.print(f"  {_format_size(f['size']):>8s}  [{f['mtime_str']}] {f['path']}")

    # 同名文件
    if report.top_duplicate_names:
        console.print()
        console.print("[bold]🔁 同名文件:[/bold]")
        for d in report.top_duplicate_names[:5]:
            console.print(f"  {d['name']} ({d['count']} 个副本)")
