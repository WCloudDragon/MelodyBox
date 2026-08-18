import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync, writeFileSync } from 'fs'

// 开发端口由 scripts/find-port.js 预先探测并写入 .vite-port
function readDevPort() {
  try {
    const value = Number.parseInt(readFileSync(resolve(__dirname, '.vite-port'), 'utf8').trim(), 10)
    if (Number.isInteger(value) && value > 0 && value < 65536) return value
  } catch {}
  return 5200
}

// Vite 监听成功后写入 .vite-ready，供 wait-on 判断服务已就绪
function writeDevPortPlugin() {
  return {
    name: 'write-dev-ready',
    configureServer(server) {
      server.httpServer?.once('listening', () => {
        writeFileSync(resolve(__dirname, '.vite-ready'), '1')
      })
    }
  }
}

export default defineConfig({
  plugins: [vue(), writeDevPortPlugin()],
  base: './',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '127.0.0.1',
    port: readDevPort(),
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
    assetsDir: 'assets',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        admin: resolve(__dirname, 'admin.html'),
      },
    },
  }
})
