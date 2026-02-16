<template>
  <div class="tb-shell" :class="{ 'tb-shell-modal': showAuthModal }">
    <aside class="tb-sidebar">
      <div class="tb-logo">Teachbase AI</div>
      <nav class="tb-nav">
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'overview' }" @click="selectTab('overview')">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M4 10.5l8-6 8 6V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1v-9.5Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          Обзор
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'kb' }" @click="selectTab('kb')">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 4h10a4 4 0 0 1 4 4v12H9a4 4 0 0 0-4 4V4Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 8h6M9 12h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          База знаний
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'sources' }" @click="selectTab('sources')">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Источники данных
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'users' }" @click="selectTab('users')">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z" stroke="currentColor" stroke-width="1.6"/><path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Пользователи и доступы
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'analytics' }" @click="selectTab('analytics')">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 12v6M12 8v10M19 4v14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Аналитика
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'settings' }" @click="selectTab('settings')">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" stroke="currentColor" stroke-width="1.6"/><path d="M4 12h2m12 0h2M12 4v2m0 12v2M6 6l1.5 1.5M16.5 16.5 18 18M18 6l-1.5 1.5M7.5 16.5 6 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Настройки
        </button>
        <button class="tb-nav-sub" :class="{ 'is-active': currentTab === 'integrations' }" @click="selectTab('integrations')">
          Интеграции
        </button>
        <button
          v-if="isWebMode"
          class="tb-nav-item"
          :class="{ 'is-active': currentTab === 'flow' }"
          @click="selectTab('flow')"
        >
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 7h6M5 17h6M13 7h6M13 17h6M9 7v10M15 7v10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Конструктор бота
        </button>
      </nav>
    </aside>

    <main class="tb-content">
      <header class="tb-top">
        <div>
          <h1 class="tb-h1">{{ tabTitle }}</h1>
          <p class="tb-sub">Управление доступом и базой знаний портала.</p>
        </div>
        <div class="tb-top-actions">
          <div class="tb-plan" v-if="webLinked && demoUntil && !isWebMode">{{ demoUntilLabel }}</div>
          <div class="tb-plan" v-if="isWebMode && demoUntil">{{ demoLeftLabel }}</div>
          <button v-if="webLinked" class="tb-btn" @click="openWebCabinet">Перейти в кабинет</button>
          <button v-if="isWebMode" class="tb-btn tb-btn-ghost" @click="openNewWebUi">Новый дизайн</button>
          <div v-if="isWebMode" class="tb-user-pill">
            <span class="tb-user-dot"></span>
            {{ webUserLabel }}
          </div>
          <button v-if="isWebMode" class="tb-btn tb-btn-ghost" @click="logoutWeb">Выйти</button>
          <div class="tb-status" v-if="!sessionReady">{{ statusMessage }}</div>
        </div>
      </header>
      <div v-if="isWebMode && pendingLinkRequests.length" class="tb-banner">
        <div>
          <div class="tb-banner-title">Запрос на привязку Bitrix24</div>
          <div class="tb-muted">Портал: {{ pendingLinkRequests[0].portal_domain }}</div>
        </div>
        <div class="tb-banner-actions">
          <button class="tb-btn" @click="openLinkModal(pendingLinkRequests[0])">Подтвердить</button>
          <button class="tb-btn tb-btn-ghost" @click="rejectLink(pendingLinkRequests[0])">Отклонить</button>
        </div>
      </div>

      <section v-if="currentTab === 'overview'" class="tb-grid" key="overview">
        <div class="tb-card">
          <h2 class="tb-card-title">База знаний</h2>
          <div class="tb-card-metrics">
            <div>
              <span>Файлов</span>
              <strong>{{ kbFiles.length }}</strong>
            </div>
            <div>
              <span>URL‑источников</span>
              <strong>{{ kbSources.length }}</strong>
            </div>
            <div>
              <span>Последнее обновление</span>
              <strong>{{ lastUpdated }}</strong>
            </div>
            <div>
              <span>Статус</span>
              <strong>{{ kbCounts.error > 0 ? 'Есть ошибки' : 'Актуальна' }}</strong>
            </div>
          </div>
        </div>

        <div class="tb-card">
          <h2 class="tb-card-title">Использование</h2>
          <div class="tb-card-metrics">
            <div>
              <span>Активные сегодня</span>
              <strong>{{ activeUsers }}</strong>
            </div>
            <div>
              <span>Всего сотрудников</span>
              <strong>{{ users.length }}</strong>
            </div>
            <div>
              <span>Доступ разрешён</span>
              <strong>{{ selectedUsers.length }}</strong>
            </div>
            <div>
              <span>Ошибки индексации</span>
              <strong>{{ kbCounts.error }}</strong>
            </div>
          </div>
        </div>

        <div class="tb-card">
          <h2 class="tb-card-title">Фокус запросов</h2>
          <div class="tb-list" v-if="topicSummaries.length">
            <div v-for="(s, idx) in topicSummaries" :key="idx" class="tb-row">
              <div class="tb-row-body">
                <div class="tb-row-text">{{ s.topic }}</div>
                <div class="tb-muted" v-if="s.score">оценка: {{ s.score }}</div>
              </div>
            </div>
          </div>
          <div class="tb-empty" v-else>Недостаточно данных.</div>
        </div>
      </section>

      <section v-if="currentTab === 'users'" class="tb-grid" key="users">
        <div class="tb-card">
          <h2 class="tb-card-title">Доступ (Bitrix)</h2>
          <div v-if="accessWarning" class="tb-alert">{{ accessWarning }}</div>
          <input v-model="userSearch" class="tb-input" type="search" placeholder="Поиск по имени..." />
          <div class="tb-userlist" v-if="filteredUsers.length">
            <div v-for="u in filteredUsers" :key="u.id" class="tb-user-row">
              <label class="tb-user">
                <input type="checkbox" :value="u.id" v-model="selectedUsers" />
                <span class="tb-user-name">{{ u.name }}</span>
              </label>
              <input
                v-model="bitrixTelegramMap[u.id]"
                class="tb-input tb-input-sm"
                placeholder="@telegram"
              />
            </div>
          </div>
          <div class="tb-empty" v-else>Сотрудников пока нет.</div>
          <div class="tb-actions">
            <button class="tb-btn tb-btn-primary" @click="saveAccess" :disabled="accessSaving">
              {{ accessSaving ? 'Сохраняю...' : 'Сохранить доступ' }}
            </button>
            <span class="tb-muted">Выбрано: {{ selectedUsers.length }}</span>
            <span class="tb-muted" v-if="accessSaveStatus">{{ accessSaveStatus }}</span>
          </div>
        </div>

        <div class="tb-card">
          <h2 class="tb-card-title">Доп. пользователи (Telegram)</h2>
          <div class="tb-field">
            <label>Имя</label>
            <input v-model="newWebUserName" class="tb-input" placeholder="Например: Иван Петров" />
          </div>
          <div class="tb-field">
            <label>Telegram username</label>
            <input v-model="newWebUserTelegram" class="tb-input" placeholder="@username" />
          </div>
          <div class="tb-actions">
            <button class="tb-btn tb-btn-primary" @click="addWebUser">Добавить</button>
            <span class="tb-muted" v-if="webUserMessage">{{ webUserMessage }}</span>
          </div>
          <div class="tb-userlist" v-if="webUsers.length">
            <div v-for="u in webUsers" :key="u.id" class="tb-user-row">
              <div>
                <div class="tb-user-name">{{ u.name }}</div>
                <div class="tb-muted" v-if="u.telegram_username">@{{ u.telegram_username }}</div>
              </div>
              <button class="tb-mini tb-mini-danger" @click="removeWebUser(u.id)">Удалить</button>
            </div>
          </div>
          <div class="tb-empty" v-else>Пока нет дополнительных пользователей.</div>
        </div>
      </section>

      <section v-if="currentTab === 'kb' && isPortalAdmin" class="tb-kb-shell" key="kb">
        <aside class="tb-kb-sidebar">
          <div class="tb-kb-side-title">Структура</div>
          <input ref="fileInput" type="file" multiple class="tb-file-hidden" @change="onFilePickerChange" />
          <div
            class="tb-dropzone tb-dropzone-mini"
            @click="openFilePicker"
            @dragover="onDragOverFiles"
            @drop="onDropFiles"
          >
            <div class="tb-dropzone-icon">+</div>
            <div class="tb-dropzone-title">Добавить файлы</div>
            <div class="tb-dropzone-sub">Перетащите сюда или нажмите</div>
          </div>
          <div
            class="tb-kb-side-item"
            :class="{ 'is-active': kbFilter.kind === 'all', 'is-drop': dragOverCollectionId === 0 }"
            @click="selectKbFilter('all')"
            @dragenter.prevent="onDragEnterCollection(0)"
            @dragleave.prevent="onDragLeaveCollection(0)"
            @dragover.prevent
            @drop="onDropToCollection(0, $event)"
          >
            Все файлы
          </div>
          <div class="tb-kb-side-group">
            <div class="tb-kb-side-group-title">Папки</div>
            <div
              v-for="c in kbCollections"
              :key="c.id"
              class="tb-kb-side-item"
              :class="{
                'is-active': kbFilter.kind === 'collection' && kbFilter.id === c.id,
                'is-drop': dragOverCollectionId === c.id,
              }"
              @click="selectKbFilter('collection', c.id)"
              @dragenter.prevent="onDragEnterCollection(c.id)"
              @dragleave.prevent="onDragLeaveCollection(c.id)"
              @dragover.prevent
              @drop="onDropToCollection(c.id, $event)"
            >
              <span class="tb-kb-side-dot" v-if="c.color" :style="{ backgroundColor: c.color }"></span>
              <span class="tb-kb-side-name">{{ c.name }}</span>
              <span class="tb-kb-side-count">{{ c.file_count || (kbCollectionFiles[c.id]?.length || 0) }}</span>
            </div>
            <div class="tb-kb-side-new">
              <input v-model="newCollectionName" class="tb-input" placeholder="Новая папка" />
              <input v-model="newCollectionColor" class="tb-input tb-input-sm" placeholder="#3A7BFA" />
              <button class="tb-btn" @click="createCollection">Создать</button>
              <div class="tb-muted">Подпапки пока не поддерживаются.</div>
            </div>
          </div>
          <div class="tb-kb-side-group">
            <div class="tb-kb-side-group-title">
              Умные папки
              <button class="tb-link" @click="smartFoldersOpen = !smartFoldersOpen">{{ smartFoldersOpen ? 'Свернуть' : 'Показать' }}</button>
            </div>
            <div v-show="smartFoldersOpen">
              <button
                v-for="s in kbSmartFolders"
                :key="s.id"
                class="tb-kb-side-item"
                :class="{ 'is-active': kbFilter.kind === 'smart' && kbFilter.id === s.id }"
                @click="selectKbFilter('smart', s.id)"
              >
                {{ s.name }}
              </button>
              <div v-if="kbTopicSuggestions.length" class="tb-kb-side-suggest">
                <div class="tb-muted">Рекомендации</div>
                <button
                  v-for="s in kbTopicSuggestions"
                  :key="s.id"
                  class="tb-kb-side-suggest-btn"
                  @click="createSmartFolderFromTopic(s.id, s.name)"
                >
                  + «{{ s.name }}»
                </button>
              </div>
            </div>
          </div>
        </aside>

        <div class="tb-kb-main" @click="closeFileMenu">
          <div class="tb-kb-header">
            <h2>Добро пожаловать в базу знаний</h2>
            <p>Управляйте документами и доступами в едином пространстве.</p>
          </div>
          <div class="tb-kb-search">
            <div class="tb-kb-search-input">
              <input v-model="kbSearch" class="tb-input" placeholder="Поиск по базе знаний" @input="scheduleSearch" />
            </div>
            <button class="tb-btn tb-btn-ghost" @click="toggleSmartSearch">Умный поиск</button>
          </div>
          <div class="tb-search-status" v-if="kbSearchLoading">Ищем…</div>
          <div class="tb-search-status tb-alert" v-if="kbSearchError">{{ kbSearchError }}</div>
          <div class="tb-search-status" v-if="kbSearchResults !== null && !kbSearchLoading && !kbSearchError">
            Найдено: {{ kbSearchResults.length }}
          </div>
          <div class="tb-search-preview" v-if="kbSearchMatches.length">
            <div class="tb-search-preview-item" v-for="m in kbSearchMatches.slice(0, 5)" :key="m.file_id">
              <div class="tb-search-preview-name">{{ m.filename }}</div>
              <div class="tb-muted" v-if="m.snippet">{{ m.snippet }}</div>
            </div>
          </div>

          <div class="tb-smart-search" v-if="smartSearchOpen">
            <div class="tb-field">
              <label>Умный запрос</label>
              <input v-model="smartSearchQuery" class="tb-input" placeholder="Например: какие есть тарифы?" />
            </div>
            <div class="tb-actions">
              <button class="tb-btn tb-btn-primary" @click="runSmartSearch" :disabled="smartSearchLoading">
                {{ smartSearchLoading ? 'Ищу...' : 'Спросить' }}
              </button>
              <span class="tb-muted" v-if="smartSearchError">{{ smartSearchError }}</span>
            </div>
            <div class="tb-smart-answer" v-if="smartSearchAnswer">{{ smartSearchAnswer }}</div>
          </div>
          <div class="tb-kb-filters">
            <select v-model="kbTypeFilter" class="tb-input">
              <option value="all">Тип: все</option>
              <option v-for="t in kbTypeOptions" :key="t" :value="t">{{ t }}</option>
            </select>
            <select v-model="kbPeopleFilter" class="tb-input">
              <option value="all">Люди: все</option>
              <option v-for="p in kbPeopleOptions" :key="p" :value="p">{{ p }}</option>
            </select>
            <select v-model="kbLocationFilter" class="tb-input">
              <option value="all">Местоположение: все</option>
              <option v-for="c in kbCollections" :key="c.id" :value="String(c.id)">{{ c.name }}</option>
            </select>
            <select v-model="kbSort" class="tb-input">
              <option value="new">Сначала новые</option>
              <option value="name">По имени</option>
              <option value="status">По статусу</option>
            </select>
            <div class="tb-view-toggle">
              <button class="tb-view-btn" :class="{ 'is-active': kbViewMode === 'table' }" @click="kbViewMode = 'table'">Таблица</button>
              <button class="tb-view-btn" :class="{ 'is-active': kbViewMode === 'grid' }" @click="kbViewMode = 'grid'">Плитки</button>
            </div>
          </div>

          <details class="tb-accordion tb-kb-accordion" :open="smartFoldersOpen" @toggle="smartFoldersOpen = ($event.target as HTMLDetailsElement).open">
            <summary class="tb-accordion-summary">Умные папки</summary>
            <div class="tb-chip-row">
              <button
                v-for="s in kbSmartFolders"
                :key="s.id"
                class="tb-chip tb-chip-ghost"
                :class="{ 'is-active': kbFilter.kind === 'smart' && kbFilter.id === s.id }"
                @click="selectKbFilter('smart', s.id)"
              >
                {{ s.name }}
              </button>
              <span v-if="kbSmartFolders.length === 0" class="tb-muted">Умных папок пока нет.</span>
            </div>
            <div v-if="kbTopicSuggestions.length" class="tb-suggestions">
              <div class="tb-muted">Предложения по темам (≥ {{ smartThreshold }} файлов):</div>
              <div class="tb-chip-row">
                <button
                  v-for="s in kbTopicSuggestions"
                  :key="s.id"
                  class="tb-chip tb-chip-outline"
                  @click="createSmartFolderFromTopic(s.id, s.name)"
                >
                  Создать «{{ s.name }}»
                </button>
              </div>
            </div>
          </details>

          <div class="tb-kb-section">
            <div class="tb-kb-section-title">Рекомендуемые папки</div>
            <div class="tb-kb-folder-row">
              <div
                v-for="c in kbCollections.slice(0, 6)"
                :key="c.id"
                class="tb-kb-folder-card"
                :class="{ 'is-drop': dragOverCollectionId === c.id }"
                @click="selectKbFilter('collection', c.id)"
                @dragenter.prevent="onDragEnterCollection(c.id)"
                @dragleave.prevent="onDragLeaveCollection(c.id)"
                @dragover.prevent
                @drop="onDropToCollection(c.id, $event)"
              >
                <div class="tb-kb-folder-icon" :style="{ backgroundColor: c.color || '#dbeafe' }">📁</div>
                <div>
                  <div class="tb-kb-folder-name">{{ c.name }}</div>
                  <div class="tb-muted">{{ c.file_count || (kbCollectionFiles[c.id]?.length || 0) }} файлов</div>
                </div>
              </div>
              <div v-if="kbCollections.length === 0" class="tb-empty">Папок пока нет.</div>
            </div>
          </div>

          <div class="tb-kb-section">
            <div class="tb-kb-section-title">Рекомендуемые файлы</div>
            <div class="tb-kb-table">
              <div class="tb-kb-table-head">
                <span>Название</span>
                <span>Причина</span>
                <span>Владелец</span>
                <span>Папка</span>
              </div>
              <div class="tb-kb-table-row" v-for="f in recommendedKbFiles" :key="f.id">
                <span class="tb-kb-file-name">
                  <span class="tb-file-icon" :style="{ backgroundColor: fileTypeIcon(f.filename).color }">{{ fileTypeIcon(f.filename).label }}</span>
                  {{ f.filename }}
                </span>
                <span>{{ (f.query_count || 0) > 0 ? `${f.query_count} запросов` : 'Новый файл' }}</span>
                <span>{{ fileOwnerLabel(f) }}</span>
                <span>{{ fileCollections(f.id)[0]?.name || 'Корень' }}</span>
              </div>
              <div v-if="recommendedKbFiles.length === 0" class="tb-empty">Рекомендаций пока нет.</div>
            </div>
          </div>

          <div class="tb-kb-section">
            <div class="tb-kb-section-head">
              <div class="tb-kb-section-title">Файлы</div>
              <button class="tb-btn" @click="reindex">Переиндексировать</button>
            </div>
            <div v-if="selectedFileIds.length" class="tb-selection-bar">
              <div>Выбрано: {{ selectedFileIds.length }}</div>
              <div class="tb-selection-actions">
                <select class="tb-input" @change="bulkMoveToCollection($event)">
                  <option value="">Переместить в папку</option>
                  <option v-for="c in kbCollections" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <button class="tb-btn" @click="bulkReindexFiles">Переиндексировать</button>
                <button class="tb-btn tb-btn-danger" @click="bulkDeleteFiles">Удалить</button>
                <button class="tb-btn tb-btn-ghost" @click="selectedFileIds = []">Снять выделение</button>
              </div>
            </div>
            <div v-if="kbViewMode === 'table' && sortedKbFiles.length" class="tb-kb-table">
              <div class="tb-kb-table-head">
                <span>
                  <label class="tb-file-check">
                    <input type="checkbox" :checked="allVisibleSelected" @change="toggleSelectAllVisible" />
                    Название
                  </label>
                </span>
                <span>Владелец</span>
                <span>Папка</span>
                <span>Статус</span>
              </div>
              <div v-for="f in sortedKbFiles" :key="f.id" class="tb-kb-table-row" draggable="true" @dragstart="onDragStartFile(f.id, $event)" @dragend="onDragEndFile">
                <span class="tb-kb-file-name">
                  <label class="tb-file-check">
                    <input type="checkbox" v-model="selectedFileIds" :value="f.id" />
                    <span class="tb-file-icon" :style="{ backgroundColor: fileTypeIcon(f.filename).color }">{{ fileTypeIcon(f.filename).label }}</span>
                    {{ f.filename }}
                  </label>
                </span>
                <span>{{ fileOwnerLabel(f) }}</span>
                <span>{{ fileCollections(f.id)[0]?.name || 'Корень' }}</span>
                <span class="tb-status-pill" :class="`is-${(f.status || '').toLowerCase()}`" :title="f.status">{{ fileStatusLabel(f.status) }}</span>
                <button class="tb-kb-menu" :class="{ 'is-open': openFileMenuId === f.id }" @click.stop="toggleFileMenu(f.id)">⋮</button>
                <div v-if="openFileMenuId === f.id" class="tb-kb-menu-pop" @click.stop>
                  <button @click="reindexFile(f.id)">Переиндексировать</button>
                  <button @click="deleteFile(f.id)">Удалить</button>
                </div>
              </div>
            </div>
            <div v-if="kbViewMode === 'grid' && sortedKbFiles.length" class="tb-file-grid">
              <div v-for="f in sortedKbFiles" :key="f.id" class="tb-file-card" draggable="true" @dragstart="onDragStartFile(f.id, $event)" @dragend="onDragEndFile">
                <div class="tb-file-card-header">
                  <span class="tb-file-icon" :style="{ backgroundColor: fileTypeIcon(f.filename).color }">{{ fileTypeIcon(f.filename).label }}</span>
                  <button class="tb-kb-menu" :class="{ 'is-open': openFileMenuId === f.id }" @click.stop="toggleFileMenu(f.id)">⋮</button>
                </div>
                <div class="tb-file-card-name">{{ f.filename }}</div>
                <div class="tb-file-card-meta">{{ fileOwnerLabel(f) }}</div>
                <div class="tb-status-pill" :class="`is-${(f.status || '').toLowerCase()}`" :title="f.status">{{ fileStatusLabel(f.status) }}</div>
                <div v-if="openFileMenuId === f.id" class="tb-kb-menu-pop" @click.stop>
                  <button @click="reindexFile(f.id)">Переиндексировать</button>
                  <button @click="deleteFile(f.id)">Удалить</button>
                </div>
              </div>
            </div>
            <div class="tb-empty" v-else>Файлов пока нет.</div>
          </div>
        </div>
      </section>

      <section v-if="currentTab === 'sources' && isPortalAdmin" class="tb-grid" key="sources">
        <div class="tb-card">
          <h2 class="tb-card-title">URL‑источники</h2>
          <div class="tb-field">
            <label>Ссылка (YouTube/VK/Rutube)</label>
            <input v-model="kbUrl" type="url" class="tb-input" placeholder="https://..." />
          </div>
          <div class="tb-actions">
            <button class="tb-btn" @click="addUrl">Добавить URL</button>
            <span class="tb-muted" v-if="kbUrlMessage">{{ kbUrlMessage }}</span>
          </div>
        </div>

        <div class="tb-card">
          <h2 class="tb-card-title">Источники</h2>
          <div class="tb-empty" v-if="kbSources.length === 0">Источников пока нет.</div>
          <div class="tb-list" v-else>
            <div v-for="s in kbSources" :key="s.id" class="tb-row">
              <div class="tb-row-body">
                <div class="tb-row-text">{{ s.url }}</div>
                <div class="tb-muted">{{ s.status }} · {{ s.created_at }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="currentTab === 'analytics'" class="tb-grid" key="analytics">
        <div class="tb-card">
          <h2 class="tb-card-title">Аналитика</h2>
          <div class="tb-empty">Скоро появится.</div>
        </div>
      </section>

      <section v-if="currentTab === 'settings'" class="tb-grid" key="settings">
        <div class="tb-card">
          <h2 class="tb-card-title">Настройки</h2>
          <div v-if="!isPortalAdmin" class="tb-empty">Доступно только администратору портала.</div>
          <div v-else>
            <div class="tb-settings-block">
              <div class="tb-settings-title">База знаний</div>
              <div class="tb-field">
                <label class="tb-label">
                  <span>Embedding‑модель</span>
                  <span class="tb-help">
                    <span class="tb-help-icon">?</span>
                    <span class="tb-help-balloon">Модель для поиска по базе знаний. Обычно не требуется менять.</span>
                  </span>
                </label>
                <select v-model="kbSettings.embedding_model">
                  <option value="">—</option>
                  <option v-for="m in embedModels" :key="m" :value="m">{{ m }}</option>
                </select>
              </div>
              <div class="tb-field">
                <label class="tb-label">
                  <span>Chat‑модель</span>
                  <span class="tb-help">
                    <span class="tb-help-icon">?</span>
                    <span class="tb-help-balloon">Основная модель, которая формирует ответ по найденным фрагментам.</span>
                  </span>
                </label>
                <select v-model="kbSettings.chat_model">
                  <option value="">—</option>
                  <option v-for="m in chatModels" :key="m" :value="m">{{ m }}</option>
                </select>
              </div>
              <div class="tb-field">
                <label class="tb-label">
                  <span>Пресет ответа</span>
                  <span class="tb-help">
                    <span class="tb-help-icon">?</span>
                    <span class="tb-help-balloon">Выберите стиль ответа: краткий обзор, FAQ или таймлайн.</span>
                  </span>
                </label>
                <select v-model="kbSettings.prompt_preset">
                  <option value="auto">Авто</option>
                  <option value="summary">Краткий обзор</option>
                  <option value="faq">FAQ</option>
                  <option value="timeline">Таймлайн</option>
                </select>
              </div>
              <div class="tb-settings-grid">
                <div class="tb-field">
                  <label class="tb-inline">
                    <input type="checkbox" v-model="kbSettings.collections_multi_assign" />
                    Разрешить файл в нескольких папках
                  </label>
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Порог для умных папок</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Когда файлов по теме ≥ порога, предложим создать умную папку.</span>
                    </span>
                  </label>
                  <input v-model.number="kbSettings.smart_folder_threshold" type="number" min="1" class="tb-input" />
                </div>
              </div>
            </div>

            <div class="tb-settings-block">
              <div class="tb-settings-title">Ответы бота</div>
              <div class="tb-field">
                <label class="tb-label">
                  <span>Препромпт</span>
                  <span class="tb-help">
                    <span class="tb-help-icon">?</span>
                    <span class="tb-help-balloon">Инструкция, которая добавляется в системное сообщение перед каждым ответом.</span>
                  </span>
                </label>
                <textarea v-model="kbSettings.system_prompt_extra" class="tb-input" rows="3" placeholder="Например: отвечай кратко и по делу."></textarea>
              </div>
              <div class="tb-field">
                <label class="tb-inline">
                  <input type="checkbox" v-model="kbSettings.show_sources" />
                  Показывать источники в ответе
                </label>
              </div>
              <div class="tb-field">
                <label class="tb-label">
                  <span>Формат источников</span>
                  <span class="tb-help">
                    <span class="tb-help-icon">?</span>
                    <span class="tb-help-balloon">Короткий список — только названия файлов. Подробный — с фрагментами.</span>
                  </span>
                </label>
                <select v-model="kbSettings.sources_format">
                  <option value="detailed">Подробный (цитаты)</option>
                  <option value="short">Короткий список</option>
                  <option value="none">Не показывать</option>
                </select>
              </div>
              <div class="tb-field">
                <label class="tb-inline">
                  <input type="checkbox" v-model="kbSettings.use_history" />
                  Учитывать контекст диалога
                </label>
              </div>
              <div class="tb-settings-grid">
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Глубина контекста (сообщений)</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Сколько последних сообщений учитывать при ответе.</span>
                    </span>
                  </label>
                  <input v-model.number="kbSettings.context_messages" type="number" min="0" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Ограничение контекста (символы)</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Максимальный объём контекста, который отправляется в модель.</span>
                    </span>
                  </label>
                  <input v-model.number="kbSettings.context_chars" type="number" min="0" class="tb-input" />
                </div>
              </div>
              <div class="tb-field">
                <label class="tb-inline">
                  <input type="checkbox" v-model="kbSettings.strict_mode" />
                  Строгий режим (только по базе знаний)
                </label>
              </div>
              <div class="tb-field">
                <label class="tb-inline">
                  <input type="checkbox" v-model="kbSettings.allow_general" />
                  Разрешить общий ответ, если база знаний пуста
                </label>
              </div>
              <div class="tb-field">
                <label class="tb-inline">
                  <input type="checkbox" v-model="kbSettings.use_cache" />
                  Использовать кэш релевантности
                </label>
              </div>
              <div class="tb-info">
                Бот отвечает только по вашей базе знаний (файлы и URL‑источники).
              </div>
            </div>

            <details class="tb-accordion">
              <summary class="tb-accordion-summary">Продвинутые параметры</summary>
              <div class="tb-settings-grid">
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Температура</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Чем выше, тем более креативные ответы. Обычно 0.2–0.5.</span>
                    </span>
                  </label>
                  <input v-model="kbSettings.temperature" type="number" step="0.05" min="0" max="1.5" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Макс. токенов</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Ограничение длины ответа.</span>
                    </span>
                  </label>
                  <input v-model="kbSettings.max_tokens" type="number" min="0" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Top‑P</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Альтернатива температуре для управления случайностью.</span>
                    </span>
                  </label>
                  <input v-model="kbSettings.top_p" type="number" step="0.05" min="0" max="1" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Presence penalty</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Снижает повторяемость тем в ответах.</span>
                    </span>
                  </label>
                  <input v-model="kbSettings.presence_penalty" type="number" step="0.1" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Frequency penalty</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Снижает повторяемость слов и фраз.</span>
                    </span>
                  </label>
                  <input v-model="kbSettings.frequency_penalty" type="number" step="0.1" class="tb-input" />
                </div>
              </div>
              <div class="tb-settings-grid">
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Top‑K фрагментов</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Сколько фрагментов базы знаний передавать в модель.</span>
                    </span>
                  </label>
                  <input v-model.number="kbSettings.retrieval_top_k" type="number" min="1" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Макс. размер контекста из базы</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Ограничение объёма найденных фрагментов.</span>
                    </span>
                  </label>
                  <input v-model.number="kbSettings.retrieval_max_chars" type="number" min="0" class="tb-input" />
                </div>
                <div class="tb-field">
                  <label class="tb-label">
                    <span>Усиление лексики</span>
                    <span class="tb-help">
                      <span class="tb-help-icon">?</span>
                      <span class="tb-help-balloon">Усиливает точное совпадение ключевых слов.</span>
                    </span>
                  </label>
                  <input v-model="kbSettings.lex_boost" type="number" step="0.01" min="0" class="tb-input" />
                </div>
              </div>
            </details>
            <div class="tb-actions">
              <button class="tb-btn tb-btn-primary" @click="saveKbSettings">Сохранить</button>
              <span class="tb-muted" v-if="kbSettingsMessage">{{ kbSettingsMessage }}</span>
            </div>
          </div>
        </div>

      </section>

      <section v-if="currentTab === 'integrations'" class="tb-grid" key="integrations">
        <div class="tb-card">
          <div class="tb-actions">
            <h2 class="tb-card-title">Интеграции</h2>
            <div class="tb-chip-row">
              <button class="tb-chip tb-chip-ghost" :class="{ 'is-active': integrationTab === 'telegram' }" @click="integrationTab = 'telegram'">Телеграм</button>
              <button class="tb-chip tb-chip-ghost" :class="{ 'is-active': integrationTab === 'bitrix' }" @click="integrationTab = 'bitrix'">Битрикс</button>
              <button class="tb-chip tb-chip-ghost" :class="{ 'is-active': integrationTab === 'amocrm' }" @click="integrationTab = 'amocrm'">AmoCRM</button>
            </div>
          </div>
          <div v-if="integrationTab === 'telegram'">
            <div v-if="!isPortalAdmin" class="tb-empty">Доступно только администратору портала.</div>
            <div v-else>
              <div class="tb-field">
                <label>
                  <input type="checkbox" v-model="tgStaffEnabled" />
                  Бот для сотрудников (RAG: staff)
                </label>
                <label class="tb-inline">
                  <input type="checkbox" v-model="tgStaffAllowUploads" />
                  Разрешить загрузку файлов
                </label>
                <div class="tb-muted" v-if="tgStaffMasked">Токен: {{ tgStaffMasked }}</div>
                <div class="tb-muted" v-if="tgStaffWebhook">Webhook: {{ tgStaffWebhook }}</div>
                <input v-model="tgStaffToken" class="tb-input" placeholder="Bot token" />
                <div class="tb-actions">
                  <button class="tb-btn tb-btn-primary" @click="saveTelegram('staff')">Сохранить</button>
                  <span class="tb-muted" v-if="tgStaffStatus">{{ tgStaffStatus }}</span>
                </div>
              </div>
              <div class="tb-field">
                <label>
                  <input type="checkbox" v-model="tgClientEnabled" />
                  Бот для клиентов (RAG: client)
                </label>
                <label class="tb-inline">
                  <input type="checkbox" v-model="tgClientAllowUploads" />
                  Разрешить загрузку файлов
                </label>
                <div class="tb-muted" v-if="tgClientMasked">Токен: {{ tgClientMasked }}</div>
                <div class="tb-muted" v-if="tgClientWebhook">Webhook: {{ tgClientWebhook }}</div>
                <input v-model="tgClientToken" class="tb-input" placeholder="Bot token" />
                <div class="tb-actions">
                  <button class="tb-btn tb-btn-primary" @click="saveTelegram('client')">Сохранить</button>
                  <span class="tb-muted" v-if="tgClientStatus">{{ tgClientStatus }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="integrationTab === 'bitrix'">
            <div v-if="!isPortalAdmin" class="tb-empty">Доступно только администратору портала.</div>
            <div v-else class="tb-field">
              <label>Client ID</label>
              <input v-model="bitrixClientId" class="tb-input" placeholder="client_id" />
              <label class="tb-label" style="margin-top:10px;">Client Secret</label>
              <input v-model="bitrixClientSecret" class="tb-input" placeholder="client_secret" />
              <div class="tb-actions">
                <button class="tb-btn tb-btn-primary" @click="saveBitrixCreds">Сохранить</button>
                <span class="tb-muted" v-if="bitrixCredsStatus">{{ bitrixCredsStatus }}</span>
              </div>
            </div>
          </div>
          <div v-else class="tb-info">
            Настройки интеграции AmoCRM появятся здесь.
          </div>
        </div>
      </section>

      <section v-if="currentTab === 'flow' && isWebMode" class="tb-flow" key="flow">
        <div class="tb-flow-toolbar">
          <button class="tb-btn" @click="addFlowNode('start')">Start</button>
          <button class="tb-btn" @click="addFlowNode('ask')">Question</button>
          <button class="tb-btn" @click="addFlowNode('branch')">Intent</button>
          <button class="tb-btn" @click="addFlowNode('kb_answer')">RAG Search</button>
          <button class="tb-btn" @click="addFlowNode('message')">Answer</button>
          <button class="tb-btn" @click="addFlowNode('webhook')">Webhook</button>
          <button class="tb-btn" @click="addFlowNode('bitrix_lead')">Bitrix Lead</button>
          <button class="tb-btn" @click="addFlowNode('bitrix_deal')">Bitrix Deal</button>
          <button class="tb-btn" @click="addFlowNode('handoff')">CTA / Handoff</button>
          <div class="tb-flow-zoom">
            <button class="tb-mini" @click="zoomOut">−</button>
            <span class="tb-muted">{{ Math.round(flowScale * 100) }}%</span>
            <button class="tb-mini" @click="zoomIn">+</button>
          </div>
          <button class="tb-btn tb-btn-primary" @click="saveFlowDraft" :disabled="flowSaving">
            {{ flowSaving ? 'Сохраняю...' : 'Сохранить' }}
          </button>
          <button class="tb-btn" @click="publishFlow" :disabled="flowPublishing">
            {{ flowPublishing ? 'Публикую...' : 'Опубликовать' }}
          </button>
          <span class="tb-muted" v-if="flowMessage">{{ flowMessage }}</span>
        </div>

        <div class="tb-flow-settings">
          <div class="tb-field">
            <label>Настроение</label>
            <select v-model="flowDraft.settings.mood">
              <option value="нейтральный">Нейтральный</option>
              <option value="дружелюбный">Дружелюбный</option>
              <option value="продающий">Продающий</option>
              <option value="строгий">Строгий</option>
            </select>
          </div>
          <div class="tb-field">
            <label>Кастомный промпт</label>
            <input v-model="flowDraft.settings.custom_prompt" class="tb-input" placeholder="Например: отвечай кратко и по делу" />
          </div>
          <label class="tb-inline">
            <input type="checkbox" v-model="flowDraft.settings.use_history" />
            Учитывать контекст диалога
          </label>
        </div>

        <div class="tb-flow-layout">
          <div>
            <div
              ref="flowCanvasRef"
              class="tb-flow-canvas"
              @mousedown="onFlowCanvasMouseDown"
              @mousemove="onFlowCanvasMouseMove"
              @mouseup="onFlowCanvasMouseUp"
              @mouseleave="onFlowCanvasMouseUp"
            >
              <div class="tb-flow-zoom-stage" :style="flowStageStyle">
                <svg class="tb-flow-lines">
                  <g v-for="edge in flowDraft.edges" :key="edge.id">
                    <path
                      class="tb-flow-edge-halo"
                      :class="{ 'is-selected': selectedEdgeId === edge.id, 'is-hover': hoverEdgeId === edge.id }"
                      :d="edgePath(edge)"
                    />
                    <path
                      class="tb-flow-edge-line"
                      :class="{ 'is-selected': selectedEdgeId === edge.id, 'is-hover': hoverEdgeId === edge.id }"
                      :d="edgePath(edge)"
                    />
                    <path
                      class="tb-flow-edge-hit"
                      :d="edgePath(edge)"
                      @mouseenter="hoverEdgeId = edge.id"
                      @mouseleave="hoverEdgeId = null"
                      @click.stop="selectEdge(edge)"
                    />
                  </g>
                  <path
                    v-if="connectPreview"
                    class="tb-flow-edge-line"
                    :d="connectPreviewPath"
                  />
                </svg>
                <div
                  v-for="node in flowDraft.nodes"
                  :key="node.id"
                  class="tb-flow-node"
                  :class="{ 'is-selected': selectedNodeId === node.id }"
                  :style="nodeStyle(node)"
                  @mousedown.stop="onNodeMouseDown(node, $event)"
                  @click.stop="selectNode(node)"
                >
                  <div class="tb-flow-node-header">
                    <span class="tb-flow-node-icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none">
                        <path :d="nodeIconPath(node.type)" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                    </span>
                    <div class="tb-flow-node-title">{{ node.title || displayName(node.type) }}</div>
                    <div class="tb-flow-node-type">{{ displayName(node.type) }}</div>
                  </div>
                  <div class="tb-flow-node-ports tb-flow-node-ports-in">
                    <div
                      class="tb-flow-port tb-flow-port-in"
                      @mouseup.stop="onPortMouseUp(node, 'in')"
                    ></div>
                  </div>
                  <div class="tb-flow-node-ports tb-flow-node-ports-out">
                    <div
                      class="tb-flow-port tb-flow-port-out"
                      @mousedown.stop="onPortMouseDown(node, 'out', $event)"
                    ></div>
                  </div>
                  <div class="tb-flow-port-stub">
                    <div class="tb-flow-port-line"></div>
                    <button class="tb-flow-plus" @click.stop="addFlowNodeAfter(node)">+</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="tb-flow-chat">
              <div class="tb-flow-chat-log">
                <div v-for="(msg, idx) in flowChatLog" :key="idx" class="tb-flow-chat-msg" :class="{ 'is-user': msg.role === 'user' }">
                  <div>{{ msg.text }}</div>
                  <div class="tb-flow-chat-trace" v-if="msg.trace">{{ msg.trace }}</div>
                </div>
              </div>
              <div class="tb-field">
                <label>Тестовое сообщение</label>
                <input v-model="flowTestInput" class="tb-input" placeholder="Введите сообщение клиента" />
              </div>
              <div class="tb-actions">
                <button class="tb-btn tb-btn-primary" @click="runFlowTest" :disabled="flowTesting">
                  {{ flowTesting ? 'Тестирую...' : 'Тестовый прогон' }}
                </button>
                <button class="tb-btn" @click="resetFlowTest">Сбросить контекст</button>
              </div>
            </div>
          </div>

          <div class="tb-flow-panel">
            <div v-if="selectedNode">
              <h3 class="tb-card-title">Параметры узла</h3>
              <div class="tb-field">
                <label>Название</label>
                <input v-model="selectedNode.title" class="tb-input" />
              </div>
              <template v-if="selectedNode.type === 'ask'">
                <div class="tb-field">
                  <label>Вопрос</label>
                  <textarea v-model="selectedNode.config.question" class="tb-input" rows="3"></textarea>
                </div>
                <div class="tb-field">
                  <label>Сохранять в переменную</label>
                  <input v-model="selectedNode.config.var" class="tb-input" placeholder="например: phone" />
                </div>
              </template>
              <template v-else-if="selectedNode.type === 'message'">
                <div class="tb-field">
                  <label>Текст</label>
                  <textarea v-model="selectedNode.config.text" class="tb-input" rows="4"></textarea>
                </div>
              </template>
              <template v-else-if="selectedNode.type === 'branch'">
                <div class="tb-field">
                  <label>Смыслы</label>
                  <div v-for="(m, idx) in selectedNode.config.meanings" :key="idx" class="tb-flow-cond">
                    <input v-model="m.title" class="tb-input" placeholder="Название смысла" />
                    <textarea v-model="m.phrases" class="tb-input" rows="2" placeholder="Фразы через запятую"></textarea>
                    <div class="tb-flow-cond-row">
                      <input v-model="m.id" class="tb-input" placeholder="id" />
                      <input v-model.number="m.sensitivity" type="number" step="0.1" min="0" max="1" class="tb-input" />
                      <button class="tb-mini tb-mini-danger" @click="removeMeaning(idx)">Удалить</button>
                    </div>
                  </div>
                  <button class="tb-mini" @click="addMeaning">Добавить смысл</button>
                </div>
              </template>
              <template v-else-if="selectedNode.type === 'kb_answer'">
                <div class="tb-field">
                  <label>Дополнительный промпт</label>
                  <textarea v-model="selectedNode.config.pre_prompt" class="tb-input" rows="3"></textarea>
                </div>
              </template>
              <template v-else-if="selectedNode.type === 'webhook'">
                <div class="tb-field">
                  <label>URL</label>
                  <input v-model="selectedNode.config.url" class="tb-input" placeholder="https://..." />
                </div>
                <div class="tb-field">
                  <label>Payload (JSON)</label>
                  <textarea v-model="selectedNode.config.payload" class="tb-input" rows="4"></textarea>
                </div>
              </template>
              <template v-else-if="selectedNode.type === 'bitrix_lead' || selectedNode.type === 'bitrix_deal'">
                <div class="tb-field">
                  <label>Fields (JSON)</label>
                  <textarea v-model="selectedNode.config.fields" class="tb-input" rows="4"></textarea>
                </div>
              </template>
              <template v-else-if="selectedNode.type === 'handoff'">
                <div class="tb-field">
                  <label>Текст</label>
                  <textarea v-model="selectedNode.config.text" class="tb-input" rows="3"></textarea>
                </div>
              </template>
              <div class="tb-flow-node-actions">
                <button class="tb-mini tb-mini-danger" @click="removeSelectedNode">Удалить узел</button>
              </div>
            </div>
            <div v-else class="tb-empty">Выберите узел для редактирования.</div>

            <div class="tb-card" style="margin-top: 12px;">
              <h3 class="tb-card-title">Связи</h3>
              <div class="tb-flow-edge" v-for="edge in flowDraft.edges" :key="edge.id">
                <div class="tb-muted">{{ edge.from }}</div>
                <div class="tb-muted">→ {{ edge.to }}</div>
                <button class="tb-mini tb-mini-danger" @click="removeEdge(edge.id)">Удалить</button>
              </div>
              <div class="tb-empty" v-if="flowDraft.edges.length === 0">Связей пока нет.</div>
            </div>
          </div>
        </div>
      </section>

    </main>

    <div v-if="showAuthModal" class="tb-auth-modal">
      <div class="tb-auth-backdrop" />
      <div class="tb-auth-card">
        <div class="tb-auth-tabs">
          <button :class="{ active: authMode === 'register' }" @click="authMode = 'register'">Регистрация</button>
          <button :class="{ active: authMode === 'login' }" @click="authMode = 'login'">Вход</button>
        </div>
        <div class="tb-auth-body">
          <div class="tb-auth-badge">Teachbase AI — Web-кабинет</div>
          <h2>{{ authMode === 'register' ? 'Регистрация' : 'Вход' }}</h2>
          <p class="tb-auth-sub">
            {{ authMode === 'register'
              ? 'Подтвердите email для доступа в кабинет.'
              : 'Email + пароль. Подтвердите email для входа.' }}
          </p>
          <div class="tb-auth-form">
            <label>
              Email
              <input v-model="authEmail" type="email" placeholder="you@company.com" />
            </label>
            <label v-if="authMode === 'register'">
              Компания
              <input v-model="authCompany" type="text" placeholder="Название компании" />
            </label>
            <div class="tb-auth-row">
              <label>
                Пароль
                <input v-model="authPassword" type="password" placeholder="Минимум 6 символов" />
              </label>
              <label v-if="authMode === 'register'">
                Повтор пароля
                <input v-model="authConfirm" type="password" placeholder="Повторите пароль" />
              </label>
            </div>
            <div v-if="authError" class="tb-auth-error">{{ authError }}</div>
            <button class="tb-btn tb-btn-primary" @click="submitAuth" :disabled="authLoading">
              {{ authLoading ? 'Отправка...' : (authMode === 'register' ? 'Создать аккаунт' : 'Войти') }}
            </button>
            <div v-if="authHint" class="tb-auth-hint">{{ authHint }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="linkModalOpen" class="tb-link-modal">
      <div class="tb-auth-backdrop" />
      <div class="tb-link-card">
        <h3>Подтверждение привязки Bitrix24</h3>
        <p class="tb-muted">Портал: {{ linkModalRequest?.portal_domain }}</p>
        <div class="tb-link-grid">
          <label>
            База знаний
            <select v-model="linkKbStrategy" class="tb-input">
              <option value="merge">Объединить</option>
              <option value="keep_web">Оставить web</option>
              <option value="keep_bitrix">Оставить Bitrix</option>
            </select>
          </label>
          <label>
            Боты
            <select v-model="linkBotsStrategy" class="tb-input">
              <option value="keep_web">Оставить web</option>
              <option value="keep_bitrix">Оставить Bitrix</option>
            </select>
          </label>
          <label>
            Конструктор
            <select v-model="linkFlowStrategy" class="tb-input">
              <option value="keep_web">Оставить web</option>
              <option value="keep_bitrix">Оставить Bitrix</option>
            </select>
          </label>
        </div>
        <div v-if="linkActionError" class="tb-auth-error">{{ linkActionError }}</div>
        <div class="tb-banner-actions">
          <button class="tb-btn" @click="approveLink" :disabled="linkActionLoading">
            {{ linkActionLoading ? 'Сохранение...' : 'Подтвердить' }}
          </button>
          <button class="tb-btn tb-btn-ghost" @click="closeLinkModal">Отмена</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

type KbFile = {
    id: number;
    filename: string;
    status: string;
    error_message?: string;
    created_at?: string;
    uploaded_by_type?: string;
    uploaded_by_id?: string;
    uploaded_by_name?: string;
    query_count?: number;
  };

type KbSource = { id: number; url: string; status: string; created_at?: string };

type DialogItem = { body?: string; direction?: 'tx' | 'rx' };
  type KbSettings = {
    embedding_model: string;
    chat_model: string;
    prompt_preset: string;
    system_prompt_extra: string;
    show_sources: boolean;
    sources_format: string;
    collections_multi_assign: boolean;
    smart_folder_threshold: number;
    allow_general: boolean;
    strict_mode: boolean;
    use_history: boolean;
    use_cache: boolean;
    context_messages: number;
    context_chars: number;
    retrieval_top_k: number;
    retrieval_max_chars: number;
    lex_boost: number;
    temperature: number;
    max_tokens: number;
    top_p: number | '';
    presence_penalty: number | '';
    frequency_penalty: number | '';
  };
type FlowNode = { id: string; type: string; title?: string; config?: any; x?: number; y?: number };
type FlowEdge = { id: string; from: string; to: string; condition?: any };
type FlowDraft = {
  version: number;
  settings: { mood: string; custom_prompt: string; use_history: boolean };
  nodes: FlowNode[];
  edges: FlowEdge[];
};

const statusMessage = ref('Загрузка...');
const sessionReady = ref(false);
const isPortalAdmin = ref(false);
const portalId = ref<number | null>(null);
const portalToken = ref<string>('');
const authRef = ref<any>(null);
const accessWarning = ref<string>('');
const isWebMode = ref(false);
const showAuthModal = ref(false);
const authMode = ref<'register' | 'login'>('register');
const authEmail = ref('');
const authCompany = ref('');
const authPassword = ref('');
const authConfirm = ref('');
const authError = ref('');
const authHint = ref('');
const authLoading = ref(false);
const webLinked = ref(false);
const webEmail = ref('');
const demoUntil = ref<string | null>(null);
const webSessionToken = ref('');
const webUserLabel = computed(() => {
  if (webEmail.value) return webEmail.value;
  try {
    const raw = localStorage.getItem('tb_web_user') || '';
    const parsed = raw ? JSON.parse(raw) : null;
    const email = parsed?.email || '';
    return email || 'Пользователь';
  } catch {
    return 'Пользователь';
  }
});
const linkRequests = ref<{ id: number; portal_id: number; portal_domain: string; status: string; created_at: string }[]>([]);
const linkModalOpen = ref(false);
const linkModalRequest = ref<{ id: number; portal_id: number; portal_domain: string } | null>(null);
const linkKbStrategy = ref('merge');
const linkBotsStrategy = ref('keep_web');
const linkFlowStrategy = ref('keep_web');
const linkActionLoading = ref(false);
const linkActionError = ref('');

const users = ref<{ id: number; name: string }[]>([]);
const userSearch = ref('');
const selectedUsers = ref<number[]>([]);
const bitrixTelegramMap = ref<Record<number, string>>({});
const webUsers = ref<{ id: string; name: string; telegram_username?: string | null }[]>([]);
const newWebUserName = ref('');
const newWebUserTelegram = ref('');
const webUserMessage = ref('');
const userStats = ref<Record<number, number>>({});
const accessSaveStatus = ref<string>('');
const accessSaving = ref(false);

const kbFiles = ref<KbFile[]>([]);
const kbCollections = ref<{ id: number; name: string; color?: string; file_count?: number }[]>([]);
const kbCollectionFiles = ref<Record<number, number[]>>({});
const kbSmartFolders = ref<{ id: number; name: string; system_tag?: string; rules?: any }[]>([]);
const kbTopics = ref<{ id: string; name: string; count: number; file_ids: number[] }[]>([]);
const kbTopicSuggestions = ref<{ id: string; name: string; count: number }[]>([]);
const kbFilter = ref<{ kind: 'all' | 'collection' | 'smart' | 'topic'; id?: number | string }>({ kind: 'all' });
const newCollectionName = ref('');
const newCollectionColor = ref('');
const smartThreshold = ref(5);
const selectedFileIds = ref<number[]>([]);
const dragOverCollectionId = ref<number | null>(null);
const kbSearch = ref('');
const kbSort = ref<'new' | 'name' | 'status'>('new');
const editingCollectionId = ref<number | null>(null);
const editingCollectionName = ref('');
const kbTypeFilter = ref('all');
const kbPeopleFilter = ref('all');
const kbLocationFilter = ref('all');
const smartFoldersOpen = ref(true);
const kbSearchResults = ref<number[] | null>(null);
const kbSearchMatches = ref<{ file_id: number; filename?: string; snippet?: string }[]>([]);
const kbSearchLoading = ref(false);
const kbSearchError = ref('');
const smartSearchOpen = ref(false);
const smartSearchQuery = ref('');
const smartSearchAnswer = ref('');
const smartSearchLoading = ref(false);
const smartSearchError = ref('');
const kbViewMode = ref<'table' | 'grid'>('table');
const draggingFileIds = ref<number[]>([]);
const openFileMenuId = ref<number | null>(null);
let searchTimer: number | null = null;
const kbSources = ref<KbSource[]>([]);
const kbUrl = ref('');
const kbUrlMessage = ref('');
const kbUploadMessage = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
const lastUpdated = ref('—');

const recentDialogs = ref<DialogItem[]>([]);
type TopicSummary = { topic: string; score?: number | null };
const topicSummaries = ref<TopicSummary[]>([]);
const currentTab = ref<'overview' | 'kb' | 'sources' | 'users' | 'analytics' | 'settings' | 'integrations' | 'flow'>('overview');
  const kbSettings = ref<KbSettings>({
    embedding_model: '',
    chat_model: '',
    prompt_preset: 'auto',
    system_prompt_extra: '',
    show_sources: true,
    sources_format: 'detailed',
    collections_multi_assign: true,
    smart_folder_threshold: 5,
    allow_general: false,
    strict_mode: true,
    use_history: true,
    use_cache: true,
    context_messages: 6,
    context_chars: 4000,
    retrieval_top_k: 5,
    retrieval_max_chars: 4000,
    lex_boost: 0.12,
    temperature: 0.2,
    max_tokens: 700,
    top_p: '',
    presence_penalty: '',
    frequency_penalty: '',
  });
const embedModels = ref<string[]>([]);
const chatModels = ref<string[]>([]);
const kbSettingsMessage = ref('');
const tgStaffEnabled = ref(false);
const tgStaffToken = ref('');
const tgStaffMasked = ref('');
const tgStaffWebhook = ref('');
const tgStaffStatus = ref('');
const tgStaffAllowUploads = ref(false);
const tgClientEnabled = ref(false);
const tgClientToken = ref('');
const tgClientMasked = ref('');
const tgClientWebhook = ref('');
const tgClientStatus = ref('');
const tgClientAllowUploads = ref(false);
const integrationTab = ref<'telegram' | 'bitrix' | 'amocrm'>('telegram');
const bitrixClientId = ref('');
const bitrixClientSecret = ref('');
const bitrixCredsStatus = ref('');
const flowDraft = ref<FlowDraft>({
  version: 1,
  settings: { mood: 'нейтральный', custom_prompt: '', use_history: true },
  nodes: [],
  edges: [],
});
const flowMessage = ref('');
const flowSaving = ref(false);
const flowPublishing = ref(false);
const flowTesting = ref(false);
const flowScale = ref(1);
const flowPan = ref({ x: 0, y: 0 });
const flowCanvasRef = ref<HTMLDivElement | null>(null);
const selectedNodeId = ref<string | null>(null);
const selectedEdgeId = ref<string | null>(null);
const hoverEdgeId = ref<string | null>(null);
const draggingNodeId = ref<string | null>(null);
const dragStart = ref<{ x: number; y: number; nodeX: number; nodeY: number } | null>(null);
const isPanning = ref(false);
const panStart = ref<{ x: number; y: number; panX: number; panY: number } | null>(null);
const connectingFrom = ref<{ id: string; x: number; y: number } | null>(null);
const connectPreview = ref<{ x: number; y: number } | null>(null);
const flowTestInput = ref('');
const flowTestState = ref<Record<string, any> | null>(null);
const flowChatLog = ref<{ role: 'user' | 'bot'; text: string; trace?: string }[]>([]);

const tabTitle = computed(() => {
  switch (currentTab.value) {
    case 'kb': return 'База знаний';
    case 'sources': return 'Источники данных';
    case 'users': return 'Пользователи и доступы';
    case 'analytics': return 'Аналитика';
    case 'settings': return 'Настройки';
    case 'integrations': return 'Интеграции';
    case 'flow': return 'Конструктор бота';
    default: return 'Обзор';
  }
});

const filteredKbFiles = computed(() => {
  const f = kbFilter.value;
  let items = kbFiles.value.slice();
  const query = kbSearch.value.trim().toLowerCase();
  const hasFullText = kbSearchResults.value !== null;
  if (query && !hasFullText) {
    items = items.filter((x) =>
      (x.filename || '').toLowerCase().includes(query) ||
      (x.uploaded_by_name || '').toLowerCase().includes(query)
    );
  }
  if (kbTypeFilter.value !== 'all') {
    items = items.filter((x) => fileTypeCategory(x.filename) === kbTypeFilter.value);
  }
  if (kbPeopleFilter.value !== 'all') {
    items = items.filter((x) => (x.uploaded_by_name || '') === kbPeopleFilter.value);
  }
  if (kbLocationFilter.value !== 'all') {
    const ids = kbCollectionFiles.value[Number(kbLocationFilter.value)] || [];
    items = items.filter((x) => ids.includes(x.id));
  }
  if (hasFullText) {
    const ids = new Set(kbSearchResults.value || []);
    items = items.filter((x) => ids.has(x.id));
  }
  if (f.kind === 'collection' && f.id) {
    const ids = kbCollectionFiles.value[Number(f.id)] || [];
    items = items.filter((x) => ids.includes(x.id));
  }
  if (f.kind === 'topic' && f.id) {
    const topic = kbTopics.value.find((t) => t.id === String(f.id));
    const ids = topic?.file_ids || [];
    items = items.filter((x) => ids.includes(x.id));
  }
  if (f.kind === 'smart' && f.id) {
    const folder = kbSmartFolders.value.find((s) => s.id === Number(f.id));
    const topicId = (folder?.system_tag || folder?.rules?.topic_id || folder?.rules?.topicId || '').toString();
    if (topicId) {
      const topic = kbTopics.value.find((t) => t.id === topicId);
      const ids = topic?.file_ids || [];
      items = items.filter((x) => ids.includes(x.id));
    }
  }
  return items;
});

const sortedKbFiles = computed(() => {
  const items = filteredKbFiles.value.slice();
  if (kbSort.value === 'name') {
    items.sort((a, b) => (a.filename || '').localeCompare(b.filename || ''));
  } else if (kbSort.value === 'status') {
    items.sort((a, b) => (a.status || '').localeCompare(b.status || ''));
  } else {
    items.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  }
  return items;
});

const recentKbFiles = computed(() => sortedKbFiles.value.slice(0, 5));

const allVisibleSelected = computed(() => {
  if (!sortedKbFiles.value.length) return false;
  return sortedKbFiles.value.every((f) => selectedFileIds.value.includes(f.id));
});

function toggleSelectAllVisible() {
  if (allVisibleSelected.value) {
    const visibleIds = new Set(sortedKbFiles.value.map((f) => f.id));
    selectedFileIds.value = selectedFileIds.value.filter((id) => !visibleIds.has(id));
    return;
  }
  const ids = new Set(selectedFileIds.value);
  for (const f of sortedKbFiles.value) ids.add(f.id);
  selectedFileIds.value = Array.from(ids);
}

const kbTypeOptions = computed(() => {
  const types = new Set<string>();
  for (const f of kbFiles.value) {
    types.add(fileTypeCategory(f.filename));
  }
  return Array.from(types).sort();
});

const kbPeopleOptions = computed(() => {
  const people = new Set<string>();
  for (const f of kbFiles.value) {
    if (f.uploaded_by_name) {
      people.add(f.uploaded_by_name);
    } else if (f.uploaded_by_type) {
      people.add(f.uploaded_by_type);
    }
  }
  return Array.from(people).sort();
});

const recommendedKbFiles = computed(() => {
  return kbFiles.value
    .filter((f) => (f.status || '').toLowerCase() === 'ready')
    .slice()
    .sort((a, b) => {
      const qa = a.query_count || 0;
      const qb = b.query_count || 0;
      if (qa !== qb) return qb - qa;
      return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    })
    .slice(0, 20);
});

const kbSearchMatchesById = computed(() => {
  const map = new Map<number, { filename?: string; snippet?: string }>();
  for (const m of kbSearchMatches.value) {
    map.set(Number(m.file_id), { filename: m.filename, snippet: m.snippet });
  }
  return map;
});

function fileCollections(fileId: number) {
  const out: { id: number; name: string; color?: string }[] = [];
  for (const c of kbCollections.value) {
    const ids = kbCollectionFiles.value[c.id] || [];
    if (ids.includes(fileId)) {
      out.push({ id: c.id, name: c.name, color: c.color });
    }
  }
  return out;
}

function fileTypeCategory(filename: string | undefined) {
  const name = (filename || '').toLowerCase();
  const ext = name.includes('.') ? name.split('.').pop() || '' : '';
  if (['pdf', 'doc', 'docx', 'txt', 'rtf'].includes(ext)) return 'Документы';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'Таблицы';
  if (['ppt', 'pptx', 'key'].includes(ext)) return 'Презентации';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return 'Изображения';
  if (['mp3', 'ogg', 'wav', 'm4a', 'aac'].includes(ext)) return 'Аудио';
  if (['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext)) return 'Видео';
  return 'Другое';
}

function fileTypeIcon(filename: string | undefined) {
  const type = fileTypeCategory(filename);
  const map: Record<string, { label: string; color: string }> = {
    'Документы': { label: 'DOC', color: '#3b82f6' },
    'Таблицы': { label: 'XLS', color: '#16a34a' },
    'Презентации': { label: 'PPT', color: '#f59e0b' },
    'Изображения': { label: 'IMG', color: '#a855f7' },
    'Аудио': { label: 'AUD', color: '#0ea5e9' },
    'Видео': { label: 'VID', color: '#f97316' },
  };
  return map[type] || { label: 'FILE', color: '#64748b' };
}

function fileStatusLabel(status: string | undefined) {
  const s = (status || '').toLowerCase();
  if (s === 'ready') return 'Готово';
  if (s === 'processing') return 'Индексируется';
  if (s === 'queued') return 'В очереди';
  if (s === 'uploaded') return 'Загружен';
  if (s === 'error') return 'Ошибка';
  return status || '—';
}

function fileOwnerLabel(file: KbFile) {
  if (file.uploaded_by_name) return file.uploaded_by_name;
  if (file.uploaded_by_type && file.uploaded_by_id) return `${file.uploaded_by_type} ${file.uploaded_by_id}`;
  return file.uploaded_by_type || '—';
}

function scheduleSearch() {
  if (searchTimer) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
  searchTimer = window.setTimeout(() => {
    runFullTextSearch();
  }, 300);
}

async function runFullTextSearch() {
  if (!portalId.value || !portalToken.value) return;
  const q = kbSearch.value.trim();
  if (!q) {
    kbSearchResults.value = null;
    kbSearchMatches.value = [];
    kbSearchError.value = '';
    return;
  }
  kbSearchLoading.value = true;
  kbSearchError.value = '';
  kbSearchResults.value = null;
  kbSearchMatches.value = [];
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/search?q=${encodeURIComponent(q)}&limit=100`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  kbSearchLoading.value = false;
  if (!ok) {
    kbSearchError.value = data?.error || data?.detail || 'Ошибка поиска';
    kbSearchResults.value = [];
    kbSearchMatches.value = [];
    return;
  }
  const ids = Array.isArray(data?.file_ids) ? data.file_ids.map((x: any) => Number(x)).filter((x: number) => Number.isFinite(x)) : [];
  kbSearchResults.value = ids;
  kbSearchMatches.value = Array.isArray(data?.matches) ? data.matches : [];
}

async function runSmartSearch() {
  if (!portalId.value || !portalToken.value) return;
  const q = smartSearchQuery.value.trim();
  if (!q) return;
  smartSearchLoading.value = true;
  smartSearchError.value = '';
  smartSearchAnswer.value = '';
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ query: q }),
  });
  smartSearchLoading.value = false;
  if (!ok) {
    smartSearchError.value = data?.error || data?.detail || 'Ошибка умного поиска';
    return;
  }
  smartSearchAnswer.value = data?.answer || '';
}

function toggleSmartSearch() {
  smartSearchOpen.value = !smartSearchOpen.value;
  if (smartSearchOpen.value && !smartSearchQuery.value) {
    smartSearchQuery.value = kbSearch.value.trim();
  }
}


const demoUntilLabel = computed(() => {
  if (!demoUntil.value) return '';
  const dt = new Date(demoUntil.value);
  if (Number.isNaN(dt.getTime())) return `Демо до ${demoUntil.value}`;
  const dd = String(dt.getDate()).padStart(2, '0');
  const mm = String(dt.getMonth() + 1).padStart(2, '0');
  const yy = dt.getFullYear();
  return `Демо до ${dd}.${mm}.${yy}`;
});

const demoLeftLabel = computed(() => {
  if (!demoUntil.value) return '';
  const dt = new Date(demoUntil.value);
  if (Number.isNaN(dt.getTime())) return `Тариф: до ${demoUntil.value}`;
  const now = new Date();
  const diffMs = dt.getTime() - now.getTime();
  const days = Math.max(0, Math.ceil(diffMs / 86400000));
  return `Тариф: осталось ${days} дн.`;
});

const pendingLinkRequests = computed(() =>
  linkRequests.value.filter((r) => r.status === 'pending')
);

const filteredUsers = computed(() => {
  const q = userSearch.value.trim().toLowerCase();
  if (!q) return users.value;
  return users.value.filter(u => u.name.toLowerCase().includes(q));
});

const kbCounts = computed(() => {
  const counts = { ready: 0, queued: 0, error: 0 };
  for (const f of kbFiles.value) {
    const st = (f.status || '').toLowerCase();
    if (st === 'ready') counts.ready += 1;
    else if (st === 'queued') counts.queued += 1;
    else if (st === 'error') counts.error += 1;
  }
  return counts;
});

const activeUsers = computed(() => Object.keys(userStats.value || {}).length || 0);
const selectedNode = computed(() => flowDraft.value.nodes.find(n => n.id === selectedNodeId.value) || null);
const flowStageStyle = computed(() => ({
  transform: `translate(${flowPan.value.x}px, ${flowPan.value.y}px) scale(${flowScale.value})`,
}));
const connectPreviewPath = computed(() => {
  if (!connectingFrom.value || !connectPreview.value) return '';
  return bezierPath(connectingFrom.value.x, connectingFrom.value.y, connectPreview.value.x, connectPreview.value.y);
});

const base = window.location.origin;
const NODE_WIDTH = 170;
const NODE_HEIGHT = 78;

function displayName(type: string) {
  const map: Record<string, string> = {
    start: 'Start',
    ask: 'Question',
    branch: 'Intent',
    kb_answer: 'RAG Search',
    message: 'Answer Composer',
    prompt: 'Answer Composer (style)',
    webhook: 'Action',
    bitrix_lead: 'Action',
    bitrix_deal: 'Action',
    handoff: 'CTA / Handoff',
  };
  return map[type] || type;
}

function nodeIconPath(type: string) {
  switch (type) {
    case 'start': return 'M5 12h14M12 5l7 7-7 7';
    case 'ask': return 'M4 6h16v8H7l-3 4V6Z';
    case 'branch': return 'M6 6h12M6 12h12M6 18h6';
    case 'kb_answer': return 'M6 4h9a4 4 0 0 1 4 4v12H9a3 3 0 0 0-3 3V4Z';
    case 'message': return 'M4 5h16v10H7l-3 4V5Z';
    case 'webhook': return 'M12 3v6M6 9l6 6 6-6M6 21h12';
    case 'bitrix_lead': return 'M4 8h8v8H4zM14 6h6v12h-6z';
    case 'bitrix_deal': return 'M5 6h14v12H5zM8 9h8M8 13h6';
    case 'handoff': return 'M6 12h6l3 3 3-3h-2a3 3 0 0 0-6 0H6Z';
    default: return 'M5 12h14';
  }
}

function ensureNodeConfig(node: FlowNode) {
  if (!node.config) node.config = {};
  if (node.type === 'branch') {
    if (!Array.isArray(node.config.meanings)) node.config.meanings = [];
  }
  if (node.type === 'webhook' && typeof node.config.payload !== 'string') {
    node.config.payload = node.config.payload ? JSON.stringify(node.config.payload, null, 2) : '';
  }
  if ((node.type === 'bitrix_lead' || node.type === 'bitrix_deal') && typeof node.config.fields !== 'string') {
    node.config.fields = node.config.fields ? JSON.stringify(node.config.fields, null, 2) : '';
  }
}

function nodeStyle(node: FlowNode) {
  return {
    left: `${node.x ?? 100}px`,
    top: `${node.y ?? 100}px`,
    width: `${NODE_WIDTH}px`,
    height: `${NODE_HEIGHT}px`,
  };
}

function nodeOutPoint(node: FlowNode) {
  return {
    x: (node.x ?? 100) + NODE_WIDTH,
    y: (node.y ?? 100) + NODE_HEIGHT / 2,
  };
}

function nodeInPoint(node: FlowNode) {
  return {
    x: (node.x ?? 100),
    y: (node.y ?? 100) + NODE_HEIGHT / 2,
  };
}

function bezierPath(x1: number, y1: number, x2: number, y2: number) {
  const dx = Math.max(60, Math.abs(x2 - x1) * 0.5);
  const c1x = x1 + dx;
  const c2x = x2 - dx;
  return `M ${x1} ${y1} C ${c1x} ${y1} ${c2x} ${y2} ${x2} ${y2}`;
}

function edgePath(edge: FlowEdge) {
  const from = flowDraft.value.nodes.find(n => n.id === edge.from);
  const to = flowDraft.value.nodes.find(n => n.id === edge.to);
  if (!from || !to) return '';
  const p1 = nodeOutPoint(from);
  const p2 = nodeInPoint(to);
  return bezierPath(p1.x, p1.y, p2.x, p2.y);
}

function zoomIn() {
  flowScale.value = Math.min(3, Math.round((flowScale.value + 0.1) * 10) / 10);
}

function zoomOut() {
  flowScale.value = Math.max(0.2, Math.round((flowScale.value - 0.1) * 10) / 10);
}

function toFlowPoint(evt: MouseEvent) {
  const canvas = flowCanvasRef.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  const x = (evt.clientX - rect.left - flowPan.value.x) / flowScale.value;
  const y = (evt.clientY - rect.top - flowPan.value.y) / flowScale.value;
  return { x, y };
}

function selectNode(node: FlowNode) {
  ensureNodeConfig(node);
  selectedNodeId.value = node.id;
  selectedEdgeId.value = null;
}

function selectEdge(edge: FlowEdge) {
  selectedEdgeId.value = edge.id;
  selectedNodeId.value = null;
}

function newNodeId() {
  return `n_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
}

function addFlowNode(type: string) {
  const idx = flowDraft.value.nodes.length;
  const node: FlowNode = {
    id: newNodeId(),
    type,
    title: displayName(type),
    x: 120 + (idx % 4) * 220,
    y: 120 + Math.floor(idx / 4) * 150,
    config: {},
  };
  if (type === 'ask') node.config = { question: 'Чем могу помочь?', var: 'answer' };
  if (type === 'message') node.config = { text: 'Спасибо за интерес!' };
  if (type === 'branch') node.config = { meanings: [] };
  if (type === 'kb_answer') node.config = { pre_prompt: '' };
  if (type === 'webhook') node.config = { url: '', payload: '' };
  if (type === 'bitrix_lead' || type === 'bitrix_deal') node.config = { fields: '' };
  if (type === 'handoff') node.config = { text: 'Передаю менеджеру.' };
  flowDraft.value.nodes.push(node);
  selectNode(node);
}

function addFlowNodeAfter(node: FlowNode) {
  const next = {
    id: newNodeId(),
    type: 'message',
    title: 'Answer',
    x: (node.x ?? 100) + 260,
    y: (node.y ?? 100),
    config: { text: '...' },
  } as FlowNode;
  flowDraft.value.nodes.push(next);
  flowDraft.value.edges.push({ id: newNodeId(), from: node.id, to: next.id });
  selectNode(next);
}

function removeSelectedNode() {
  if (!selectedNodeId.value) return;
  const id = selectedNodeId.value;
  flowDraft.value.nodes = flowDraft.value.nodes.filter(n => n.id !== id);
  flowDraft.value.edges = flowDraft.value.edges.filter(e => e.from !== id && e.to !== id);
  selectedNodeId.value = null;
}

function removeEdge(edgeId: string) {
  flowDraft.value.edges = flowDraft.value.edges.filter(e => e.id !== edgeId);
  if (selectedEdgeId.value === edgeId) selectedEdgeId.value = null;
}

function addMeaning() {
  if (!selectedNode.value) return;
  ensureNodeConfig(selectedNode.value);
  selectedNode.value.config.meanings.push({ id: '', title: '', phrases: '', sensitivity: 0.5 });
}

function removeMeaning(idx: number) {
  if (!selectedNode.value) return;
  ensureNodeConfig(selectedNode.value);
  selectedNode.value.config.meanings.splice(idx, 1);
}

function onNodeMouseDown(node: FlowNode, evt: MouseEvent) {
  if (evt.button !== 0) return;
  selectNode(node);
  draggingNodeId.value = node.id;
  const p = toFlowPoint(evt);
  dragStart.value = { x: p.x, y: p.y, nodeX: node.x ?? 100, nodeY: node.y ?? 100 };
}

function onFlowCanvasMouseDown(evt: MouseEvent) {
  if (evt.button !== 0) return;
  if ((evt.target as HTMLElement).closest('.tb-flow-node')) return;
  selectedNodeId.value = null;
  selectedEdgeId.value = null;
  isPanning.value = true;
  panStart.value = { x: evt.clientX, y: evt.clientY, panX: flowPan.value.x, panY: flowPan.value.y };
}

function onFlowCanvasMouseMove(evt: MouseEvent) {
  if (draggingNodeId.value && dragStart.value) {
    const node = flowDraft.value.nodes.find(n => n.id === draggingNodeId.value);
    if (!node) return;
    const p = toFlowPoint(evt);
    node.x = dragStart.value.nodeX + (p.x - dragStart.value.x);
    node.y = dragStart.value.nodeY + (p.y - dragStart.value.y);
  }
  if (isPanning.value && panStart.value) {
    flowPan.value.x = panStart.value.panX + (evt.clientX - panStart.value.x);
    flowPan.value.y = panStart.value.panY + (evt.clientY - panStart.value.y);
  }
  if (connectingFrom.value) {
    const p = toFlowPoint(evt);
    connectPreview.value = { x: p.x, y: p.y };
  }
}

function onFlowCanvasMouseUp() {
  draggingNodeId.value = null;
  dragStart.value = null;
  isPanning.value = false;
  panStart.value = null;
  if (connectingFrom.value) {
    connectPreview.value = null;
    connectingFrom.value = null;
  }
}

function onPortMouseDown(node: FlowNode, dir: 'out', evt: MouseEvent) {
  if (dir !== 'out') return;
  const p = nodeOutPoint(node);
  connectingFrom.value = { id: node.id, x: p.x, y: p.y };
  const pt = toFlowPoint(evt);
  connectPreview.value = { x: pt.x, y: pt.y };
}

function onPortMouseUp(node: FlowNode, dir: 'in') {
  if (dir !== 'in') return;
  if (!connectingFrom.value) return;
  if (connectingFrom.value.id === node.id) return;
  flowDraft.value.edges.push({ id: newNodeId(), from: connectingFrom.value.id, to: node.id });
  connectingFrom.value = null;
  connectPreview.value = null;
}

function onKeydown(evt: KeyboardEvent) {
  if (evt.key !== 'Delete' && evt.key !== 'Backspace') return;
  if (selectedEdgeId.value) {
    removeEdge(selectedEdgeId.value);
    return;
  }
  if (selectedNodeId.value) {
    removeSelectedNode();
  }
}

async function apiJson(url: string, opts: RequestInit = {}) {
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => null);
  if (r.status === 401 || r.status === 403) {
    if (authRef.value) {
      const refreshed = await refreshSession(authRef.value);
      if (refreshed) {
        const r2 = await fetch(url, {
          ...opts,
          headers: {
            ...(opts.headers || {}),
            'Authorization': portalToken.value ? `Bearer ${portalToken.value}` : (opts.headers as any)?.Authorization,
          },
        });
        const data2 = await r2.json().catch(() => null);
        return { ok: r2.ok, status: r2.status, data: data2 };
      }
    } else if (isWebMode.value && webSessionToken.value) {
      const refreshed = await refreshWebSession();
      if (refreshed) {
        const r2 = await fetch(url, {
          ...opts,
          headers: {
            ...(opts.headers || {}),
            'Authorization': portalToken.value ? `Bearer ${portalToken.value}` : (opts.headers as any)?.Authorization,
          },
        });
        const data2 = await r2.json().catch(() => null);
        return { ok: r2.ok, status: r2.status, data: data2 };
      }
    }
  }
  return { ok: r.ok, status: r.status, data };
}

async function refreshSession(auth: any) {
  const userId = auth?.user_id || auth?.USER_ID || auth?.userId || auth?.USERID || null;
  const { ok, data } = await apiJson(base + '/api/v1/bitrix/session/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ auth: { access_token: auth?.access_token, domain: auth?.domain, member_id: auth?.member_id, user_id: userId } }),
  });
  if (!ok || !data) return false;
  portalId.value = data.portal_id;
  portalToken.value = data.portal_token;
  isPortalAdmin.value = !!data.is_portal_admin;
  sessionReady.value = true;
  return true;
}

async function refreshWebSession() {
  if (!webSessionToken.value) return false;
  const { ok, data } = await webApiJson('/v1/web/auth/me');
  if (!ok || !data?.portal_token) return false;
  portalToken.value = data.portal_token;
  localStorage.setItem('tb_web_portal_token', data.portal_token);
  if (data.portal_id && Number(data.portal_id)) {
    portalId.value = Number(data.portal_id);
    localStorage.setItem('tb_web_portal_id', String(data.portal_id));
  }
  return true;
}

async function selectTab(tab: string) {
  currentTab.value = tab as any;
  if (!sessionReady.value || !portalId.value || !portalToken.value) return;
  if (tab === 'overview') {
    await loadRecentDialogs();
    await loadTopicSummaries();
    if (isPortalAdmin.value) {
      await loadKbFiles();
      await loadKbSources();
    }
    return;
  }
  if (tab === 'users') {
    await loadUsers();
    await loadAllowlist();
    if (!isWebMode.value) {
      await loadUserStats();
    }
    return;
  }
  if (tab === 'kb' && isPortalAdmin.value) {
    await loadKbFiles();
    await loadKbCollections();
    await loadKbSmartFolders();
    await loadKbTopics();
    return;
  }
  if (tab === 'sources' && isPortalAdmin.value) {
    await loadKbSources();
    return;
  }
  if (tab === 'settings' && isPortalAdmin.value) {
    await loadKbSettings();
    await loadKbModels();
    await loadTelegramSettings();
    return;
  }
  if (tab === 'flow' && isWebMode.value) {
    await loadFlow();
    return;
  }
}

async function loadWebLinkStatus() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/web/status`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (!ok) return;
  webLinked.value = !!data?.linked;
  webEmail.value = data?.email || '';
  demoUntil.value = data?.demo_until || null;
  if (!webLinked.value) {
    showAuthModal.value = true;
  }
}

async function webApiJson(path: string, opts: RequestInit = {}) {
  if (!webSessionToken.value) return { ok: false, status: 401, data: null };
  const r = await fetch(base + path, {
    ...opts,
    headers: {
      ...(opts.headers || {}),
      'Authorization': `Bearer ${webSessionToken.value}`,
      'Accept': 'application/json',
    },
  });
  const data = await r.json().catch(() => null);
  if ((r.status === 401 || r.status === 403) && await refreshWebSession()) {
    const r2 = await fetch(base + path, {
      ...opts,
      headers: {
        ...(opts.headers || {}),
        'Authorization': `Bearer ${webSessionToken.value}`,
        'Accept': 'application/json',
      },
    });
    const data2 = await r2.json().catch(() => null);
    return { ok: r2.ok, status: r2.status, data: data2 };
  }
  return { ok: r.ok, status: r.status, data };
}

async function loadLinkRequests() {
  if (!webSessionToken.value) return;
  const { ok, data } = await webApiJson('/v1/web/link/requests');
  if (!ok) return;
  linkRequests.value = Array.isArray(data?.items) ? data.items : [];
}

function openLinkModal(req: { id: number; portal_id: number; portal_domain: string }) {
  linkModalRequest.value = req;
  linkKbStrategy.value = 'merge';
  linkBotsStrategy.value = 'keep_web';
  linkFlowStrategy.value = 'keep_web';
  linkActionError.value = '';
  linkModalOpen.value = true;
}

function closeLinkModal() {
  linkModalOpen.value = false;
  linkModalRequest.value = null;
}

async function approveLink() {
  if (!linkModalRequest.value) return;
  linkActionLoading.value = true;
  linkActionError.value = '';
  const { ok, data } = await webApiJson(`/v1/web/link/requests/${linkModalRequest.value.id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      kb_strategy: linkKbStrategy.value,
      bots_strategy: linkBotsStrategy.value,
      flow_strategy: linkFlowStrategy.value,
    }),
  });
  linkActionLoading.value = false;
  if (!ok) {
    linkActionError.value = data?.detail || 'Не удалось подтвердить.';
    return;
  }
  closeLinkModal();
  await loadLinkRequests();
}

