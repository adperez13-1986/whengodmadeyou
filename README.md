# When God Made You — archive

Grace's Weebly site (`whengodmadeyou.weebly.com`), saved before Weebly deleted it.
Mirrored 2026-09-23 from the live site.

## View it

Open `site/index.html` in a browser, or serve it:

```sh
cd site && python3 -m http.server 8000   # http://localhost:8000
```

The `site/` folder is plain static HTML, so it can go on any static host (GitHub Pages, Netlify, Cloudflare Pages) as-is.

## What's here

- `site/` — the full site: 459 pages (every blog post, archive and category page) and 1,350 photos under `site/uploads/`.
- `export/` — the original "Download My Data" zip from Weebly. It holds the posts as raw HTML in CSV files, plus account data (her email, login IPs). **Don't publish this folder.**
- `tools/mirror.py` — the crawler that built `site/`. `tools/cleanup.py` — the post-processing pass that removes what can't work offline.

## What doesn't work any more

- Leaving new comments, and the share buttons (both removed). Existing comments are still shown.
- The embedded Facebook feed (SocialStream) and YouTube videos load from those services, so they need an internet connection.
- Some theme scripts still load extras from Weebly's shared CDN (`editmysite.com`). All the text and photos are local and display without them.

## Known gaps

About 170 photos listed in the export no longer exist on Weebly's servers (they return 404; see `tools/failures.txt`).
Almost all are old versions or drafts that no page uses. Only one photo that a page still shows is missing, and it was already broken on the live site.
