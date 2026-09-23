"""Mirror whengodmadeyou.weebly.com into ../site as a static, offline-browsable copy.

Pages on the site host are crawled by following links. Assets (uploads, theme files,
Weebly CDN css/js/fonts/images) are downloaded and every reference is rewritten to a
relative local path, so the result works from file:// and from any static host.
"""
import concurrent.futures as cf
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = "whengodmadeyou.weebly.com"
BASE = f"https://{HOST}"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "site"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
CDN_RE = re.compile(r"^cdn\d*\.editmysite\.com$|^[a-z0-9-]+\.editmysite\.com$")
ASSET_EXT = re.compile(r"\.(jpe?g|png|gif|webp|svg|ico|css|js|woff2?|ttf|eot|otf|mp3|mp4|mov|m4a|pdf|docx?|xlsx?|pptx?|zip)$", re.I)
SKIP_PREFIXES = ("/cdn-cgi/", "/store/", "/ajax/", "/apps/")

lock = threading.Lock()
done = {}          # absolute url -> local relative path (or None on failure)
failed = []
pages_seen = set()


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 410):
                raise
            time.sleep(1 + i * 2)
        except Exception:
            time.sleep(1 + i * 2)
    raise RuntimeError(f"giving up on {url}")


def normalize(ref, base_url):
    """Resolve a reference found in a document to an absolute url, or None to leave it alone."""
    ref = ref.strip().replace("\\/", "/").replace("&amp;", "&")
    if not ref or ref.startswith(("data:", "mailto:", "tel:", "javascript:", "#", "about:")):
        return None
    absu = urllib.parse.urljoin(base_url, ref)
    p = urllib.parse.urlsplit(absu)
    if p.scheme not in ("http", "https", ""):
        return None
    host = p.netloc.lower()
    if host in (HOST, "www." + HOST):
        if p.path.startswith(SKIP_PREFIXES):
            return None
        return urllib.parse.urlunsplit(("https", HOST, p.path or "/", "", ""))
    if CDN_RE.match(host):
        return urllib.parse.urlunsplit(("https", host, p.path, "", ""))
    return None


def is_asset(url):
    p = urllib.parse.urlsplit(url)
    return p.netloc != HOST or p.path.startswith(("/uploads/", "/files/")) or bool(ASSET_EXT.search(p.path))


def local_path(url):
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(p.path)
    if p.netloc != HOST:
        return "_cdn/" + p.netloc + path
    if is_asset(url):
        return path.lstrip("/")
    if path in ("", "/"):
        return "index.html"
    path = path.rstrip("/")
    return path.lstrip("/") + ("" if path.endswith((".html", ".htm")) else ".html")


def rel(target, from_local):
    return os.path.relpath(target, os.path.dirname(from_local) or ".").replace(os.sep, "/")


# url( ... ), src/href/srcset/data-* attributes, and bare quoted strings in inline JS/JSON.
ATTR_RE = re.compile(r'''((?:src|href|data-src|data-orig|data-full|poster|data-image)\s*=\s*)(["'])(.*?)\2''', re.I | re.S)
SRCSET_RE = re.compile(r'''(srcset\s*=\s*)(["'])(.*?)\2''', re.I | re.S)
CSSURL_RE = re.compile(r'''url\(\s*(&quot;|&#39;|["']?)([^"')]+?)\1\s*\)''', re.I)
JSSTR_RE = re.compile(r'''(["'])((?:https?:)?(?:\\?/\\?/(?:whengodmadeyou\.weebly\.com|cdn\d*\.editmysite\.com))?\\?/(?:uploads|files)\\?/[^"'\s<>]+?)\1''')
SLIDESHOW_RE = re.compile(r'''"url"\s*:\s*"(\d\\?/\d\\?/\d\\?/\d\\?/113684273\\?/[^"]+)"''')


def rewrite(text, base_url, my_local, queue):
    def sub_url(ref, keep_escaped=False):
        absu = normalize(ref, base_url)
        if not absu:
            return None
        queue.append(absu)
        r = rel(local_path(absu), my_local)
        return r.replace("/", "\\/") if keep_escaped and "\\/" in ref else r

    def attr(m):
        new = sub_url(m.group(3))
        return m.group(0) if new is None else f"{m.group(1)}{m.group(2)}{new}{m.group(2)}"

    def srcset(m):
        parts = []
        for item in m.group(3).split(","):
            bits = item.strip().split()
            if bits:
                new = sub_url(bits[0])
                bits[0] = new or bits[0]
            parts.append(" ".join(bits))
        return f"{m.group(1)}{m.group(2)}{', '.join(parts)}{m.group(2)}"

    def cssurl(m):
        new = sub_url(m.group(2))
        return m.group(0) if new is None else f"url({m.group(1)}{new}{m.group(1)})"

    def jsstr(m):
        new = sub_url(m.group(2), keep_escaped=True)
        return m.group(0) if new is None else f"{m.group(1)}{new}{m.group(1)}"

    # Slideshow images are stored relative to /uploads/; fetch them, rewriting happens in postprocess.
    for s in SLIDESHOW_RE.findall(text):
        queue.append(BASE + "/uploads/" + s.replace("\\/", "/"))

    text = ATTR_RE.sub(attr, text)
    text = SRCSET_RE.sub(srcset, text)
    text = CSSURL_RE.sub(cssurl, text)
    text = JSSTR_RE.sub(jsstr, text)
    return text


def process(url):
    with lock:
        if url in done:
            return []
        done[url] = None
    local = local_path(url)
    dest = os.path.join(ROOT, local)
    if not local.endswith((".html", ".css")) and os.path.exists(dest):
        with lock:
            done[url] = local
        return []
    try:
        data, ctype, final = fetch(url)
    except Exception as e:
        with lock:
            failed.append((url, str(e)))
        return []
    queue = []
    textual = "text/html" in ctype or "text/css" in ctype or local.endswith((".css", ".html"))
    if textual:
        text = data.decode("utf-8", errors="replace")
        text = rewrite(text, url, local, queue)
        data = text.encode("utf-8")
        if "text/html" in ctype:
            with lock:
                pages_seen.add(url)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    with lock:
        done[url] = local
    return queue


def crawl(seeds):
    pending = set(seeds)
    last = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {}
        while pending or futures:
            while pending:
                u = pending.pop()
                with lock:
                    if u in done:
                        continue
                futures[ex.submit(process, u)] = u
            finished, _ = cf.wait(list(futures), return_when=cf.FIRST_COMPLETED)
            for f in finished:
                futures.pop(f)
                for q in f.result():
                    with lock:
                        if q not in done:
                            pending.add(q)
            with lock:
                n = len(done)
            if time.time() - last > 10:
                last = time.time()
                print(f"  {n} fetched, {len(pages_seen)} pages", flush=True)


if __name__ == "__main__":
    seeds = [BASE + "/"] + [BASE + "/uploads/" + line.strip() for line in open(sys.argv[1])] if len(sys.argv) > 1 else [BASE + "/"]
    crawl(seeds)
    print(f"done: {len(done)} urls, {len(pages_seen)} html pages, {len(failed)} failures")
    with open(os.path.join(ROOT, "..", "tools", "failures.txt"), "w") as f:
        for u, e in sorted(failed):
            f.write(f"{u}\t{e}\n")
