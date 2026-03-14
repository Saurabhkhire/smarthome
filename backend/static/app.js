(function () {
  const API = ""; // same origin
  const sessionId = "web-" + Math.random().toString(36).slice(2, 10);
  const messagesEl = document.getElementById("messages");
  const input = document.getElementById("input");
  const form = document.getElementById("form");
  const panel = document.getElementById("listing-panel");
  document.getElementById("session-label").textContent = "Session · " + sessionId;

  function addMsg(role, text, meta) {
    const div = document.createElement("div");
    div.className = "msg " + (role === "user" ? "user" : "bot");
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.textContent = meta;
      div.appendChild(m);
    }
    const p = document.createElement("div");
    p.textContent = text;
    div.appendChild(p);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderListings(listings) {
    panel.innerHTML = "";
    if (!listings || !listings.length) {
      panel.innerHTML = '<p class="hint">No listings in last reply. Search or run scraper.</p>';
      return;
    }
    listings.forEach(function (L) {
      const price =
        L.listing_kind === "rent" && L.price_display
          ? L.price_display
          : "$" + (L.price || 0).toLocaleString();
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML =
        '<span class="tag">' +
        (L.listing_kind || "sale") +
        " · " +
        (L.source || "") +
        "</span>" +
        "<strong>" +
        escapeHtml(L.title || "") +
        "</strong><br/>" +
        price +
        " · " +
        L.beds +
        "bd/" +
        L.baths +
        "ba · " +
        escapeHtml(L.city || "") +
        "<br/><a href=\"" +
        escapeAttr(L.url) +
        "\" target=\"_blank\" rel=\"noopener\">Open link</a>";
      panel.appendChild(card);
    });
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }
  function escapeAttr(s) {
    return String(s || "").replace(/"/g, "&quot;");
  }

  addMsg(
    "bot",
    "Hi — I’m Aria. I search the listings loaded by your ScrapeGraph scraper. What are you looking for?",
    "Welcome"
  );

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    addMsg("user", text);
    addMsg("bot", "…", "Thinking");

    try {
      const r = await fetch(API + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          lang: "en",
        }),
      });
      const data = await r.json();
      messagesEl.removeChild(messagesEl.lastChild);
      addMsg("bot", data.reply || "(no reply)", data.type || "reply");
      renderListings(data.listings);
    } catch (err) {
      messagesEl.removeChild(messagesEl.lastChild);
      addMsg("bot", "Couldn’t reach the server. Is uvicorn running?", "Error");
    }
  });

  document.getElementById("btn-clear").addEventListener("click", async function () {
    await fetch(API + "/session/" + encodeURIComponent(sessionId), { method: "DELETE" });
    messagesEl.innerHTML = "";
    panel.innerHTML = "";
    addMsg("bot", "Fresh thread. What should we look for?", "New chat");
  });

  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  });
})();
