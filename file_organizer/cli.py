"""文件整理工具 CLI —— 入口文件"""

import sys
from pathlib import Path
from typing import Optional

import typer

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from file_organizer.analyzer import Analyzer, print_report
from file_organizer.batch_renamer import (
    AddPrefix,
    AddSuffix,
    BatchRenamer,
    CaseConvert,
    ReplaceSpaces,
    SearchReplace,
    SequentialNumber,
)
from file_organizer.reporter import _format_size, console, print_dry_run_notice, print_success
from file_organizer.cleaner import (
    ClutterFinder,
    clean_empty_dirs,
    clean_temp_files,
    print_clutter_report,
)
from file_organizer.date_organizer import DateOrganizer
from file_organizer.duplicate_finder import DuplicateFinder
from file_organizer.suggester import Suggester, print_suggestion

app = typer.Typer(
    name="fileorg",
    help="📂 文件整理工具 — 分析、整理、清理、重命名文件的智能助手",
    add_completion=False,
)

# ============================================================
# 子命令组
# ============================================================
date_app = typer.Typer(help="按日期整理文件", add_completion=False)
app.add_typer(date_app, name="date")

dup_app = typer.Typer(help="查找和删除重复文件", add_completion=False)
app.add_typer(dup_app, name="dup")

rename_app = typer.Typer(help="批量重命名文件", add_completion=False)
app.add_typer(rename_app, name="rename")

analyze_app = typer.Typer(help="分析目录并生成诊断报告", add_completion=False)
app.add_typer(analyze_app, name="analyze")

clean_app = typer.Typer(help="清理杂乱文件（旧文件、临时文件、空目录、大文件）", add_completion=False)
app.add_typer(clean_app, name="clean")

suggest_app = typer.Typer(help="建议合理的文件夹结构", add_completion=False)
app.add_typer(suggest_app, name="suggest")

undo_app = typer.Typer(help="撤销操作", add_completion=False)
app.add_typer(undo_app, name="undo")


# ============================================================
# web 命令
# ============================================================
@app.command(name="web")
def web_start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址（0.0.0.0=局域网可访问）"),
    port: int = typer.Option(8888, "--port", "-p", help="监听端口"),
    no_browser: bool = typer.Option(False, "--no-browser", help="不自动打开浏览器"),
):
    """启动 Web 界面（浏览器中操作）"""
    from web.server import main
    url = f"http://127.0.0.1:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
    console.print(f"🚀 启动 Web 服务，浏览器打开: [cyan]{url}[/cyan]")
    main(host=host, port=port, open_browser=not no_browser)