async function rejectLink(req: { id: number }) {
  linkActionError.value = '';
  await webApiJson(`/v1/web/link/requests/${req.id}/reject`, { method: 'POST' });
  await loadLinkRequests();
}

function openWebCabinet() {
  window.open('https://necrogame.ru/app', '_blank');
}

function openNewWebUi() {
  localStorage.setItem('tb_web_ui_mode', 'new');
  window.location.href = '/app/overview';
}

function logoutWeb() {
  localStorage.removeItem('tb_web_user');
  localStorage.removeItem('tb_web_session_token');
  localStorage.removeItem('tb_web_portal_id');
  localStorage.removeItem('tb_web_portal_token');
  window.location.href = '/login';
}

async function submitAuth() {
  authError.value = '';
  authHint.value = '';
  if (!portalId.value || !portalToken.value) return;
  if (!authEmail.value || !authPassword.value) {
    authError.value = 'Укажите email и пароль.';
    return;
  }
  if (authMode.value === 'register') {
    if (authPassword.value.length < 6) {
      authError.value = 'Пароль должен быть не короче 6 символов.';
      return;
    }
    if (authPassword.value !== authConfirm.value) {
      authError.value = 'Пароли не совпадают.';
      return;
    }
  }
  authLoading.value = true;
  const payload = authMode.value === 'register'
    ? { email: authEmail.value, password: authPassword.value, company: authCompany.value }
    : { email: authEmail.value, password: authPassword.value };
  const url = authMode.value === 'register'
    ? `${base}/api/v1/bitrix/portals/${portalId.value}/web/register`
    : `${base}/api/v1/bitrix/portals/${portalId.value}/web/login`;
  const { ok, data } = await apiJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(payload),
  });
  authLoading.value = false;
  if (!ok) {
    if (data?.detail === 'email_not_verified') {
      authHint.value = 'Подтвердите email. Письмо отправлено при регистрации.';
      return;
    }
    authError.value = data?.detail || data?.error || 'Ошибка авторизации.';
    return;
  }
  if (data?.status === 'pending') {
    authHint.value = 'Запрос на привязку отправлен. Подтвердите в веб‑кабинете.';
    return;
  }
  if (data?.status === 'confirm_required') {
    authHint.value = 'Письмо с подтверждением отправлено. Подтвердите email, чтобы продолжить.';
    return;
  }
  webLinked.value = true;
  demoUntil.value = data?.demo_until || demoUntil.value;
  showAuthModal.value = false;
}

