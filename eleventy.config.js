import path from "node:path";
import markdownIt from "markdown-it";

const PER_PAGE = 10;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const SITE_TITLE = "When God Made You";

const md = markdownIt({ html: true, breaks: true, linkify: true });

const slugify = (s) => s.toLowerCase().normalize("NFKD").replace(/[^\w\s-]/g, "").trim().replace(/[\s_-]+/g, "-");
const pad = (n) => String(n).padStart(2, "0");

// Weebly shows dates as d/m/yyyy. Post dates are stored without a zone and read as UTC.
const blogDate = (d) => `${d.getUTCDate()}/${d.getUTCMonth() + 1}/${d.getUTCFullYear()}`;

function chunk(items, size) {
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out.length ? out : [[]];
}

// Root-relative URLs ("/uploads/x.jpg") become relative to the page, so the site works
// under any path prefix (GitHub Pages project URL, a custom domain, or straight from disk).
function relativize(html, pageUrl) {
  const dir = pageUrl.endsWith("/") ? pageUrl : path.posix.dirname(pageUrl);
  const rel = (u) => {
    if (!u.startsWith("/") || u.startsWith("//")) return u;
    const [, p, rest] = u.match(/^([^?#]*)(.*)$/);
    const target = p === "/" ? "/index.html" : p;
    const r = path.posix.relative(dir, target) + (p.endsWith("/") && p !== "/" ? "/" : "");
    return (r || "./") + rest;
  };
  return html
    .replace(/(\s(?:src|href|data-src|poster|action)=)(["'])(.*?)\2/g, (m, a, q, u) => a + q + rel(u) + q)
    .replace(/(\ssrcset=)(["'])(.*?)\2/g, (m, a, q, v) =>
      a + q + v.split(",").map((part) => part.trim().replace(/^\S+/, rel)).join(", ") + q)
    .replace(/url\((&quot;|&#39;|["']?)(\/[^"')]*?)\1\)/g, (m, q, u) => `url(${q}${rel(u)}${q})`);
}

export default function (eleventyConfig) {
  eleventyConfig.setLibrary("md", md);
  eleventyConfig.ignores.add("src/_weebly/**");
  eleventyConfig.ignores.add("src/admin/**");
  eleventyConfig.addPassthroughCopy({ "src/uploads": "uploads", "src/files": "files", "src/_cdn": "_cdn", "src/admin": "admin", "src/assets": "assets" });
  eleventyConfig.addWatchTarget("src/_weebly/");

  // Nunjucks' selectattr can't compare values, so lookups get their own filters.
  const get = (o, key) => key.split(".").reduce((v, k) => v?.[k], o);
  eleventyConfig.addFilter("findBy", (list, key, value) => (list || []).find((x) => get(x, key) === value));
  eleventyConfig.addFilter("whereEq", (list, key, value) => (list || []).filter((x) => get(x, key) === value));
  eleventyConfig.addFilter("blogDate", blogDate);
  eleventyConfig.addFilter("rfc822", (d) => d.toUTCString());
  eleventyConfig.addFilter("flyoutsJson", (nav) =>
    JSON.stringify(nav.map((n) => ({ id: n.id, title: n.title, url: n.url, target: "", nav_menu: false, nonclickable: false }))));

  // Full post HTML: the original Weebly content (old posts) followed by anything written in the editor.
  const postHtml = (post) => (post.data.weebly_html || "") + (post.content || "");
  eleventyConfig.addFilter("postHtml", postHtml);
  eleventyConfig.addFilter("postExcerpt", (post) => {
    const html = postHtml(post);
    const i = html.indexOf("<!--more-->");
    return i === -1 ? null : html.slice(0, i);
  });
  eleventyConfig.addFilter("plainText", (html, n = 200) => {
    const text = (html || "").replace(/<[^>]+>/g, " ").replace(/&nbsp;|&#8203;/g, " ").replace(/\s+/g, " ").trim();
    return text.length > n ? text.slice(0, n).replace(/\s\S*$/, "") + "..." : text;
  });
  eleventyConfig.addFilter("firstImage", (html) => (html || "").match(/<img[^>]+src="(\/[^"]+)"/)?.[1] || null);
  eleventyConfig.addFilter("absoluteUrls", (html, base) =>
    (html || "").replace(/(\s(?:src|href)=")\/(?!\/)/g, `$1${base}/`));

  const livePosts = (api) =>
    api.getFilteredByGlob("src/posts/**/*.md")
      .filter((p) => !p.data.draft)
      .sort((a, b) => b.date - a.date);

  eleventyConfig.addCollection("posts", livePosts);

  // Every generated blog page: listing pages, month archives, category pages.
  eleventyConfig.addCollection("listings", (api) => {
    const blogs = api.getAll()[0]?.data.blogs || [];
    const posts = livePosts(api);
    const pages = [];
    const add = (blog, kind, title, urlFor, list) => {
      const groups = chunk(list, PER_PAGE);
      groups.forEach((group, i) => {
        pages.push({
          blog, kind, title: typeof title === "function" ? title(i) : title,
          url: urlFor(i), posts: group,
          older: i + 1 < groups.length ? urlFor(i + 1) : null,
          newer: i > 0 ? urlFor(i - 1) : null,
        });
      });
    };
    for (const blog of blogs) {
      const mine = posts.filter((p) => p.data.blog === blog.key);
      const k = blog.key;
      add(blog, "index", (i) => (i === 0 ? blog.pageTitle : `Blog Posts - ${SITE_TITLE}`),
        (i) => (i === 0 ? `/${k}.html` : `/${k}/previous/${i + 1}.html`), mine);
      add(blog, "category", `All Categories - ${SITE_TITLE}`,
        (i) => (i === 0 ? `/${k}/category/all.html` : `/${k}/category/all/${i + 1}.html`), mine);
      for (const cat of categoriesOf(blog, mine)) {
        add(blog, "category", `Category: ${cat.name} - ${SITE_TITLE}`,
          (i) => (i === 0 ? `/${k}/category/${cat.slug}.html` : `/${k}/category/${cat.slug}/${i + 1}.html`),
          mine.filter((p) => (p.data.categories || []).includes(cat.name)));
      }
      for (const m of monthsOf(mine)) {
        add(blog, "archive", `Blog Archives - ${SITE_TITLE}`,
          (i) => (i === 0 ? `/${k}/archives/${m.key}.html` : `/${k}/archives/${m.key}/${i + 1}.html`),
          mine.filter((p) => monthKey(p.date) === m.key));
      }
    }
    return pages;
  });

  const monthKey = (d) => `${pad(d.getUTCMonth() + 1)}-${d.getUTCFullYear()}`;
  function monthsOf(posts) {
    const seen = new Map();
    for (const p of posts) {
      const key = monthKey(p.date);
      if (!seen.has(key)) seen.set(key, { key, label: `${MONTHS[p.date.getUTCMonth()]} ${p.date.getUTCFullYear()}` });
    }
    return [...seen.values()];
  }
  // Categories in use, in Weebly's order: the ones the blog already had, then any new ones A-Z.
  function categoriesOf(blog, posts) {
    const used = new Set(posts.flatMap((p) => p.data.categories || []));
    const known = blog.categories.filter((c) => used.has(c.name));
    const extra = [...used].filter((n) => !blog.categories.some((c) => c.name === n)).sort()
      .map((name) => ({ name, slug: slugify(name) }));
    return [...known, ...extra];
  }

  // The blog sidebar from Weebly, with its Archives and Categories lists regenerated.
  eleventyConfig.addFilter("sidebar", (blog, posts, weebly) => {
    const mine = posts.filter((p) => p.data.blog === blog.key);
    const sidebar = weebly.blogs[blog.key].sidebar;
    const archives = `<p class="blog-archive-list">\n` + monthsOf(mine).map((m) =>
      `\t\t<a href="/${blog.key}/archives/${m.key}.html" class="blog-link">${m.label}</a>\n\t\t<br />\n`).join("") + `</p>`;
    const cats = [{ name: "All", slug: "all" }, ...categoriesOf(blog, mine)];
    const categories = `<p class="blog-category-list">\n` + cats.map((c) =>
      `\t<a href="/${blog.key}/category/${c.slug}.html" class="blog-link">${c.name}</a>\n\t<br />\n`).join("") + `</p>`;
    return sidebar.replace("<!--ARCHIVES-->", archives).replace("<!--CATEGORIES-->", categories);
  });

  eleventyConfig.addTransform("relativize", function (content) {
    // Drafts have outputPath false: nothing is written, so there is nothing to rewrite.
    const out = this.page.outputPath;
    if (typeof out !== "string" || !out.endsWith(".html") || this.page.url.startsWith("/admin/")) return content;
    return relativize(content, this.page.url);
  });

  return {
    dir: { input: "src", output: "_site" },
    templateFormats: ["njk", "md", "html"],
    htmlTemplateEngine: false,
    markdownTemplateEngine: false,
  };
}
