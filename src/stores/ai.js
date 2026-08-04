import { defineStore } from 'pinia'
import { ref } from 'vue'

const AI_BASE = 'http://127.0.0.1:5000/api/ai'
const STATS_BASE = 'http://127.0.0.1:5000/api/stats'

// 首页封面预览缓存（纯展示数据，5 分钟）
const PREVIEWS_KEY = 'melodybox_ai_previews'
const PREVIEWS_TTL = 5 * 60 * 1000
// 封面颜色缓存
const COLOR_CACHE_KEY = 'melodybox_cover_colors'

/**
 * AI 推荐 store（重构版）
 *
 * 变化：
 * - 推荐列表不再在前端做 localStorage 缓存，改由后端服务端缓存负责
 *   （缓存 key 含画像版本 + 向量代次，自动失效）；
 * - 新增 reportFeedback：播放/跳过/听完/喜欢/不喜欢 → 画像反馈闭环；
 * - 首页封面预览保留本地缓存（展示数据），与推荐列表同源由后端保证。
 */
export const useAiStore = defineStore('ai', () => {
  const recommendations = ref([])
  const isLoaded = ref(false)
  const isLoading = ref(false)

  // 当前推荐模式
  const currentMode = ref('comprehensive')
  const currentSub = ref(null)

  // 首页封面预览数据（单一数据源）
  const previews = ref({})
  const previewsLoading = ref(false)
  const coverColors = ref({})

  // Embedding 状态
  const embeddingStatus = ref({
    total: 0, done: 0, pending: 0, ready: false, st_available: null,
    mood_scores_ready: false, audio_done: 0, audio_total: 0,
    audio_available: false, audio_processing: false, text_processing: false,
    text_provider: 'idle', provider: 'cpu',
    e5_download: { status: 'idle', percent: 0 },
    mert_download: { status: 'idle', percent: 0 },
  })
  const isGenerating = ref(false)

  const downloadProgress = ref({
    status: 'idle', percent: 0, downloaded_mb: 0, total_mb: 0, message: '',
  })
  const isDownloading = ref(false)

  // ==================== 推荐列表（服务端缓存） ====================

  async function loadRecommendations(limit = 20) {
    isLoading.value = true
    try {
      let url = `${AI_BASE}/recommend?limit=${limit}&mode=${currentMode.value}`
      if (currentSub.value != null) {
        url += `&${currentSub.value}`
      }
      const res = await fetch(url)
      if (!res.ok) {
        recommendations.value = []
        isLoaded.value = true
        return
      }
      const data = await res.json()
      for (const s of data) {
        s.path = s.file_path
        s.cover = s.cover_url
        s.url = `http://127.0.0.1:51234/audio?path=${encodeURIComponent(s.file_path)}`
      }
      recommendations.value = data
      isLoaded.value = true
    } catch {
      recommendations.value = []
      isLoaded.value = true
    } finally {
      isLoading.value = false
    }
  }

  async function setMode(mode, subValue = null) {
    currentMode.value = mode
    currentSub.value = subValue
    await loadRecommendations()
  }

  // ==================== 反馈闭环 ====================

  /**
   * 上报播放反馈事件（skip / complete / like / dislike）。
   * 后端写入 events 表并异步刷新画像。
   */
  async function reportFeedback(event, track, extra = {}) {
    if (!track) return
    try {
      await fetch(`${STATS_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: track.path || '',
          title: track.title || '',
          artist: track.artist || '',
          album: track.album || '',
          event,
          duration_ratio: extra.durationRatio ?? null,
        }),
      })
    } catch {
      // 静默失败，不影响播放
    }
  }

  // ==================== 首页封面预览 ====================

  function _loadPreviewsCache() {
    try {
      const raw = localStorage.getItem(PREVIEWS_KEY)
      if (!raw) return null
      const cached = JSON.parse(raw)
      if (cached.expireAt > Date.now()) return cached.data
    } catch {}
    return null
  }

  function _savePreviewsCache(data) {
    try {
      localStorage.setItem(PREVIEWS_KEY, JSON.stringify({
        data, expireAt: Date.now() + PREVIEWS_TTL,
      }))
    } catch {}
  }

  function updateCoverFromRecommend(mode, mood, firstTrack) {
    if (!firstTrack) return
    const cover = firstTrack.cover_url || ''
    if (!cover) return
    const cardKey = mode === 'comprehensive' ? 'daily'
      : mode === 'hidden_gem' ? 'hidden_gem'
      : mood ? `mood_${mood}` : null
    if (!cardKey) return

    const entry = { title: firstTrack.title || '', artist: firstTrack.artist || '', cover }
    const pv = { ...previews.value }

    if (cardKey === 'daily') pv.daily = entry
    else if (cardKey === 'hidden_gem') pv.hidden_gem = entry
    else {
      if (!pv.moods) pv.moods = {}
      pv.moods = { ...pv.moods, [cardKey.replace('mood_', '')]: entry }
    }
    if (mode === 'weather' && mood) {
      if (!pv.moods) pv.moods = {}
      pv.moods = { ...pv.moods, [mood]: entry }
    }

    previews.value = pv
    _savePreviewsCache(pv)
  }

  async function loadPreviews(force = false) {
    if (!force && previewsLoading.value) return
    if (!force) {
      const cached = _loadPreviewsCache()
      if (cached && Object.keys(cached).length > 0) {
        previews.value = cached
        // 缓存命中也要恢复取色：有缓存颜色直接恢复，无则按需补提取
        await extractAllColors()
        return
      }
    }
    previewsLoading.value = true
    try {
      const res = await fetch(`${AI_BASE}/recommend/previews`)
      if (res.ok) {
        const data = await res.json()
        previews.value = data
        _savePreviewsCache(data)
        await extractAllColors()
      }
    } catch {
      // 失败时保持现有 previews，加载状态复位
    } finally {
      previewsLoading.value = false
    }
  }

  // ==================== 封面颜色提取 ====================

  async function extractAllColors() {
    const pv = previews.value
    const entries = []
    if (pv.daily?.cover) entries.push(['daily', pv.daily.cover])
    if (pv.hidden_gem?.cover) entries.push(['hidden_gem', pv.hidden_gem.cover])
    if (pv.moods) {
      for (const [key, val] of Object.entries(pv.moods)) {
        if (val?.cover) entries.push([key, val.cover])
      }
    }

    const fallbacks = {
      daily: { mid: '#4a3f6b', shadow: '#2a2545', highlight: '#8b7fbf' },
      hidden_gem: { mid: '#3f4a6b', shadow: '#252a45', highlight: '#7f8bbf' },
      sad: { mid: '#4a5a4a', shadow: '#2d362d', highlight: '#8ba88b' },
      energetic: { mid: '#6b3f3f', shadow: '#452525', highlight: '#bf7f7f' },
      calm: { mid: '#3f4a6b', shadow: '#252a45', highlight: '#7f8bbf' },
      upbeat: { mid: '#6b3f5a', shadow: '#452536', highlight: '#bf7fa8' },
      fresh: { mid: '#3f6b4a', shadow: '#25452d', highlight: '#7fbf8b' },
      romantic: { mid: '#6b3f55', shadow: '#452533', highlight: '#bf7fa3' },
      inspire: { mid: '#6b5a3f', shadow: '#453625', highlight: '#bfa87f' },
    }

    let cachedColors = {}
    try { cachedColors = JSON.parse(localStorage.getItem(COLOR_CACHE_KEY) || '{}') } catch {}

    const newColors = { ...cachedColors }
    const toExtract = entries.filter(([key, url]) => cachedColors[key]?.sourceUrl !== url)

    if (toExtract.length === 0) {
      coverColors.value = cachedColors
      return
    }

    const BATCH = 3
    for (let i = 0; i < toExtract.length; i += BATCH) {
      const batch = toExtract.slice(i, i + BATCH)
      await Promise.all(batch.map(async ([key, url]) => {
        const colors = await extractCoverColors(url)
        if (colors) {
          newColors[key] = { ...colors, sourceUrl: url }
        } else {
          newColors[key] = { ...(fallbacks[key] || fallbacks.daily), sourceUrl: url }
        }
      }))
    }

    for (const [key, fb] of Object.entries(fallbacks)) {
      if (!newColors[key]) newColors[key] = fb
    }
    coverColors.value = newColors
    try { localStorage.setItem(COLOR_CACHE_KEY, JSON.stringify(newColors)) } catch {}
  }

  // ==================== Embedding 管理 ====================

  async function loadEmbeddingStatus() {
    try {
      const res = await fetch(`${AI_BASE}/embedding/status`)
      if (res.ok) {
        embeddingStatus.value = await res.json()
      }
    } catch {}
  }

  function pollDownloadProgress(intervalMs = 1500) {
    isDownloading.value = true
    downloadProgress.value = {
      status: 'preparing', percent: 0, downloaded_mb: 0, total_mb: 0,
      message: '检测 GPU 环境中...',
    }
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${AI_BASE}/model-download/progress`)
        if (res.ok) {
          downloadProgress.value = await res.json()
          const st = downloadProgress.value.status
          if (st === 'completed' || st === 'error' || st === 'restarting' || st === 'idle') {
            clearInterval(timer)
            isDownloading.value = false
          }
        }
      } catch {
        // 下载中/重启中后端不可达，静默
      }
    }, intervalMs)
    return () => {
      clearInterval(timer)
      isDownloading.value = false
    }
  }

  async function generateEmbeddings() {
    isGenerating.value = true
    try {
      const res = await fetch(`${AI_BASE}/embedding/generate`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        return data
      }
    } catch (e) {
      // embedding 生成触发失败
    } finally {
      isGenerating.value = false
    }
    return null
  }

  function pollEmbeddingStatus(intervalMs = 2000, onDone) {
    const timer = setInterval(async () => {
      await loadEmbeddingStatus()
      const st = embeddingStatus.value
      if (st.pending === 0 && !st.audio_processing) {
        clearInterval(timer)
        if (onDone) onDone()
        return
      }
    }, intervalMs)
    return () => clearInterval(timer)
  }

  async function refreshMoodScores() {
    try {
      const res = await fetch(`${AI_BASE}/mood-scores/refresh`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        return data
      }
    } catch (e) {
      // 情绪分数刷新触发失败
    }
    return null
  }

  // 初始化：加载 embedding 状态和推荐（侧边栏依赖 recommendations）
  loadEmbeddingStatus()
  loadRecommendations()

  return {
    recommendations,
    isLoaded,
    isLoading,
    currentMode,
    currentSub,
    previews,
    previewsLoading,
    coverColors,
    embeddingStatus,
    isGenerating,
    downloadProgress,
    isDownloading,
    loadRecommendations,
    setMode,
    loadPreviews,
    updateCoverFromRecommend,
    extractAllColors,
    reportFeedback,
    loadEmbeddingStatus,
    generateEmbeddings,
    pollEmbeddingStatus,
    pollDownloadProgress,
    refreshMoodScores,
  }
})

// ==================== 封面颜色提取工具 ====================

function extractCoverColors(imageUrl) {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'Anonymous'
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        const size = 64
        canvas.width = size
        canvas.height = size
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, size, size)
        const imageData = ctx.getImageData(0, 0, size, size).data
        let r = 0, g = 0, b = 0, count = 0
        for (let i = 0; i < imageData.length; i += 16) {
          r += imageData[i]
          g += imageData[i + 1]
          b += imageData[i + 2]
          count++
        }
        r = Math.round(r / count)
        g = Math.round(g / count)
        b = Math.round(b / count)
        const darken = (v, f) => Math.round(v * f)
        const lighten = (v, f) => Math.min(255, Math.round(v + (255 - v) * f))
        resolve({
          mid: `rgb(${r},${g},${b})`,
          shadow: `rgb(${darken(r, 0.4)},${darken(g, 0.4)},${darken(b, 0.4)})`,
          highlight: `rgb(${lighten(r, 0.5)},${lighten(g, 0.5)},${lighten(b, 0.5)})`,
        })
      } catch { resolve(null) }
    }
    img.onerror = () => resolve(null)
    img.src = imageUrl
  })
}