async function loadUsers() {
  if (!portalId.value || !portalToken.value) return;
  if (isWebMode.value) {
    await webApiJson(`/v1/web/portals/${portalId.value}/bitrix/users/sync`, { method: 'POST' });
  }
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/users?portal_id=${portalId.value}`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (!ok) {
    if (isWebMode.value) {
      const accessRes = await webApiJson(`/v1/web/portals/${portalId.value}/access/users`);
      if (accessRes.ok && Array.isArray(accessRes.data?.items)) {
        const fallback = accessRes.data.items.filter((it: any) => (it.kind || 'bitrix') === 'bitrix');
        users.value = fallback.map((u: any) => ({
          id: Number(u.user_id),
          name: u.display_name || u.user_id,
        })).filter((u: any) => Number.isFinite(u.id));
        accessWarning.value = 'Bitrix API недоступен. Показан последний сохранённый список.';
        return;
      }
    }
    accessWarning.value = data?.detail || data?.error || 'Не удалось загрузить пользователей.';
    return;
  }
  users.value = (data.users || []).map((u: any) => ({ id: Number(u.id), name: `${u.name || ''} ${u.last_name || ''}`.trim() || u.email || `ID ${u.id}` }));
}

async function loadAllowlist() {
  if (!portalId.value || !portalToken.value) return;
  const url = isWebMode.value
    ? `${base}/api/v1/web/portals/${portalId.value}/access/users`
    : `${base}/api/v1/bitrix/portals/${portalId.value}/access/users`;
  const { ok, data } = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/access/users`)
    : await apiJson(url, {
        headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
  if (!ok) return;
  const items = Array.isArray(data?.items) ? data.items : [];
  const bitrixIds = items
    .filter((it: any) => (it.kind || 'bitrix') === 'bitrix')
    .map((it: any) => Number(it.user_id))
    .filter((n: number) => Number.isFinite(n));
  selectedUsers.value = bitrixIds;
  const tgMap: Record<number, string> = {};
  for (const it of items) {
    if ((it.kind || 'bitrix') !== 'bitrix') continue;
    const id = Number(it.user_id);
    if (Number.isFinite(id)) {
      const raw = it.telegram_username || '';
      tgMap[id] = raw ? `@${raw}` : '';
    }
  }
  bitrixTelegramMap.value = tgMap;
  webUsers.value = items
    .filter((it: any) => it.kind === 'web')
    .map((it: any) => ({
      id: String(it.user_id),
      name: it.display_name || it.user_id,
      telegram_username: it.telegram_username || '',
    }));
}

async function addWebUser() {
  webUserMessage.value = '';
  const name = newWebUserName.value.trim();
  if (!name) {
    webUserMessage.value = 'Укажите имя.';
    return;
  }
  const payload = { name, telegram_username: newWebUserTelegram.value.trim() || null };
  const res = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    : await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/access/web-users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(payload),
      });
  if (!res.ok) {
    webUserMessage.value = res.data?.detail || res.data?.error || 'Ошибка добавления.';
    return;
  }
  newWebUserName.value = '';
  newWebUserTelegram.value = '';
  await loadAllowlist();
  webUserMessage.value = 'Добавлено';
}

