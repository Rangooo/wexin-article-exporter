# wechat_article_downloader.py 使用说明

## 与原始 Skill 的区别

原始 `download_article` 只将 HTML 文件保存到磁盘并返回文件路径，**不提取正文内容**。  
本脚本在此基础上补全了"从 HTML 提取纯文本正文"的环节，并封装了批量下载能力。

### 核心改进

| 能力 | 原始 Skill | 本脚本 |
|------|-----------|--------|
| 获取正文 | `download_article` 返回 HTML 文件路径，需手动读取 | 自动读取 HTML → 提取纯文本 → 清理临时文件 |
| 翻页 | `list_articles` 单次最多 20 篇 | 自动翻页获取全部文章 |
| 批量下载 | 不支持 | 多公众号批量下载，支持增量跳过 |
| 输出格式 | 散落 HTML 文件 | 每篇独立 `.txt` + 合并 `_全部文章.json` |

## 快速开始

### 前置条件

- Node.js >= 22
- 已运行 `bash scripts/bootstrap.sh` 完成依赖安装与构建
- 已通过 `session_start` → `login_get_qrcode` → `login_scan_status` → `login_finalize` 完成微信登录

### 配置

编辑 `wechat_article_downloader.py` 中的 `accounts` 字典：

```python
accounts = {
    "公众号名称": "fakeid",  # fakeid 通过 search_account 获取
}
```

获取 fakeid 示例：

```bash
node skills/wechat-article-exporter/scripts/wechat-exporter-skill.cjs \
  --json '{"action":"search_account","keyword":"人民日报"}'
```

### 运行

```bash
python3 wechat_article_downloader.py
```

### 输出结构

```
wechat_articles/
  公众号名称_文章列表.json        # 文章元数据列表
  公众号名称_全部文章.json        # 包含完整正文的合并文件
  公众号名称/
    文章标题1.txt                 # 单篇正文纯文本
    文章标题2.txt
```

### 增量下载

脚本会自动跳过已存在的 `.txt` 文件（文件大小 > 50 字节视为有效），支持断点续传。

### 限制下载数量

默认获取全部文章。如需限制数量：

```python
articles = list_all_articles(fakeid, max_total=50)
```
