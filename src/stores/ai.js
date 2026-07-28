import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const AI_BASE = 'http://127.0.0.1:5000/api/ai'

// 统一缓存 key
const CACHE_KEY = 'melodybox_ai_cache'
// 后端缓存 5 分钟，前端对齐 5 分钟
const CACHE_TTL = 5 * 60 * 1000

/**
 * 统一缓存结构:
 * {
 *   expireAt: number,
 *   recommendations: { [mode_mood_lang]: Track[] },
 *   previews: { daily, hidden_gem, moods },
 *   coverColors: { [key]: { mid, shadow, highlight } },
 * }
 */

export const useAiStore = defineStore('ai', () => {
  const recommendations = ref([])
  const isLoaded = ref(false)
  const isLoading = ref(false)

  // 当前推荐模式
  const currentMode = ref('comprehensive')
  // 推荐模式子选项（语言/情绪等）
  const currentSub = ref(null)

  // 首页封面预览数据（单一数据源）
  const previews = ref({})
  const coverColors = ref({})

  // Embedding 状态
  const embeddingStatus = ref({ total: 0, done: 0, pending: 0, ready: false, st_available: null, mood_scores_ready: false, audio_done: 0, audio_total: 0, audio_available: false, audio_processing: false, text_processing: false, text_provider: 'idle', provider: 'cpu', e5_download: { status: 'idle', percent: 0 }, mert_download: { status: 'idle', percent: 0 } })
  const isGenerating = ref(false)

  // 模型下载进度
  const downloadProgress = ref({
    status: 'idle',       // idle | downloading | completed | error
    percent: 0,
    downloaded_mb: 0,
    total_mb: 0,
    message: ''
  })
  const isDownloading = ref(false)

  // ==================== 统一缓存层 ====================

  function _loadCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY)
      if (!raw) return null
      const cached = JSON.parse(raw)
      if (cached.expireAt > Date.now()) return cached
    } catch {}
    return null
  }

  function _saveCache(patch) {
    try {
      const existing = _loadCache() || {}
      const data = { ...existing, ...patch, expireAt: Date.now() + CACHE_TTL }
      localStorage.setItem(CACHE_KEY, JSON.stringify(data))
    } catch {}
  }

  // ==================== 推荐列表 ====================

  /** 加载 AI 推荐 */
  async function loadRecommendations(limit = 20) {
    isLoading.value = true
    try {
      let url = `${AI_BASE}/recommend?limit=${limit}&mode=${currentMode.value}`
      if (currentSub.value != null) {
        url += `&${currentSub.value}`
      }
      const res = await fetch(url)
      if (!res.ok) {
        const cached = _loadCache()
        if (cached?.recommendations?.length) {
          recommendations.value = cached.recommendations
        } else {
          recommendations.value = []
        }
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
      _saveCache({ recommendations: data })
    } catch {
      const cached = _loadCache()
      if (cached?.recommendations?.length) {
        recommendations.value = cached.recommendations
      }
      isLoaded.value = true
    } finally {
      isLoading.value = false
    }
  }

  /** 切换推荐模式 */
  async function setMode(mode, subValue = null) {
    currentMode.value = mode
    currentSub.value = subValue
    await loadRecommendations()
  }

  // ==================== 首页封面预览 ====================

  /** 从推荐结果更新单个卡片封面（推荐列表页调用） */
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
      pv.moods = { ...pv.moods, [cardKey.replace('mood_', '')] : entry }
    }
    // weather 模式也覆盖对应的 mood key
    if (mode === 'weather' && mood) {
      if (!pv.moods) pv.moods = {}
      pv.moods = { ...pv.moods, [mood]: entry }
    }

    previews.value = pv
    _saveCache({ previews: pv })
  }

  /** 加载首页封面预览数据 */
  async function loadPreviews(force = false) {
    if (!force) {
      const cached = _loadCache()
      if (cached?.previews && Object.keys(cached.previews).length > 0) {
        previews.value = cached.previews
        if (cached.coverColors) coverColors.value = cached.coverColors
        return
      }
    }
    try {
      const res = await fetch(`${AI_BASE}/recommend/previews`)
      if (res.ok) {
        const data = await res.json()
        previews.value = data
        _saveCache({ previews: data })
        await extractAllColors()
      }
    } catch {}
  }

  // ==================== 封面颜色提取 ====================

  const COLOR_CACHE_KEY = 'melodybox_cover_colors'

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

    // 仅对封面 URL 变化的条目重新提取颜色
    let cachedColors = {}
    try { cachedColors = JSON.parse(localStorage.getItem(COLOR_CACHE_KEY) || '{}') } catch {}

    const newColors = { ...cachedColors }
    const toExtract = entries.filter(([key, url]) => cachedColors[key]?.sourceUrl !== url)

    if (toExtract.length === 0) {
      coverColors.value = cachedColors
      _saveCache({ coverColors: cachedColors })
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
    _saveCache({ coverColors: newColors })
    try { localStorage.setItem(COLOR_CACHE_KEY, JSON.stringify(newColors)) } catch {}
  }

  // ==================== Embedding 管理 ====================

  /** 获取 embedding 生成状态 */
  async function loadEmbeddingStatus() {
    try {
      const res = await fetch(`${AI_BASE}/embedding/status`)
      if (res.ok) {
        embeddingStatus.value = await res.json()
      }
    } catch {}
  }

  /** 轮询模型下载进度 */
  function pollDownloadProgress(intervalMs = 1500) {
    isDownloading.value = true
    downloadProgress.value = { status: 'preparing', percent: 0, downloaded_mb: 0, total_mb: 0, message: '检测 GPU 环境中...' }
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

  /** 触发 embedding 生成（异步，完成需轮询状态） */
  async function generateEmbeddings() {
    try {
      isGenerating.value = true
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

  /** 轮询 embedding 生成进度 */
  function pollEmbeddingStatus(intervalMs = 2000, onDone) {
    const timer = setInterval(async () => {
      await loadEmbeddingStatus()
      const st = embeddingStatus.value
      // 文本 embedding 和音频 embedding 都完成才算真正结束
      if (st.pending === 0 && !st.audio_processing) {
        clearInterval(timer)
        if (onDone) onDone()
        return
      }
    }, intervalMs)
    return () => clearInterval(timer)
  }

  /** 刷新情绪分数（预计算，之后情绪推荐免模型） */
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
    loadEmbeddingStatus,
    generateEmbeddings,
    pollEmbeddingStatus,
    pollDownloadProgress,
    refreshMoodScores
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