async function removeWebUser(id: string) {
  webUserMessage.value = '';
  const res = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/users/${id}`, { method: 'DELETE' })
    : await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/access/web-users/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
  if (!res.ok) {
    webUserMessage.value = res.data?.detail || res.data?.error || 'Ошибка удаления.';
    return;
  }
  await loadAllowlist();
  webUserMessage.value = 'Удалено';
}

async function saveAccess() {
  if (!portalId.value || !portalToken.value) return;
  accessWarning.value = '';
  accessSaving.value = true;
  accessSaveStatus.value = 'Сохраняю...';
  const items = selectedUsers.value.map((id) => ({
    user_id: id,
    telegram_username: bitrixTelegramMap.value[id] || null,
  }));
  const { ok, data } = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/access/users`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      })
    : await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/access/users`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ items }),
      });
  if (!ok) {
    accessWarning.value = data?.detail || data?.error || 'Не удалось сохранить доступ.';
    accessSaveStatus.value = 'Ошибка';
  } else {
    if (isWebMode.value) {
      accessSaveStatus.value = 'Сохранено';
    } else {
      const welcome = data?.welcome;
      if (welcome?.status === 'ok') {
        accessSaveStatus.value = 'Сохранено, welcome отправлен';
      } else if (welcome?.status === 'skipped') {
        accessSaveStatus.value = 'Сохранено';
      } else {
        accessSaveStatus.value = 'Сохранено, welcome: ошибка';
      }
    }
  }
  accessSaving.value = false;
}

async function loadUserStats() {
  if (!portalId.value || !portalToken.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/users/stats?hours=24`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.stats) userStats.value = data.stats;
}


