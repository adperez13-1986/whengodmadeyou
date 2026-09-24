"""Build src/_includes/layouts/base.njk from a real mirrored page, so the page shell
(head, header, navigation, footer, theme scripts) matches Weebly's output exactly.

One-off migration step; run after extract.py. The per-page parts (title, meta tags,
body class, nav highlight, banner, main content) become template variables.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import extract  # noqa: E402

FLY_START = "<script type=\"text/javascript\"><!--\n\t\n\t\n\tfunction initFlyouts(){"
SAMPLE = "our-journey-of-love/the-wedding-proposal-november-24-2013.html"
OUT = os.path.join(extract.SRC, "_includes", "layouts", "base.njk")


def cut(text, start, end):
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def raw(s):
    return "{% raw %}" + s + "{% endraw %}"


def main():
    t = extract.rootify(extract.read(SAMPLE), SAMPLE)

    head_static = cut(t, "<meta http-equiv='cache-control'", FLY_START)
    flyouts = cut(t, FLY_START, "</script>\n") + "</script>\n"
    fly_tail = flyouts[flyouts.index('\t\t\t\'\',\n\t\t\t\'active\''):]
    footer = cut(t, '<div id="footer-wrap">', "<!-- JavaScript -->")
    theme_js = cut(t, "<!-- JavaScript -->", "<script type=\"text/javascript\">\n\tvar _gaq")
    li = cut(t, '<li id="active" class="wsite-menu-item-wrap">', "</li>") + "</li>"
    li = li.replace('<li id="active"', '<li id="{{ \'active\' if item.id == activeNav else \'pg\' + item.id }}"')
    li = re.sub(r'href="[^"]*"', 'href="{{ item.url }}"', li)
    li = re.sub(r">\s*Our Journey of Love\s*</a>", ">\n\t\t\t\t{{ item.title }}\n\t\t\t</a>", li)
    nav_ul = '<ul class="wsite-menu-default">\n\t\t{% for item in nav %}' + li + "{% endfor %}\n</ul>\n"

    header = cut(t, '<div id="header-wrap">', '<div id="main-content">')
    header = re.sub(r'<ul class="wsite-menu-default">.*?</ul>\n', lambda m: "@@NAV@@", header, flags=re.S)
    header_parts = header.split("@@NAV@@")
    logo = re.search(r'<img src="([^"]+)" alt="When God Made You" />', header_parts[0]).group(1)

    layout = "".join([
        "<!DOCTYPE html>\n<html lang=\"en\">\n\t<head>\n",
        "\t\t<title>{{ pageTitle }}</title><meta property=\"og:site_name\" content=\"When God Made You\" />\n",
        "<meta property=\"og:title\" content=\"{{ ogTitle or pageTitle }}\" />\n",
        "{% if ogDescription %}<meta property=\"og:description\" content=\"{{ ogDescription }}\" />\n{% endif %}",
        "{% if ogImage %}<meta property=\"og:image\" content=\"{{ site.url }}{{ ogImage }}\" />\n{% endif %}",
        "<meta property=\"og:url\" content=\"{{ site.url }}{{ page.url }}\" />\n",
        "{% if description %}<meta name=\"description\" content=\"{{ description }}\" />\n{% endif %}",
        "{% if keywords %}<meta name=\"keywords\" content=\"{{ keywords }}\" />\n{% endif %}",
        raw(head_static),
        "<script type=\"text/javascript\"><!--\n\tfunction initFlyouts(){\n\t\tinitPublishedFlyoutMenus(\n\t\t\t{{ nav | flyoutsJson(page.url) | safe }},\n\t\t\t\"{{ activeNav }}\",\n",
        raw(fly_tail),
        "\t<style>#commentReplyTitle,.blogCommentReplyWrapper,.blog-social,.blog-comment-area .blogCommentOptions{display:none!important}"
        ".blog-content img{max-width:100%;height:auto}</style>\n",
        "</head>\n<body class=\"{{ bodyClass }}\">",
        raw(header_parts[0].replace(logo, "@@LOGO@@")).replace("@@LOGO@@", "{% endraw %}" + logo + "{% raw %}"),
        nav_ul,
        raw(header_parts[1]),
        nav_ul,
        raw(header_parts[2]),
        "<div id=\"main-content\">\n\t\t\t\t<!-- banner-wrap -->\n\t\t\t\t<div id=\"banner-wrap\">",
        "{{ weebly.banners[banner] | safe }}",
        "<!-- end banner-wrap -->\n\t\t\t\t<div id=\"main-wrap\" class=\"content-wrap\">",
        "{% block main %}{{ content | safe }}{% endblock %}",
        raw(footer),
        raw(theme_js),
        "\t<script src=\"/assets/tabs.js\"></script>\n",
        "\t</body>\n</html>\n",
    ])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(layout)
    print("wrote", os.path.relpath(OUT))


if __name__ == "__main__":
    main()
