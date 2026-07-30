#!/usr/bin/env python3
"""
ContentJourney 热点 LLM 分析脚本
读取当日热点 JSON，分平台用 LLM 筛选+总结，最后交叉汇总生成 index.md

环境变量配置：
  OPENAI_API_KEY  — API Key（必填）
  OPENAI_BASE_URL — API 地址（默认 https://api.openai.com/v1）
  OPENAI_MODEL    — 模型名（默认 gpt-4o-mini）
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ==================== 配置 ====================

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
TODAY = NOW.strftime("%Y-%m-%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "hotspots" / "data"
INDEX_FILE = REPO_ROOT / "hotspots" / "index.md"

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL = os.environ.get("OPENAI_MODEL", "agnes-2.0-flash")

TIMEOUT = 60

# ==================== LLM 调用 ====================


def llm_chat(system_prompt, user_prompt, temperature=0.7):
    """调用 OpenAI 兼容 API"""
    if not API_KEY:
        print("  ✗ 未设置 OPENAI_API_KEY，跳过 LLM 分析")
        return None

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 0:
                print(f"  重试: {e}")
                time.sleep(2)
            else:
                print(f"  ✗ LLM 调用失败: {e}")
                return None


# ==================== Prompt 设计 ====================

SYSTEM_PROMPT = """你是一位资深自媒体内容策划师，擅长从热点中挖掘有深度解读价值的内容选题。

你的工作流是：获取每日热点 → 匹配书籍知识库 → 产出知识型内容。

你需要从热点列表中筛选出适合做"知识型自媒体内容"的热点——即有深度解读空间、能结合书籍知识做延伸分析的话题。

筛选标准（优先级从高到低）：
1. **知识延展性**：能关联到书籍/学科知识（如心理学、经济学、历史、社会学、科学等）
2. **深度解读空间**：不是简单的新闻播报，而是可以拆解底层逻辑、原理、背景
3. **受众关注度**：热度高、讨论度广，有明确的内容消费需求
4. **内容持久性**：不是转瞬即逝的纯娱乐八卦，而是有沉淀价值的选题

请严格筛选，宁缺毋滥。不是所有热点都值得做内容。"""


def build_platform_prompt(platform_name, items):
    """构建单平台分析 prompt"""
    # 只传标题和热度，减少 token
    hot_list = []
    for item in items:
        title = item.get("title", "")
        hot = item.get("hot", "")
        hot_list.append(f"- {title}" + (f"（热度: {hot}）" if hot else ""))

    items_text = "\n".join(hot_list)

    return f"""以下是【{platform_name}】今日的热点列表（共 {len(items)} 条）：

{items_text}

请完成以下分析：

1. **筛选出 3-8 个适合知识型自媒体内容创作的热点**，按推荐优先级排序
2. 对每个筛选出的热点，给出：
   - 选题方向（一句话点明可以做什么角度的内容）
   - 推荐理由（为什么这个热点值得做，关联什么领域的知识）
   - 可关联的书籍/学科方向（如：行为经济学、社会心理学、中国近代史等）

输出格式（Markdown）：

### 推荐选题

**1. [热点标题]**
- 选题方向：...
- 推荐理由：...
- 知识关联：...

**2. [热点标题]**
...

### 本平台热点特征
（一句话总结今日{platform_name}热点的整体特征和内容趋势）

注意：如果今天的热点确实没有适合知识型内容的，可以少选甚至不选，但要说明原因。"""


CROSS_SYSTEM_PROMPT = """你是一位资深自媒体内容策略顾问。

你将收到多个平台的热点分析结果，需要做交叉分析，找出跨平台共识热点，并给出今日整体内容策略建议。"""


def build_cross_prompt(platform_analyses):
    """构建交叉汇总 prompt"""
    analyses_text = ""
    for name, analysis in platform_analyses.items():
        analyses_text += f"\n---\n## {name}\n{analysis}\n"

    return f"""以下是今日各平台的热点分析结果：

{analyses_text}

请完成交叉汇总分析：

1. **跨平台共识热点**：哪些热点在多个平台同时出现？这些是今日最值得关注的内容选题。按跨平台出现次数排序。

2. **今日 TOP 5 选题推荐**：综合所有平台，推荐 5 个最值得做的知识型内容选题。每个给出：
   - 选题名称
   - 涉及平台（哪些平台在讨论）
   - 内容角度建议
   - 可关联的知识领域

3. **今日内容趋势**：一两句话总结今天整体的热点特征和内容机会。

输出格式（Markdown），简洁有力：