async function loadKbCollections() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/collections`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) {
    kbCollections.value = data.items;
    await loadAllCollectionFiles();
  }
}

async function loadAllCollectionFiles() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const mapping: Record<number, number[]> = {};
  for (const c of kbCollections.value) {
    const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/collections/${c.id}/files`, {
      headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    });
    if (ok && data?.file_ids) {
      mapping[c.id] = data.file_ids.map((x: any) => Number(x)).filter((x: number) => Number.isFinite(x));
    }
  }
  kbCollectionFiles.value = mapping;
}

async function loadKbSmartFolders() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/smart-folders`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) {
    kbSmartFolders.value = data.items;
  }
}

async function loadKbTopics() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/topics`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data) {
    kbTopics.value = data.topics || [];
    kbTopicSuggestions.value = data.suggestions || [];
    smartThreshold.value = data.threshold || 5;
  }
}

async function createCollection() {
  if (!portalId.value || !portalToken.value || !newCollectionName.value.trim()) return;
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ name: newCollectionName.value.trim(), color: newCollectionColor.value.trim() || null }),
  });
  newCollectionName.value = '';
  newCollectionColor.value = '';
  await loadKbCollections();
}

function startEditCollection(c: { id: number; name: string }) {
  editingCollectionId.value = c.id;
  editingCollectionName.value = c.name;
}

