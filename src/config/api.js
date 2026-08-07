/**
 * 全局 API 配置（C/S 用户端与 B/S 管理端共用）
 *
 * 服务器地址解析优先级：
 *   1. localStorage['melodybox_api_base'] —— 运行时覆盖（设置页可配）
 *   2. VITE_API_BASE 环境变量 —— 构建期配置
 *   3. 默认 http://127.0.0.1:5000 —— 本地 C/S 部署
 *
 * 音频服务器（Electron 主进程 51234）与本机绑定，不随 API 地址变化；
 * 浏览器（B/S 管理端）不需要音频播放，因此不受影响。
 */

const DEFAULT_API_BASE = 'http://127.0.0.1:5000'

export function resolveApiBase() {
  try {
    const saved = localStorage.getItem('melodybox_api_base')
    if (saved && saved.trim()) return saved.trim().replace(/\/+$/, '')
  } catch {}
  return (import.meta.env.VITE_API_BASE || DEFAULT_API_BASE).replace(/\/+$/, '')
}

export const API_BASE = resolveApiBase()

/** 拼接后端接口地址：apiUrl('/api/music/songs') */
export function apiUrl(path) {
  const p = String(path || '').replace(/^\/+/, '')
  return `${API_BASE}/${p}`
}

/** 拼接封面地址（本地路径 → 后端封面接口；已是 http 则原样返回） */
export function coverUrl(path) {
  if (!path) return null
  if (/^https?:\/\//i.test(path)) return path
  return apiUrl(`/api/music/cover?path=${encodeURIComponent(path)}`)
}

// ==================== 音频服务（Electron 主进程） ====================

let audioPort = 51234
let portInitialized = false

/** 从 Electron 主进程获取音频服务器端口（浏览器模式回退默认 51234） */
export async function initAudioPort() {
  if (portInitialized) return
  portInitialized = true
  if (window.electronAPI?.getAudioServerPort) {
    try {
      const port = await window.electronAPI.getAudioServerPort()
      if (port) audioPort = port
    } catch {}
  }
}

/** 本地文件路径 → 音频流 URL（Electron 音频服务器，固定本机） */
export function audioUrl(filePath) {
  return `http://127.0.0.1:${audioPort}/audio?path=${encodeURIComponent(filePath)}`
}

/** 云端歌曲 → Flask 模拟网络流 */
export function cloudStreamUrl(filePath) {
  return apiUrl(`/api/cloud/stream?path=${encodeURIComponent(filePath)}`)
}

/** 构造携带 Bearer token 的请求头 */
export function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}
