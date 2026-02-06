import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import bitrix24UIPluginVite from '@bitrix24/b24ui-nuxt/vite';

export default defineConfig({
  base: '/iframe/',
  plugins: [vue(), bitrix24UIPluginVite()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
});
