export function formatRuntimeError(raw: unknown, fallback: string): string {
  const value = String(raw || "").trim();
  if (!value) return fallback;

  const normalized = value.toLowerCase();
  const byCode: Record<string, string> = {
    kb_ask_failed: "Не удалось получить ответ по базе знаний. Повторите запрос.",
    preview_missing: "Предпросмотр для этого файла пока недоступен.",
    invalid_credentials: "Неверный логин или пароль.",
    http_error: "Не удалось выполнить запрос. Проверьте соединение и повторите.",
    pdf_render_error: "Не удалось отрисовать PDF-предпросмотр.",
    media_minutes_limit_reached: "Лимит минут медиа на текущем тарифе исчерпан.",
    max_users_limit_reached: "Лимит пользователей на текущем тарифе исчерпан.",
    bitrix_portal_limit_reached: "На текущем тарифе нельзя подключить ещё один портал Bitrix24.",
    insufficient_role: "Недостаточно прав для этого действия.",
    portal_mismatch: "Текущий портал не связан с выбранным аккаунтом.",
  };

  return byCode[normalized] || value || fallback;
}
