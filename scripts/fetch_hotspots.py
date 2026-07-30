#!/usr/bin/env python3
"""
ContentJourney 热点获取脚本
抓取微博热搜、知乎热榜、B站热门、抖音热点、头条热榜
输出 JSON（供匹配工作流消费）+ Markdown（GitHub Pages 展示）
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

# ==================== 配置 ====================

# 北京时间
CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
TODAY = NOW.strftime("%Y-%m-%d")

# 仓库根目录（脚本在 scripts/ 下，根目录是上一级）
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "hotspots" / "data"
INDEX_FILE = REPO_ROOT / "hotspots" / "index.md"

# 通用请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.google.com",
}

# 超时和重试
TIMEOUT = 10
MAX_RETRIES = 2
RETRY_DELAY = 1


def fetch(url, **kwargs):
    """带重试的 HTTP 请求"""
    headers = kwargs.pop("headers", HEADERS)
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  重试 {attempt + 1}/{MAX_RETRIES}: {e}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  ✗ 抓取失败: {e}")
                return None


# ==================== 各平台抓取函数 ====================


def fetch_baidu():
    """百度热搜 - PC 版 API"""
    print("[百度] 抓取中...")
    url = "https://top.baidu.com/api/board"
    params = {"platform": "pc", "tab": "realtime"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://top.baidu.com/board?tab=realtime",
        "Acs-Token": "123",
    }
    data = fetch(url, params=params, headers=headers)
    if not data:
        return []

    items = []
    try:
        cards = data["data"]["cards"]
        for card in cards:
            content = card.get("content", [])
            for entry in content:
                title = entry.get("word", "").strip()
                if not title:
                    continue
                hot = entry.get("hotScore", "")
                url_str = entry.get("url", entry.get("rawUrl", ""))
                items.append(
                    {
                        "rank": len(items) + 1,
                        "title": title,
                        "hot": str(hot),
                        "url": url_str,
                    }
                )
            if len(items) >= 50:
                break
    except (KeyError, TypeError) as e:
        print(f"  ✗ 解析失败: {e}")

    print(f"  ✓ 获取 {len(items)} 条")
    return items


def fetch_zhihu():
    """知乎日报 - 官方 API"""
    print("[知乎] 抓取中...")
    url = "https://daily.zhihu.com/api/4/news/latest"
    data = fetch(url)
    if not data:
        return []

    items = []
    try:
        for story in data.get("stories", []):
            title = story.get("title", "").strip()
            if not title:
                continue
            story_id = story.get("id", "")
            url_str = f"https://daily.zhihu.com/story/{story_id}"
            items.append(
                {
                    "rank": len(items) + 1,
                    "title": title,
                    "hot": "",
                    "url": url_str,
                }
            )
    except (KeyError, TypeError) as e:
        print(f"  ✗ 解析失败: {e}")

    print(f"  ✓ 获取 {len(items)} 条")
    return items


def fetch_bilibili():
    """B站热门视频 - 官方 API"""
    print("[B站] 抓取中...")
    url = "https://api.bilibili.com/x/web-interface/popular"
    params = {"ps": 50, "pn": 1}
    headers = {**HEADERS, "Referer": "https://www.bilibili.com"}
    data = fetch(url, params=params, headers=headers)
    if not data:
        return []

    items = []
    try:
        for video in data["data"]["list"]:
            title = video.get("title", "").strip()
            if not title:
                continue
            bvid = video.get("bvid", "")
            # 热度用综合得分
            hot = video.get("score", 0)
            stat = video.get("stat", {})
            view = stat.get("view", 0)
            hot_str = f"{view}播放" if view else ""
            url_str = f"https://www.bilibili.com/video/{bvid}"
            items.append(
                {
                    "rank": len(items) + 1,
                    "title": title,
                    "hot": hot_str,
                    "url": url_str,
                }
            )
    except (KeyError, TypeError) as e:
        print(f"  ✗ 解析失败: {e}")

    print(f"  ✓ 获取 {len(items)} 条")
    return items


def fetch_douyin():
    """抖音热点 - iesdouyin 接口"""
    print("[抖音] 抓取中...")
    url = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"
    headers = {
        **HEADERS,
        "Referer": "https://www.douyin.com/hot",
    }
    data = fetch(url, headers=headers)
    if not data:
        return []

    items = []
    try:
        for entry in data.get("word_list", []):
            title = entry.get("word", "").strip()
            if not title:
                continue
            hot = entry.get("hot_value", "")
            url_str = f"https://www.douyin.com/search/{quote(title)}"
            items.append(
                {
                    "rank": len(items) + 1,
                    "title": title,
                    "hot": str(hot),
                    "url": url_str,
                }
            )
    except (KeyError, TypeError) as e:
        print(f"  ✗ 解析失败: {e}")

    print(f"  ✓ 获取 {len(items)} 条")
    return items


def fetch_toutiao():
    """头条热榜 - 网页接口"""
    print("[头条] 抓取中...")
    url = "https://www.toutiao.com/hot-event/hot-board/"
    params = {"origin": "toutiao_pc"}
    headers = {**HEADERS, "Referer": "https://www.toutiao.com/"}
    data = fetch(url, params=params, headers=headers)
    if not data:
        return []

    items = []
    try:
        for entry in data["data"]:
            title = entry.get("Title", "").strip()
            if not title:
                continue
            hot = entry.get("HotValue", "")
            url_str = entry.get("Url", "")
            items.append(
                {
                    "rank": len(items) + 1,
                    "title": title,
                    "hot": str(hot),
                    "url": url_str,
                }
            )
    except (KeyError, TypeError) as e:
        print(f"  ✗ 解析失败: {e}")

    print(f"  ✓ 获取 {len(items)} 条")
    return items


# ==================== 输出函数 ====================


def save_json(platforms_data):
    """保存 JSON 文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_file = DATA_DIR / f"{TODAY}.json"

    output = {
        "date": TODAY,
        "fetched_at": NOW.isoformat(),
        "platforms": {},
    }

    for name, items in platforms_data.items():
        output["platforms"][name] = {
            "count": len(items),
            "items": items,
        }

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ JSON 已保存: {json_file.relative_to(REPO_ROOT)}")
    return json_file


