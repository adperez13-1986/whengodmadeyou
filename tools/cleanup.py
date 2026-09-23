"""Post-process the mirrored pages so they work as a standalone static site.

Removes the pieces that only work while Weebly hosts the site (comment form, share
buttons, analytics, ads, Weebly signup footer) and decodes Cloudflare-obfuscated
mailto links. Safe to run more than once.
"""
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "site"))
MARK = "<!-- archive-cleanup -->"
HIDE_CSS = (
    MARK + "<style>#commentReplyTitle,.blogCommentReplyWrapper,.blog-social,"
    "#weebly-footer-signup-container-v3,.adsbygoogle{display:none!important}</style>"
)


def decode_cf_email(hexstr):
    key = int(hexstr[:2], 16)
    return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))


def clean(text):
    text = re.sub(r'<iframe[^>]*showCommentForm[^>]*>\s*</iframe>', "", text)
    text = re.sub(r'<script[^>]*adsbygoogle\.js[^>]*>\s*</script>', "", text)
    text = re.sub(r'<script>\s*\(adsbygoogle\s*=.*?</script>', "", text, flags=re.S)
    text = text.replace("'//cdn2.editmysite.com/js/wsnbn/snowday262.js'", "'about:blank'")
    text = re.sub(r'<script[^>]*email-decode\.min\.js[^>]*>\s*</script>', "", text)
    text = re.sub(
        r'<div id="weebly-footer-signup-container-v3">.*?Weebly\.footer\.setupContainer.*?</script>',
        "",
        text,
        flags=re.S,
    )
    text = re.sub(
        r'(?:[./]*)cdn-cgi/l/email-protection#([0-9a-f]+)',
        lambda m: "mailto:" + decode_cf_email(m.group(1)),
        text,
    )
    text = re.sub(
        r'<(span|a)[^>]*class="__cf_email__"[^>]*data-cfemail="([0-9a-f]+)"[^>]*>.*?</\1>',
        lambda m: decode_cf_email(m.group(2)),
        text,
        flags=re.S,
    )
    if MARK not in text:
        text = text.replace("</head>", HIDE_CSS + "\n</head>", 1)
    return text


if __name__ == "__main__":
    n = 0
    for path in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True):
        with open(path, encoding="utf-8") as f:
            before = f.read()
        after = clean(before)
        if after != before:
            with open(path, "w", encoding="utf-8") as f:
                f.write(after)
            n += 1
    print(f"cleaned {n} pages")
