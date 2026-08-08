import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { apiUrl } from '@/config/api'

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
  desktop_lyrics_view_lines: 'desktopLyricsViewLines',
  enable_dynamic_bg: 'enableDynamicBg',
  enable_audio_rhythm: 'enableAudioRhythm',
  weather_private_key: 'weatherPrivateKey',
  weather_credential_id: 'weatherCredentialId',
  weather_project_id: 'weatherProjectId',
  weather_api_host: 'weatherApiHost',
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
  const showVisualizer = ref(true)
  // 律动响应帧率（30/60）；逐字动画帧率自适应（用满屏幕刷新率）
  const rhythmFps = ref(Number(localStorage.getItem('melodybox_rhythm_fps')) || 30)
  const fpsAdaptive = ref(localStorage.getItem('melodybox_fps_adaptive') === '1')
  const measuredRefresh = ref(Number(localStorage.getItem('melodybox_refresh_hz')) || 60)

  // 系统设置
  const autoScan = ref(false)
  const language = ref('zh-CN')

  // 桌面歌词设置
  const desktopLyricsFontSize = ref(24)
  const desktopLyricsActiveScale = ref(120)
  const desktopLyricsTransScale = ref(60)
  const desktopLyricsViewLines = ref(2)

  // 动态流光背景（封面主色驱动的渐变流动效果）
  const enableDynamicBg = ref(true)
  const enableAudioRhythm = ref(true)

  // 天气 API 配置（Ed25519 JWT）
  const weatherPrivateKey = ref('')
  const weatherCredentialId = ref('')
  const weatherProjectId = ref('')
  const weatherApiHost = ref('api.qweather.com')

  // 调试模式（前端 only，不持久化到后端）
  const debugMode = ref(false)

  // 画质档位（2.13：自动/低/中/高/自定义）
  const qualityPreset = ref('custom')

  /** 有效逐字动画帧率：自适应模式用实测刷新率（夹在 24–240），否则用设定值 */
  const effectiveWordAnimFps = computed(() => {
    if (fpsAdaptive.value) {
      return Math.min(Math.max(measuredRefresh.value, 24), 240)
    }
    return wordAnimFps.value
  })

  function _persistPerfPrefs() {
    try {
      localStorage.setItem('melodybox_rhythm_fps', String(rhythmFps.value))
      localStorage.setItem('melodybox_fps_adaptive', fpsAdaptive.value ? '1' : '0')
      localStorage.setItem('melodybox_refresh_hz', String(measuredRefresh.value))
    } catch {}
  }

  /**
   * 用 rAF 采样实测屏幕刷新率（60 帧时间戳中位数）。
   * 自适应帧率模式下自动调用；显示器变更时可手动重测。
   */
  function detectRefreshRate() {
    return new Promise((resolve) => {
      // 1) Electron 主进程 screen API：准确刷新率
      if (window.electronAPI?.getRefreshRate) {
        window.electronAPI.getRefreshRate().then((hz) => {
          if (hz && hz >= 24) {
            measuredRefresh.value = Math.min(1000, Math.max(24, hz))
            _persistPerfPrefs()
            resolve(measuredRefresh.value)
            return
          }
          _probeWithRaf(resolve)
        }).catch(() => _probeWithRaf(resolve))
        return
      }
      // 2) 浏览器兜底：rAF 采样
      _probeWithRaf(resolve)
    })
  }

  /** 浏览器兜底：rAF 采样实测刷新率（等窗口可见，最多 3 次取最大，规避启动期限流） */
  function _probeWithRaf(resolve) {
    let attempts = 0
    let best = 0
    const run = () => {
      if (document.hidden) {
        window.addEventListener('visibilitychange', function once() {
          window.removeEventListener('visibilitychange', once)
          run()
        }, { once: true })
        return
      }
      const deltas = []
      let last = null
      let raf = 0
      const tick = (now) => {
        if (last !== null) deltas.push(now - last)
        last = now
        if (deltas.length < 120) {
          raf = requestAnimationFrame(tick)
        } else {
          cancelAnimationFrame(raf)
          deltas.sort((a, b) => a - b)
          const median = deltas[Math.floor(deltas.length / 2)]
          const hz = Math.min(1000, Math.max(1, Math.round(1000 / Math.max(median, 1))))
          best = Math.max(best, hz)
          attempts += 1
          if (attempts < 3 && hz <= 60) {
            setTimeout(run, 400)
          } else {
            measuredRefresh.value = best
            _persistPerfPrefs()
            resolve(best)
          }
        }
      }
      raf = requestAnimationFrame(tick)
    }
    run()
  }

  function ensureRefreshDetected() {
    if (fpsAdaptive.value && (!measuredRefresh.value || measuredRefresh.value <= 0)) {
      detectRefreshRate()
    }
  }

  let _loaded = false
  let _saveTimer = null

  async function loadSettings() {
    try {
      const res = await fetch(apiUrl('/api/settings'))
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
      showVisualizer.value = data.showVisualizer ?? true
      autoScan.value = !!data.autoScan
      language.value = data.language ?? 'zh-CN'
      desktopLyricsFontSize.value = data.desktopLyricsFontSize ?? 24
      desktopLyricsActiveScale.value = data.desktopLyricsActiveScale ?? 120
      desktopLyricsTransScale.value = data.desktopLyricsTransScale ?? 60
      desktopLyricsViewLines.value = data.desktopLyricsViewLines ?? 2
      enableDynamicBg.value = data.enableDynamicBg ?? true
      enableAudioRhythm.value = data.enableAudioRhythm ?? true
      weatherPrivateKey.value = data.weatherPrivateKey ?? ''
      weatherCredentialId.value = data.weatherCredentialId ?? ''
      weatherProjectId.value = data.weatherProjectId ?? ''
      weatherApiHost.value = data.weatherApiHost ?? 'api.qweather.com'
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
        body.showVisualizer = showVisualizer.value ? 1 : 0
        body.autoScan = autoScan.value ? 1 : 0
        body.language = language.value
        body.desktopLyricsFontSize = desktopLyricsFontSize.value
        body.desktopLyricsActiveScale = desktopLyricsActiveScale.value
        body.desktopLyricsTransScale = desktopLyricsTransScale.value
        body.desktopLyricsViewLines = desktopLyricsViewLines.value
        body.enableDynamicBg = enableDynamicBg.value ? 1 : 0
        body.enableAudioRhythm = enableAudioRhythm.value ? 1 : 0
        body.weatherPrivateKey = weatherPrivateKey.value || ''
        body.weatherCredentialId = weatherCredentialId.value || ''
        body.weatherProjectId = weatherProjectId.value || ''
        body.weatherApiHost = weatherApiHost.value || 'api.qweather.com'
        await fetch(apiUrl('/api/settings'), {
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

  // 手动改任意效果开关 → 档位自动切为"自定义"
  let _applyingPreset = false
  watch(
    [enableLyricsBlur, enableDominoScroll, enableWordLift, wordAnimFps,
     enableDynamicBg, enableAudioRhythm, showVisualizer,
     rhythmFps, fpsAdaptive],
    () => {
      if (_applyingPreset) return
      if (qualityPreset.value !== 'custom') qualityPreset.value = 'custom'
    }
  )

  // 律动/自适应偏好持久化到 localStorage（前端 only）
  watch([rhythmFps, fpsAdaptive, measuredRefresh], _persistPerfPrefs)

  /** 应用画质预设档位（low / medium / high） */
  function applyQualityPreset(preset) {
    const map = {
      high: { enableLyricsBlur: true, enableDominoScroll: true, enableWordLift: true, wordAnimFps: 60, fpsAdaptive: true, rhythmFps: 60, enableDynamicBg: true, enableAudioRhythm: true, showVisualizer: true },
      medium: { enableLyricsBlur: true, enableDominoScroll: true, enableWordLift: true, wordAnimFps: 60, fpsAdaptive: false, rhythmFps: 30, enableDynamicBg: true, enableAudioRhythm: false, showVisualizer: true },
      low: { enableLyricsBlur: false, enableDominoScroll: false, enableWordLift: false, wordAnimFps: 30, fpsAdaptive: false, rhythmFps: 30, enableDynamicBg: false, enableAudioRhythm: false, showVisualizer: false },
    }
    const cfg = map[preset]
    if (!cfg) return
    _applyingPreset = true
    enableLyricsBlur.value = cfg.enableLyricsBlur
    enableDominoScroll.value = cfg.enableDominoScroll
    enableWordLift.value = cfg.enableWordLift
    wordAnimFps.value = cfg.wordAnimFps
    fpsAdaptive.value = cfg.fpsAdaptive
    rhythmFps.value = cfg.rhythmFps
    enableDynamicBg.value = cfg.enableDynamicBg
    enableAudioRhythm.value = cfg.enableAudioRhythm
    showVisualizer.value = cfg.showVisualizer
    qualityPreset.value = preset
    _applyingPreset = false
    ensureRefreshDetected()
    saveSettingsImmediate()
  }

  // 先尝试 localStorage 迁移到后端
  loadSettings()
  ensureRefreshDetected()

  return {
    theme, accentColor, blurStrength, followSystemTheme,
    lyricsFontSize, lyricsFontWeight,
    lyricsTransScale, lyricsActiveScale,
    enableLyricsBlur, enableDominoScroll, enableWordLift, wordAnimFps,
    showVisualizer,
    rhythmFps, fpsAdaptive, measuredRefresh, effectiveWordAnimFps,
    autoScan, language,
    desktopLyricsFontSize, desktopLyricsActiveScale, desktopLyricsTransScale, desktopLyricsViewLines,
    enableDynamicBg,
    enableAudioRhythm,
    qualityPreset,
    weatherPrivateKey,
    weatherCredentialId,
    weatherProjectId,
    weatherApiHost,
    debugMode,
    loadSettings, saveSettings, saveSettingsImmediate, resetLyricsDefaults,
    applyQualityPreset,
    detectRefreshRate, ensureRefreshDetected,
  }
})