def generate_index(platforms_data):
    """生成 Markdown 汇总页"""
    lines = [
        "# ContentJourney 每日热点",
        "",
        f"> 最后更新: {NOW.strftime('%Y-%m-%d %H:%M')} (北京时间)",
        "",
        "每日定时抓取百度热搜、知乎日报、B站热门、抖音热点、头条热榜。",
        "",
        "---",
        "",
    ]

    # 统计概览
    total = sum(len(items) for items in platforms_data.values())
    lines.append(f"**今日共获取 {total} 条热点**")
    lines.append("")

    for platform_name, items in platforms_data.items():
        if not items:
            continue
        emoji_map = {
            "百度热搜": "🔍",
            "知乎日报": "💡",
            "B站热门": "📺",
            "抖音热点": "🎵",
            "头条热榜": "📰",
        }
        emoji = emoji_map.get(platform_name, "📌")
        lines.append(f"## {emoji} {platform_name} ({len(items)}条)")
        lines.append("")
        lines.append("| 排名 | 热点标题 | 热度 | 链接 |")
        lines.append("|---|---|---|---|")
        for item in items[:30]:  # Markdown 最多展示30条
            title = item["title"].replace("|", "\\|")
            hot = item.get("hot", "")
            url = item.get("url", "")
            link = f"[查看]({url})" if url else ""
            lines.append(f"| {item['rank']} | {title} | {hot} | {link} |")
        if len(items) > 30:
            lines.append(f"\n*...还有 {len(items) - 30} 条，完整数据见 JSON 文件*")
        lines.append("")

    # 底部
    lines.extend(
        [
            "---",
            "",
            "## 数据文件",
            "",
            f"- [`{TODAY}.json`](data/{TODAY}.json) — 今日完整 JSON 数据",
            "",
            "## 说明",
            "",
            "- 数据由 GitHub Actions 每日定时抓取",
            "- 仅供内容创作参考，版权归各平台所有",
            "- 完整工作流：热点获取 → 匹配书籍知识库 → 输出 Notion 报告",
            "",
        ]
    )

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✓ Markdown 已保存: {INDEX_FILE.relative_to(REPO_ROOT)}")


# ==================== 主流程 ====================


def main():
    print(f"=== ContentJourney 热点获取 {TODAY} ===\n")

    platforms = [
        ("百度热搜", fetch_baidu),
        ("知乎日报", fetch_zhihu),
        ("B站热门", fetch_bilibili),
        ("抖音热点", fetch_douyin),
        ("头条热榜", fetch_toutiao),
    ]

    results = {}
    for name, fetcher in platforms:
        try:
            results[name] = fetcher()
        except Exception as e:
            print(f"  ✗ {name} 异常: {e}")
            results[name] = []

    # 保存 JSON（index.md 由 analyze_hotspots.py 用 LLM 生成）
    save_json(results)

    # 汇总
    print("\n=== 汇总 ===")
    for name, items in results.items():
        status = f"{len(items)}条" if items else "失败"
        print(f"  {name}: {status}")

    # 如果全部失败，返回非零退出码
    if not any(results.values()):
        print("\n✗ 所有平台抓取失败")
        sys.exit(1)

    print(f"\n✓ 完成! 时间: {NOW.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
