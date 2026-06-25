import { defineStore } from 'pinia'
import { ref } from 'vue'

const API_BASE = 'http://127.0.0.1:5000/api/settings'

// 后端 snake_case ↔ 前端 camelCase 映射
const SNAKE_TO_CAMEL = {
  accent_color: 'accentColor', blur_strength: 'blurStrength',
  follow_system_theme: 'followSystemTheme', show_lyrics: 'showLyrics',
  lyrics_font_size: 'lyricsFontSize', lyrics_font_weight: 'lyricsFontWeight',
  lyrics_trans_scale: 'lyricsTransScale', lyrics_active_scale: 'lyricsActiveScale',
  enable_lyrics_blur: 'enableLyricsBlur', enable_domino_scroll: 'enableDominoScroll',
  enable_word_lift: 'enableWordLift', word_anim_fps: 'wordAnimFps',
  show_visualizer: 'showVisualizer', auto_scan: 'autoScan',
  desktop_lyrics_font_size: 'desktopLyricsFontSize',
  desktop_lyrics_active_scale: 'desktopLyricsActiveScale',
  desktop_lyrics_trans_scale: 'desktopLyricsTransScale',
}
const CAMEL_TO_SNAKE = Object.fromEntries(
  Object.entries(SNAKE_TO_CAMEL).map(([k, v]) => [v, k])
)

export const useSettingsStore = defineStore('settings', () => {
  // 外观设置
  const theme = ref('dark')
  const accentColor = ref('#6366f1')
  const blurStrength = ref('10px')
  const followSystemTheme = ref(false)

  // 播放界面设置
  const lyricsFontSize = ref(32)
  const lyricsFontWeight = ref(700)
  const lyricsTransScale = ref(60)
  const lyricsActiveScale = ref(115)

  // 动画效果开关
  const enableLyricsBlur = ref(true)
  const enableDominoScroll = ref(true)
  const enableWordLift = ref(true)
  const wordAnimFps = ref(60)

  // 系统设置
  const autoScan = ref(false)
  const language = ref('zh-CN')

  // 桌面歌词设置
  const desktopLyricsFontSize = ref(24)
  const desktopLyricsActiveScale = ref(120)
  const desktopLyricsTransScale = ref(60)

  let _loaded = false
  let _saveTimer = null

  async function loadSettings() {
    try {
      const res = await fetch(API_BASE)
      if (!res.ok) return
      const data = await res.json()
      theme.value = data.theme ?? 'dark'
      accentColor.value = data.accentColor ?? '#6366f1'
      blurStrength.value = data.blurStrength ?? '10px'
      followSystemTheme.value = !!data.followSystemTheme
      lyricsFontSize.value = data.lyricsFontSize ?? 32
      lyricsFontWeight.value = data.lyricsFontWeight ?? 700
      lyricsTransScale.value = data.lyricsTransScale ?? 60
      lyricsActiveScale.value = data.lyricsActiveScale ?? 115
      enableLyricsBlur.value = !!data.enableLyricsBlur
      enableDominoScroll.value = !!data.enableDominoScroll
      enableWordLift.value = !!data.enableWordLift
      wordAnimFps.value = data.wordAnimFps ?? 60
      autoScan.value = !!data.autoScan
      language.value = data.language ?? 'zh-CN'
      desktopLyricsFontSize.value = data.desktopLyricsFontSize ?? 24
      desktopLyricsActiveScale.value = data.desktopLyricsActiveScale ?? 120
      desktopLyricsTransScale.value = data.desktopLyricsTransScale ?? 60
      _loaded = true
    } catch {}
  }

  function saveSettings() {
    if (!_loaded) return
    // 防抖 500ms
    clearTimeout(_saveTimer)
    _saveTimer = setTimeout(async () => {
      try {
        const body = {}
        body.theme = theme.value
        body.accentColor = accentColor.value
        body.blurStrength = blurStrength.value
        body.followSystemTheme = followSystemTheme.value ? 1 : 0
        body.lyricsFontSize = lyricsFontSize.value
        body.lyricsFontWeight = lyricsFontWeight.value
        body.lyricsTransScale = lyricsTransScale.value
        body.lyricsActiveScale = lyricsActiveScale.value
        body.enableLyricsBlur = enableLyricsBlur.value ? 1 : 0
        body.enableDominoScroll = enableDominoScroll.value ? 1 : 0
        body.enableWordLift = enableWordLift.value ? 1 : 0
        body.wordAnimFps = wordAnimFps.value
        body.autoScan = autoScan.value ? 1 : 0
        body.language = language.value
        body.desktopLyricsFontSize = desktopLyricsFontSize.value
        body.desktopLyricsActiveScale = desktopLyricsActiveScale.value
        body.desktopLyricsTransScale = desktopLyricsTransScale.value
        await fetch(API_BASE, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        })
      } catch {}
    }, 500)
  }

  function saveSettingsImmediate() {
    clearTimeout(_saveTimer)
    _saveTimer = null
    saveSettings()
  }

  function resetLyricsDefaults() {
    lyricsFontSize.value = 32
    lyricsFontWeight.value = 700
    lyricsTransScale.value = 60
    lyricsActiveScale.value = 115
    saveSettingsImmediate()
  }

  // 先尝试 localStorage 迁移到后端
  loadSettings()

  return {
    theme, accentColor, blurStrength, followSystemTheme,
    lyricsFontSize, lyricsFontWeight,
    lyricsTransScale, lyricsActiveScale,
    enableLyricsBlur, enableDominoScroll, enableWordLift, wordAnimFps,
    autoScan, language,
    desktopLyricsFontSize, desktopLyricsActiveScale, desktopLyricsTransScale,
    loadSettings, saveSettings, resetLyricsDefaults
  }
})
