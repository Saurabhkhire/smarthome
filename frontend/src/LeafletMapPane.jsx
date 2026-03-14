import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";

export default function LeafletMapPane({ listings, onPinClick, focusListingId }) {
  const mapDiv = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const onPin = useRef(onPinClick);
  onPin.current = onPinClick;

  const withCoords = useMemo(() => {
    return (listings || []).filter((row) => {
      const lat = Number(row.lat);
      const lng = Number(row.lng);
      return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
    });
  }, [listings]);

  useLayoutEffect(() => {
    const el = mapDiv.current;
    if (!el) return;
    if (mapRef.current) {
      try {
        mapRef.current.remove();
      } catch {
        /* ignore */
      }
      mapRef.current = null;
    }
    markersRef.current = [];
    delete el._leaflet_id;
    el.replaceChildren();
    if (withCoords.length === 0) return;

    const map = Leaflet.map(el, { zoomControl: true });
    Leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);

    withCoords.forEach((row) => {
      const icon = Leaflet.divIcon({
        className: "map-pulse-wrap",
        html: '<div class="map-pulse-dot"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      const m = Leaflet.marker([Number(row.lat), Number(row.lng)], { icon })
        .addTo(map)
        .on("click", () => onPin.current(row));
      markersRef.current.push({ id: row.id, marker: m, row });
    });

    if (withCoords.length === 1) {
      map.setView([Number(withCoords[0].lat), Number(withCoords[0].lng)], 14);
    } else {
      const b = Leaflet.latLngBounds(withCoords.map((r) => [Number(r.lat), Number(r.lng)]));
      if (b.isValid()) map.fitBounds(b, { padding: [48, 48], maxZoom: 14 });
    }
    map.invalidateSize();
    requestAnimationFrame(() => map.invalidateSize());
    mapRef.current = map;
    return () => {
      try {
        map.remove();
      } catch {
        /* ignore */
      }
      mapRef.current = null;
      markersRef.current = [];
      delete el._leaflet_id;
      el.replaceChildren();
    };
  }, [withCoords]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusListingId) return;
    const row = withCoords.find((r) => r.id === focusListingId);
    if (!row) return;
    map.setView([Number(row.lat), Number(row.lng)], 16, { animate: true });
  }, [focusListingId, withCoords]);

  return (
    <div className="map-box google-map-root">
      <div ref={mapDiv} style={{ width: "100%", height: "100%", minHeight: 280 }} />
      {withCoords.length === 0 && (
        <div className="map-fallback map-fallback--overlay map-fallback--hint">
          Click a listing to focus the map on that home
        </div>
      )}
    </div>
  );
}
