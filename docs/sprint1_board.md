# Sprint 1 Board

Период: 2026-03-10 .. 2026-03-21  
Цель: закрыть P0-риски и подготовить foundation для тарифов/финансов.

## In Progress

- `SEC-01` Инвентаризация периметра хоста (ports/firewall/ssh/docker publish)
- `SEC-03` Security report + remediation backlog
- `GIGA-01` Диагностика 401-паттернов (auth_key/scope/token)
- `GIGA-03` Формальная тех-диагностика в API (`/v1/admin/kb/credentials/health`)
- `ADM-02` Целевая IA + wireframe экрана "Ошибки API"

## To Do

- `SEC-02` Аудит хранения секретов (.env/app_settings/backups)
- `SEC-03` Security report + remediation backlog
- `RAG-01` Baseline из 20 контрольных запросов
- `RAG-02` Строгий режим: стабилизация качества ответов
- `RAG-03` Regression tests для critical RAG flow
- `TAR-03` Unit-экономика v1 (доходы/расходы/маржа)

## Done

- `PLAN-01` Утвержден Sprint 1 scope и DoD
- `ADM-01` IA/UX-аудит админки
- `TAR-01` Тарифная матрица v1
- `GIGA-02` Runbook ротации ключа + smoke checklist
- `TAR-02` DB/API контракт тарифов и account overrides
- `SEC-02` Аудит хранения секретов (.env/app_settings/backups)

## DoD (Sprint 1)

- Есть security-отчет по прод-хосту без ручных предположений.
- Ротация GigaChat ключа воспроизводима и проверяема через API диагностики.
- RAG strict mode не выдает частичных/обрезанных ответов в baseline.
- Подготовлены спецификации админ IA и тарифной системы для Sprint 2.
