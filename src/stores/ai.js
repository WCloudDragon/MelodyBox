import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const AI_BASE = 'http://127.0.0.1:5000/api/ai'

export const useAiStore = defineStore('ai', () => {
  const recommendations = ref([])
  const isLoaded = ref(false)
  const isLoading = ref(false)

  // 当前推荐模式
  const currentMode = ref('comprehensive')
  // 推荐模式子选项（语言/情绪等）
  const currentSub = ref(null)

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
        recommendations.value = []
        isLoaded.value = true
        return
      }
      const data = await res.json()
      // 修复封面 URL
      for (const s of data) {
        if (s.cover_url && !s.cover_url.startsWith('http')) {
          s.cover_url = `http://127.0.0.1:5000/api/music/cover?path=${encodeURIComponent(s.cover_url)}`
        }
        // 补全前端需要的字段
        s.path = s.file_path
        s.cover = s.cover_url
        s.url = `http://127.0.0.1:51234/audio?path=${encodeURIComponent(s.file_path)}`
      }
      recommendations.value = data
      isLoaded.value = true
    } catch {
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
      console.error('[ai] embedding 生成触发失败:', e)
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
      console.error('[ai] 情绪分数刷新触发失败:', e)
    }
    return null
  }

  // 初始化
  loadRecommendations()
  loadEmbeddingStatus()

  return {
    recommendations,
    isLoaded,
    isLoading,
    currentMode,
    currentSub,
    embeddingStatus,
    isGenerating,
    downloadProgress,
    isDownloading,
    loadRecommendations,
    setMode,
    loadEmbeddingStatus,
    generateEmbeddings,
    pollEmbeddingStatus,
    pollDownloadProgress,
    refreshMoodScores
  }
})