# ============================================================
# date 子命令
# ============================================================
@date_app.command(name="sort")
def date_sort(
    source: str = typer.Argument(..., help="源目录路径"),
    dest: Optional[str] = typer.Argument(None, help="目标目录路径（默认等于源目录）"),
    pattern: str = typer.Option(
        "{year}/{month:02d}",
        "--pattern", "-p",
        help="日期目录格式，支持 {year} {month} {day} {hour}",
    ),
    mode: str = typer.Option(
        "move", "--mode", "-m",
        help="操作模式: move（移动） / copy（复制）",
    ),
    conflict: str = typer.Option(
        "skip", "--conflict", "-c",
        help="冲突处理: skip（跳过） / rename（自动重命名） / overwrite（覆盖）",
    ),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """按日期将文件归档到 YYYY/MM 等目录结构中"""
    source_path = Path(source).expanduser()
    dest_path = Path(dest).expanduser() if dest else None

    organizer = DateOrganizer(pattern=pattern, mode=mode, conflict=conflict)
    organizer.organize(source_path, dest_path, recursive=recursive, dry_run=dry_run)


# ============================================================
# dup 子命令
# ============================================================
@dup_app.command(name="find")
def dup_find(
    source: str = typer.Argument(..., help="源目录路径"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="递归扫描子目录"),
    min_size: str = typer.Option("0", "--min-size", help="最小文件大小（如 1KB, 1MB）"),
):
    """查找目录中的重复文件（仅统计，不展示详情）"""
    source_path = Path(source).expanduser()
    finder = DuplicateFinder(min_size=_parse_size(min_size))
    duplicates = finder.find(source_path, recursive=recursive)
    if duplicates:
        total = sum(len(files) for files in duplicates.values())
        waste = sum(
            (len(files) - 1) * files[0].stat().st_size
            for files in duplicates.values() if files
        )
        console.print(f"\n📊 总计: [bold red]{len(duplicates)}[/bold red] 组重复, "
                      f"{total} 个文件, 可释放 [bold yellow]{_format_size(waste)}[/bold yellow]")


@dup_app.command(name="review")
def dup_review(
    source: str = typer.Argument(..., help="源目录路径"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="递归扫描子目录"),
    min_size: str = typer.Option("0", "--min-size", help="最小文件大小（如 1KB, 1MB）"),
    keep: str = typer.Option("newest", "--keep", "-k", help="推荐保留策略: newest / oldest / best"),
    top: int = typer.Option(20, "--top", "-t", help="展示前 N 组（按浪费空间排序）"),
    show_all: bool = typer.Option(True, "--show-all/--compact", help="展示全部文件路径 / 精简模式"),
):
    """
    逐组审查重复文件，标记推荐保留/删除的文件

    每组会展示：
    - 所有文件路径、大小、修改日期
    - 推荐保留哪个、为什么
    - 将删除哪些副本
    """
    source_path = Path(source).expanduser()
    finder = DuplicateFinder(min_size=_parse_size(min_size))
    duplicates = finder.find(source_path, recursive=recursive)

    if not duplicates:
        return

    # 审查
    keep_strategy = "newest" if keep == "newest" else "oldest" if keep == "oldest" else "first"
    reviewed = finder.review(duplicates, keep=keep_strategy, max_groups=top)
    finder.print_review_detail(reviewed, show_all=show_all)

    if top > 0 and len(duplicates) > top:
        console.print(f"[dim]（仅展示前 {top} 组，共 {len(duplicates)} 组。用 --top 0 查看全部）[/dim]")


@dup_app.command(name="clean")
def dup_clean(
    source: str = typer.Argument(..., help="源目录路径"),
    keep: str = typer.Option("newest", "--keep", "-k", help="保留策略: newest / oldest / best"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="递归扫描子目录"),
    min_size: str = typer.Option("0", "--min-size", help="最小文件大小（如 1KB, 1MB）"),
    top: int = typer.Option(20, "--top", "-t", help="审查前 N 组（默认 20，0=全部审查）"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际删除"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="审查后直接删除，不再确认"),
):
    """
    审查并删除重复文件。

    流程：
    1. 扫描重复文件
    2. 按浪费空间排序，逐组展示推荐保留/删除的文件
    3. 确认后执行删除
    """
    source_path = Path(source).expanduser()
    finder = DuplicateFinder(min_size=_parse_size(min_size))
    duplicates = finder.find(source_path, recursive=recursive)

    if not duplicates:
        return

    # 先审查
    keep_strategy = "newest" if keep == "newest" else "oldest" if keep == "oldest" else "first"
    max_groups = top if top > 0 else 0
    reviewed = finder.review(duplicates, keep=keep_strategy, max_groups=max_groups)

    if not reviewed:
        return

    # 展示审查结果
    finder.print_review_detail(reviewed, show_all=True)

    # 确认执行
    total_delete = sum(len(r["delete_files"]) for r in reviewed)
    total_waste = sum(r["file_size"] * len(r["delete_files"]) for r in reviewed)

    if dry_run:
        print_dry_run_notice()
        console.print(f"将删除 [bold red]{total_delete}[/bold red] 个文件，"
                      f"释放 [bold yellow]{_format_size(total_waste)}[/bold yellow]")
        return

    if not confirm:
        console.print(f"将删除 [bold red]{total_delete}[/bold red] 个文件，"
                      f"释放 [bold yellow]{_format_size(total_waste)}[/bold yellow]")
        response = input("确认删除？[y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            console.print("已取消")
            return

    # 执行
    finder.clean(duplicates, keep=keep_strategy, dry_run=False, confirm=True, reviewed=reviewed)


# ============================================================
# rename 子命令
# ============================================================
@rename_app.command(name="replace")
def rename_replace(
    search: str = typer.Argument(..., help="要查找的文本"),
    replace: str = typer.Argument(..., help="替换为的文本"),
    path: str = typer.Argument(".", help="目标目录"),
    regex: bool = typer.Option(False, "--regex", "-r", help="使用正则表达式"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """查找替换文件名中的文本"""
    renamer = BatchRenamer()
    op = SearchReplace(search=search, replace=replace, use_regex=regex)
    renamer.rename(Path(path).expanduser(), [op], recursive=recursive, dry_run=dry_run)


@rename_app.command(name="prefix")
def rename_prefix(
    text: str = typer.Argument(..., help="要添加的前缀"),
    path: str = typer.Argument(".", help="目标目录"),
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="文件名过滤 glob，如 *.jpg"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """给文件名添加前缀"""
    renamer = BatchRenamer()
    op = AddPrefix(prefix=text)
    renamer.rename(
        Path(path).expanduser(), [op],
        filter_pattern=filter_pattern, recursive=recursive, dry_run=dry_run,
    )


@rename_app.command(name="suffix")
def rename_suffix(
    text: str = typer.Argument(..., help="要添加的后缀（在扩展名之前）"),
    path: str = typer.Argument(".", help="目标目录"),
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="文件名过滤 glob，如 *.jpg"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """给文件名添加后缀（在扩展名之前）"""
    renamer = BatchRenamer()
    op = AddSuffix(suffix=text)
    renamer.rename(
        Path(path).expanduser(), [op],
        filter_pattern=filter_pattern, recursive=recursive, dry_run=dry_run,
    )


@rename_app.command(name="sequence")
def rename_sequence(
    path: str = typer.Argument(".", help="目标目录"),
    start: int = typer.Option(1, "--start", "-s", help="起始编号"),
    step: int = typer.Option(1, "--step", help="编号步长"),
    padding: int = typer.Option(3, "--padding", "-p", help="编号位数（如 3 → 001）"),
    prefix: str = typer.Option("", "--prefix", help="编号前缀"),
    suffix: str = typer.Option("", "--suffix", help="编号后缀"),
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="文件名过滤 glob，如 *.jpg"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """将文件按顺序编号重命名"""
    renamer = BatchRenamer()
    op = SequentialNumber(start=start, step=step, padding=padding, prefix=prefix, suffix=suffix)
    renamer.rename(
        Path(path).expanduser(), [op],
        filter_pattern=filter_pattern, recursive=recursive, dry_run=dry_run,
    )


@rename_app.command(name="case")
def rename_case(
    path: str = typer.Argument(".", help="目标目录"),
    mode: str = typer.Option("lower", "--mode", "-m", help="转换模式: lower / upper / title"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """转换文件名大小写"""
    renamer = BatchRenamer()
    op = CaseConvert(mode=mode)
    renamer.rename(Path(path).expanduser(), [op], recursive=recursive, dry_run=dry_run)


@rename_app.command(name="spaces")
def rename_spaces(
    path: str = typer.Argument(".", help="目标目录"),
    replacement: str = typer.Option("_", "--replace", "-r", help="替换空格的字符"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="递归扫描子目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """替换文件名中的空格"""
    renamer = BatchRenamer()
    op = ReplaceSpaces(replacement=replacement)
    renamer.rename(Path(path).expanduser(), [op], recursive=recursive, dry_run=dry_run)


# ============================================================
# analyze 子命令
# ============================================================
@analyze_app.command(name="run")
def analyze_run(
    path: str = typer.Argument(".", help="要分析的目录路径"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="递归扫描子目录"),
    top_n: int = typer.Option(10, "--top", "-t", help="报告中展示的前 N 名"),
    issues_only: bool = typer.Option(False, "--issues-only", help="只显示发现的问题"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出格式: json"),
):
    """分析目录结构并生成诊断报告"""
    import json

    analyzer = Analyzer(recursive=recursive)
    report = analyzer.analyze(Path(path).expanduser(), top_n=top_n)

    if output == "json":
        console.print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print_report(report, issues_only=issues_only)


# ============================================================
# clean 子命令
# ============================================================
@clean_app.command(name="old")
def clean_old(
    path: str = typer.Argument(".", help="目标目录"),
    months: int = typer.Option(24, "--months", "-m", help="N 个月前的文件视为旧文件"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """查找 N 个月未修改的旧文件"""
    path = Path(path).expanduser()
    finder = ClutterFinder()
    old_files = finder.find_old_files(path, months=months)

    total = sum(f["size"] for f in old_files)
    console.print(f"\n找到 [bold yellow]{len(old_files)}[/bold yellow] 个"
                  f" {months} 个月前的旧文件，共 {_format_size(total)}")

    if old_files:
        from rich.table import Table
        table = Table()
        table.add_column("修改日期", style="dim")
        table.add_column("大小", justify="right")
        table.add_column("路径")
        for f in old_files[:30]:
            table.add_row(f["mtime"], _format_size(f["size"]), f["path"])
        console.print(table)

    if dry_run:
        print_dry_run_notice()


@clean_app.command(name="temp")
def clean_temp(
    path: str = typer.Argument(".", help="目标目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际删除"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="跳过确认，直接删除"),
):
    """查找并清理临时文件（*.tmp, *.bak, ~$* 等）"""
    path = Path(path).expanduser()
    finder = ClutterFinder()
    temp_files = finder.find_temp_files(path)

    if not temp_files:
        console.print("✅ 没有发现临时文件")
        return

    total = sum(Path(f).stat().st_size for f in temp_files if Path(f).exists())
    console.print(f"\n找到 [bold yellow]{len(temp_files)}[/bold yellow] 个临时文件，"
                  f"共 {_format_size(total)}")

    if dry_run:
        print_dry_run_notice()
        for f in temp_files[:30]:
            console.print(f"  [dim]将删除:[/dim] {f}")
        return

    if not confirm:
        response = input(f"\n确认删除 {len(temp_files)} 个临时文件？[y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            console.print("已取消")
            return

    deleted = clean_temp_files(temp_files, dry_run=False)
    print_success(f"已删除 {deleted} 个临时文件")


@clean_app.command(name="empty")
def clean_empty(
    path: str = typer.Argument(".", help="目标目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际删除"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="跳过确认，直接删除"),
):
    """查找并清理空目录"""
    path = Path(path).expanduser()
    finder = ClutterFinder()
    empty_dirs = finder.find_empty_dirs(path)

    if not empty_dirs:
        console.print("✅ 没有发现空目录")
        return

    console.print(f"\n找到 [bold yellow]{len(empty_dirs)}[/bold yellow] 个空目录")

    if dry_run:
        print_dry_run_notice()
        for d in empty_dirs[:30]:
            console.print(f"  [dim]将删除空目录:[/dim] {d}")
        return

    if not confirm:
        response = input(f"\n确认删除 {len(empty_dirs)} 个空目录？[y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            console.print("已取消")
            return

    deleted = clean_empty_dirs(str(path), empty_dirs=empty_dirs, dry_run=False)
    print_success(f"已删除 {deleted} 个空目录")


@clean_app.command(name="large")
def clean_large(
    path: str = typer.Argument(".", help="目标目录"),
    min_size: str = typer.Option("100MB", "--min-size", "-s", help="大小阈值（如 100MB, 1GB）"),
):
    """查找大文件"""
    path = Path(path).expanduser()
    finder = ClutterFinder()
    threshold = _parse_size(min_size)
    large_files = finder.find_large_files(path, min_size=threshold)

    total = sum(f["size"] for f in large_files)
    console.print(f"\n找到 [bold yellow]{len(large_files)}[/bold yellow] 个"
                  f" 大于 {min_size} 的文件，共 {_format_size(total)}")

    from rich.table import Table
    table = Table()
    table.add_column("修改日期", style="dim")
    table.add_column("大小", justify="right")
    table.add_column("路径")
    for f in large_files[:20]:
        table.add_row(f["mtime"], _format_size(f["size"]), f["path"])
    console.print(table)


@clean_app.command(name="all")
def clean_all(
    path: str = typer.Argument(".", help="目标目录"),
    old_months: int = typer.Option(24, "--old-months", help="旧文件判定月数"),
    large_threshold: str = typer.Option("100MB", "--large-threshold", help="大文件阈值"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览模式，不实际执行"),
):
    """综合扫描全部杂乱（旧文件 + 临时文件 + 空目录 + 大文件）"""
    path = Path(path).expanduser()
    finder = ClutterFinder()
    report = finder.full_scan(
        path,
        old_months=old_months,
        large_threshold=_parse_size(large_threshold),
    )
    print_clutter_report(report, dry_run=dry_run)


# ============================================================
# suggest 子命令
# ============================================================
@suggest_app.command(name="run")
def suggest_run(
    path: str = typer.Argument(".", help="目标目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅预览建议，不执行"),
):
    """分析目录并建议合理的文件夹结构"""
    path = Path(path).expanduser()
    suggester = Suggester()
    suggestion = suggester.suggest(path)
    print_suggestion(suggestion, dry_run=dry_run)


# ============================================================
# undo 子命令
# ============================================================
@undo_app.command(name="rename")
def undo_rename(
    log_file: str = typer.Argument(..., help="撤销日志文件路径（.json）"),
):
    """根据日志文件撤销批量重命名操作"""
    BatchRenamer.undo(Path(log_file).expanduser())


# ============================================================
# 辅助函数
# ============================================================
def _parse_size(size_str: str) -> int:
    """解析大小字符串为字节数"""
    size_str = size_str.strip().upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    for unit, mult in multipliers.items():
        if size_str.endswith(unit):
            try:
                return int(float(size_str[:-len(unit)]) * mult)
            except ValueError:
                pass
    try:
        return int(size_str)
    except ValueError:
        return 0


if __name__ == "__main__":
    # 双击启动时默认进入 Web 模式
    if len(sys.argv) <= 1:
        sys.argv.append("web")
    app()
