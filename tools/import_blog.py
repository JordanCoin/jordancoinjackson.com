#!/usr/bin/env python3
"""Import the old Hugo "Life & Times" blog (Bluehost) into /blog, re-set in the
site's ledger design. Fetches post list from index.xml, extracts each post's
date/title/content from the Hemingway template, downloads same-origin images,
and writes /blog/index.html + /blog/<slug>/index.html.

Run once (or again to refresh) while jordancoinjackson.com DNS still points at
Bluehost: python3 tools/import_blog.py
"""
import datetime
import email.utils
import html
import os
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET

ORIGIN = "https://www.jordancoinjackson.com"
ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOG = ROOT / "blog"
ASSETS = BLOG / "assets"


def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site migration)"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception:
            if attempt == tries - 1:
                raise
            import time
            time.sleep(3 * (attempt + 1))


def extract_content(page):
    """Return inner HTML of the post's <div class="content">, balanced."""
    m = re.search(r'<div class="content">', page)
    if not m:
        return None
    i = m.end()
    depth = 1
    for tag in re.finditer(r"<div\b|</div>", page[i:]):
        depth += 1 if tag.group(0).startswith("<div") else -1
        if depth == 0:
            return page[i:i + tag.start()].strip()
    return None


STYLE = """
:root {
  --paper: oklch(97.2% 0.011 85); --paper-deep: oklch(94.5% 0.016 83);
  --ink: oklch(24% 0.02 60); --ink-soft: oklch(40% 0.018 60);
  --rule: oklch(85% 0.02 80); --terracotta: oklch(62% 0.13 40);
  --terracotta-deep: oklch(52% 0.13 38); --teal: oklch(38% 0.06 190);
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: oklch(21% 0.015 55); --paper-deep: oklch(25% 0.018 55);
    --ink: oklch(90% 0.02 85); --ink-soft: oklch(72% 0.02 80);
    --rule: oklch(34% 0.02 60); --terracotta: oklch(70% 0.13 42);
    --terracotta-deep: oklch(78% 0.12 45); --teal: oklch(75% 0.07 190);
  }
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font-family: "Newsreader", Georgia, serif;
  font-size: clamp(1.05rem, 0.95rem + 0.4vw, 1.2rem); line-height: 1.68; }
.page { max-width: 42rem; margin: 0 auto; padding: clamp(2rem, 5vw, 4rem) clamp(1.25rem, 5vw, 2.5rem) 4rem; }
a { color: inherit; text-decoration-color: color-mix(in oklch, var(--terracotta) 55%, transparent); text-underline-offset: 3px; }
a:hover { color: var(--terracotta-deep); }
.crumb { font-size: .85rem; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-soft); text-decoration: none; }
.crumb:hover { color: var(--terracotta-deep); }
.masthead { padding-bottom: 1.1rem; border-bottom: 3px double var(--rule); display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
.blogname { font-family: "Fraunces", serif; font-weight: 900; font-size: 1.25rem; text-decoration: none; }
.blogname .amp { color: var(--terracotta); font-style: italic; font-weight: 400; }
h1.post-title { font-family: "Fraunces", serif; font-weight: 900; font-size: clamp(1.9rem, 1.4rem + 2.4vw, 3rem); line-height: 1.08; letter-spacing: -0.01em; margin: 2.2rem 0 .5rem; }
.post-date { font-size: .82rem; letter-spacing: .18em; text-transform: uppercase; color: var(--terracotta-deep); }
.prose { margin-top: 1.8rem; }
.prose p { margin: 0 0 1.1rem; }
.prose img { max-width: 100%; height: auto; border: 1px solid var(--rule); margin: 1.4rem 0; }
.prose h1, .prose h2, .prose h3 { font-family: "Fraunces", serif; font-weight: 600; margin: 2rem 0 .7rem; line-height: 1.2; }
.prose blockquote { border-left: 3px solid var(--terracotta); padding-left: 1.1rem; color: var(--ink-soft); font-style: italic; margin: 1.4rem 0; }
.prose ul, .prose ol { margin: 0 0 1.1rem 1.4rem; }
.prose code { background: var(--paper-deep); padding: .1em .35em; font-size: .9em; }
.prose pre { background: var(--paper-deep); padding: 1rem; overflow-x: auto; margin: 1.4rem 0; border: 1px solid var(--rule); }
.prose pre code { background: none; padding: 0; }
.postlist { list-style: none; margin-top: 2rem; }
.postlist li { display: grid; grid-template-columns: 1fr auto; gap: .2rem 1.25rem; align-items: baseline; padding: 1rem 0; border-bottom: 1px solid var(--rule); }
.postlist li:first-child { border-top: 1px solid var(--rule); }
.postlist .t { font-family: "Fraunces", serif; font-weight: 600; font-size: 1.12em; }
.postlist .t a { text-decoration: none; border-bottom: 2px solid color-mix(in oklch, var(--terracotta) 45%, transparent); }
.postlist .t a:hover { border-bottom-color: var(--terracotta-deep); }
.postlist .d { font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-soft); white-space: nowrap; }
.postlist .s { grid-column: 1 / -1; color: var(--ink-soft); font-size: .93em; }
.foot { margin-top: 3.5rem; padding-top: 1.3rem; border-top: 3px double var(--rule); color: var(--ink-soft); font-size: .85em; font-style: italic; }
@media (max-width: 540px) { .postlist li { grid-template-columns: 1fr; } }
"""

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>✒️</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,900;1,9..144,400&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap" rel="stylesheet">
<style>{style}</style>
</head>
<body>
<div class="page">
<nav class="masthead">
  <a class="blogname" href="/blog/">Life <span class="amp">&amp;</span> Times</a>
  <a class="crumb" href="/">← jordancoinjackson.com</a>
