(() => {
  let preference = "dark";
  try {
    const stored = localStorage.getItem("kokogray-theme");
    if (["light", "dark", "system"].includes(stored)) preference = stored;
  } catch {
    // A blocked storage API must not prevent the page from rendering.
  }
  const theme = preference === "system"
    ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themePreference = preference;
})();
