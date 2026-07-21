"""批量重命名器——支持多种重命名操作和撤销"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from file_organizer.config import UNDO_LOG_DIR
from file_organizer.reporter import (
    console,
    create_progress,
    print_dry_run_notice,
    print_error,
    print_rename_preview,
    print_success,
    print_warning,
)
from file_organizer.scanner import FileScanner


class RenameOperation:
    """重命名操作的基类"""

    def apply(self, filename: str) -> str:
        """对文件名（不含路径）应用操作，返回新文件名"""
        raise NotImplementedError


class SearchReplace(RenameOperation):
    """查找替换"""

    def __init__(self, search: str, replace: str, use_regex: bool = False):
        self.search = search
        self.replace = replace
        self.use_regex = use_regex

    def apply(self, filename: str) -> str:
        if self.use_regex:
            return re.sub(self.search, self.replace, filename)
        else:
            return filename.replace(self.search, self.replace)


class AddPrefix(RenameOperation):
    """添加前缀"""

    def __init__(self, prefix: str):
        self.prefix = prefix

    def apply(self, filename: str) -> str:
        return self.prefix + filename


class AddSuffix(RenameOperation):
    """添加后缀（在扩展名之前）"""

    def __init__(self, suffix: str):
        self.suffix = suffix

    def apply(self, filename: str) -> str:
        stem, ext = os.path.splitext(filename)
        return stem + self.suffix + ext


class SequentialNumber(RenameOperation):
    """顺序编号重命名"""

    def __init__(
        self,
        start: int = 1,
        step: int = 1,
        padding: int = 3,
        prefix: str = "",
        suffix: str = "",
    ):
        self.start = start
        self.step = step
        self.padding = padding
        self.prefix = prefix
        self.suffix = suffix
        self._counter = start

    def apply(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1]
        seq = f"{self._counter:0{self.padding}d}"
        new_name = f"{self.prefix}{seq}{self.suffix}{ext}"
        self._counter += self.step
        return new_name

    def reset(self) -> None:
        """重置计数器"""
        self._counter = self.start


class CaseConvert(RenameOperation):
    """大小写转换"""

    def __init__(self, mode: str = "lower"):
        self.mode = mode  # lower / upper / title

    def apply(self, filename: str) -> str:
        stem, ext = os.path.splitext(filename)
        if self.mode == "lower":
            return stem.lower() + ext.lower()
        elif self.mode == "upper":
            return stem.upper() + ext.upper()
        elif self.mode == "title":
            return stem.title() + ext
        return filename


class ReplaceSpaces(RenameOperation):
    """替换空格"""

    def __init__(self, replacement: str = "_"):
        self.replacement = replacement

    def apply(self, filename: str) -> str:
        return filename.replace(" ", self.replacement)


class BatchRenamer:
    """批量重命名器"""

    def __init__(self):
        pass

    def rename(
        self,
        source: Path,
        operations: list[RenameOperation],
        filter_pattern: Optional[str] = None,
        recursive: bool = False,
        dry_run: bool = False,
    ) -> list[tuple[Path, Path]]:
        """
        批量重命名文件。

        参数：
            source: 源目录或文件
            operations: 重命名操作列表（按顺序应用）
            filter_pattern: 文件名过滤 glob 模式
            recursive: 是否递归扫描子目录
            dry_run: 仅预览不执行

        返回：[(原路径, 新路径), ...]
        """
        source = source.resolve()

        if not source.exists():
            print_error(f"路径不存在: {source}")
            return []

        if dry_run:
            print_dry_run_notice()

        # 扫描文件
        include = [filter_pattern] if filter_pattern else None
        scanner = FileScanner(recursive=recursive, include_patterns=include)
        files = scanner.scan(source)

        if not files:
            console.print("没有匹配的文件", style="dim")
            return []

        # 预览变更
        renames: list[tuple[Path, Path]] = []

        for file_path in files:
            new_name = file_path.name
            for op in operations:
                new_name = op.apply(new_name)

            if new_name != file_path.name:
                new_path = file_path.parent / new_name
                renames.append((file_path, new_path))

        # 检查命名冲突
        renames = self._resolve_conflicts(renames)

        # 显示预览
        print_rename_preview(renames)

        # 执行
        if not dry_run and renames:
            console.print()
            progress = create_progress()
            task = progress.add_task("重命名中...", total=len(renames))

            undo_log = []
            with progress:
                for old_path, new_path in renames:
                    try:
                        old_path.rename(new_path)
                        undo_log.append({
                            "old": str(old_path),
                            "new": str(new_path),
                            "time": datetime.now().isoformat(),
                        })
                        progress.update(task, advance=1)
                    except (OSError, PermissionError) as e:
                        print_error(f"重命名失败: {old_path.name} — {e}")

            # 保存撤销日志
            self._save_undo_log(undo_log)
            print_success(f"已重命名 {len(undo_log)} 个文件")

        return renames

    def _resolve_conflicts(
        self, renames: list[tuple[Path, Path]]
    ) -> list[tuple[Path, Path]]:
        """检测并解决重命名后的路径冲突"""
        seen_new: set[str] = set()
        resolved: list[tuple[Path, Path]] = []

        for old_path, new_path in renames:
            target = str(new_path)
            if target in seen_new:
                # 自动加后缀
                stem = new_path.stem
                ext = new_path.suffix
                counter = 1
                while True:
                    alt = new_path.parent / f"{stem} ({counter}){ext}"
                    if str(alt) not in seen_new:
                        new_path = alt
                        break
                    counter += 1
            seen_new.add(str(new_path))
            resolved.append((old_path, new_path))

        return resolved

    def _save_undo_log(self, log: list[dict]) -> Path:
        """保存撤销日志"""
        undo_dir = Path(os.path.expanduser(UNDO_LOG_DIR))
        undo_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = undo_dir / f"rename_{timestamp}.json"

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)

        console.print(f"📝 撤销日志已保存: [dim]{log_file}[/dim]")
        return log_file

    @staticmethod
    def undo(log_file: Path) -> list[Path]:
        """
        根据撤销日志文件恢复重命名。

        返回：成功恢复的文件路径列表
        """
        log_file = Path(log_file)
        if not log_file.exists():
            print_error(f"撤销日志不存在: {log_file}")
            return []

        with open(log_file, "r", encoding="utf-8") as f:
            log = json.load(f)

        restored = []
        for entry in reversed(log):
            old_path = Path(entry["new"])  # 现在是"新"文件名
            new_path = Path(entry["old"])  # 恢复到"旧"文件名

            if old_path.exists():
                try:
                    old_path.rename(new_path)
                    console.print(f"  ↩ {old_path.name} → {new_path.name}")
                    restored.append(new_path)
                except (OSError, PermissionError) as e:
                    print_error(f"撤销失败: {old_path.name} — {e}")

        print_success(f"已撤销 {len(restored)} 个文件的重命名")
        return restored
