"""Turn the Weebly mirror (site/) into editable source for the Eleventy build (src/).

One-off migration. Writes:
  src/posts/<blog>/<slug>.md          one file per post; Weebly HTML kept in `weebly_html`
  src/pages/<name>.html               standalone pages (home, about me, ...)
  src/_weebly/banners/*.html          banner block per page / blog
  src/_weebly/blogs/<blog>-*.html     per-blog content around the post list, and the sidebar
  src/_data/blogs.json, nav.json, redirects.json
All URLs are made root-relative ("/uploads/..."); the build turns them back into
relative links so the site works under any path prefix.
"""
import datetime as dt
import glob
import html
import json
import os
import posixpath
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "site")
SRC = os.path.join(HERE, "..", "src")
PAGES = ["index", "home", "about-me", "christian-song-journal", "travel", "yanah", "youtube-channel"]
SPAM_COMMENT_AUTHORS = {"detox rehab treatment"}
# Old URLs that have no page in the rebuild: an archive month Weebly filed in another
# timezone, and a post link that was already broken on Weebly (the post is in Homemaking).
EXTRA_REDIRECTS = [
    {"from": "/lets-explore-asia--europe/archives/01-2017.html", "to": "/lets-explore-asia--europe.html"},
    {"from": "/living-with-a-toddler/received-free-alkaline-water-system-by-eight-stars-alkaline-system.html",
     "to": "/homemaking/received-free-alkaline-water-system-by-eight-stars-alkaline-system.html"},
]


