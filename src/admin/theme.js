// B/S 管理端主题：浅色 / 深色 / 跟随系统
// 独立于 Electron 客户端设置，仅作用于管理后台页面
import { ref, computed } from 'vue'

const STORAGE_KEY = 'melodybox.admin-theme'
const VALID = ['light', 'dark', 'system']

function normalize(value) {
  return VALID.includes(value) ? value : 'system'
}

const media = window.matchMedia('(prefers-color-scheme: dark)')

export const themeMode = ref(normalize(localStorage.getItem(STORAGE_KEY)))
const systemDark = ref(media.matches)

// 当前实际生效的主题（跟随系统时解析系统色彩方案）
export const resolvedTheme = computed(() =>
  themeMode.value === 'system' ? (systemDark.value ? 'dark' : 'light') : themeMode.value
)

export function applyTheme() {
  const html = document.documentElement
  const actual = resolvedTheme.value
  html.setAttribute('data-theme', actual)
  html.classList.toggle('dark', actual === 'dark')
}

export function setThemeMode(mode) {
  themeMode.value = normalize(mode)
  localStorage.setItem(STORAGE_KEY, themeMode.value)
  applyTheme()
}

media.addEventListener('change', (e) => {
  systemDark.value = e.matches
  if (themeMode.value === 'system') applyTheme()
})

// 模块加载即生效（admin.html 内联脚本已在首屏前设置过一次，避免闪白/闪黑）
applyTheme()
