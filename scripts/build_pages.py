"""将 hotspots/index.md 转换为 index.html 并构建 Pages 站点"""
import os
import shutil

try:
    import markdown
except ImportError:
    os.system("pip install markdown")
    import markdown

md_path = "hotspots/index.md"
html_path = "hotspots/index.html"

with open(md_path) as f:
    body = markdown.markdown(f.read(), extensions=["tables", "fenced_code"])

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ContentJourney 每日热点分析</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">
</head>
<body>
{body}
</body>
</html>"""

with open(html_path, "w") as f:
    f.write(html)

# 构建 _site 目录
site_dir = "_site"
if os.path.exists(site_dir):
    shutil.rmtree(site_dir)
shutil.copytree("hotspots", site_dir)
print(f"Pages 站点已构建: {len(os.listdir(site_dir))} 个文件")