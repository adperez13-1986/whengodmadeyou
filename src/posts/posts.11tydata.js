// Every post lives at src/posts/<blog>/<slug>.md and is published at /<blog>/<slug>.html,
// the same URLs the Weebly site used.
export default {
  layout: "layouts/post.njk",
  eleventyComputed: {
    blog: (data) => data.page.inputPath.split("/").at(-2),
    permalink: (data) => (data.draft ? false : `/${data.page.inputPath.split("/").at(-2)}/${data.page.fileSlug}.html`),
    eleventyExcludeFromCollections: (data) => Boolean(data.draft),
  },
};
