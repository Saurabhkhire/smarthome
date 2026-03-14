import { useCallback, useEffect, useRef, useState } from "react";
import LeafletMapPane from "./LeafletMapPane.jsx";

const LANGS = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
];

const API = "";

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "aria",
      text: "I'm **Aria** — **San Francisco homes only**. Map is **OpenStreetMap** (free, no API key). Chips, negotiate meter, Spanish.",
      meta: "Welcome",
    },
  ]);
  const [input, setInput] = useState("");
  const [lang, setLang] = useState("en");
  const [loading, setLoading] = useState(false);
  const [streamingCards, setStreamingCards] = useState([]);
  const [sessionId] = useState(() => "react-" + Math.random().toString(36).slice(2, 11));
  const [listings, setListings] = useState([]);
  const [chips, setChips] = useState([]);
  const [trail, setTrail] = useState([]);
  const [toast, setToast] = useState(null);
  const [langBadge, setLangBadge] = useState(null);
  const [overlayListing, setOverlayListing] = useState(null);
  const [highlightId, setHighlightId] = useState(null);
  const [mapFocusId, setMapFocusId] = useState(null);
  const cardRefs = useRef({});
  const [lastNegotiate, setLastNegotiate] = useState(null);
  const [areaMedian, setAreaMedian] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingCards]);

  const sendRaw = useCallback(
    async (text) => {
      if (!text.trim() || loading) return;
      setInput("");
      setMessages((m) => [...m, { role: "user", text }]);
      setLoading(true);
      setStreamingCards([]);
      setChips([]);
      setLastNegotiate(null);
      try {
        const r = await fetch(API + "/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, session_id: sessionId, lang }),
        });
        const data = await r.json();
        if (data.scrape_ms != null || (data.scrape_stages && data.scrape_stages.length)) {
          const ms = data.scrape_ms != null ? `${(data.scrape_ms / 1000).toFixed(1)}s` : "";
          setToast(
            [(data.scrape_stages || []).join(" → "), ms && `done in ${ms}`].filter(Boolean).join(" · ")
          );
          setTimeout(() => setToast(null), 5000);
        }
        if (data.lang_badge) setLangBadge(data.lang_badge);
        else setLangBadge(null);
        setTrail(data.memory_trail || []);
        setChips(data.suggested_chips || []);
        setAreaMedian(data.area_median_price);
        if (data.negotiate_score != null) {
          setLastNegotiate({ score: data.negotiate_score, label: data.negotiate_label });
        }
        const Ls = data.listings || [];
        setListings(Ls);
        for (let i = 0; i < Ls.length; i++) {
          await new Promise((res) => setTimeout(res, 220));
          setStreamingCards((c) => [...c, Ls[i]]);
        }
        setMessages((m) => [
          ...m,
          {
            role: "aria",
            text: data.reply || "",
            meta: [data.type, data.email_sent ? "Emailed" : ""].filter(Boolean).join(" · "),
            negotiate: data.negotiate_score,
          },
        ]);
      } catch {
        setMessages((m) => [...m, { role: "aria", text: "API offline — start backend :8000", meta: "Error" }]);
      } finally {
        setLoading(false);
        setStreamingCards([]);
      }
    },
    [loading, sessionId, lang]
  );

  const send = (e) => {
    e?.preventDefault();
    sendRaw(input);
  };

  const clearChat = async () => {
    await fetch(API + "/session/" + encodeURIComponent(sessionId), { method: "DELETE" });
    setMessages([{ role: "aria", text: "New thread.", meta: "Aria" }]);
    setListings([]);
    setTrail([]);
    setChips([]);
  };

  function cardSubtitle(L) {
    const price =
      L.price_display ||
      `$${Number(L.price).toLocaleString()}${L.listing_kind === "rent" ? "/mo" : ""}`;
    const bb = `${L.beds ?? 0} bd · ${L.baths ?? 0} ba`;
    const loc = [L.city, L.state].filter(Boolean).join(", ") || "—";
    const sq = L.sqft_display || (L.sqft ? `${Number(L.sqft).toLocaleString()} sqft` : null);
    const walk = L.walk_score != null ? `Walk ${L.walk_score}` : null;
    return [price, bb, loc, sq, walk].filter(Boolean).join(" · ");
  }

  function explainAnnotations(L) {
    const rows = [];
    if ((L.description || "").toLowerCase().includes("hoa"))
      rows.push({ dot: "hoa", text: "HOA / fees mentioned in description" });
    if (L.pct_vs_median != null) {
      rows.push({
        dot: "price",
        text:
          L.pct_vs_median > 0
            ? `Price ~${L.pct_vs_median}% above this batch median`
            : `Price ~${Math.abs(L.pct_vs_median)}% below median — relative value`,
      });
    }
    if (L.walk_score != null)
      rows.push({
        dot: "walk",
        text: `Walk Score ${L.walk_score} — ${L.walk_score >= 80 ? "very walkable" : L.walk_score >= 50 ? "somewhat walkable" : "car-dependent"}`,
      });
    if (rows.length === 0) rows.push({ dot: "ok", text: "No HOA flag in text · compare on map with other pins" });
    return rows;
  }

  const maxBar = Math.max(
    ...(listings.map((x) => x.price).filter(Boolean) || [1]),
    areaMedian || 0,
    1
  );

  return (
    <div className="layout">
      {langBadge && <div className="lang-badge">{langBadge}</div>}
      {toast && <div className="toast">{toast}</div>}

      <div className="trail-bar">
        <strong>Your search trail</strong>
        {trail.length === 0 && <span>— filters appear here as you refine</span>}
        {trail.map((c, i) => (
          <span key={i}>
            {i > 0 && <span className="trail-sep">→</span>}
            <button type="button" className="trail-crumb" onClick={() => sendRaw(c)}>
              {c.length > 36 ? c.slice(0, 33) + "…" : c}
            </button>
          </span>
        ))}
      </div>

      <div className="split">
        <div className="chat-pane">
          <header className="header">
            <h1>Aria · SF</h1>
            <select className="lang-select" value={lang} onChange={(e) => setLang(e.target.value)}>
              {LANGS.map((L) => (
                <option key={L.code} value={L.code}>
                  {L.label}
                </option>
              ))}
            </select>
            <button type="button" className="btn-ghost" onClick={clearChat}>
              New chat
            </button>
          </header>

          <div className="messages">
            {messages.map((msg, i) => (
              <div key={i} className={`msg ${msg.role}`}>
                {msg.meta && <div className="meta">{msg.meta}</div>}
                {msg.text}
                {msg.role === "aria" && msg.negotiate != null && (
                  <div className="negotiate-meter">
                    <h4>Negotiation power</h4>
                    <div className="gauge">
                      <div
                        className={`gauge-fill ${msg.negotiate >= 60 ? "high" : msg.negotiate >= 40 ? "mid" : "low"}`}
                        style={{ width: `${msg.negotiate}%` }}
                      />
                    </div>
                    <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted)" }}>
                      {msg.negotiate}/100 · {lastNegotiate?.label}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="msg aria">
                <div className="meta">Aria · thinking</div>
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
                {streamingCards.length > 0 && (
                  <div className="cards-stream">
                    {streamingCards.map((L, idx) => (
                      <div
                        key={L.id}
                        className="listing-card-anim"
                        style={{ animationDelay: `${idx * 0.05}s` }}
                        onClick={() => {
                          setHighlightId(L.id);
                          setMapFocusId(L.id);
                        }}
                        onDoubleClick={() => setOverlayListing(L)}
                      >
                        <div className="card-inner">
                          <div className="card-front">
                            <div className="line1">
                              {L.title?.slice(0, 42)}
                              {L.title?.length > 42 ? "…" : ""}
                            </div>
                            <div className="line2">{cardSubtitle(L)}</div>
                            {L.address ? (
                              <div className="line3">{L.address}</div>
                            ) : null}
                            {areaMedian && L.price ? (
                              <div className="card-bar-wrap">
                                <div className="card-bar-label">
                                  <span>Area median (~batch)</span>
                                  <span>This listing</span>
                                </div>
                                <div className="card-bar">
                                  <div
                                    className="card-bar-median"
                                    style={{ width: `${(areaMedian / maxBar) * 100}%` }}
                                  />
                                </div>
                                <div className="card-bar" style={{ marginTop: 4 }}>
                                  <div
                                    className="card-bar-listing"
                                    style={{ width: `${(L.price / maxBar) * 100}%` }}
                                  />
                                </div>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!loading && listings.length > 0 && (
              <div className="cards-persist">
                {listings.map((L) => (
                  <div
                    key={L.id}
                    ref={(el) => {
                      if (el) cardRefs.current[L.id] = el;
                    }}
                    className={`listing-card-anim persist ${highlightId === L.id ? "highlight" : ""}`}
                    style={{ animation: "none", opacity: 1 }}
                    onClick={() => {
                      setHighlightId(L.id);
                      setMapFocusId(L.id);
                    }}
                    onDoubleClick={() => setOverlayListing(L)}
                  >
                    <div className="card-inner">
                      <div className="card-front">
                        <div className="line1">{L.title?.slice(0, 48)}{L.title?.length > 48 ? "…" : ""}</div>
                        <div className="line2">{cardSubtitle(L)}</div>
                        <div className="line3">Click = map · Double-click = explain</div>
                        {areaMedian && L.price ? (
                          <div className="card-bar-wrap">
                            <div className="card-bar-label">
                              <span>Area median</span>
                              <span>This listing</span>
                            </div>
                            <div className="card-bar">
                              <div className="card-bar-median" style={{ width: `${(areaMedian / maxBar) * 100}%` }} />
                            </div>
                            <div className="card-bar" style={{ marginTop: 4 }}>
                              <div className="card-bar-listing" style={{ width: `${(L.price / maxBar) * 100}%` }} />
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!loading && chips.length > 0 && (
              <div className="chips">
                {chips.map((c) => (
                  <button key={c} type="button" className="chip" onClick={() => sendRaw(c)}>
                    {c}
                  </button>
                ))}
              </div>
            )}

            <div ref={endRef} />
          </div>

          <form className="composer" onSubmit={send}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
              placeholder="Try: 1br under 4000 SF · or paste Redfin URL"
            />
            <button type="submit" disabled={loading}>
              Send
            </button>
          </form>
        </div>

        <div className="map-wrap">
          <div className="map-box google-map-root" style={{ position: "relative" }}>
            <div className="map-osm-banner">Map · OpenStreetMap (free, no key)</div>
            <LeafletMapPane
              listings={listings}
              focusListingId={mapFocusId}
              onPinClick={(row) => {
                setHighlightId(row.id);
                setMapFocusId(row.id);
                cardRefs.current[row.id]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
              }}
            />
          </div>
        </div>
      </div>

      {overlayListing && (
        <div className="overlay-backdrop" onClick={() => setOverlayListing(null)}>
          <div className="overlay-panel" onClick={(e) => e.stopPropagation()}>
            <h3>Explain this listing</h3>
            <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 0 }}>{overlayListing.title}</p>
            <p style={{ fontSize: 12, color: "var(--text)" }}>{cardSubtitle(overlayListing)}</p>
            {explainAnnotations(overlayListing).map((a, i) => (
              <div key={i} className="annotation">
                <span className={`dot ${a.dot}`} />
                <span>{a.text}</span>
              </div>
            ))}
            <a href={overlayListing.url} target="_blank" rel="noreferrer" style={{ color: "var(--mint)" }}>
              Open listing
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
