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
import { RegistrationsPage } from "./pages/admin/RegistrationsPage";
import { ErrorsPage } from "./pages/admin/ErrorsPage";
import { B24AppPage } from "./pages/b24/B24AppPage";
import { RegisterPage } from "./pages/web/RegisterPage";
import { WebLoginPage } from "./pages/web/WebLoginPage";
import { WebLayout } from "./pages/web/WebLayout";
import { WebOverviewPage } from "./pages/web/WebOverviewPage";
import { WebStubPage } from "./pages/web/WebStubPage";
import { WebKbPage } from "./pages/web/WebKbPage";
import { WebSourcesPage } from "./pages/web/WebSourcesPage";
import { WebUsersPage } from "./pages/web/WebUsersPage";
import { WebSettingsPage } from "./pages/web/WebSettingsPage";
import { WebIntegrationsPage } from "./pages/web/WebIntegrationsPage";
import { WebFlowPage } from "./pages/web/WebFlowPage";
import { ConfirmEmailPage } from "./pages/web/ConfirmEmailPage";
import { WebAiRopPage } from "./pages/web/WebAiRopPage";
import { WebAiRopAccessPage } from "./pages/web/WebAiRopAccessPage";
import { WebChatPage } from "./pages/web/WebChatPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/register" replace />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<WebLoginPage />} />
      <Route path="/confirm" element={<ConfirmEmailPage />} />
      <Route path="/app" element={<WebLayout />}>
        <Route index element={<Navigate to="/app/overview" replace />} />
        <Route path="overview" element={<WebOverviewPage />} />
        <Route path="chat" element={<WebChatPage />} />
        <Route path="kb" element={<WebKbPage />} />
        <Route path="sources" element={<WebSourcesPage />} />
        <Route path="users" element={<WebUsersPage />} />
        <Route path="analytics" element={<WebStubPage title="Аналитика" />} />
        <Route path="settings" element={<WebSettingsPage />} />
        <Route path="settings/integrations" element={<WebIntegrationsPage />} />
        <Route path="ai-rop" element={<WebAiRopPage />} />
        <Route path="ai-rop/access" element={<WebAiRopAccessPage />} />
        <Route path="ai-rop/trainer" element={<WebStubPage title="AI Тренер" />} />
        <Route path="ai-rop/analyst" element={<WebStubPage title="AI Аналитик" />} />
        <Route path="flow" element={<WebFlowPage />} />
      </Route>
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
        <Route path="registrations" element={<RegistrationsPage />} />
        <Route path="errors" element={<ErrorsPage />} />
        <Route index element={<Navigate to="portals" replace />} />
      </Route>
      <Route path="/b24/app" element={<B24AppPage />} />
    </Routes>
  );
}
