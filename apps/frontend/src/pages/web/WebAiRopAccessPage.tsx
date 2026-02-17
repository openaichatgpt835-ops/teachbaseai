import { WebUsersPage } from "./WebUsersPage";

export function WebAiRopAccessPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">AI РОП — Доступ</h1>
        <p className="text-sm text-slate-500 mt-1">Настройте доступ к анализу сделок: Bitrix-сотрудники и Telegram-пользователи.</p>
      </div>
      <WebUsersPage />
    </div>
  );
}
