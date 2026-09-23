# When God Made You

Grace's blog, moved off Weebly in September 2026 and rebuilt so she can keep writing.

- Site: https://adperez13-1986.github.io/whengodmadeyou/
- Editor: https://adperez13-1986.github.io/whengodmadeyou/admin/

## Writing a post

1. Open the editor and sign in (see below; it only has to be done once per browser).
2. Pick the blog in the left menu (Motherhood/Parenting, Yuri, ...) and press **New Post**.
3. Fill in the title and date, write the post, and add photos with the image button. Photos are shrunk automatically before upload.
4. Press **Save**. The site updates about two minutes later.

Turn on **Draft** to save a post without publishing it. Old posts can be edited too. Their original Weebly layout sits in the "Original post from Weebly" field as HTML, so edit that carefully. Text written in **Post** appears below it.

## Signing in to the editor (one-time setup)

The editor saves by committing to this repository, so it needs a GitHub access token:

1. On GitHub (as the repo owner): Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token.
   - Repository access: **Only select repositories** → `whengodmadeyou`
   - Permissions → Repository permissions → **Contents: Read and write**
   - Pick the longest expiry offered, and note the date.
2. In the browser Grace writes from, open the editor, choose **Sign In Using Access Token** and paste the token. It stays saved in that browser.

When the token expires, make a new one and sign in again. The token is scoped to this one repository, so it can't touch anything else.
Saves show up in the history as commits by the token's owner.

## How it works

- `src/posts/<blog>/<slug>.md`: one file per post, published at `/<blog>/<slug>.html`, the same URLs Weebly used.
- `src/pages/`: the standalone pages (home, About Me, ...), kept as Weebly's HTML. Edit these in the repo, not the editor.
- `src/_weebly/`: each page's banner and each blog's sidebar and surrounding content, carried over verbatim.
- `src/_includes/`: the page layout (Weebly's markup and theme), and the post and blog templates.
- `eleventy.config.js`: builds the listing pages (10 per page), month archives, category pages, RSS feeds and redirects from old Weebly links. It also rewrites links to be relative, so the site works under any URL.
- `src/admin/`: the editor ([Sveltia CMS](https://github.com/sveltia/sveltia-cms), pinned to a version in `index.html`).
- `.github/workflows/deploy.yml`: every push to `main` builds the site with [Eleventy](https://www.11ty.dev/) and publishes it to GitHub Pages.

Run it locally:

```sh
npm install
npm start        # http://localhost:8080
```

## History

- `export/` (not in git): the original Weebly "Download My Data" zip. It holds her email and login IP addresses. **Never publish it.**
- `tools/`: the one-off migration scripts. `mirror.py` and `cleanup.py` copied the live Weebly site; `extract.py` and `make_layout.py` turned that copy into `src/`. The mirror itself was removed after the rebuild; it's in git history at commit `75237b2`, if the scripts ever need to be rerun.
- Known gaps from Weebly: about 170 old photos the export lists were already gone from Weebly's servers (`tools/failures.txt`); none are used by a published page except one already broken on the live site.
