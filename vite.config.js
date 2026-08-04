import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: './',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5200,
    strictPort: true,
    // 预热首屏入口模块：Vite 启动即预编译，Electron 打开时无需现编译
    warmup: {
      clientFiles: [
        './src/main.js',
        './src/App.vue',
        './src/router/index.js',
        './src/stores/player.js',
        './src/stores/library.js',
        './src/stores/ai.js',
        './src/views/HomeView.vue',
        './src/views/LibraryView.vue'
      ]
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
