import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import b24UiPlugin from '@bitrix24/b24ui-nuxt/vue-plugin';
import App from './App.vue';
import './style.css';

const router = createRouter({
  history: createWebHistory(),
  routes: []
});

const app = createApp(App);
app.use(router);
app.use(b24UiPlugin);
app.mount('#app');
