"""日期整理器——将文件按日期归类到文件夹"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from file_organizer.config import DEFAULT_DATE_PATTERN
from file_organizer.metadata import extract_date
from file_organizer.reporter import (
    console,
    create_progress,
    print_date_organize_report,
    print_dry_run_notice,
    print_error,
    print_success,
    print_warning,
)
from file_organizer.scanner import FileScanner


class DateOrganizer:
    """按日期整理文件到归档目录"""

    def __init__(
        self,
        pattern: str = DEFAULT_DATE_PATTERN,
        mode: str = "move",
        conflict: str = "skip",
    ):
        """
        参数：
            pattern: 目标路径的日期格式，如 "{year}/{month:02d}" 或 "{year}-{month:02d}-{day:02d}"
            mode: "move" 移动文件 / "copy" 复制文件
            conflict: 冲突处理策略 — "skip" 跳过 / "rename" 自动重命名 / "overwrite" 覆盖
        """
        self.pattern = pattern
        self.mode = mode
        self.conflict = conflict

    def organize(
        self,
        source: Path,
        dest: Optional[Path] = None,
        recursive: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """
        执行日期整理。

        参数：
            source: 源目录
            dest: 目标目录，默认等同于 source
            recursive: 是否递归扫描
            dry_run: 仅预览不执行

        返回：
            {"total": int, "processed": int, "skipped": int, "errors": int, "details": list}
        """
        if dest is None:
            dest = source

        source = source.resolve()
        dest = dest.resolve()

        if not source.exists():
            print_error(f"源目录不存在: {source}")
            return {"total": 0, "processed": 0, "skipped": 0, "errors": 0, "details": []}

        if dry_run:
            print_dry_run_notice()

        # 预创建目标目录
        if not dry_run:
            dest.mkdir(parents=True, exist_ok=True)

        # 扫描文件
        scanner = FileScanner(recursive=recursive)
        files = scanner.scan(source)
        total = len(files)

        console.print(f"📂 扫描到 [bold]{total}[/bold] 个文件")
        console.print(f"📅 日期格式: [cyan]{self.pattern}[/cyan]")
        console.print(f"📁 目标目录: [cyan]{dest}[/cyan]")
        console.print()

        processed = 0
        skipped = 0
        errors = 0
        details = []

        progress = create_progress()
        task = progress.add_task("整理中...", total=total)

        with progress:
            for file_path in files:
                try:
                    result = self._process_one(file_path, dest, dry_run)
                    details.append(result)

                    if result["status"] == "ok":
                        processed += 1
                    elif result["status"] == "skipped":
                        skipped += 1
                    else:
                        errors += 1
                except Exception as e:
                    errors += 1
                    details.append({
                        "file": str(file_path),
                        "status": "error",
                        "error": str(e),
                    })

                progress.update(task, advance=1, description=f"整理中... [{processed}/{total}]")

        report = {
            "total": total,
            "processed": processed,
            "skipped": skipped,
            "errors": errors,
            "details": details,
        }

        print_date_organize_report(total, processed, skipped, errors, dry_run)
        return report

    def _process_one(self, file_path: Path, dest: Path, dry_run: bool) -> dict:
        """处理单个文件"""
        result = {
            "file": str(file_path),
            "status": "ok",
            "date_found": None,
            "dest_path": None,
        }

        # 提取日期
        date = extract_date(file_path)
        if date is None:
            result["status"] = "skipped"
            result["reason"] = "无法提取日期"
            return result

        result["date_found"] = date.isoformat()

        # 构建目标路径
        dest_path = self._build_dest_path(file_path, date, dest)
        result["dest_path"] = str(dest_path)

        # 如果目标路径和源路径相同，跳过
        if dest_path == file_path:
            result["status"] = "skipped"
            result["reason"] = "已在目标位置"
            return result

        # 冲突处理
        if dest_path.exists():
            if self.conflict == "skip":
                result["status"] = "skipped"
                result["reason"] = "目标文件已存在 (策略: skip)"
                return result
            elif self.conflict == "rename":
                dest_path = self._auto_rename(dest_path)
            elif self.conflict == "overwrite":
                pass

        # 执行
        if dry_run:
            console.print(f"  [dim]→[/dim] {file_path.name} [dim]→[/dim] {dest_path}")
        else:
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if self.mode == "move":
                    shutil.move(str(file_path), str(dest_path))
                else:
                    shutil.copy2(str(file_path), str(dest_path))
            except (OSError, PermissionError) as e:
                result["status"] = "error"
                result["error"] = str(e)

        return result

    def _build_dest_path(self, file_path: Path, date: datetime, dest: Path) -> Path:
        """根据日期模板构建目标路径"""
        # 支持的模板变量
        folder_name = self.pattern.format(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=date.hour,
        )
        return dest / folder_name / file_path.name

    @staticmethod
    def _auto_rename(path: Path) -> Path:
        """自动生成不冲突的文件名：在原文件名后加 (1), (2), ..."""
        if not path.exists():
            return path
        stem = path.stem
        ext = path.suffix
        counter = 1
        while True:
            new_path = path.parent / f"{stem} ({counter}){ext}"
            if not new_path.exists():
                return new_path
            counter += 1
