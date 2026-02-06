<template>
  <div class="tb-shell">
    <aside class="tb-sidebar">
      <div class="tb-logo">Teachbase AI</div>
      <nav class="tb-nav">
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'overview' }" @click="currentTab = 'overview'">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M4 10.5l8-6 8 6V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1v-9.5Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          Обзор
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'kb' }" @click="currentTab = 'kb'">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 4h10a4 4 0 0 1 4 4v12H9a4 4 0 0 0-4 4V4Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 8h6M9 12h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          База знаний
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'sources' }" @click="currentTab = 'sources'">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Источники данных
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'users' }" @click="currentTab = 'users'">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z" stroke="currentColor" stroke-width="1.6"/><path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Пользователи и доступы
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'analytics' }" @click="currentTab = 'analytics'">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 12v6M12 8v10M19 4v14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Аналитика
        </button>
        <button class="tb-nav-item" :class="{ 'is-active': currentTab === 'settings' }" @click="currentTab = 'settings'">
          <span class="tb-nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" stroke="currentColor" stroke-width="1.6"/><path d="M4 12h2m12 0h2M12 4v2m0 12v2M6 6l1.5 1.5M16.5 16.5 18 18M18 6l-1.5 1.5M7.5 16.5 6 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          Настройки
        </button>
      </nav>
    </aside>

    <main class="tb-content">
      <header class="tb-top">
        <div>
          <h1 class="tb-h1">{{ tabTitle }}</h1>
          <p class="tb-sub">Управление доступом и базой знаний портала.</p>
        </div>
        <div class="tb-status" v-if="!sessionReady">{{ statusMessage }}</div>
      </header>

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
          <h2 class="tb-card-title">Доступ</h2>
          <div v-if="accessWarning" class="tb-alert">{{ accessWarning }}</div>
          <input v-model="userSearch" class="tb-input" type="search" placeholder="Поиск по имени..." />
          <div class="tb-userlist" v-if="filteredUsers.length">
            <label v-for="u in filteredUsers" :key="u.id" class="tb-user">
              <input type="checkbox" :value="u.id" v-model="selectedUsers" />
              <span class="tb-user-name">{{ u.name }}</span>
            </label>
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
      </section>

      <section v-if="currentTab === 'kb' && isPortalAdmin" class="tb-grid" key="kb">
        <div class="tb-card">
          <h2 class="tb-card-title">Загрузка файлов</h2>
          <div class="tb-field">
            <label>Файлы</label>
            <input ref="fileInput" type="file" multiple class="tb-input tb-file-input" />
          </div>
          <div class="tb-actions">
            <button class="tb-btn tb-btn-primary" @click="uploadFiles">Загрузить</button>
            <button class="tb-btn" @click="reindex">Переиндексировать</button>
            <span class="tb-muted" v-if="kbUploadMessage">{{ kbUploadMessage }}</span>
          </div>
        </div>

        <div class="tb-card">
          <h2 class="tb-card-title">Файлы</h2>
          <div class="tb-empty" v-if="kbFiles.length === 0">Файлов пока нет.</div>
          <div class="tb-list" v-else>
            <div v-for="f in kbFiles" :key="f.id" class="tb-row">
              <div class="tb-row-body">
                <div class="tb-row-text">{{ f.filename }}</div>
                <div class="tb-muted">{{ f.status }} · {{ f.created_at }}</div>
                <div class="tb-alert" v-if="f.error_message">ошибка: {{ f.error_message }}</div>
                <div class="tb-actions">
                  <button class="tb-btn" @click="reindexFile(f.id)">Переиндексировать</button>
                  <button class="tb-btn tb-btn-danger" @click="deleteFile(f.id)">Удалить</button>
                </div>
              </div>
            </div>
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
            <div class="tb-field">
              <label>Embedding model</label>
              <select v-model="kbSettings.embedding_model">
                <option value="">—</option>
                <option v-for="m in embedModels" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <div class="tb-field">
              <label>Chat model</label>
              <select v-model="kbSettings.chat_model">
                <option value="">—</option>
                <option v-for="m in chatModels" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <div class="tb-field">
              <label>Пресет ответа</label>
              <select v-model="kbSettings.prompt_preset">
                <option value="auto">Авто</option>
                <option value="summary">Краткий обзор</option>
                <option value="faq">FAQ</option>
                <option value="timeline">Таймлайн</option>
              </select>
            </div>
            <div class="tb-actions">
              <button class="tb-btn tb-btn-primary" @click="saveKbSettings">Сохранить</button>
              <span class="tb-muted" v-if="kbSettingsMessage">{{ kbSettingsMessage }}</span>
            </div>
          </div>
        </div>
      </section>

    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

