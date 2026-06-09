import { useState } from "react";
import { usingStubs } from "./api.js";
import Dashboard from "./views/Dashboard.jsx";
import Positions from "./views/Positions.jsx";
import AgentLog from "./views/AgentLog.jsx";
import Performance from "./views/Performance.jsx";
import Daily from "./views/Daily.jsx";
import Blotter from "./views/Blotter.jsx";

// Tab registry. frontend-beta drops the "Performance" entry from this list.
const TABS = [
  { id: "dashboard", label: "Dashboard", Component: Dashboard },
  { id: "positions", label: "Positions", Component: Positions },
  { id: "daily", label: "Daily", Component: Daily },
  { id: "agent-log", label: "Agent Log", Component: AgentLog },
  { id: "performance", label: "Performance", Component: Performance },
  { id: "blotter", label: "Blotter", Component: Blotter },
];

export default function App() {
  const [active, setActive] = useState(TABS[0].id);
  const Active = TABS.find((t) => t.id === active).Component;

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Portfolio Manager</h1>
        <span className="sub">Autonomous paper-trading demo</span>
      </header>

      {usingStubs && (
        <div className="stub-banner">
          Demo data — no backend connected. Set <code>VITE_API_BASE</code> to use the live API.
        </div>
      )}

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${t.id === active ? "active" : ""}`}
            onClick={() => setActive(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        <Active />
      </main>
    </div>
  );
}