</nav>
"""

FOOT = """
<p class="foot">Life &amp; Times ran 2016–2019 on the old site. Preserved here, re-set by hand. © Jordan Coin Jackson.</p>
</div>
</body>
</html>
"""


def localize_images(content, slug):
    """Download same-origin images into blog/assets and rewrite refs."""
    def repl(m):
        url = m.group(1)
        if "jordancoinjackson.com" not in url and not url.startswith("/"):
            return m.group(0)  # external (unsplash etc.) stays
        src = url if url.startswith("http") else ORIGIN + url
        name = slug + "-" + os.path.basename(url.split("?")[0])
        ASSETS.mkdir(parents=True, exist_ok=True)
        dest = ASSETS / name
        if not dest.exists():
            try:
                dest.write_bytes(fetch(src))
            except Exception as e:
                print(f"  ! image failed {src}: {e}")
                return m.group(0)
        return m.group(0).replace(url, f"/blog/assets/{name}")
    return re.sub(r'<img[^>]+src="([^"]+)"', lambda m: repl(m), content)


def main():
    rss = fetch(ORIGIN + "/index.xml").decode("utf-8")
    # own-site feed, but strip DOCTYPE anyway so stdlib ET can't expand entities
    rss = re.sub(r"<!DOCTYPE[^>]*>", "", rss)
    root = ET.fromstring(rss)
    items = root.findall(".//item")
    posts = []
    for it in items:
        title = it.findtext("title") or "Untitled"
        link = it.findtext("link") or ""
        desc = (it.findtext("description") or "").strip()
        pub = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        slug = link.rstrip("/").split("/")[-1]
        print(f"importing: {slug}")
        page = fetch(link.replace("https://jordancoinjackson.com", ORIGIN)).decode("utf-8")
        content = extract_content(page)
        if not content:
            print(f"  ! no content div, skipping")
            continue
        content = localize_images(content, slug)
        # drop the Medium-import artifact: a first paragraph that just repeats the title
        content = re.sub(
            r"^(\s*(<p><img[^>]*></p>)?\s*)<p>\s*" + re.escape(html.escape(title)) + r"\s*</p>",
            r"\1", content, count=1, flags=re.I)
        date_h = pub.strftime("%B %-d, %Y")
        out = BLOG / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        first_sentence = html.escape(re.sub(r"\s+", " ", desc)[:150])
        out.write_text(
            HEAD.format(title=f"{html.escape(title)} — Life & Times", desc=first_sentence, style=STYLE)
            + f'<p class="post-date" style="margin-top:2.2rem">{date_h}</p>\n'
            + f'<h1 class="post-title" style="margin-top:.3rem">{html.escape(title)}</h1>\n'
            + f'<div class="prose">\n{content}\n</div>\n'
            + FOOT)
        posts.append((pub, title, slug, desc))

    posts.sort(reverse=True)
    rows = []
    for pub, title, slug, desc in posts:
        summary = html.escape(re.sub(r"\s+", " ", desc))
        # trim summary to one clean sentence-ish
        if len(summary) > 160:
            summary = summary[:160].rsplit(" ", 1)[0] + "…"
        rows.append(
            f'<li><span class="t"><a href="/blog/{slug}/">{html.escape(title)}</a></span>'
            f'<span class="d">{pub.strftime("%b %Y")}</span>'
            f'<span class="s">{summary}</span></li>')
    index = (
        HEAD.format(title="Life & Times — the blog of Jordan Coin Jackson",
                    desc="The original blog (2016–2019): Detroit, startups, becoming an engineer.", style=STYLE)
        + '<h1 class="post-title" style="margin-top:2.2rem">The old blog</h1>\n'
        + '<p style="color:var(--ink-soft);margin-top:.6rem;font-style:italic">Life &amp; Times, 2016–2019. '
        + 'Written before the products, mostly from Detroit. Kept because the person who wrote them was right about more than he knew.</p>\n'
        + f'<ul class="postlist">\n{chr(10).join(rows)}\n</ul>\n'
        + FOOT)
    (BLOG / "index.html").write_text(index)
    print(f"done: {len(posts)} posts -> /blog")


if __name__ == "__main__":
    main()