type KbFile = { id: number; filename: string; status: string; error_message?: string; created_at?: string };

type KbSource = { id: number; url: string; status: string; created_at?: string };

type DialogItem = { body?: string; direction?: 'tx' | 'rx' };
type KbSettings = { embedding_model: string; chat_model: string; prompt_preset: string };

const statusMessage = ref('Загрузка...');
const sessionReady = ref(false);
const isPortalAdmin = ref(false);
const portalId = ref<number | null>(null);
const portalToken = ref<string>('');
const authRef = ref<any>(null);
const accessWarning = ref<string>('');

const users = ref<{ id: number; name: string }[]>([]);
const userSearch = ref('');
const selectedUsers = ref<number[]>([]);
const userStats = ref<Record<number, number>>({});
const accessSaveStatus = ref<string>('');
const accessSaving = ref(false);

const kbFiles = ref<KbFile[]>([]);
const kbSources = ref<KbSource[]>([]);
const kbUrl = ref('');
const kbUrlMessage = ref('');
const kbUploadMessage = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
const lastUpdated = ref('—');

const recentDialogs = ref<DialogItem[]>([]);
type TopicSummary = { topic: string; score?: number | null };
const topicSummaries = ref<TopicSummary[]>([]);
const currentTab = ref<'overview' | 'kb' | 'sources' | 'users' | 'analytics' | 'settings'>('overview');
const kbSettings = ref<KbSettings>({ embedding_model: '', chat_model: '', prompt_preset: 'auto' });
const embedModels = ref<string[]>([]);
const chatModels = ref<string[]>([]);
const kbSettingsMessage = ref('');

const tabTitle = computed(() => {
  switch (currentTab.value) {
    case 'kb': return 'База знаний';
    case 'sources': return 'Источники данных';
    case 'users': return 'Пользователи и доступы';
    case 'analytics': return 'Аналитика';
    case 'settings': return 'Настройки';
    default: return 'Обзор';
  }
});

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

const base = window.location.origin;

async function apiJson(url: string, opts: RequestInit = {}) {
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => null);
  if ((r.status === 401 || r.status === 403) && authRef.value) {
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

async function loadUsers() {
  if (!portalId.value || !portalToken.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/users?portal_id=${portalId.value}`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (!ok) {
    accessWarning.value = data?.detail || data?.error || 'Не удалось загрузить пользователей.';
    return;
  }
  users.value = (data.users || []).map((u: any) => ({ id: Number(u.id), name: `${u.name || ''} ${u.last_name || ''}`.trim() || u.email || `ID ${u.id}` }));
}

async function loadAllowlist() {
  if (!portalId.value || !portalToken.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/access/users`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.user_ids) {
    selectedUsers.value = data.user_ids.map((id: any) => Number(id));
  }
}

async function saveAccess() {
  if (!portalId.value || !portalToken.value) return;
  accessWarning.value = '';
  accessSaving.value = true;
  accessSaveStatus.value = 'Сохраняю...';
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/access/users`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ user_ids: selectedUsers.value })
  });
  if (!ok) {
    accessWarning.value = data?.detail || data?.error || 'Не удалось сохранить доступ.';
    accessSaveStatus.value = 'Ошибка';
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
  accessSaving.value = false;
}

async function loadUserStats() {
  if (!portalId.value || !portalToken.value) return;
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/users/stats?hours=24`, {
    headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (ok && data?.stats) userStats.value = data.stats;
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
      prompt_preset: data.prompt_preset || 'auto'
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

async function saveKbSettings() {
  if (!portalId.value || !portalToken.value || !isPortalAdmin.value) return;
  kbSettingsMessage.value = 'Сохранение...';
  const { ok, data } = await apiJson(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(kbSettings.value)
  });
  kbSettingsMessage.value = ok ? 'Сохранено' : (data?.error || 'Ошибка');
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

async function uploadFiles() {
  if (!portalId.value || !portalToken.value) return;
  const input = fileInput.value;
  if (!input || !input.files || input.files.length === 0) return;
  kbUploadMessage.value = 'Загрузка...';
  for (const f of Array.from(input.files)) {
    const fd = new FormData();
    fd.append('file', f);
    await fetch(`${base}/api/v1/bitrix/portals/${portalId.value}/kb/files/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${portalToken.value}`, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: fd,
    });
  }
  input.value = '';
  kbUploadMessage.value = 'Файлы загружены.';
  await loadKbFiles();
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

onMounted(init);
</script>



