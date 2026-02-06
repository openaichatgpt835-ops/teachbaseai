# Bitrix24 Docs Index для Teachbase AI

Этот файл — "каноническая полка" ссылок на документацию Bitrix24. Используем её как источник истины при разработке, тестировании и расследовании инцидентов. Только Bitrix24 Cloud REST/Marketplace.

## 1) Доступ к REST API, OAuth, scopes
- Access to REST API (first steps): https://github.com/bitrix24/b24restdocs/blob/main/first-steps/access-to-rest-api.md
- Scopes / Permissions (официальная таблица): https://apidocs.bitrix24.com/api-reference/scopes/permissions.html

Обязательные scopes для текущего MVP: `imbot`, `im`, `placement`, `user`.

## 2) Чат-боты и сообщения
- Chat-bots index: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/chat-bots/index.md
- imbot.register: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/chat-bots/imbot-register.md
- imbot.chat.add: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/chat-bots/chats/imbot-chat-add.md (создание чата от имени бота, USERS, MESSAGE, CHAT_ID в ответе)
- imbot.message.add: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/chat-bots/messages/imbot-message-add.md (DIALOG_ID = user_id или chat{CHAT_ID})
- imbot.command.register: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/chat-bots/commands/imbot-command-register.md

## 3) События, обработчики, безопасность
- Safe event handlers: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/events/safe-event-handlers.md
- onAppUninstall: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/common/events/on-app-uninstall.md
- ONAPPINSTALL (если используем): https://github.com/bitrix24/b24restdocs/blob/main/api-reference/chat-bots/events/on-app-install.md

## 4) Пользователи и allowlist (выбор сотрудников)
- user.search: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/user/user-search.md
- user.get (если используем): https://github.com/bitrix24/b24restdocs/blob/main/api-reference/user/user-get.md

В Teachbase AI: allowlist настраивает админ портала в iframe UI приложения. Если allowlist непустой — отвечаем только разрешённым, иначе пишем событие `blocked_by_acl`.

## 5) Placement (встраивание UI)
- placement.bind: https://github.com/bitrix24/b24restdocs/blob/main/api-reference/widgets/placement-bind.md

## 6) Правило использования
При любых изменениях интеграции Bitrix24 сначала сверяйся с этим файлом, а затем уже с кодом. Если требования доки противоречат текущей реализации — фиксируем реализацию или документируем отклонение.
