// Verbatim HTML blocks carried over from the Weebly site (banners, and the content
// around each blog's post list). Loaded as data so they are never run through a
// template engine.
import fs from "node:fs";
import path from "node:path";

const dir = path.join(import.meta.dirname, "..", "_weebly");
const read = (...p) => fs.readFileSync(path.join(dir, ...p), "utf8");

export default function () {
  const banners = {};
  for (const f of fs.readdirSync(path.join(dir, "banners"))) banners[f.replace(/\.html$/, "")] = read("banners", f);
  const blogs = {};
  for (const f of fs.readdirSync(path.join(dir, "blogs"))) {
    const [, key, part] = f.match(/^(.*)-(before|after|sidebar)\.html$/);
    (blogs[key] ||= {})[part] = read("blogs", f);
  }
  return { banners, blogs };
}