def read(rel):
    with open(os.path.join(SITE, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    path = os.path.join(SRC, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def rootify(text, page):
    """Rewrite relative URLs (relative to `page`) into root-relative ones."""
    base = posixpath.dirname(page)

    def resolve(u):
        if re.match(r"^(https?:|//|#|mailto:|tel:|data:|javascript:|about:|/)", u) or not u.strip():
            return u
        return "/" + posixpath.normpath(posixpath.join(base, u))

    text = re.sub(r'''(\b(?:src|href|data-src)=)(["'])(.*?)\2''', lambda m: m.group(1) + m.group(2) + resolve(m.group(3)) + m.group(2), text)
    text = re.sub(r'''(srcset=)(["'])(.*?)\2''', lambda m: m.group(1) + m.group(2) + ", ".join(
        " ".join([resolve(p.split()[0])] + p.split()[1:]) for p in m.group(3).split(",") if p.strip()) + m.group(2), text)
    text = re.sub(r'''url\(\s*(&quot;|&#39;|["']?)([^"')]+?)\1\s*\)''', lambda m: f"url({m.group(1)}{resolve(m.group(2))}{m.group(1)})", text)
    return text


def between(text, start, end, s_from=0):
    i = text.index(start, s_from)
    j = text.index(end, i + len(start))
    return text[i + len(start):j]


def matching_close(text, start, tag):
    """Index just past the tag that closes the <tag> opened at `start`."""
    depth, pos = 0, start
    pat = re.compile(rf"<(/?){tag}\b[^>]*>", re.I)
    while True:
        m = pat.search(text, pos)
        if not m:
            raise ValueError(f"unbalanced <{tag}>")
        depth += -1 if m.group(1) else 1
        pos = m.end()
        if depth == 0:
            return pos


def strip_platform_scripts(chunk):
    # Weebly "platform element" boot scripts do nothing without Weebly's app runtime.
    return re.sub(r'<script type="text/javascript" class="element-script">.*?</script>', "", chunk, flags=re.S)


def page_parts(rel):
    t = rootify(read(rel), rel)
    parts = {"raw": t}
    parts["title"] = html.unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1).strip())
    parts["body_class"] = re.search(r'<body class="([^"]*)"', t).group(1)
    m = re.search(r'<meta name="description" content="(.*?)" />', t, re.S)
    parts["description"] = html.unescape(m.group(1)) if m else None
    m = re.search(r'<meta name="keywords" content="(.*?)" />', t, re.S)
    parts["keywords"] = html.unescape(m.group(1)) if m else None
    parts["banner"] = between(t, '<div id="banner-wrap">', "<!-- end banner-wrap -->")
    parts["main"] = between(t, '<div id="main-wrap" class="content-wrap">', '<div id="footer-wrap">')
    return parts


def split_blog_main(main):
    """-> (before, blog_td_inner, sidebar_td_inner, after) around #blogTable."""
    i = main.index("<table \n\tid=\"blogTable\"") if "<table \n\tid=\"blogTable\"" in main else main.index('id="blogTable"')
    i = main.rindex("<table", 0, i + len("<table"))
    j = matching_close(main, i, "table")
    table = main[i:j]
    s = table.index('<td class="blog-sidebar" valign="top">')
    sidebar = table[s + len('<td class="blog-sidebar" valign="top">'):table.rindex("</td>")]
    return main[:i], table[:s], sidebar, main[j:]


def post_blocks(blog_td):
    """Yield (post_id, block_html) for every .blog-post in a blog column."""
    for m in re.finditer(r'<div id="blog-post-(\d+)" class="blog-post">', blog_td):
        end = matching_close(blog_td, m.start(), "div")
        yield m.group(1), blog_td[m.start():end]


def post_content(block):
    """Body HTML of a post block, plus whether it was cut off with Read More."""
    start = block.index('<div class="blog-content">') + len('<div class="blog-content">')
    end = matching_close(block, start - len('<div class="blog-content">'), "div") - len("</div>")
    inner = block[start:end]
    rm = re.search(r'\s*<br/>\s*<div class="blog-read-more">.*?</div>\s*$', inner, re.S)
    if rm:
        return inner[:rm.start()], True
    return inner, False


def slideshows_to_galleries(body):
    """Weebly slideshows are drawn by Weebly's own JavaScript, which builds image paths that
    break outside weebly.com. Replace each with Weebly's static image-gallery markup (4 across,
    click to open the photo), which the theme's lightbox already handles."""
    def convert(m):
        gid = m.group(1)
        images = json.loads(re.search(r"images:(\[.*?\])\}\)", m.group(0), re.S).group(1))
        items = []
        for n, im in enumerate(images):
            url = "/uploads/" + im["url"].replace("\\/", "/")
            ratio = im["height"] / im["width"] * 100
            top = -((ratio - 75) / 2) / 75 * 100 if ratio > 75 else 0
            items.append(
                f"<div id='{gid}-imageContainer{n}' style='float:left;width:24.95%;margin:0;'>"
                f"<div id='{gid}-insideImageContainer{n}' style='position:relative;margin:5px;'>"
                f"<div class='galleryImageHolder' style='position:relative; width:100%; padding:0 0 75%;overflow:hidden;'>"
                f"<div class='galleryInnerImageHolder'><a href='{url}' rel='lightbox[gallery{gid}]'>"
                f"<img src='{url}' class='galleryImage' _width='{im['width']}' _height='{im['height']}' "
                f"style='position:absolute;border:0;width:100%;top:{top:.0f}%;left:0%' /></a></div></div></div></div>")
        return (f"<div id='{gid}-gallery' class='imageGallery' style='line-height: 0px; padding: 0; margin: 0'>"
                + "".join(items)
                + "<span style='display: block; clear: both; height: 0px; overflow: hidden;'></span>\n</div>")
    return re.sub(r"<div id='(\d+)-slideshow'></div>\s*<script type='text/javascript'>.*?wSlideshow\.render.*?</script>",
                  convert, body, flags=re.S)


def parse_comments(t):
    comments = []
    for m in re.finditer(r'<div class="blogCommentWrap.*?<div class="blogCommentOptions">', t, re.S):
        c = m.group(0)
        name = html.unescape(re.sub(r"<[^>]+>", "", re.search(r'class="name"[^>]*>(.*?)</', c, re.S).group(1)).strip())
        if name in SPAM_COMMENT_AUTHORS:
            continue
        when = re.search(r'<div class="blogCommentDate">(.*?)</div>', c).group(1).strip()
        text = re.search(r'<div class="blogCommentText">\s*<p>\s*(.*?)\s*</p>', c, re.S).group(1)
        comments.append({"name": name, "date": when, "html": text.strip()})
    return comments


def listing_pages(blog):
    """Blog index pages in order: newest posts first."""
    pages = [f"{blog}.html"]
    n = 2
    while os.path.exists(os.path.join(SITE, blog, "previous", f"{n}.html")):
        pages.append(f"{blog}/previous/{n}.html")
        n += 1
    return pages


def category_pages(blog, slug):
    pages = [f"{blog}/category/{slug}.html"]
    n = 2
    while os.path.exists(os.path.join(SITE, blog, "category", slug, f"{n}.html")):
        pages.append(f"{blog}/category/{slug}/{n}.html")
        n += 1
    return pages


class LiteralStr(str):
    """Emitted as a YAML literal block (|), for long HTML."""


def to_yaml(value, indent=0):
    """Tiny YAML emitter for front matter: strings, lists, dicts. JSON-quoted strings are valid YAML."""
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if isinstance(v, LiteralStr):
                lines.append(f"{pad}{k}: |2-\n" + "\n".join((pad + "  " + l) if l else "" for l in v.split("\n")))
            elif isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:\n{to_yaml(v, indent + 1)}")
            else:
                lines.append(f"{pad}{k}: {to_yaml(v)}")
        return "\n".join(lines)
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict):
                inner = to_yaml(v, indent + 1).lstrip()
                out.append(f"{pad}- {inner}")
            else:
                out.append(f"{pad}- {to_yaml(v)}")
        return "\n".join(out)
    return json.dumps(value, ensure_ascii=False)


