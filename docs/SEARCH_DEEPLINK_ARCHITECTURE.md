# Поиск и Deep-Link к источникам: взрослая реализация

## 1) Текущий статус и ограничения

### Что уже есть
- Обычный поиск: `GET /v1/bitrix/portals/{portal_id}/kb/search`.
- Умный поиск: `POST /v1/bitrix/portals/{portal_id}/kb/ask`.
- Для источников в ответе чата возвращаются `file_id`, `chunk_index`, `page_num`, `start_ms`.
- Модалка предпросмотра открывается из чата и из базы знаний.

### Почему для `doc/docx/epub` не открывается "на нужной странице"
- Для `doc/docx/epub` сейчас нет стабильного "page anchor" в текущих viewers.
- `page_num` по факту надежно есть только для PDF.
- `epub` и `docx` требуют отдельные якоря:
  - EPUB: CFI (`epubcfi(...)`)
  - DOCX: offset/segment id в HTML-представлении.

## 2) Целевая модель deep-link

Добавляем единый якорь для каждого чанка:
- `anchor_kind`: `pdf_page | media_ms | epub_cfi | text_offset | chunk_index`
- `anchor_value`: строка/число (в JSON)

Правило:
- Любой источник в `search/ask/chunks` возвращает `anchor_kind` + `anchor_value`.
- Viewer открывает файл через адаптер по `anchor_kind`.

## 3) Backend изменения (поэтапно)

### Этап A. Контракт (без миграций)
- В ответы:
  - `/kb/search` → `matches[].anchor_kind`, `matches[].anchor_value`
  - `/kb/ask` → `sources[].anchor_kind`, `sources[].anchor_value`
  - `/kb/files/{id}/chunks` → `items[].anchor_kind`, `items[].anchor_value`
- Формирование anchor на лету:
  - если `page_num` → `pdf_page`
  - если `start_ms` → `media_ms`
  - иначе → `chunk_index`

### Этап B. Персистентные anchors (с миграцией)
- Добавить в `kb_chunks`:
  - `anchor_kind` (TEXT)
  - `anchor_value` (TEXT)
- Ingest выставляет anchors сразу при построении чанков.

### Этап C. EPUB/DOCX точные anchors
- EPUB:
  - индексировать через `epub.js`/серверный парсер с CFI.
  - чанк хранит `anchor_kind=epub_cfi`, `anchor_value=<cfi>`.
- DOCX:
  - конвертировать в HTML (deterministic), хранить `text_offset`/`segment_id`.
  - `anchor_kind=text_offset`.

## 4) Frontend изменения

### Этап A. Нормализация UX поиска
- Если строка обычного поиска пустая:
  - сбрасывать `results/matches/error`.
- Блок обычного поиска:
  - "Найденные фрагменты" (кликабельно, открытие модалки на anchor).
- При открытии "Умный поиск":
  - обычные matches сворачиваются в `details`.

### Этап B. Единый viewer adapter
- `PdfAdapter`: переход на страницу + подсветка chunk-текста.
- `MediaAdapter`: seek на `start_ms`.
- `EpubAdapter`: open CFI.
- `DocxTextAdapter`: scroll к `text_offset`.
- `FallbackAdapter`: открытие + подсветка/фокус на chunk в правой панели.

### Этап C. Из чата и из БЗ одинаковое поведение
- Один компонент модалки.
- Один входной контракт: `file_id + anchor_kind + anchor_value`.

## 5) Поиск по scope (что обсуждали)

Добавляем фильтры поиска:
- `scope.folder_ids[]`
- `scope.smart_folder_ids[]`
- `scope.topic_ids[]`
- `scope.file_ids[]`

Поддержка в API:
- `/kb/search?q=...&folder_id=...&topic_id=...`
- `/kb/ask` body:
  - `scope: { folder_ids?: number[], topic_ids?: string[], file_ids?: number[] }`

Поведение:
- Обычный и умный поиск используют один и тот же scope.
- В UI видно активный scope и можно быстро сбросить.

## 6) DoD

- `docx/epub/pdf/audio/video` открываются на релевантном anchor.
- Из клика по фрагменту поиска всегда открывается нужное место.
- Из клика по `[n]` в чате всегда открывается нужное место.
- Пустой поиск не переводит список в "файлов нет".
- Есть search scope по папкам/темам/файлам.

## 7) Порядок внедрения (минимальный риск)

1. Контракт anchors без миграции (быстрый выигрыш).
2. Единый viewer adapter с текущими anchors (`page_num/start_ms/chunk_index`).
3. Scope-поиск (folder/topic/file) для `search` и `ask`.
4. Миграция `kb_chunks.anchor_*`.
5. Точные anchors для `epub/docx`.
