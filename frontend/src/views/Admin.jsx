import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { getProperty, saveProperty, uploadLogo } from "../api.js";

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME ?? "YourBot";

function PicksEditor({ picks, onChange }) {
  function update(i, field, value) {
    const next = picks.map((p, idx) => (idx === i ? { ...p, [field]: value } : p));
    onChange(next);
  }
  function add() {
    onChange([...picks, { name: "", note: "", mapsUrl: "" }]);
  }
  function remove(i) {
    onChange(picks.filter((_, idx) => idx !== i));
  }

  return (
    <div className="picks-editor">
      {picks.map((p, i) => (
        <div key={i} className="pick-row">
          <input placeholder="Place name" value={p.name} onChange={(e) => update(i, "name", e.target.value)} />
          <input placeholder="Owner's note" value={p.note} onChange={(e) => update(i, "note", e.target.value)} />
          <input placeholder="Google Maps URL (optional)" value={p.mapsUrl} onChange={(e) => update(i, "mapsUrl", e.target.value)} />
          <button type="button" className="btn-remove" onClick={() => remove(i)}>✕</button>
        </div>
      ))}
      <button type="button" className="btn-add" onClick={add}>+ Add place</button>
    </div>
  );
}

export default function Admin() {
  const { id: routeId } = useParams(); // from /manage/:id

  const [form, setForm] = useState({
    id: routeId ?? "",
    adminToken: "",
    name: "",
    address: "",
    lat: "",
    lng: "",
    wifiName: "",
    wifiPassword: "",
    accentColor: "#2563eb",
    tips: "",
    ownerPicks: [],
  });
  const [logoFile, setLogoFile] = useState(null);
  const [saved, setSaved] = useState(null); // { id, adminToken }
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (routeId && form.adminToken) {
      getProperty(routeId).then((prop) => {
        setForm((f) => ({
          ...f,
          name: prop.name ?? "",
          address: prop.location?.address ?? "",
          lat: prop.location?.lat ?? "",
          lng: prop.location?.lng ?? "",
          wifiName: prop.wifi?.name ?? "",
          wifiPassword: prop.wifi?.password ?? "",
          accentColor: prop.branding?.accentColor ?? "#2563eb",
          tips: prop.tips ?? "",
          ownerPicks: prop.ownerPicks ?? [],
        }));
      }).catch(() => {});
    }
  }, [routeId]);

  function set(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setStatus("");
    try {
      const params = {
        id: form.id || undefined,
        adminToken: form.adminToken,
        name: form.name,
        address: form.address,
        lat: form.lat,
        lng: form.lng,
        wifiName: form.wifiName,
        wifiPassword: form.wifiPassword,
        accentColor: form.accentColor,
        tips: form.tips,
        ownerPicks: JSON.stringify(form.ownerPicks),
      };
      const result = await saveProperty(params);
      const propertyId = result.id;

      if (logoFile) {
        await uploadLogo(propertyId, form.adminToken, logoFile);
      }

      setSaved({ id: propertyId, adminToken: form.adminToken });
      setForm((f) => ({ ...f, id: propertyId }));
      setStatus("Saved!");
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  const guestLink = saved ? `${window.location.origin}/p/${saved.id}` : null;
  const telegramLink = saved ? `https://t.me/${BOT_USERNAME}?start=${saved.id}` : null;

  return (
    <div className="app admin-page">
      <header className="app-header">
        <h1>LocalGuide Admin</h1>
        <span className="sub">{form.id ? `Editing property ${form.id}` : "Create new property"}</span>
      </header>

      {saved && (
        <div className="links-panel">
          <h2>Share with guests</h2>
          <div className="link-row">
            <span className="link-label">Telegram</span>
            <a href={telegramLink} target="_blank" rel="noreferrer" className="link-value">{telegramLink}</a>
            <button onClick={() => navigator.clipboard.writeText(telegramLink)} className="btn-copy">Copy</button>
          </div>
          <div className="link-row">
            <span className="link-label">Web fallback</span>
            <a href={guestLink} target="_blank" rel="noreferrer" className="link-value">{guestLink}</a>
            <button onClick={() => navigator.clipboard.writeText(guestLink)} className="btn-copy">Copy</button>
          </div>
          <p className="token-note">
            Save your admin token — you need it to edit: <code>{saved.adminToken}</code>
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="admin-form panel">
        <section>
          <h2>Access</h2>
          {form.id && <div className="field"><label>Property ID</label><input readOnly value={form.id} /></div>}
          <div className="field">
            <label>Admin token <span className="hint">(keep this secret)</span></label>
            <input required value={form.adminToken} onChange={set("adminToken")} placeholder="Choose a password" />
          </div>
        </section>

        <section>
          <h2>Property</h2>
          <div className="field"><label>Name</label><input required value={form.name} onChange={set("name")} placeholder="The Cozy Corner B&B" /></div>
          <div className="field"><label>Address</label><input value={form.address} onChange={set("address")} placeholder="12 Rue de Rivoli, Paris" /></div>
          <div className="field-row">
            <div className="field"><label>Latitude</label><input value={form.lat} onChange={set("lat")} placeholder="48.8566" /></div>
            <div className="field"><label>Longitude</label><input value={form.lng} onChange={set("lng")} placeholder="2.3522" /></div>
          </div>
          <div className="field">
            <label>Logo</label>
            <input type="file" accept="image/*" onChange={(e) => setLogoFile(e.target.files[0])} />
          </div>
          <div className="field">
            <label>Accent colour</label>
            <input type="color" value={form.accentColor} onChange={set("accentColor")} />
          </div>
        </section>

        <section>
          <h2>WiFi</h2>
          <div className="field"><label>Network name</label><input value={form.wifiName} onChange={set("wifiName")} placeholder="MyHotel_Guest" /></div>
          <div className="field"><label>Password</label><input value={form.wifiPassword} onChange={set("wifiPassword")} placeholder="supersecret" /></div>
        </section>

        <section>
          <h2>Owner's picks</h2>
          <PicksEditor picks={form.ownerPicks} onChange={(picks) => setForm((f) => ({ ...f, ownerPicks: picks }))} />
        </section>

        <section>
          <h2>Tips &amp; local info</h2>
          <div className="field">
            <textarea value={form.tips} onChange={set("tips")} rows={5} placeholder="Check-in 3pm. Quiet hours after 10pm. Parking on Rue Mouffetard is free after 7pm." />
          </div>
        </section>

        <div className="form-footer">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Saving…" : form.id ? "Update property" : "Create property"}
          </button>
          {status && <span className={status.startsWith("Error") ? "status-error" : "status-ok"}>{status}</span>}
        </div>
      </form>
    </div>
  );
}
