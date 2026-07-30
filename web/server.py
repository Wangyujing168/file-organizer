"""FastAPI Web 服务——文件整理工具的 Web 界面"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from file_organizer.analyzer import Analyzer
from file_organizer.cleaner import ClutterFinder, clean_empty_dirs, clean_temp_files
from file_organizer.duplicate_finder import DuplicateFinder, _format_size
from file_organizer.suggester import Suggester

app = FastAPI(title="文件整理工具", version="2.0.0")

# 静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

TEMPLATE_DIR = Path(__file__).parent / "templates"


# ============================================================
# 页面
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    html_path = TEMPLATE_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>Web 界面未找到，请先构建</h1>"


# ============================================================
# 目录浏览 API
# ============================================================
@app.get("/api/browse")
async def browse(path: str = Query(default="/")):
    """浏览目录，返回子目录和文件列表"""
    p = Path(path).expanduser()
    result = {
        "path": str(p.resolve()),
        "exists": p.exists(),
        "is_dir": p.is_dir() if p.exists() else False,
        "parent": str(p.parent.resolve()) if p != p.parent else None,
        "children": [],
        "drives": [],
    }

    # Windows 根目录：列出盘符
    if sys.platform == "win32" and (path == "/" or path == ""):
        import string
        for letter in string.ascii_uppercase:
            d = Path(f"{letter}:\\")
            if d.exists():
                result["drives"].append({"name": f"{letter}:", "path": f"{letter}:\\"})
        return result

    if not p.exists():
        return result

    if p.is_dir():
        try:
            items = []
            for item in sorted(p.iterdir()):
                try:
                    is_dir = item.is_dir()
                    items.append({
                        "name": item.name,
                        "path": str(item.resolve()),
                        "is_dir": is_dir,
                        "size": "" if is_dir else _format_size(item.stat().st_size),
                        "mtime": "",
                    })
                except (OSError, PermissionError):
                    pass
            result["children"] = items
        except PermissionError:
            pass

    return result


# ============================================================
# 分析 API
# ============================================================
@app.post("/api/analyze")
async def analyze(path: str = Query(...), recursive: bool = Query(True)):
    """分析目录"""
    p = Path(path).expanduser()
    analyzer = Analyzer(recursive=recursive)
    report = analyzer.analyze(p)
    return report.to_dict()


# ============================================================
# 重复文件 API
# ============================================================
@app.post("/api/dup/find")
async def dup_find(path: str = Query(...), recursive: bool = Query(True)):
    """查找重复文件"""
    p = Path(path).expanduser()
    finder = DuplicateFinder()
    duplicates = finder.find(p, recursive=recursive)

    if not duplicates:
        return {"groups": [], "total_groups": 0, "total_files": 0, "total_waste": 0, "total_waste_human": "0 B"}

    total = sum(len(files) for files in duplicates.values())
    waste = sum((len(files) - 1) * files[0].stat().st_size for files in duplicates.values() if files)

    return {
        "groups": len(duplicates),
        "total_groups": len(duplicates),
        "total_files": total,
        "total_waste": waste,
        "total_waste_human": _format_size(waste),
    }


@app.post("/api/dup/review")
async def dup_review(
    path: str = Query(...),
    keep: str = Query("newest"),
    top: int = Query(50),
):
    """审查重复文件"""
    p = Path(path).expanduser()
    finder = DuplicateFinder()
    duplicates = finder.find(p)

    if not duplicates:
        return {"groups": [], "summary": {"keep": 0, "delete": 0, "waste": "0 B"}}

    keep_strategy = "newest" if keep == "newest" else "oldest" if keep == "oldest" else "first"
    max_groups = top if top > 0 else len(duplicates)
    reviewed = finder.review(duplicates, keep=keep_strategy, max_groups=max_groups)

    # 转为 JSON 友好格式
    groups = []
    total_delete = 0
    total_waste = 0
    for r in reviewed:
        groups.append({
            "index": r["index"],
            "file_size_human": r["file_size_human"],
            "total_copies": r["total_copies"],
            "waste": _format_size(r["file_size"] * len(r["delete_files"])),
            "keep_file": r["keep_file"],
            "delete_files": r["delete_files"],
            "recommendation": r["recommendation"],
        })
        total_delete += len(r["delete_files"])
        total_waste += r["file_size"] * len(r["delete_files"])

    return {
        "groups": groups,
        "summary": {
            "keep": len(reviewed),
            "delete": total_delete,
            "waste": _format_size(total_waste),
        },
    }


@app.post("/api/dup/clean")
async def dup_clean(
    path: str = Query(...),
    keep: str = Query("newest"),
    dry_run: bool = Query(False),
):
    """执行重复文件清理"""
    p = Path(path).expanduser()
    finder = DuplicateFinder()
    duplicates = finder.find(p)

    if not duplicates:
        return {"deleted": 0, "freed": "0 B", "dry_run": dry_run}

    result = finder.clean(duplicates, keep=keep, dry_run=dry_run, confirm=True)
    return {
        "deleted": result["deleted"],
        "freed": _format_size(result["freed_bytes"]),
        "errors": result["errors"],
        "dry_run": dry_run,
    }


# ============================================================
# 清理 API
# ============================================================
@app.post("/api/clean/scan")
async def clean_scan(
    path: str = Query(...),
    old_months: int = Query(12),
    large_threshold: str = Query("100MB"),
):
    """综合杂乱扫描"""
    from file_organizer.cleaner import _format_size as fs

    p = Path(path).expanduser()
    threshold = _parse_size(large_threshold)
    finder = ClutterFinder()
    report = finder.full_scan(p, old_months=old_months, large_threshold=threshold)

    return {
        "old_files": {"count": len(report.old_files), "size": fs(report.total_old_size)},
        "temp_files": {"count": len(report.temp_files), "size": fs(report.total_temp_size)},
        "empty_dirs": {"count": len(report.empty_dirs)},
        "large_files": {"count": len(report.large_files), "size": fs(report.total_large_size)},
        "total_clutter": fs(report.total_old_size + report.total_temp_size),
        # 详细列表（前端展示用）
        "old_files_list": report.old_files[:30],
        "temp_files_list": report.temp_files[:30],
        "empty_dirs_list": report.empty_dirs[:30],
        "large_files_list": report.large_files[:20],
    }


@app.post("/api/clean/execute")
async def clean_execute(
    path: str = Query(...),
    target: str = Query("temp"),  # temp / empty / old
    dry_run: bool = Query(False),
):
    """执行清理"""
    p = Path(path).expanduser()
    finder = ClutterFinder()

    if target == "temp":
        items = finder.find_temp_files(p)
        deleted = clean_temp_files(items, dry_run=dry_run)
    elif target == "empty":
        items = finder.find_empty_dirs(p)
        deleted = clean_empty_dirs(items, dry_run=dry_run)
    else:
        return {"deleted": 0, "message": "不支持的操作"}

    return {"deleted": deleted, "dry_run": dry_run}


# ============================================================
# 建议 API
# ============================================================
@app.post("/api/suggest")
async def suggest(path: str = Query(...)):
    """组织建议"""
    p = Path(path).expanduser()
    suggester = Suggester()
    suggestion = suggester.suggest(p)

    return {
        "scene": suggestion.scene,
        "structure": suggestion.proposed_structure,
        "moves": suggestion.file_moves[:20],
        "total_moves": suggestion.total_files_to_move,
        "tips": suggestion.tips,
    }


# ============================================================
# 健康检查
# ============================================================
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ============================================================
# 辅助函数
# ============================================================
def _parse_size(size_str: str) -> int:
    """解析大小字符串"""
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


def main(host: str = "127.0.0.1", port: int = 8888, open_browser: bool = True):
    """启动 Web 服务"""
    import threading
    import webbrowser

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()