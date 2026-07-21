"""重复文件查找器——查找、审查和清理重复文件"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from file_organizer.hasher import FileHasher
from file_organizer.reporter import (
    console,
    create_progress,
    print_dry_run_notice,
    print_error,
    print_info,
    print_success,
    print_warning,
    _format_size,
)
from file_organizer.scanner import FileScanner


def _get_file_info(file_path: Path) -> dict:
    """获取单个文件的信息"""
    info = {"path": str(file_path), "name": file_path.name, "size": 0, "mtime": "", "mtime_ts": 0}
    try:
        stat = file_path.stat()
        info["size"] = stat.st_size
        info["mtime_ts"] = stat.st_mtime
        info["mtime"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    except (OSError, PermissionError):
        pass
    return info


def _score_filename(name: str) -> int:
    """给文件名打分：越清晰规范的分数越高（用于推荐保留哪个）"""
    score = 0
    lower = name.lower()
    # 包含 copy/副本/备份/backup 等关键词的扣分
    bad_words = ["copy", "副本", "备份", "backup", " (", "(1)", "(2)", "old", "旧"]
    for w in bad_words:
        if w in lower:
            score -= 10
    # 包含版本号/日期的加分
    if any(c.isdigit() for c in name):
        score += 2
    # 路径更短的加分（更接近根目录）
    return score


class DuplicateFinder:
    """查找和管理重复文件"""

    def __init__(self, min_size: int = 0):
        self.min_size = min_size
        self.hasher = FileHasher()

    def find(self, source: Path, recursive: bool = True) -> dict[str, list[Path]]:
        """查找重复文件。两轮策略：先按大小分组，再哈希比对。"""
        source = source.resolve()
        if not source.exists():
            print_error(f"目录不存在: {source}")
            return {}

        console.print(f"🔍 扫描 [cyan]{source}[/cyan] ...")

        scanner = FileScanner(recursive=recursive, min_size=self.min_size)
        size_groups = scanner.scan_by_size(source)

        total_candidates = sum(len(files) for files in size_groups.values())
        console.print(f"📏 第 1 轮: 发现 {len(size_groups)} 个大小碰撞组，"
                      f"共 {total_candidates} 个候选文件")

        if not size_groups:
            console.print("没有重复文件的候选（所有文件大小唯一）")
            return {}

        console.print("🔬 第 2 轮: 计算文件哈希...")
        hash_groups: dict[str, list[Path]] = {}

        progress = create_progress()
        task = progress.add_task("哈希计算中...", total=total_candidates)

        with progress:
            for files in size_groups.values():
                for file_path in files:
                    file_hash = self.hasher.hash_file(file_path)
                    if file_hash:
                        if file_hash not in hash_groups:
                            hash_groups[file_hash] = []
                        hash_groups[file_hash].append(file_path)
                    progress.update(task, advance=1)

        duplicates = {
            h: files for h, files in hash_groups.items() if len(files) >= 2
        }

        return duplicates

    def review(self, duplicates: dict[str, list[Path]], keep: str = "newest",
               max_groups: int = 0) -> list[dict]:
        """
        逐组审查重复文件，标记推荐保留和删除的文件。

        参数：
            duplicates: find() 返回的重复文件字典
            keep: 保留策略
            max_groups: 最多展示多少组（0=全部）

        返回：[{hash, files, keep_file, delete_files, recommendation, total_waste}]
        """
        if not duplicates:
            console.print("没有重复文件需要审查")
            return []

        review_results = []
        total_waste = 0
        total_delete = 0

        # 按浪费空间排序（大的优先展示）
        sorted_dupes = sorted(
            duplicates.items(),
            key=lambda x: x[1][0].stat().st_size * (len(x[1]) - 1) if x[1] else 0,
            reverse=True,
        )

        groups_to_show = sorted_dupes[:max_groups] if max_groups > 0 else sorted_dupes

        for idx, (hash_val, files) in enumerate(groups_to_show, 1):
            # 收集文件信息
            file_infos = [_get_file_info(f) for f in files]

            # 按策略排序
            if keep == "newest":
                file_infos.sort(key=lambda f: f["mtime_ts"], reverse=True)
            elif keep == "oldest":
                file_infos.sort(key=lambda f: f["mtime_ts"])
            else:  # "first" — 按文件名质量
                file_infos.sort(key=lambda f: _score_filename(f["name"]), reverse=True)

            keep_file = file_infos[0]
            delete_files = file_infos[1:]

            # 生成推荐理由
            if keep == "newest":
                reason = "最新修改"
            elif keep == "oldest":
                reason = "最早版本"
            else:
                reason = "文件名最清晰"

            # 如果 keep_file 恰好也是路径最短或名字最清晰的，加强理由
            if keep_file is file_infos[0]:
                best_name = max(file_infos, key=lambda f: _score_filename(f["name"]))
                if keep_file["path"] == best_name["path"]:
                    reason += "，文件名最规范"
                # 检查是否路径最短
                shortest = min(file_infos, key=lambda f: len(f["path"]))
                if keep_file["path"] == shortest["path"]:
                    reason += "，路径最简洁"

            waste = keep_file["size"] * len(delete_files)
            total_waste += waste
            total_delete += len(delete_files)

            review_results.append({
                "index": idx,
                "hash": hash_val,
                "file_size": keep_file["size"],
                "file_size_human": _format_size(keep_file["size"]),
                "total_copies": len(file_infos),
                "keep_file": keep_file,
                "delete_files": delete_files,
                "recommendation": reason,
                "all_files": file_infos,
            })

        # 打印汇总
        console.print()
        console.print(f"[bold]📋 审查结果: 共 {len(review_results)} 组重复"
                      f"（共 {total_delete + len(review_results)} 个文件）[/bold]")
        console.print(f"   🟢 [green]保留 {len(review_results)} 个[/green]  |  "
                      f"🔴 [red]删除 {total_delete} 个[/red]  |  "
                      f"💾 [yellow]释放 {_format_size(total_waste)}[/yellow]")
        console.print()

        return review_results

    def print_review_detail(self, review_results: list[dict], group_index: int = 0,
                            show_all: bool = False) -> None:
        """打印审查详情。使用列表格式确保路径完整显示。"""
        from rich.panel import Panel

        items = [review_results[group_index - 1]] if group_index > 0 else review_results

        for result in items:
            waste = _format_size(result["file_size"] * len(result["delete_files"]))
            console.print(Panel.fit(
                f"[bold]重复组 #{result['index']}[/bold]  "
                f"大小: {result['file_size_human']}  |  "
                f"副本数: {result['total_copies']}  |  "
                f"浪费: {waste}",
                border_style="yellow",
            ))

            if show_all:
                # 保留的文件
                console.print(f"  🟢 [bold green]保留[/bold green] "
                            f"[green]{result['keep_file']['name']}[/green]  "
                            f"[dim]({result['keep_file']['mtime']})[/dim]")
                console.print(f"     [dim]{result['keep_file']['path']}[/dim]")
                console.print()

                # 删除的文件
                for f in result["delete_files"]:
                    console.print(f"  🔴 [bold red]删除[/bold red] "
                                f"[red]{f['name']}[/red]  "
                                f"[dim]({f['mtime']})[/dim]")
                    console.print(f"     [dim]{f['path']}[/dim]")
                    console.print()

            # 推荐说明
            console.print(f"  💡 推荐保留: [green]{result['keep_file']['name']}[/green]"
                         f" — {result['recommendation']}")

            if not show_all:
                console.print(f"  🔴 将删除 [red]{len(result['delete_files'])} 个副本[/red]:")
                for f in result["delete_files"]:
                    console.print(f"     [dim]{f['mtime']} | {f['name']}[/dim]")
                    console.print(f"     [dim]{f['path']}[/dim]")

            console.print()

    def clean(
        self,
        duplicates: dict[str, list[Path]],
        keep: str = "oldest",
        dry_run: bool = False,
        confirm: bool = False,
        reviewed: Optional[list[dict]] = None,
    ) -> dict:
        """
        删除重复文件。支持先审查再删除。

        参数：
            duplicates: find() 返回的重复文件字典（如果传了 reviewed 则忽略）
            keep: 保留策略 — "oldest" / "newest" / "first"
            dry_run: 仅预览不删除
            confirm: 是否需要交互确认
            reviewed: review() 的返回结果。如果提供，将使用其中标记的 keep/delete 决定。
        """
        if not duplicates and not reviewed:
            console.print("没有重复文件需要清理")
            return {"deleted": 0, "freed_bytes": 0, "errors": 0}

        if dry_run:
            print_dry_run_notice()

        to_delete: list[Path] = []
        to_keep: list[Path] = []

        if reviewed:
            # 使用审查结果中的决策
            for result in reviewed:
                to_keep.append(Path(result["keep_file"]["path"]))
                for f in result["delete_files"]:
                    to_delete.append(Path(f["path"]))
        else:
            # 按策略自动决定
            for hash_val, files in duplicates.items():
                paths = list(files)
                if keep == "oldest":
                    paths.sort(key=lambda p: p.stat().st_mtime)
                elif keep == "newest":
                    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                to_keep.append(paths[0])
                for f in paths[1:]:
                    to_delete.append(f)

        # 确认
        if not dry_run and not confirm:
            total_size = sum(
                f.stat().st_size for f in to_delete if f.exists()
            )
            console.print(f"\n将删除 [bold red]{len(to_delete)}[/bold red] 个重复文件，"
                          f"释放 [bold yellow]{_format_size(total_size)}[/bold yellow]")
            response = input("确认删除？[y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                console.print("已取消")
                return {"deleted": 0, "freed_bytes": 0, "errors": 0}

        # 执行删除
        deleted = 0
        freed_bytes = 0
        errors = 0

        for file_path in to_delete:
            try:
                size = file_path.stat().st_size if file_path.exists() else 0
                if dry_run:
                    console.print(f"  [dim]将删除:[/dim] {file_path}")
                else:
                    os.remove(file_path)
                    console.print(f"  [red]已删除:[/red] {file_path}")
                deleted += 1
                freed_bytes += size
            except (OSError, PermissionError) as e:
                errors += 1
                print_error(f"删除失败: {file_path} — {e}")

        console.print()
        if dry_run:
            print_info(f"将删除 {deleted} 个文件，释放 {_format_size(freed_bytes)}")
        else:
            print_success(f"已删除 {deleted} 个重复文件，释放 {_format_size(freed_bytes)}")

        return {"deleted": deleted, "freed_bytes": freed_bytes, "errors": errors}