async function saveCollectionName(collectionId: number) {
  if (!portalId.value || !portalToken.value) return;
  const name = editingCollectionName.value.trim();
  if (!name) return;
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/collections/${collectionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ name }),
  });
  editingCollectionId.value = null;
  editingCollectionName.value = '';
  await loadKbCollections();
}

function onAddToCollection(fileId: number, event: Event) {
  const target = event.target as HTMLSelectElement | null;
  if (!target) return;
  const id = Number(target.value);
  if (!id) return;
  addToCollection(id, fileId);
  target.value = '';
}

async function addToCollection(collectionId: number, fileId: number) {
  if (!portalId.value || !portalToken.value) return;
  if (!kbSettings.value.collections_multi_assign) {
    for (const c of kbCollections.value) {
      if (c.id === collectionId) continue;
      const ids = kbCollectionFiles.value[c.id] || [];
      if (ids.includes(fileId)) {
        await removeFromCollection(c.id, fileId);
      }
    }
  }
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/collections/${collectionId}/files`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ file_id: fileId }),
  });
  await loadAllCollectionFiles();
}

async function removeFromCollection(collectionId: number, fileId: number) {
  if (!portalId.value || !portalToken.value) return;
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/collections/${collectionId}/files/${fileId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  await loadAllCollectionFiles();
}

async function createSmartFolderFromTopic(topicId: string, name: string) {
  if (!portalId.value || !portalToken.value) return;
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/smart-folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ name, system_tag: topicId, rules_json: { type: 'topic', topic_id: topicId } }),
  });
  await loadKbSmartFolders();
}

function selectKbFilter(kind: 'all' | 'collection' | 'smart' | 'topic', id?: number | string) {
  kbFilter.value = { kind, id };
  if (kind === 'collection' && id) {
    kbLocationFilter.value = String(id);
  } else if (kind === 'all') {
    kbLocationFilter.value = 'all';
  }
}
async function loadKbFiles() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/files`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) {
    kbFiles.value = data.items;
    lastUpdated.value = new Date().toLocaleString();
  }
}