def front_matter(data, body=""):
    return "---\n" + to_yaml(data) + "\n---\n" + body


def clean_block(s):
    # Literal blocks: drop trailing whitespace and turn leading tabs into spaces (YAML forbids tab indentation).
    lines = [re.sub(r"^\t+", lambda m: "  " * len(m.group(0)), line.rstrip()) for line in s.strip("\n").splitlines()]
    return "\n".join(lines)


def main():
    if os.path.exists(SRC) and "--force" not in sys.argv:
        sys.exit("src/ exists; pass --force to regenerate it")
    # Remove only what this script generates; hand-written files (e.g. *.11tydata.*) stay.
    for d in glob.glob(os.path.join(SRC, "posts", "*", "")):
        shutil.rmtree(d)
    for f in glob.glob(os.path.join(SRC, "pages", "*.html")):
        os.remove(f)
    shutil.rmtree(os.path.join(SRC, "_weebly"), ignore_errors=True)

    home = read("index.html")
    nav_json = re.search(r"initPublishedFlyoutMenus\(\s*(\[.*?\]),", home, re.S).group(1)
    nav = [{"id": n["id"], "title": n["title"], "url": "/" + n["url"]} for n in json.loads(nav_json)]

    banners = {}

    def banner_key(name, chunk):
        for k, v in banners.items():
            if v == chunk:
                return k
        banners[name] = chunk
        return name

    blogs, redirects, report = [], [], []
    post_by_id = {}

    blog_keys = [n["url"][1:-5] for n in nav if os.path.isdir(os.path.join(SITE, n["url"][1:-5]))]
    for blog in blog_keys:
        idx = page_parts(f"{blog}.html")
        before, blog_td, sidebar, after = split_blog_main(idx["main"])
        blog_id = re.search(r'id="(\d+)-blog"', blog_td).group(1)
        nav_item = next(n for n in nav if n["url"] == f"/{blog}.html")

        # Sidebar: swap the generated lists for placeholders the build fills in.
        sidebar = strip_platform_scripts(sidebar)
        sidebar = re.sub(r'<p class="blog-archive-list">.*?</p>', "<!--ARCHIVES-->", sidebar, flags=re.S)
        sidebar = re.sub(r'<p class="blog-category-list">.*?</p>', "<!--CATEGORIES-->", sidebar, flags=re.S)
        sidebar = re.sub(r'href="/\d+/feed\.html"', f'href="/{blog}/feed.xml"', sidebar)
        cat_links = re.findall(rf'<a href="/{re.escape(blog)}/category/([^"/]+)\.html" class="blog-link">(.*?)</a>', idx["main"])
        categories = {slug: html.unescape(name) for slug, name in cat_links if slug != "all"}

        write(f"_weebly/blogs/{blog}-before.html", strip_platform_scripts(before))
        write(f"_weebly/blogs/{blog}-after.html", strip_platform_scripts(after))
        write(f"_weebly/blogs/{blog}-sidebar.html", sidebar)

        # Newest-first order from the listing pages, and which posts showed an excerpt.
        order, excerpts = [], {}
        for lp in listing_pages(blog):
            _, td, _, _ = split_blog_main(page_parts(lp)["main"])
            for pid, block in post_blocks(td):
                order.append(pid)
                content, cut = post_content(block)
                if cut:
                    excerpts[pid] = content

        members = {}
        for slug in categories:
            for cp in category_pages(blog, slug):
                _, td, _, _ = split_blog_main(page_parts(cp)["main"])
                for pid, _ in post_blocks(td):
                    members.setdefault(pid, []).append(categories[slug])

        post_files = sorted(p for p in glob.glob(os.path.join(SITE, blog, "*.html")))
        bkey = None
        for pf in post_files:
            rel = os.path.relpath(pf, SITE)
            parts = page_parts(rel)
            if bkey is None:
                bkey = banner_key(blog, parts["banner"])
            elif parts["banner"] != banners[bkey]:
                report.append(f"banner differs on {rel}")
            b, td, sb, a = split_blog_main(parts["main"])
            if strip_platform_scripts(b) != strip_platform_scripts(before) or strip_platform_scripts(a) != strip_platform_scripts(after):
                report.append(f"before/after differs on {rel}")
            (pid, block), = list(post_blocks(td))
            title = html.unescape(re.sub(r"<[^>]+>", "", re.search(r'class="blog-title-link blog-link"[^>]*>(.*?)</a>', block, re.S).group(1)).strip())
            d, m, y = map(int, re.search(r'<span class="date-text">\s*(\d+)/(\d+)/(\d+)', block).groups())
            body, _ = post_content(block)
            body = slideshows_to_galleries(body)
            slug = os.path.basename(rel)[:-5]
            if "<!--BLOG_SUMMARY_END-->" in body:
                body = body.replace("<!--BLOG_SUMMARY_END-->", "<!--more-->", 1)
            elif pid in excerpts:
                ex = excerpts[pid].rstrip()
                if body.startswith(ex):
                    body = ex + "\n<!--more-->\n" + body[len(ex):]
                else:
                    report.append(f"excerpt is not a prefix of the post: {rel}")
            rank = order.index(pid) if pid in order else len(order)
            post_by_id[pid] = {
                "blog": blog, "slug": slug, "title": title, "date": dt.datetime(y, m, d),
                "rank": rank, "categories": members.get(pid, []), "body": body,
                "comments": parse_comments(parts["raw"]), "weebly_id": pid,
            }
            if pid not in order:
                report.append(f"post not in any listing (unlisted?): {rel}")

        blogs.append({
            "key": blog, "id": blog_id, "title": nav_item["title"], "pageTitle": idx["title"],
            "bodyClass": idx["body_class"].replace("wsite-blog-index", "BLOGKIND"),
            "banner": bkey, "categories": [{"slug": s, "name": n} for s, n in categories.items()],
            "description": idx["description"], "keywords": idx["keywords"],
        })

    # Same-day posts keep their listing order: newer rank -> later time of day.
    for p in post_by_id.values():
        same_day = sorted((q for q in post_by_id.values() if q["blog"] == p["blog"] and q["date"].date() == p["date"].date()), key=lambda q: q["rank"])
        p["datetime"] = p["date"] + dt.timedelta(hours=12, minutes=len(same_day) - 1 - same_day.index(p))

    for p in post_by_id.values():
        fm = {"title": p["title"], "date": p["datetime"].strftime("%Y-%m-%dT%H:%M:%S")}
        if p["categories"]:
            fm["categories"] = p["categories"]
        if p["comments"]:
            fm["comments"] = [{"name": c["name"], "date": c["date"], "html": c["html"]} for c in p["comments"]]
        fm["weebly_id"] = p["weebly_id"]
        fm["weebly_html"] = LiteralStr(clean_block(p["body"]))
        write(f"posts/{p['blog']}/{p['slug']}.md", front_matter(fm))

    # Old Weebly permalinks (/4/post/2013/11/x.html) that posts link to: redirect to the new page.
    for pf in glob.glob(os.path.join(SITE, "*", "post", "**", "*.html"), recursive=True):
        rel = os.path.relpath(pf, SITE)
        m = re.search(r'id="blog-post-(\d+)"', read(rel))
        if m and m.group(1) in post_by_id:
            p = post_by_id[m.group(1)]
            redirects.append({"from": "/" + rel, "to": f"/{p['blog']}/{p['slug']}.html"})
        else:
            report.append(f"legacy page with no matching post: {rel}")

    for name in PAGES:
        parts = page_parts(f"{name}.html")
        fm = {"title": parts["title"], "bodyClass": parts["body_class"], "banner": banner_key(name, parts["banner"])}
        if parts["description"]:
            fm["description"] = parts["description"]
        if parts["keywords"]:
            fm["keywords"] = parts["keywords"]
        fm["permalink"] = f"/{name}.html"
        write(f"pages/{name}.html", front_matter(fm, strip_platform_scripts(parts["main"])))

    for key, chunk in banners.items():
        write(f"_weebly/banners/{key}.html", strip_platform_scripts(chunk))

    write("_data/nav.json", json.dumps(nav, indent=2, ensure_ascii=False) + "\n")
    write("_data/blogs.json", json.dumps(blogs, indent=2, ensure_ascii=False) + "\n")
    redirects += EXTRA_REDIRECTS
    write("_data/redirects.json", json.dumps(sorted(redirects, key=lambda r: r["from"]), indent=2) + "\n")

    print(f"{len(post_by_id)} posts, {len(blogs)} blogs, {len(PAGES)} pages, {len(banners)} banners, {len(redirects)} redirects")
    for line in report:
        print("  !", line)


if __name__ == "__main__":
    main()
