import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getProperty, getPlaces } from "../api.js";

const TYPE_LABEL = {
  parking: "Parking",
  restaurant: "Restaurant",
  cafe: "Café",
  tourist_attraction: "Attraction",
  supermarket: "Supermarket",
};

function WifiCard({ wifi }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(wifi.password);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <div className="card wifi-card">
      <div className="card-icon">📶</div>
      <div className="wifi-info">
        <div className="wifi-name">{wifi.name}</div>
        <div className="wifi-password">{wifi.password}</div>
      </div>
      <button className="btn-copy" onClick={copy}>{copied ? "Copied!" : "Copy"}</button>
    </div>
  );
}

function PlaceCard({ place }) {
  return (
    <a href={place.mapsUrl} target="_blank" rel="noreferrer" className="card place-card">
      <div className="place-type">{TYPE_LABEL[place.type] ?? place.type}</div>
      <div className="place-name">{place.name}</div>
      {place.address && <div className="place-address">{place.address}</div>}
      {place.rating && <div className="place-rating">★ {place.rating}</div>}
    </a>
  );
}

function PickCard({ pick }) {
  return (
    <a href={pick.mapsUrl || undefined} target="_blank" rel="noreferrer" className={`card pick-card${pick.mapsUrl ? " linked" : ""}`}>
      <div className="pick-name">{pick.name}</div>
      {pick.note && <div className="pick-note">{pick.note}</div>}
    </a>
  );
}

export default function GuestPage() {
  const { id } = useParams();
  const [prop, setProp] = useState(null);
  const [places, setPlaces] = useState([]);
  const [tab, setTab] = useState("nearby");
  const [error, setError] = useState(null);

  useEffect(() => {
    getProperty(id)
      .then((p) => {
        setProp(p);
        if (p.branding?.accentColor) {
          document.documentElement.style.setProperty("--accent", p.branding.accentColor);
        }
      })
      .catch(() => setError("Property not found. Please check the link with your host."));

    getPlaces(id).then(setPlaces).catch(() => {});
  }, [id]);

  if (error) {
    return <div className="app"><main className="panel state error">{error}</main></div>;
  }
  if (!prop) {
    return <div className="app"><main className="panel state">Loading…</main></div>;
  }

  const picks = prop.ownerPicks ?? [];

  return (
    <div className="app guest-page">
      <header className="guest-header">
        {prop.branding?.logoUrl && <img src={prop.branding.logoUrl} alt="logo" className="property-logo" />}
        <h1>{prop.name}</h1>
      </header>

      {prop.wifi?.password && <WifiCard wifi={prop.wifi} />}

      <nav className="tabs">
        <button className={tab === "nearby" ? "tab active" : "tab"} onClick={() => setTab("nearby")}>Nearby</button>
        {picks.length > 0 && (
          <button className={tab === "picks" ? "tab active" : "tab"} onClick={() => setTab("picks")}>Owner's Picks</button>
        )}
        {prop.tips && (
          <button className={tab === "tips" ? "tab active" : "tab"} onClick={() => setTab("tips")}>Tips</button>
        )}
      </nav>

      <main className="tab-content">
        {tab === "nearby" && (
          <div className="cards-grid">
            {places.length === 0
              ? <p className="state">Loading nearby places…</p>
              : places.map((p, i) => <PlaceCard key={i} place={p} />)
            }
          </div>
        )}
        {tab === "picks" && (
          <div className="cards-grid">
            {picks.map((p, i) => <PickCard key={i} pick={p} />)}
          </div>
        )}
        {tab === "tips" && (
          <div className="tips-panel panel">
            <p>{prop.tips}</p>
          </div>
        )}
      </main>
    </div>
  );
}
