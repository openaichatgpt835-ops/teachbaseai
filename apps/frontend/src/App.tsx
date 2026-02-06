import { Routes, Route, Navigate } from "react-router-dom";
import { AdminLayout } from "./layouts/AdminLayout";
import { LoginPage } from "./pages/admin/LoginPage";
import { PortalsPage } from "./pages/admin/PortalsPage";
import { PortalDetailPage } from "./pages/admin/PortalDetailPage";
import { DialogsPage } from "./pages/admin/DialogsPage";
import { DialogDetailPage } from "./pages/admin/DialogDetailPage";
import { SystemPage } from "./pages/admin/SystemPage";
import { TracesPage } from "./pages/admin/TracesPage";
import { TraceDetailPage } from "./pages/admin/TraceDetailPage";
import { InboundEventsPage } from "./pages/admin/InboundEventsPage";
import { InboundEventDetailPage } from "./pages/admin/InboundEventDetailPage";
import { KnowledgeBasePage } from "./pages/admin/KnowledgeBasePage";
import { BotSettingsPage } from "./pages/admin/BotSettingsPage";
import { B24AppPage } from "./pages/b24/B24AppPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin/login" replace />} />
      <Route path="/admin/login" element={<LoginPage />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route path="portals" element={<PortalsPage />} />
        <Route path="portals/:id" element={<PortalDetailPage />} />
        <Route path="dialogs" element={<DialogsPage />} />
        <Route path="dialogs/:id" element={<DialogDetailPage />} />
        <Route path="system" element={<SystemPage />} />
        <Route path="traces" element={<TracesPage />} />
        <Route path="traces/:traceId" element={<TraceDetailPage />} />
        <Route path="inbound-events" element={<InboundEventsPage />} />
        <Route path="inbound-events/:id" element={<InboundEventDetailPage />} />
        <Route path="knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="bot-settings" element={<BotSettingsPage />} />
        <Route index element={<Navigate to="portals" replace />} />
      </Route>
      <Route path="/b24/app" element={<B24AppPage />} />
    </Routes>
  );
}
