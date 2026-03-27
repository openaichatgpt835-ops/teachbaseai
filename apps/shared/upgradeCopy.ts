export type UpgradeCopy = {
  title: string;
  text: string;
  description?: string;
  bullets?: string[];
  previewTitle?: string;
};

export const UPGRADE_BADGE_LOCKED = "Недоступно на текущем тарифе";
export const UPGRADE_BADGE_HIGHER_PLAN = "Доступно на старших тарифах";
export const UPGRADE_CTA_PRIMARY = "Тарифы и оплата";
export const UPGRADE_CTA_SECONDARY = "Подробнее";
export const UPGRADE_DRAWER_TITLE = "Апгрейд тарифа";
export const UPGRADE_DRAWER_HINT =
  "Снять ограничение можно через апгрейд тарифа или персональный override для аккаунта.";
export const UPGRADE_DRAWER_CLOSE = "Закрыть";
export const UPGRADE_PLAN_LABEL = "Текущий тариф";

export const UPGRADE_COPY = {
  modelSelection: {
    title: "Ручной выбор моделей",
    text: "Выбор embedding- и chat-моделей доступен на старших тарифах. На текущем тарифе блок доступен только для просмотра.",
    description:
      "Ручной выбор моделей позволяет гибко менять баланс скорости, точности и стоимости ответа под задачи конкретного аккаунта.",
  },
  advancedTuning: {
    title: "Продвинутые параметры модели",
    text: "Тонкая настройка prompt, retrieval и параметров генерации доступна на старших тарифах.",
    description:
      "Продвинутые параметры нужны, когда команде важно управлять длиной ответа, релевантностью retrieval, системным промптом и качеством генерации.",
  },
  telegramClient: {
    title: "Клиентский Telegram-бот",
    text: "Внешний клиентский канал через Telegram доступен на старших тарифах.",
    description:
      "Клиентский Telegram-бот открывает внешний канал для клиентов: принимает сообщения и файлы, запускает сценарии и отвечает поверх базы знаний.",
  },
  amocrm: {
    title: "Интеграция AmoCRM",
    text: "Подключение AmoCRM, обмен статусами и передача лидов доступны на старших тарифах.",
    description:
      "Интеграция с AmoCRM нужна, когда надо связывать диалоги с CRM: передавать лиды, обновлять статусы и строить автоматические цепочки обработки.",
    bullets: [
      "Подключение аккаунта и канала AmoCRM",
      "Передача лидов и событий из сценариев",
      "Синхронизация статусов и маршрутов",
    ],
    previewTitle: "AmoCRM",
  },
  webhookNodes: {
    title: "Webhook-ноды",
    text: "Webhook-ноды и внешние вызовы доступны на старших тарифах.",
    description:
      "Webhook-ноды нужны, когда сценарий должен вызывать внешние сервисы, передавать данные наружу или запускать автоматические действия вне платформы.",
  },
} satisfies Record<string, UpgradeCopy>;
