// AJAX submit so we follow the redirect after upload
document.getElementById("uploadForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);
  const res = await fetch(form.action, { method: "POST", body: data });
  // if server redirected, fetch will follow; if it returns redirect response we handle:
  if (res.redirected) {
    window.location = res.url;
    return;
  }
  if (res.ok) {
    window.location = "/dashboard";
    return;
  }
  alert("Upload failed");
});
