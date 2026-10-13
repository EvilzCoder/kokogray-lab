(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const root = document.documentElement;
  const media = matchMedia("(prefers-color-scheme: dark)");
  const basePath = (document.body.dataset.baseUrl || ".").replace(/\/+$/, "");
  const siteBase = new URL(`${basePath}/`, location.href);
  let toastTimer;

  function notify(message) {
    const toast = $(".toast");
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3000);
  }

  function applyTheme(preference) {
    root.dataset.themePreference = preference;
    root.dataset.theme = preference === "system" ? (media.matches ? "dark" : "light") : preference;
    $$("[data-set-theme]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.setTheme === preference));
    });
  }

  applyTheme(root.dataset.themePreference || "dark");
  $$("[data-set-theme]").forEach(button => {
    button.addEventListener("click", () => {
      const preference = button.dataset.setTheme;
      applyTheme(preference);
      try { localStorage.setItem("kokogray-theme", preference); } catch { /* Optional persistence. */ }
    });
  });
  media.addEventListener("change", () => {
    if (root.dataset.themePreference === "system") applyTheme("system");
  });

  const sidebar = $(".site-sidebar");
  const menuButton = $("[data-open-nav]");
  const backdrop = $(".nav-backdrop");
  const mobile = matchMedia("(max-width: 1023px)");
  const focusable = 'a[href], button:not([disabled]), summary, input, [tabindex="0"]';

  function setNavigation(open, restoreFocus = true) {
    const isOpen = open && mobile.matches;
    document.body.classList.toggle("nav-open", isOpen);
    backdrop.hidden = !isOpen;
    menuButton.setAttribute("aria-expanded", String(isOpen));
    menuButton.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    if (mobile.matches) sidebar.inert = !isOpen;
    else sidebar.inert = false;
    $$(".site-header, .page-main, .page-outline").forEach(element => { element.inert = isOpen; });
    if (isOpen) {
      sidebar.setAttribute("role", "dialog");
      sidebar.setAttribute("aria-modal", "true");
      requestAnimationFrame(() => {
        if (document.body.classList.contains("nav-open")) {
          $("[data-close-nav]", sidebar).focus({ preventScroll: true });
        }
      });
    } else {
      sidebar.removeAttribute("role");
      sidebar.removeAttribute("aria-modal");
      if (restoreFocus && mobile.matches) menuButton.focus();
    }
  }

  setNavigation(false, false);
  menuButton.addEventListener("click", () => setNavigation(!document.body.classList.contains("nav-open")));
  $$("[data-close-nav]").forEach(button => button.addEventListener("click", () => setNavigation(false)));
  mobile.addEventListener("change", () => setNavigation(false, false));
  $$(".nav-link", sidebar).forEach(link => link.addEventListener("click", () => {
    if (mobile.matches) setNavigation(false, false);
  }));

  document.addEventListener("keydown", event => {
    if (!document.body.classList.contains("nav-open")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      setNavigation(false);
    }
    if (event.key === "Tab") {
      const elements = $$(focusable, sidebar).filter(element => element.checkVisibility());
      const first = elements[0];
      const last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  async function copy(text, message) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const previousFocus = document.activeElement;
        const input = document.createElement("textarea");
        input.value = text;
        input.className = "sr-only";
        input.setAttribute("readonly", "");
        document.body.append(input);
        input.select();
        const copied = document.execCommand("copy");
        input.remove();
        previousFocus?.focus({ preventScroll: true });
        if (!copied) throw new Error("Clipboard unavailable");
      }
      notify(message);
    } catch {
      notify("Clipboard access is blocked. Select the text and copy it manually.");
    }
  }

  $$("[data-copy-link]").forEach(button => button.addEventListener("click", () => copy(location.href, "Link copied")));
  $$("[data-copy-page]").forEach(button => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const response = await fetch(document.body.dataset.markdownUrl);
      if (!response.ok) throw new Error("Page source unavailable");
      await copy(await response.text(), "Page copied as Markdown");
    } catch {
      notify("Could not load the Markdown source. Please try again.");
    } finally {
      button.disabled = false;
    }
  }));

  $$(".codehilite").forEach(block => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "code-copy";
    button.setAttribute("aria-label", "Copy code");
    button.title = "Copy code";
    button.textContent = "Copy";
    button.addEventListener("click", () => copy($("code", block).textContent.replace(/\n$/, ""), "Code copied"));
    block.append(button);
  });

  const headings = $$(".page-content h2[id], .page-content h3[id]");
  const outlineLinks = $$(".page-outline nav a");
  let scrollQueued = false;
  function updateOutline() {
    scrollQueued = false;
    let current = headings[0];
    for (const heading of headings) {
      if (heading.getBoundingClientRect().top <= 130) current = heading;
    }
    outlineLinks.forEach(link => {
      const active = Boolean(current) && decodeURIComponent(link.hash.slice(1)) === current.id;
      link.classList.toggle("is-current", active);
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }
  if (headings.length) {
    updateOutline();
    window.addEventListener("scroll", () => {
      if (!scrollQueued) {
        scrollQueued = true;
        requestAnimationFrame(updateOutline);
      }
    }, { passive: true });
    window.addEventListener("resize", updateOutline);
  }
  const mobileOutline = $(".mobile-outline");
  if (mobileOutline) {
    const summary = $("summary", mobileOutline);
    $$("a", mobileOutline).forEach(link => link.addEventListener("click", () => {
      mobileOutline.open = false;
      const heading = document.getElementById(decodeURIComponent(link.hash.slice(1)));
      if (heading) {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      }
    }));
    mobileOutline.addEventListener("keydown", event => {
      if (event.key === "Escape" && mobileOutline.open) {
        event.preventDefault();
        mobileOutline.open = false;
        summary.focus({ preventScroll: true });
      }
    });
    document.addEventListener("click", event => {
      if (!mobileOutline.contains(event.target)) mobileOutline.open = false;
    });
    mobileOutline.addEventListener("focusout", event => {
      if (!mobileOutline.contains(event.relatedTarget)) mobileOutline.open = false;
    });
  }

  const dialog = $("#search-dialog");
  const input = $("#site-search");
  const results = $("#search-results");
  const status = $("[data-search-status]");
  let searchDocuments = null;
  let loadingIndex = null;
  let selected = -1;
  let searchTimer;
  let lastSearchTrigger;
  const isApple = /Mac|iPhone|iPad/.test(navigator.platform);
  $$("[data-shortcut-mod]").forEach(element => { element.textContent = isApple ? "⌘" : "Ctrl"; });

  async function getSearchIndex() {
    if (searchDocuments) return searchDocuments;
    if (!loadingIndex) {
      loadingIndex = fetch(new URL("search/search_index.json", siteBase))
        .then(response => {
          if (!response.ok) throw new Error("Search unavailable");
          return response.json();
        })
        .then(index => {
          searchDocuments = index.docs.map(doc => ({
            ...doc,
            text: doc.text.replace(/\s+/g, " ").trim(),
            titleLower: doc.title.toLocaleLowerCase(),
            textLower: doc.text.replace(/\s+/g, " ").trim().toLocaleLowerCase()
          }));
          return searchDocuments;
        })
        .catch(error => { loadingIndex = null; throw error; });
    }
    return loadingIndex;
  }

  function highlighted(text, terms) {
    const fragment = document.createDocumentFragment();
    const lower = text.toLocaleLowerCase();
    let start = 0;
    while (start < text.length) {
      let next = -1;
      let length = 0;
      for (const term of terms) {
        const position = lower.indexOf(term, start);
        if (position >= 0 && (next < 0 || position < next)) {
          next = position;
          length = term.length;
        }
      }
      if (next < 0) { fragment.append(text.slice(start)); break; }
      fragment.append(text.slice(start, next));
      const mark = document.createElement("mark");
      mark.textContent = text.slice(next, next + length);
      fragment.append(mark);
      start = next + length;
    }
    return fragment;
  }

  function selectResult(index, moveFocus = false) {
    const links = $$(".search-result", results);
    if (!links.length) return;
    selected = (index + links.length) % links.length;
    links.forEach((link, i) => {
      link.classList.toggle("is-selected", i === selected);
      if (i === selected) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
    links[selected].scrollIntoView({ block: "nearest" });
    if (moveFocus) links[selected].focus({ preventScroll: true });
  }

  async function search() {
    const query = input.value.trim();
    const terms = [...new Set(query.toLocaleLowerCase().split(/\s+/).filter(Boolean))];
    results.replaceChildren();
    selected = -1;
    if (!terms.length) {
      status.textContent = "Type to search the lab.";
      return;
    }
    status.textContent = "Searching…";
    try {
      const docs = await getSearchIndex();
      if (query !== input.value.trim()) return;
      const matches = docs.map(doc => {
        const combined = `${doc.titleLower} ${doc.textLower}`;
        if (!terms.every(term => combined.includes(term))) return null;
        const score = terms.reduce((total, term) => total +
          (doc.titleLower.includes(term) ? 12 : 0) +
          (doc.titleLower.startsWith(term) ? 5 : 0) +
          (doc.textLower.includes(term) ? 1 : 0), 0) +
          (doc.titleLower === query.toLocaleLowerCase() ? 30 : 0);
        return { ...doc, score };
      }).filter(Boolean).sort((a, b) => b.score - a.score);
      const uniquePages = new Map();
      for (const match of matches) {
        const page = match.location.split("#")[0];
        if (!uniquePages.has(page)) uniquePages.set(page, match);
      }
      const visible = [...uniquePages.values()].slice(0, 20);
      for (const doc of visible) {
        const href = new URL(doc.location, siteBase);
        if (href.origin !== location.origin || !href.pathname.startsWith(siteBase.pathname)) continue;
        const link = document.createElement("a");
        link.className = "search-result";
        link.href = href.href;
        const symbol = $(".sidebar-caption .icon").cloneNode(true);
        const label = document.createElement("span");
        const title = document.createElement("strong");
        title.append(highlighted(doc.title, terms));
        const snippet = document.createElement("small");
        const first = Math.max(0, doc.textLower.indexOf(terms[0]));
        const start = Math.max(0, first - 50);
        const excerpt = `${start ? "…" : ""}${doc.text.slice(start, start + 170)}${doc.text.length > start + 170 ? "…" : ""}`;
        snippet.append(highlighted(excerpt, terms));
        label.append(title, snippet);
        link.append(symbol, label);
        link.addEventListener("click", () => dialog.close());
        link.addEventListener("focus", () => selectResult($$(".search-result", results).indexOf(link)));
        results.append(link);
      }
      status.textContent = visible.length
        ? `${uniquePages.size} matching ${uniquePages.size === 1 ? "page" : "pages"}${uniquePages.size > 20 ? " · showing the first 20" : ""}`
        : `No results for “${query}”. Try a different word.`;
      if (visible.length) selectResult(0);
    } catch {
      status.textContent = "Search could not load. Check your connection and type again to retry.";
    }
  }

  function openSearch(trigger) {
    if (dialog.open) return;
    const navigationOpen = document.body.classList.contains("nav-open");
    lastSearchTrigger = navigationOpen ? menuButton : (trigger || document.activeElement);
    if (navigationOpen) setNavigation(false, false);
    dialog.showModal();
    input.focus();
    input.select();
    search();
  }
  $$("[data-open-search]").forEach(button => button.addEventListener("click", () => openSearch(button)));
  $("[data-close-search]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => lastSearchTrigger?.focus({ preventScroll: true }));
  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  input.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(search, 100);
  });
  dialog.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      dialog.close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      selectResult(selected + (event.key === "ArrowDown" ? 1 : -1), true);
    } else if (event.key === "Enter" && document.activeElement === input && selected >= 0) {
      event.preventDefault();
      $$(".search-result", results)[selected]?.click();
    }
  });
  document.addEventListener("keydown", event => {
    const editing = event.target.matches("input, textarea, select, [contenteditable=true]");
    if (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") || (event.key === "/" && !editing && !event.ctrlKey && !event.metaKey && !event.altKey)) {
      event.preventDefault();
      openSearch(document.activeElement);
    }
  });
})();