async function loadKbSources() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/sources`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) kbSources.value = data.items;
}

  async function loadKbSettings() {
    if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
    const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/settings`, {
      headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    });
    if (ok && data) {
      kbSettings.value = {
        embedding_model: data.embedding_model || 'EmbeddingsGigaR',
        chat_model: data.chat_model || 'GigaChat-2-Pro',
        prompt_preset: data.prompt_preset || 'auto',
        system_prompt_extra: data.system_prompt_extra || '',
        show_sources: data.show_sources !== false,
        sources_format: data.sources_format || 'detailed',
        collections_multi_assign: data.collections_multi_assign !== false,
        smart_folder_threshold: data.smart_folder_threshold ?? 5,
        allow_general: !!data.allow_general,
        strict_mode: data.strict_mode !== false,
        use_history: data.use_history !== false,
        use_cache: data.use_cache !== false,
        context_messages: data.context_messages ?? 6,
        context_chars: data.context_chars ?? 4000,
        retrieval_top_k: data.retrieval_top_k ?? 5,
        retrieval_max_chars: data.retrieval_max_chars ?? 4000,
        lex_boost: data.lex_boost ?? 0.12,
        temperature: data.temperature ?? 0.2,
        max_tokens: data.max_tokens ?? 700,
        top_p: data.top_p ?? '',
        presence_penalty: data.presence_penalty ?? '',
        frequency_penalty: data.frequency_penalty ?? '',
      };
    }
  }

