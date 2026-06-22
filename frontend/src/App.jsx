import { Routes, Route, Navigate } from "react-router-dom";
import Admin from "./views/Admin.jsx";
import GuestPage from "./views/GuestPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/p/:id" element={<GuestPage />} />
      <Route path="/admin/:id" element={<Admin />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}
