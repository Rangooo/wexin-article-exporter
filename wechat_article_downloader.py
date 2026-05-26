#!/usr/bin/env python3
"""
微信公众号文章批量下载脚本（完善版）

相比原始 skill 仅返回摘要，此脚本能抓取完整正文内容。
原理：调用 download_article 获取 HTML 文件路径，再从 HTML 中提取正文文字。

用法：
    python wechat_article_downloader.py

依赖：
    - Node.js >= 22
    - 已运行 bootstrap.sh 构建
    - 已通过 session_start / login 流程登录微信

配置：
    修改下方 SKILL_DIR 为本地 skill 仓库路径
    修改 accounts 字典为目标公众号
"""

import json
import subprocess
import os
import re
import time
import html
import sys

# ============ 配置区域 ============
# 请修改为你的 skill 仓库本地路径
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(os.path.dirname(SKILL_DIR), "wechat_articles")
# Node 二进制路径（如果系统 Node >= 22 可留空）
NODE_BIN = ""
# ==================================

if NODE_BIN:
    os.environ["PATH"] = NODE_BIN + ":" + os.environ.get("PATH", "")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_skill(action, **kwargs):
    """调用 wechat-exporter-skill CLI"""
    params = {"action": action, **kwargs}
    json_str = json.dumps(params, ensure_ascii=False)
    env = os.environ.copy()
    env["NITRO_BOOT_MODE"] = "embedded"

    skill_script = os.path.join(SKILL_DIR, "skills", "wechat-article-exporter", "scripts", "wechat-exporter-skill.cjs")
    cmd = ["node", skill_script, "--json", json_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=SKILL_DIR, env=env)

    for line in result.stdout.split('\n'):
        line = line.strip()
        if line.startswith('{') and '"ok"' in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"ok": False, "raw": result.stdout[:300]}


def list_all_articles(fakeid, max_total=30):
    """获取公众号文章列表（自动翻页）"""
    all_articles = []
    begin = 0
    size = 20
    while len(all_articles) < max_total:
        print(f"  获取文章列表 begin={begin}...", flush=True)
        result = run_skill("list_articles", fakeid=fakeid, begin=begin, size=size)
        if not result.get("ok"):
            print(f"  ❌ 获取失败", flush=True)
            break
        articles = result.get("data", {}).get("response", {}).get("articles", [])
        if not articles:
            break
        all_articles.extend(articles)
        print(f"  ✅ 获取到 {len(articles)} 篇，累计 {len(all_articles)} 篇", flush=True)
        if len(articles) < size:
            break
        begin += size
        time.sleep(1)
    return all_articles[:max_total]


def extract_text_from_html(html_content):
    """从微信文章 HTML 中提取正文文字"""
    # 提取 <div class="rich_media_content" ...> 中的内容
    match = re.search(
        r'<div class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<script',
        html_content, re.DOTALL
    )
    if not match:
        match = re.search(r'id="js_content"[^>]*>(.*?)</div>', html_content, re.DOTALL)
    if not match:
        match = re.search(r'<article[^>]*>(.*?)</article>', html_content, re.DOTALL)

    text = match.group(1) if match else html_content

    # 清理 HTML 标签
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def download_article_text(url):
    """
    下载文章正文（核心改进）：
    1. 调用 download_article -> 返回 HTML 文件本地路径
    2. 读取 HTML 文件
    3. 从 HTML 中提取纯文本正文
    4. 清理临时 HTML 文件
    """
    result = run_skill("download_article", url=url)
    if not result.get("ok"):
        return None

    data = result.get("data", {})
    file_path = data.get("absolute_path", "")

    if file_path and os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        text = extract_text_from_html(html_content)
        try:
            os.remove(file_path)
        except OSError:
            pass
        return text

    return None


def search_account(keyword):
    """搜索公众号，返回匹配列表"""
    result = run_skill("search_account", keyword=keyword)
    if result.get("ok"):
        return result.get("data", {}).get("response", {}).get("list", [])
    return []


def safe_filename(title, max_len=60):
    """生成安全的文件名"""
    title = re.sub(r'[\\/:*?"<>|]', '_', title)
    return title[:max_len]


def main():
    # ============ 配置目标公众号 ============
    # 方式1：直接填 fakeid（从 search_account 获取）
    # 方式2：填公众号名称，脚本会自动搜索
    # 请替换为你自己的公众号名称和 fakeid
    # fakeid 可通过 search_account 获取
    accounts = {
        # "示例公众号": "MzAwNTM4NTQ5OQ==",
    }
    # ========================================

    for name, fakeid in accounts.items():
        print(f"\n{'='*60}", flush=True)
        print(f"📡 【{name}】获取文章列表...", flush=True)
        print(f"{'='*60}", flush=True)

        articles = list_all_articles(fakeid, max_total=30)

        if not articles:
            print(f"⚠️ 未获取到文章，跳过", flush=True)
            continue

        # 保存文章列表
        list_path = os.path.join(OUTPUT_DIR, f"{name}_文章列表.json")
        with open(list_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"📋 文章列表已保存 ({len(articles)} 篇)", flush=True)

        article_dir = os.path.join(OUTPUT_DIR, name)
        os.makedirs(article_dir, exist_ok=True)

        all_contents = []
        for i, article in enumerate(articles):
            title = article.get("title", f"unknown_{i}")
            link = article.get("link", "")
            digest = article.get("digest", "")
            create_time = article.get("create_time", 0)
            author = article.get("author_name", name)

            print(f"\n  [{i+1}/{len(articles)}] {title}", flush=True)

            content = ""
            if link:
                try:
                    content = download_article_text(link)
                    time.sleep(2)  # 避免请求过快
                except Exception as e:
                    print(f"    ⚠️ 下载失败: {e}", flush=True)

            if not content:
                content = digest
                print(f"    使用摘要代替 ({len(content)} 字)", flush=True)
            else:
                print(f"    ✅ 正文: {len(content)} 字", flush=True)

            article_data = {
                "title": title,
                "link": link,
                "digest": digest,
                "content": content,
                "create_time": create_time,
                "author": author,
            }
            all_contents.append(article_data)

            # 保存单篇文章
            fname = safe_filename(title) + ".txt"
            fpath = os.path.join(article_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(f"标题: {title}\n作者: {author}\n链接: {link}\n时间: {create_time}\n\n{content}\n")

        # 保存合并文件
        merged_path = os.path.join(OUTPUT_DIR, f"{name}_全部文章.json")
        with open(merged_path, 'w', encoding='utf-8') as f:
            json.dump(all_contents, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 【{name}】完成！共 {len(all_contents)} 篇，保存到 {merged_path}", flush=True)

    print("\n🎉 所有文章下载完成！", flush=True)


if __name__ == "__main__":
    main()
