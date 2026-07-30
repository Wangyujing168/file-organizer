"""杂乱清理器——识别旧文件、临时文件、空目录、大文件"""

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from file_organizer.reporter import (
    console,
    create_progress,
    print_dry_run_notice,
    print_error,
    print_info,
    print_success,
    _format_size,
)
from file_organizer.scanner import FileScanner

# 常见临时文件模式
TEMP_PATTERNS = [
    "*.tmp", "*.temp", "*.swp", "*.swo",
    "~$*", "._*", "*.lock", "*.cache", "Thumbs.db",
    ".DS_Store", "*.part", "*.crdownload",
    # CAD 相关的临时文件
    "*.dwl", "*.dwl2", "*.ac$", "*.sv$",
]


@dataclass
class ClutterReport:
    """杂乱扫描报告"""

    path: str
    old_files: list[dict] = field(default_factory=list)
    temp_files: list[str] = field(default_factory=list)
    empty_dirs: list[str] = field(default_factory=list)
    large_files: list[dict] = field(default_factory=list)
    total_old_size: int = 0
    total_temp_size: int = 0
    total_large_size: int = 0


class ClutterFinder:
    """发现并清理杂乱文件"""

    def __init__(self, recursive: bool = True):
        self.recursive = recursive

    def find_old_files(self, path: Path, months: int = 6, top_n: int = 100) -> list[dict]:
        """查找 N 个月未修改的文件"""
        cutoff = datetime.now().timestamp() - months * 30 * 24 * 3600
        old_files = []

        scanner = FileScanner(recursive=self.recursive)
        for file_path in scanner.iter_files(path):
            try:
                mtime = file_path.stat().st_mtime
                if mtime < cutoff:
                    old_files.append({
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "mtime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
                    })
            except (OSError, PermissionError):
                pass

        old_files.sort(key=lambda f: f["size"], reverse=True)
        return old_files[:top_n]

    def find_temp_files(self, path: Path) -> list[str]:
        """查找临时文件"""
        import fnmatch

        temp_files = []
        scanner = FileScanner(recursive=self.recursive)
        for file_path in scanner.iter_files(path):
            name = file_path.name
            for pattern in TEMP_PATTERNS:
                if fnmatch.fnmatch(name, pattern):
                    temp_files.append(str(file_path))
                    break
        return temp_files

    def find_empty_dirs(self, path: Path) -> list[str]:
        """查找空目录"""
        empty = []
        if self.recursive:
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if not dirs and not files:
                    empty.append(root)
        return empty

    def find_large_files(self, path: Path, min_size: int, top_n: int = 50) -> list[dict]:
        """查找超过阈值的大文件"""
        large_files = []
        scanner = FileScanner(recursive=self.recursive, min_size=min_size)
        for file_path in scanner.iter_files(path):
            try:
                stat = file_path.stat()
                large_files.append({
                    "path": str(file_path),
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                })
            except (OSError, PermissionError):
                pass

        large_files.sort(key=lambda f: f["size"], reverse=True)
        return large_files[:top_n]

    def full_scan(
        self,
        path: Path,
        old_months: int = 12,
        large_threshold: int = 100 * 1024 * 1024,
    ) -> ClutterReport:
        """综合扫描全部杂乱"""
        console.print(f"🔍 综合扫描 [cyan]{path}[/cyan] ...")
        report = ClutterReport(path=str(path))

        # 旧文件
        console.print("  查找旧文件...")
        report.old_files = self.find_old_files(path, months=old_months)
        report.total_old_size = sum(f["size"] for f in report.old_files)

        # 临时文件
        console.print("  查找临时文件...")
        report.temp_files = self.find_temp_files(path)
        for tf in report.temp_files:
            try:
                report.total_temp_size += os.path.getsize(tf)
            except OSError:
                pass

        # 空目录
        console.print("  查找空目录...")
        report.empty_dirs = self.find_empty_dirs(path)

        # 大文件
        console.print("  查找大文件...")
        report.large_files = self.find_large_files(path, min_size=large_threshold)
        report.total_large_size = sum(f["size"] for f in report.large_files)

        return report


def print_clutter_report(report: ClutterReport, dry_run: bool = False) -> None:
    """打印杂乱扫描报告"""
    from rich.table import Table

    if dry_run:
        print_dry_run_notice()

    # 旧文件
    if report.old_files:
        console.print()
        console.print(f"[bold yellow]📦 旧文件[/bold yellow] "
                      f"({len(report.old_files)} 个, {_format_size(report.total_old_size)})")
        table = Table()
        table.add_column("修改日期", style="dim")
        table.add_column("大小", justify="right")
        table.add_column("路径", style="yellow")
        for f in report.old_files[:20]:
            table.add_row(f["mtime"], _format_size(f["size"]), f["path"])
        console.print(table)
        if len(report.old_files) > 20:
            console.print(f"  ... 还有 {len(report.old_files) - 20} 个")
    else:
        console.print("\n✅ 没有发现旧文件")

    # 临时文件
    if report.temp_files:
        console.print()
        console.print(f"[bold yellow]🗑️  临时文件[/bold yellow] "
                      f"({len(report.temp_files)} 个, {_format_size(report.total_temp_size)})")
        for f in report.temp_files[:20]:
            console.print(f"  {f}")
        if len(report.temp_files) > 20:
            console.print(f"  ... 还有 {len(report.temp_files) - 20} 个")
    else:
        console.print("✅ 没有发现临时文件")

    # 空目录
    if report.empty_dirs:
        console.print()
        console.print(f"[bold yellow]📁 空目录[/bold yellow] ({len(report.empty_dirs)} 个)")
        for d in report.empty_dirs[:20]:
            console.print(f"  {d}")
        if len(report.empty_dirs) > 20:
            console.print(f"  ... 还有 {len(report.empty_dirs) - 20} 个")
    else:
        console.print("✅ 没有发现空目录")

    # 大文件
    if report.large_files:
        console.print()
        total = _format_size(report.total_large_size)
        console.print(f"[bold yellow]💾 大文件[/bold yellow] "
                      f"({len(report.large_files)} 个, {total})")
        for f in report.large_files[:10]:
            console.print(f"  {_format_size(f['size']):>8s}  [{f['mtime']}] {f['path']}")
    else:
        console.print("✅ 没有发现大文件")

    # 汇总
    console.print()
    total_clutter = report.total_old_size + report.total_temp_size
    if total_clutter > 0:
        console.print(f"[bold]💡 可清理空间约: {_format_size(total_clutter)}[/bold]")


def clean_temp_files(temp_files: list[str], dry_run: bool = False) -> int:
    """删除临时文件，返回删除数量"""
    deleted = 0
    for file_path in temp_files:
        try:
            if dry_run:
                console.print(f"  [dim]将删除:[/dim] {file_path}")
            else:
                os.remove(file_path)
            deleted += 1
        except (OSError, PermissionError) as e:
            print_error(f"删除失败: {file_path} — {e}")
    return deleted


def clean_empty_dirs(base_path: str, empty_dirs: list[str] = None, dry_run: bool = False) -> int:
    """删除空目录，返回删除数量"""
    if empty_dirs is None:
        empty_dirs = []

    deleted = 0
    # 深度优先：先删深层的
    for dir_path in sorted(empty_dirs, key=lambda d: -d.count(os.sep)):
        try:
            if dry_run:
                console.print(f"  [dim]将删除空目录:[/dim] {dir_path}")
            else:
                os.rmdir(dir_path)
            deleted += 1
        except (OSError, PermissionError):
            pass
    return deleted