async function loadKbModels() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/models`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) {
    const names = data.items.map((m: any) => String(m.id || m.name || m.model || '')).filter(Boolean);
    embedModels.value = names.filter((n: string) => n.toLowerCase().includes('embed'));
    chatModels.value = names.filter((n: string) => !n.toLowerCase().includes('embed'));
  }
}

  function toOptionalNumber(v: any) {
    if (v === '' || v === null || v === undefined) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function toOptionalInt(v: any) {
    if (v === '' || v === null || v === undefined) return null;
    const n = Number(v);
    return Number.isFinite(n) ? Math.trunc(n) : null;
  }

  async function saveKbSettings() {
    if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
    kbSettingsMessage.value = 'Сохранение...';
      const payload = {
      ...kbSettings.value,
      top_p: toOptionalNumber(kbSettings.value.top_p),
      presence_penalty: toOptionalNumber(kbSettings.value.presence_penalty),
      frequency_penalty: toOptionalNumber(kbSettings.value.frequency_penalty),
      temperature: toOptionalNumber(kbSettings.value.temperature),
      max_tokens: toOptionalInt(kbSettings.value.max_tokens),
      context_messages: toOptionalInt(kbSettings.value.context_messages),
      context_chars: toOptionalInt(kbSettings.value.context_chars),
      retrieval_top_k: toOptionalInt(kbSettings.value.retrieval_top_k),
      retrieval_max_chars: toOptionalInt(kbSettings.value.retrieval_max_chars),
      lex_boost: toOptionalNumber(kbSettings.value.lex_boost),
      show_sources: kbSettings.value.sources_format === 'none' ? false : kbSettings.value.show_sources,
      collections_multi_assign: kbSettings.value.collections_multi_assign,
      smart_folder_threshold: toOptionalInt(kbSettings.value.smart_folder_threshold),
    };
    const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(payload)
    });
    kbSettingsMessage.value = ok ? 'Сохранено' : (data?.error || 'Ошибка');
  }

async function loadTelegramSettings() {
  if (!portalId.value || !portalToken.value) return;
  const staffRes = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/telegram/staff`)
    : await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/telegram/staff`, {
        headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
  if (staffRes.ok && staffRes.data) {
    tgStaffEnabled.value = !!staffRes.data.enabled;
    tgStaffAllowUploads.value = !!staffRes.data.allow_uploads;
    tgStaffMasked.value = staffRes.data.token_masked || '';
    tgStaffWebhook.value = staffRes.data.webhook_url || '';
  }
  const clientRes = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/telegram/client`)
    : await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/telegram/client`, {
        headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
  if (clientRes.ok && clientRes.data) {
    tgClientEnabled.value = !!clientRes.data.enabled;
    tgClientAllowUploads.value = !!clientRes.data.allow_uploads;
    tgClientMasked.value = clientRes.data.token_masked || '';
    tgClientWebhook.value = clientRes.data.webhook_url || '';
  }
}

async function saveTelegram(kind: 'staff' | 'client') {
  if (!portalId.value || !portalToken.value) return;
  const payload = kind === 'staff'
    ? { bot_token: tgStaffToken.value || null, enabled: tgStaffEnabled.value, allow_uploads: tgStaffAllowUploads.value }
    : { bot_token: tgClientToken.value || null, enabled: tgClientEnabled.value, allow_uploads: tgClientAllowUploads.value };
  const res = isWebMode.value
    ? await webApiJson(`/v1/web/portals/${portalId.value}/telegram/${kind}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    : await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/telegram/${kind}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(payload),
      });
  const ok = res.ok;
  if (kind === 'staff') {
    tgStaffStatus.value = ok ? 'Сохранено' : (res.data?.detail || res.data?.error || 'Ошибка');
    if (ok) {
      tgStaffToken.value = '';
      tgStaffMasked.value = res.data?.token_masked || tgStaffMasked.value;
      tgStaffWebhook.value = res.data?.webhook_url || tgStaffWebhook.value;
    }
  } else {
    tgClientStatus.value = ok ? 'Сохранено' : (res.data?.detail || res.data?.error || 'Ошибка');
    if (ok) {
      tgClientToken.value = '';
      tgClientMasked.value = res.data?.token_masked || tgClientMasked.value;
      tgClientWebhook.value = res.data?.webhook_url || tgClientWebhook.value;
    }
  }
}

async function loadFlow() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/botflow/client`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (!ok) {
    flowMessage.value = data?.error || 'Не удалось загрузить сценарий';
    return;
  }
  const draft = data?.draft;
  if (draft) {
    flowDraft.value = {
      version: draft.version || 1,
      settings: {
        mood: draft.settings?.mood || 'нейтральный',
        custom_prompt: draft.settings?.custom_prompt || '',
        use_history: draft.settings?.use_history !== false,
      },
      nodes: draft.nodes || [],
      edges: (draft.edges || []).map((e: any) => ({ ...e, id: e.id || newNodeId() })),
    };
  } else {
    flowDraft.value = {
      version: 1,
      settings: { mood: 'нейтральный', custom_prompt: '', use_history: true },
      nodes: [
        { id: 'start', type: 'start', title: 'Start', x: 120, y: 120, config: {} },
        { id: 'kb', type: 'kb_answer', title: 'RAG Search', x: 380, y: 120, config: { pre_prompt: '' } },
      ],
      edges: [{ id: newNodeId(), from: 'start', to: 'kb' }],
    };
  }
}

async function saveFlowDraft() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  flowSaving.value = true;
  flowMessage.value = '';
  const payload = JSON.parse(JSON.stringify(flowDraft.value));
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/botflow/client`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ draft_json: payload }),
  });
  flowSaving.value = false;
  flowMessage.value = ok ? 'Сохранено' : (data?.error || 'Ошибка');
}

async function publishFlow() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  flowPublishing.value = true;
  flowMessage.value = '';
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/botflow/client/publish`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  flowPublishing.value = false;
  flowMessage.value = ok ? 'Опубликовано' : (data?.error || 'Ошибка');
}

async function runFlowTest() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value || !flowTestInput.value.trim()) return;
  flowTesting.value = true;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/botflow/client/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ text: flowTestInput.value, draft_json: flowDraft.value, state_json: flowTestState.value }),
  });
  flowTesting.value = false;
  if (!ok) {
    flowChatLog.value.push({ role: 'bot', text: data?.error || 'Ошибка теста' });
    return;
  }
  flowChatLog.value.push({ role: 'user', text: flowTestInput.value });
  flowChatLog.value.push({ role: 'bot', text: data?.text || '', trace: (data?.trace || []).map((t: any) => t.type || t.event).filter(Boolean).join(' → ') });
  flowTestState.value = data?.state || null;
  flowTestInput.value = '';
}

function resetFlowTest() {
  flowTestState.value = null;
  flowChatLog.value = [];
}

async function loadRecentDialogs() {
  if (!portalId.value || !portalToken.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/dialogs/recent?limit=80`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) {
    recentDialogs.value = data.items.map((it: any) => ({ body: it.body || '', direction: it.direction }));
  }
}

async function loadTopicSummaries() {
  if (!portalId.value || !portalToken.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/dialogs/summary`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.items) {
    topicSummaries.value = data.items;
  } else {
    topicSummaries.value = [];
  }
}

async function uploadFiles(files?: FileList | File[]) {
  if (!portalId.value || !portalToken.value) return;
  const input = fileInput.value;
  const list = files ? Array.from(files as any) : (input?.files ? Array.from(input.files) : []);
  if (!list.length) return;
  kbUploadMessage.value = 'Загрузка...';
  for (const f of list) {
    const fd = new FormData();
    fd.append('file', f);
    await fetch(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/files/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: fd,
    });
  }
  if (input) input.value = '';
  kbUploadMessage.value = 'Файлы загружены.';
  await loadKbFiles();
}

function openFilePicker() {
  if (!fileInput.value) return;
  fileInput.value.click();
}

async function onFilePickerChange() {
  if (!fileInput.value?.files?.length) return;
  await uploadFiles(fileInput.value.files);
}

async function onDropFiles(event: DragEvent) {
  event.preventDefault();
  if (!event.dataTransfer?.files?.length) return;
  await uploadFiles(event.dataTransfer.files);
}

function onDragOverFiles(event: DragEvent) {
  event.preventDefault();
}

function onDragStartFile(fileId: number, event: DragEvent) {
  if (!event.dataTransfer) return;
  const ids = selectedFileIds.value.includes(fileId) ? selectedFileIds.value.slice() : [fileId];
  draggingFileIds.value = ids;
  event.dataTransfer.setData('application/json', JSON.stringify(ids));
  event.dataTransfer.setData('text/plain', String(fileId));
  event.dataTransfer.effectAllowed = 'move';
}

function onDragEndFile() {
  draggingFileIds.value = [];
  dragOverCollectionId.value = null;
}

function onDragEnterCollection(collectionId: number) {
  dragOverCollectionId.value = collectionId;
}

function onDragLeaveCollection(collectionId: number) {
  if (dragOverCollectionId.value === collectionId) {
    dragOverCollectionId.value = null;
  }
}

async function saveBitrixCreds() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  bitrixCredsStatus.value = 'Сохранение...';
  const payload = {
    client_id: bitrixClientId.value,
    client_secret: bitrixClientSecret.value,
  };
  const res = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/bitrix/credentials`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(payload),
  });
  bitrixCredsStatus.value = res.ok ? 'Сохранено' : (res.data?.error || 'Ошибка');
}

async function onDropToCollection(collectionId: number, event: DragEvent) {
  event.preventDefault();
  dragOverCollectionId.value = null;
  const json = event.dataTransfer?.getData('application/json') || '';
  let ids: number[] = [];
  if (json) {
    try {
      ids = JSON.parse(json) as number[];
    } catch (e) {
      ids = [];
    }
  }
  if (!ids.length) {
    const idStr = event.dataTransfer?.getData('text/plain') || '';
    const fileId = Number(idStr);
    if (Number.isFinite(fileId) && fileId > 0) ids = [fileId];
  }
  if (!ids.length) return;
  if (collectionId === 0) {
    for (const id of ids) {
      for (const c of kbCollections.value) {
        const list = kbCollectionFiles.value[c.id] || [];
        if (list.includes(id)) {
          await removeFromCollection(c.id, id);
        }
      }
    }
    draggingFileIds.value = [];
    return;
  }
  for (const id of ids) {
    await addToCollection(collectionId, id);
  }
  draggingFileIds.value = [];
}

async function bulkMoveToCollection(event: Event) {
  const target = event.target as HTMLSelectElement | null;
  if (!target) return;
  const collectionId = Number(target.value);
  target.value = '';
  if (!collectionId) return;
  if (!selectedFileIds.value.length) return;
  for (const id of selectedFileIds.value) {
    await addToCollection(collectionId, id);
  }
  selectedFileIds.value = [];
}

async function bulkDeleteFiles() {
  if (!selectedFileIds.value.length) return;
  for (const id of selectedFileIds.value) {
    await deleteFile(id);
  }
  selectedFileIds.value = [];
}

async function bulkReindexFiles() {
  if (!selectedFileIds.value.length) return;
  for (const id of selectedFileIds.value) {
    await reindexFile(id);
  }
  selectedFileIds.value = [];
}

function toggleFileMenu(fileId: number) {
  openFileMenuId.value = openFileMenuId.value === fileId ? null : fileId;
}

function closeFileMenu() {
  openFileMenuId.value = null;
}

async function reindex() {
  if (!portalId.value || !portalToken.value) return;
  kbUploadMessage.value = 'Запуск индексации...';
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/reindex`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  kbUploadMessage.value = 'Очередь запущена.';
  await loadKbFiles();
}

async function addUrl() {
  if (!portalId.value || !portalToken.value || !kbUrl.value) return;
  kbUrlMessage.value = 'Добавление...';
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/sources/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ url: kbUrl.value })
  });
  if (!ok) {
    kbUrlMessage.value = data?.error || data?.detail || 'Ошибка';
    return;
  }
  kbUrlMessage.value = 'Добавлено.';
  kbUrl.value = '';
  await loadKbSources();
}

async function reindexFile(fileId: number) {
  if (!portalId.value || !portalToken.value) return;
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/files/${fileId}/reindex`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  await loadKbFiles();
}

async function deleteFile(fileId: number) {
  if (!portalId.value || !portalToken.value) return;
  await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/files/${fileId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  await loadKbFiles();
}

async function init() {
  statusMessage.value = 'Инициализация...';
  const params = new URLSearchParams(window.location.search || '');
  if (params.get('mode') === 'web') {
    isWebMode.value = true;
    const webPortalId = Number(localStorage.getItem('tb_web_portal_id') || 0);
    const webPortalToken = localStorage.getItem('tb_web_portal_token') || '';
    webSessionToken.value = localStorage.getItem('tb_web_session_token') || '';
    if (!webPortalId || !webPortalToken || !webSessionToken.value) {
      statusMessage.value = 'Нет данных веб-сессии. Войдите в веб-кабинет.';
      return;
    }
    portalId.value = webPortalId;
    portalToken.value = webPortalToken;
    const refreshed = await refreshWebSession();
    if (!refreshed) {
      statusMessage.value = 'Сессия истекла. Войдите в веб-кабинет заново.';
      return;
    }
    isPortalAdmin.value = true;
    sessionReady.value = true;
    statusMessage.value = 'Сессия активна.';
    await loadLinkRequests();
    await loadUsers();
    await loadAllowlist();
    await loadRecentDialogs();
    await loadTopicSummaries();
    await loadKbFiles();
    await loadKbSources();
    await loadKbSettings();
    await loadKbModels();
    await loadTelegramSettings();
    await loadFlow();
    setInterval(async () => {
      await loadRecentDialogs();
      await loadTopicSummaries();
      await loadKbFiles();
      await loadKbSources();
    }, 15000);
    return;
  }
  const b24 = (window as any).B24Js ? await (window as any).B24Js.initializeB24Frame() : null;
  const auth = b24?.auth?.getAuthData ? b24.auth.getAuthData() : null;
  if (!auth) {
    statusMessage.value = 'Нет данных авторизации. Обновите страницу.';
    return;
  }
  authRef.value = auth;
  const ok = await refreshSession(auth);
  if (!ok) {
    statusMessage.value = 'Не удалось получить сессию.';
    return;
  }
  statusMessage.value = 'Сессия активна.';
  await loadWebLinkStatus();
  await loadUsers();
  await loadAllowlist();
  await loadUserStats();
  await loadRecentDialogs();
  await loadTopicSummaries();
  if (isPortalAdmin.value) {
    await loadKbFiles();
    await loadKbSources();
    await loadKbSettings();
    await loadKbModels();
    await loadTelegramSettings();
  }
  setInterval(async () => {
    await loadRecentDialogs();
    await loadTopicSummaries();
    if (isPortalAdmin.value) {
      await loadKbFiles();
      await loadKbSources();
    }
  }, 15000);
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown);
  window.addEventListener('mouseup', onFlowCanvasMouseUp);
  window.addEventListener('mousemove', (evt) => {
    if (draggingNodeId.value || isPanning.value || connectingFrom.value) {
      onFlowCanvasMouseMove(evt);
    }
  });
  init();
});
</script>