## 跨平台共识热点

1. **[热点]** — 出现在 [平台A、平台B]
   - 内容角度：...

...

## 今日 TOP 5 选题

**1. [选题名称]**
- 平台覆盖：...
- 内容角度：...
- 知识关联：...

...

## 今日内容趋势

一两句话总结。"""


# ==================== 主流程 ====================


def load_today_json():
    """加载今日 JSON 数据"""
    json_file = DATA_DIR / f"{TODAY}.json"
    if not json_file.exists():
        # 尝试找最新的 JSON 文件
        json_files = sorted(DATA_DIR.glob("*.json"), reverse=True)
        if json_files:
            json_file = json_files[0]
            print(f"  今日无数据，使用最近文件: {json_file.name}")
        else:
            print("  ✗ 未找到任何热点 JSON 文件")
            return None
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_platform(platform_name, items):
    """分析单个平台"""
    if not items:
        return f"*今日{platform_name}无数据或抓取失败。*"

    print(f"  [{platform_name}] LLM 分析中...")
    user_prompt = build_platform_prompt(platform_name, items)
    result = llm_chat(SYSTEM_PROMPT, user_prompt)

    if result:
        print(f"  [{platform_name}] ✓ 分析完成")
        return result
    else:
        # LLM 失败时的降级方案：列出原始标题
        print(f"  [{platform_name}] ⚠ LLM 分析失败，降级为原始列表")
        lines = [f"*LLM 分析不可用，以下为原始热点列表：*", ""]
        for item in items[:10]:
            lines.append(f"- {item['title']}")
        return "\n".join(lines)


def main():
    print(f"=== ContentJourney 热点 LLM 分析 {TODAY} ===\n")

    if not API_KEY:
        print("⚠ 未设置 OPENAI_API_KEY，将使用降级模式（仅原始列表）\n")

    # 1. 加载数据
    data = load_today_json()
    if not data:
        sys.exit(1)

    platforms = data.get("platforms", {})
    if not platforms:
        print("✗ JSON 中无平台数据")
        sys.exit(1)

    # 2. 分平台 LLM 分析
    print("\n--- 分平台分析 ---")
    platform_analyses = {}
    for name, platform_data in platforms.items():
        items = platform_data.get("items", [])
        analysis = analyze_platform(name, items)
        platform_analyses[name] = analysis

    # 3. 交叉汇总
    print("\n--- 交叉汇总 ---")
    cross_analysis = None
    if API_KEY:
        print("  [交叉汇总] LLM 分析中...")
        cross_prompt = build_cross_prompt(platform_analyses)
        cross_analysis = llm_chat(CROSS_SYSTEM_PROMPT, cross_prompt, temperature=0.5)
        if cross_analysis:
            print("  [交叉汇总] ✓ 完成")
        else:
            print("  [交叉汇总] ⚠ 失败")

    # 4. 生成 index.md
    print("\n--- 生成报告 ---")
    lines = [
        f"# ContentJourney 每日热点分析",
        "",
        f"> {NOW.strftime('%Y-%m-%d %H:%M')} (北京时间) | 模型: {MODEL}",
        "",
        "---",
        "",
    ]

    # 交叉汇总放最前面（用户最关心的）
    if cross_analysis:
        lines.append(cross_analysis)
        lines.append("")
        lines.append("---")
        lines.append("")

    # 各平台详细分析
    emoji_map = {
        "百度热搜": "🔍",
        "知乎日报": "💡",
        "B站热门": "📺",
        "抖音热点": "🎵",
        "头条热榜": "📰",
    }
    for name, analysis in platform_analyses.items():
        emoji = emoji_map.get(name, "📌")
        lines.append(f"# {emoji} {name}")
        lines.append("")
        lines.append(analysis)
        lines.append("")
        lines.append("---")
        lines.append("")

    # 底部：原始数据链接
    json_filename = data.get("date", TODAY) + ".json"
    lines.extend(
        [
            "## 原始数据",
            "",
            f"- [`{json_filename}`](data/{json_filename}) — 完整 JSON 数据（可溯源）",
            "",
            "## 说明",
            "",
            "- 数据由 GitHub Actions 每日定时抓取并 LLM 分析",
            "- 各平台分析独立进行，最后交叉汇总",
            "- 完整工作流：热点获取 → LLM 分析 → 匹配书籍知识库 → 输出 Notion 报告",
            "",
        ]
    )

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✓ 报告已保存: {INDEX_FILE.relative_to(REPO_ROOT)}")
    print(f"\n✓ 完成! 时间: {NOW.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
