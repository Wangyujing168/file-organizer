"""输出模块——基于 Rich 的美化输出：进度条、表格、树形视图"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.tree import Tree

console = Console()


def print_success(message: str) -> None:
    """打印成功消息（绿色）"""
    console.print(f"✅ {message}", style="green")


def print_error(message: str) -> None:
    """打印错误消息（红色）"""
    console.print(f"❌ {message}", style="red")


def print_warning(message: str) -> None:
    """打印警告消息（黄色）"""
    console.print(f"⚠️  {message}", style="yellow")


def print_info(message: str) -> None:
    """打印信息消息（蓝色）"""
    console.print(f"ℹ️  {message}", style="blue")


def print_dry_run_notice() -> None:
    """打印 dry-run 模式提示"""
    console.print("\n🔍 [bold yellow]DRY-RUN 模式[/bold yellow] — 不会实际修改任何文件\n")


def create_progress() -> Progress:
    """创建一个标准进度条"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def print_rename_preview(renames: list[tuple[Path, Path]]) -> None:
    """打印重命名预览表格"""
    if not renames:
        console.print("没有匹配的文件需要重命名。", style="dim")
        return

    table = Table(title="重命名预览", title_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("原文件名", style="red")
    table.add_column("新文件名", style="green")

    for i, (old, new) in enumerate(renames, 1):
        table.add_row(str(i), old.name, new.name)

    console.print(table)
    console.print(f"\n共 {len(renames)} 个文件将被重命名")


def print_duplicate_table(duplicates: dict[str, list[Path]]) -> None:
    """打印重复文件表格"""
    if not duplicates:
        console.print("没有发现重复文件。", style="dim")
        return

    total_sets = len(duplicates)
    total_files = sum(len(files) for files in duplicates.values())
    wasted_bytes = sum(
        (len(files) - 1) * files[0].stat().st_size
        for files in duplicates.values()
        if files
    )

    console.print(f"\n发现 [bold red]{total_sets}[/bold red] 组重复文件，"
                  f"共 {total_files} 个文件，"
                  f"可释放 [bold yellow]{_format_size(wasted_bytes)}[/bold yellow]\n")

    for i, (hash_val, files) in enumerate(duplicates.items(), 1):
        size_str = ""
        try:
            size_str = _format_size(files[0].stat().st_size)
        except OSError:
            pass

        console.print(f"[bold]重复组 #{i}[/bold] — 哈希: {hash_val[:12]}... — 大小: {size_str}")
        for f in files:
            mtime_str = ""
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass
            console.print(f"  📄 {f}  [dim]({mtime_str})[/dim]")
        console.print()


def print_date_organize_report(
    total: int,
    processed: int,
    skipped: int,
    errors: int,
    dry_run: bool,
) -> None:
    """打印日期整理的汇总报告"""
    console.print()
    table = Table(title="整理结果汇总", title_style="bold cyan")
    table.add_column("项目", style="cyan")
    table.add_column("数量", justify="right")

    table.add_row("扫描文件总数", str(total))
    table.add_row("已整理", f"[green]{processed}[/green]")
    table.add_row("已跳过", f"[yellow]{skipped}[/yellow]" if skipped else "0")
    table.add_row("错误", f"[red]{errors}[/red]" if errors else "0")

    console.print(table)

    if dry_run:
        print_dry_run_notice()
    else:
        print_success(f"整理完成，共处理 {processed} 个文件")


def _format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
