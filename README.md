# fileorg - 文件整理工具

智能文件整理助手：分析、整理、清理、重命名文件的 CLI 工具。

## 安装

```bash
pip install -e .
```

## 用法概览

```
fileorg --help
```

---

### 七大功能

#### 1. 目录分析 `fileorg analyze`

扫描目录并生成诊断报告：文件类型分布、大小区间、日期范围、发现问题。

```bash
# 完整分析报告
fileorg analyze run ./

# 只看问题
fileorg analyze run ./ --issues-only

# JSON 格式输出
fileorg analyze run ./ --output json
```

#### 2. 按日期整理 `fileorg date sort`

将文件按日期归档到目录结构中，支持 EXIF 拍摄日期提取。

```bash
fileorg date sort ./photos
fileorg date sort ./photos --pattern "{year}-{month:02d}-{day:02d}" --dry-run
fileorg date sort ./downloads ./organized --mode copy
fileorg date sort ./photos --conflict rename
```

#### 3. 查找和删除重复文件 `fileorg dup`

两轮策略：先按大小分组，再对可疑文件做哈希比对，高效准确。

```bash
fileorg dup find ./downloads
fileorg dup find ./documents --recursive --min-size 1MB
fileorg dup clean ./downloads --keep newest --dry-run
fileorg dup clean ./downloads --keep oldest --confirm
```

#### 4. 杂乱清理 `fileorg clean`

识别并清理旧文件、临时文件、空目录、大文件。

```bash
# 查找 12 个月前的旧文件
fileorg clean old ./ --months 12 --dry-run

# 查找临时文件（*.tmp, *.bak, ~$* 等）
fileorg clean temp ./ --dry-run

# 查找空目录
fileorg clean empty ./ --dry-run

# 查找大文件
fileorg clean large ./ --min-size 100MB

# 综合扫描全部杂乱
fileorg clean all ./ --dry-run

# 确认删除临时文件
fileorg clean temp ./ --confirm
```

#### 5. 组织方案建议 `fileorg suggest`

根据文件类型模式，智能建议文件夹结构。

```bash
# 分析并建议结构
fileorg suggest run ./
```

#### 6. 批量重命名 `fileorg rename`

```bash
# 查找替换
fileorg rename replace "IMG_" "Photo_" ./
fileorg rename replace "\d+" "N" ./ --regex

# 添加前缀/后缀
fileorg rename prefix "vacation_" ./ --filter "*.jpg"
fileorg rename suffix "_final" ./ --filter "*.pdf"

# 顺序编号
fileorg rename sequence ./ --padding 3 --prefix "img-" --dry-run

# 大小写转换
fileorg rename case ./ --mode lower

# 替换空格
fileorg rename spaces ./ --replace "_"
```

#### 7. 撤销操作 `fileorg undo`

```bash
fileorg undo rename ~/.fileorg/undo_logs/rename_20240721_143000.json
```

---

### 核心原则

| 原则 | 说明 |
|---|---|
| 🔍 **先预览** | 任何修改操作支持 `--dry-run`，确认无误再执行 |
| ✅ **需确认** | 删除操作默认需确认，或加 `--confirm`/`-y` 跳过 |
| 📝 **可撤销** | 重命名操作自动记录日志，`fileorg undo rename` 恢复 |
| 🛡️ **不丢失** | 冲突处理支持 skip/rename/overwrite 三种策略 |

### 常用选项

| 选项 | 说明 |
|---|---|
| `--dry-run` | 预览模式，不实际修改文件 |
| `--recursive` / `--no-recursive` | 递归扫描子目录 |
| `--filter` / `-f` | 文件名过滤（如 `*.jpg`） |
| `--confirm` / `-y` | 跳过交互确认 |

## 项目结构

```
file-organization/
├── cli.py
├── pyproject.toml
├── README.md
├── file_organizer/
│   ├── scanner.py              # 文件扫描引擎
│   ├── hasher.py               # 哈希计算
│   ├── metadata.py             # EXIF/日期提取
│   ├── analyzer.py             # 目录分析器
│   ├── date_organizer.py       # 日期整理器
│   ├── duplicate_finder.py     # 重复查找器
│   ├── cleaner.py              # 杂乱清理器
│   ├── suggester.py            # 组织方案建议器
│   ├── batch_renamer.py        # 批量重命名器
│   ├── reporter.py             # Rich 美化输出
│   └── config.py               # 全局配置
└── tests/                      # 58 个测试
```

## 开发

```bash
# 运行测试
pytest tests/ -v

# 安装开发模式
pip install -e .
```
