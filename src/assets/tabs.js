// Weebly's "tabbed box" widget (home page: As A Daughter/Sister, As A Mother, ...).
// On Weebly it was driven by Weebly's own app runtime; this is a standalone
// replacement with the same behaviour: click a tab to show its panel, first tab
// open on load, arrows to scroll the tab bar when it doesn't fit.
(function () {
  function setup(box) {
    var bar = box.querySelector(":scope > .tabbed-box-bar");
    var group = bar && bar.querySelector(":scope > .tabbed-box-tab-group");
    var panels = box.querySelector(":scope > .tabbed-box-content-group");
    if (!group || !panels) return;
    var tabs = Array.prototype.slice.call(group.children);
    var left = bar.querySelector(":scope > .scrollArrow-left");
    var right = bar.querySelector(":scope > .scrollArrow-right");

    function arrows() {
      var scrollable = group.scrollWidth > group.clientWidth;
      box.classList.toggle("scrollable", scrollable);
      if (left) left.classList.toggle("active", scrollable && group.scrollLeft > 0);
      if (right) right.classList.toggle("active", scrollable && group.scrollLeft + group.clientWidth < group.scrollWidth - 1);
    }

    function show(tab) {
      tabs.forEach(function (t) { t.classList.toggle("active", t === tab); });
      var rel = tab.getAttribute("rel");
      Array.prototype.forEach.call(panels.children, function (p) {
        p.style.display = p.classList.contains(rel) ? "block" : "none";
      });
      tab.scrollIntoView({ block: "nearest", inline: "nearest" });
      window.dispatchEvent(new Event("resize"));
    }

    tabs.forEach(function (tab) {
      tab.style.cursor = "pointer";
      tab.addEventListener("click", function (e) { e.stopPropagation(); show(tab); });
    });
    if (left) left.addEventListener("click", function () { group.scrollBy({ left: -200, behavior: "smooth" }); });
    if (right) right.addEventListener("click", function () { group.scrollBy({ left: 200, behavior: "smooth" }); });
    group.addEventListener("scroll", arrows);
    window.addEventListener("resize", arrows);
    if (tabs.length) show(tabs[0]);
    arrows();
  }

  function init() { document.querySelectorAll(".tabbed-box").forEach(setup); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
