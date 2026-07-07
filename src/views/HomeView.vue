<template>
  <div class="home-view">
    <div class="home-view__header">
      <h1>欢迎回来</h1>
      <p class="subtitle">沉浸式音乐体验，从这里开始</p>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions" v-if="!hasMusic">
      <div class="welcome-card">
        <div class="welcome-card__icon">
          <el-icon size="48"><Headset /></el-icon>
        </div>
        <h2>您的音乐库为空</h2>
        <p>导入本地音乐文件，开始享受沉浸式音乐体验</p>
        <el-button type="primary" size="large" @click="handleImport" :loading="libraryStore.isLoading">
          导入本地音乐
        </el-button>
      </div>
    </div>

    <template v-else>
      <!-- AI 智能推荐 -->
      <section class="section">

        <!-- embedding 未生成提示 -->
        <div v-if="(aiStore.embeddingStatus.pending > 0 || aiStore.embeddingStatus.audio_processing || generatingEmbeddings) && libraryStore.tracks.length > 0" class="embedding-banner">
          <div v-if="aiStore.embeddingStatus.st_available === false" class="embedding-banner__content">
            <span>需要安装 fastembed 以启用 AI 推荐</span>
            <el-button type="primary" size="small" @click="copyInstallCmd">
              复制安装命令
            </el-button>
          </div>
          <div v-else-if="aiStore.downloadProgress.status === 'restarting'" class="embedding-banner__content" style="flex-direction: column; align-items: stretch; gap: 10px;">
            <span style="font-weight: 600; color: var(--accent-color);">正在重启以启用 GPU 加速...</span>
            <div class="progress-bar-wrap"><div class="progress-bar progress-bar--indeterminate"></div></div>
            <span style="font-size: 12px; color: var(--text-secondary);">应用重启后将自动使用 GPU 继续生成向量</span>
          </div>
          <div v-else-if="generatingEmbeddings" class="embedding-banner__content" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <!-- 文本分析进度条 -->
            <div style="display: flex; flex-direction: column; gap: 3px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 600; min-width: 56px;">文本语义</span>
                <div class="progress-bar-wrap" style="flex: 1;"><div class="progress-bar progress-bar--active" :style="{ width: e5DisplayPct + '%' }"></div></div>
                <span style="font-size: 12px; color: var(--text-secondary); min-width: 80px; text-align: right;">{{ e5DisplayCount }}</span>
              </div>
              <span style="font-size: 11px; color: var(--text-tertiary); padding-left: 64px;">{{ e5DisplayText }}</span>
            </div>
            <!-- 音频分析进度条 -->
            <div style="display: flex; flex-direction: column; gap: 3px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 600; min-width: 56px;">音频特征</span>
                <div class="progress-bar-wrap" style="flex: 1;"><div class="progress-bar progress-bar--active progress-bar--audio" :style="{ width: mertDisplayPct + '%' }"></div></div>
                <span style="font-size: 12px; color: var(--text-secondary); min-width: 80px; text-align: right;">{{ mertDisplayCount }}</span>
              </div>
              <span style="font-size: 11px; color: var(--text-tertiary); padding-left: 64px;">{{ mertDisplayText }}</span>
            </div>
          </div>
          <div v-else class="embedding-banner__content">
            <span>AI 推荐需要先生成歌曲文本语义与音频特征向量（每首约4KB）</span>
            <el-button type="primary" size="small" @click="handleGenerateEmbeddings" :loading="false">一键生成向量</el-button>
          </div>
        </div>

        <!-- 推荐入口卡片网格 -->
        <div v-if="hasRecData" class="rec-entries">
          <!-- 天气推荐卡片 -->
          <div
            v-if="weatherStore.isConfigured && !weatherStore.error"
            class="rec-entry rec-entry--weather"
            v-ripple
            @click="$router.push(`/recommend?mode=weather&mood=${weatherStore.mood}`)"
          >
            <div class="rec-entry__bg" :style="weatherGradient">
              <span class="rec-entry__weather-icon">{{ weatherStore.weatherIcon }}</span>
            </div>
            <div class="rec-entry__info">
              <div class="rec-entry__title">{{ weatherStore.weatherText }} {{ weatherStore.temp }}°</div>
              <div class="rec-entry__subtitle">{{ weatherStore.suggestion }}</div>
            </div>
            <div class="rec-entry__city">{{ weatherStore.city }}</div>
          </div>

          <!-- 每日推荐卡片 -->
          <div
            class="rec-entry rec-entry--cover"
            v-ripple
            @click="$router.push('/recommend?mode=comprehensive')"
          >
            <div class="rec-entry__cover-bg">
              <img v-if="getPreview('daily')?.cover" :src="getPreview('daily').cover" class="rec-entry__cover-img" />
              <div v-else class="rec-entry__cover-placeholder">
                <span>✨</span>
              </div>
              <div class="rec-entry__cover-mask"></div>
            </div>
            <div class="rec-entry__info" :style="getCoverStyle('daily')">
              <div class="rec-entry__title">每日推荐</div>
              <div class="rec-entry__subtitle">根据你的听歌偏好</div>
            </div>
          </div>

          <!-- 冷门宝藏卡片 -->
          <div
            class="rec-entry rec-entry--cover"
            v-ripple
            @click="$router.push('/recommend?mode=hidden_gem')"
          >
            <div class="rec-entry__cover-bg">
              <img v-if="getPreview('hidden_gem')?.cover" :src="getPreview('hidden_gem').cover" class="rec-entry__cover-img" />
              <div v-else class="rec-entry__cover-placeholder rec-entry__cover-placeholder--gem">
                <span>💎</span>
              </div>
              <div class="rec-entry__cover-mask"></div>
            </div>
            <div class="rec-entry__info" :style="getCoverStyle('hidden_gem')">
              <div class="rec-entry__title">冷门宝藏</div>
              <div class="rec-entry__subtitle">被忽视的好歌</div>
            </div>
          </div>

          <!-- 按情绪推荐卡片（前3种） -->
          <div
            v-for="m in moods.slice(0, 3)"
            :key="m.key"
            class="rec-entry rec-entry--cover"
            v-ripple
            @click="$router.push(`/recommend?mode=mood&mood=${m.key}`)"
          >
            <div class="rec-entry__cover-bg">
              <img v-if="getPreview(m.key)?.cover" :src="getPreview(m.key).cover" class="rec-entry__cover-img" />
              <div v-else class="rec-entry__cover-placeholder" :style="{ background: m.gradient }">
                <span>{{ m.icon }}</span>
              </div>
              <div class="rec-entry__cover-mask"></div>
            </div>
            <div class="rec-entry__info" :style="getCoverStyle(m.key)">
              <div class="rec-entry__title">{{ m.label }}</div>
              <div class="rec-entry__subtitle">{{ m.sub }}</div>
            </div>
          </div>
        </div>

        <!-- 语言推荐入口（横排） -->
        <div v-if="aiStore.embeddingStatus.pending === 0 && topLangs.length > 0" class="rec-lang-row">
          <div
            v-for="l in topLangs"
            :key="l.code"
            class="rec-lang-chip"
            v-ripple
            @click="$router.push(`/recommend?mode=language&lang=${l.code}`)"
          >
            <span class="rec-lang-chip__label">{{ l.label }}推荐</span>
          </div>
        </div>

        <!-- AI 推荐（直接展示，兼容旧模式） -->
        <div v-if="aiStore.embeddingStatus.pending === 0 && aiRecommendations.length > 0" class="tracks-grid" style="margin-top: 12px;">
          <div
            v-for="track in aiRecommendations"
            :key="track.song_id"
            class="ai-track-card"
            @click="playAiTrack(track)"
          >
            <MusicCard :track="track" @play="playAiTrack(track)" />
            <div class="ai-track-card__reason" :title="'匹配度: ' + (track.score * 100).toFixed(1) + '%'">
              {{ track.reason }}
            </div>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="aiStore.isLoading && aiStore.embeddingStatus.pending === 0" class="loading-hint">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在生成推荐...</span>
        </div>
      </section>

      <!-- 最近播放 / 推荐 -->
      <section class="section">
        <div class="section__header">
          <h3>音乐库</h3>
          <div style="display: flex; align-items: center; gap: 8px;">
            <!-- 筛选：全部 / 本地 / 云端 -->
            <div class="src-filter">
              <button
                v-for="s in sourceFilters"
                :key="s.key"
                class="src-chip"
                :class="{ 'src-chip--active': libraryStore.sourceFilter === s.key }"
                @click="libraryStore.setSourceFilter(s.key)"
              >{{ s.label }}</button>
            </div>
            <el-button text type="primary" @click="$router.push('/library')">查看全部</el-button>
          </div>
        </div>
        <div class="tracks-grid">
          <MusicCard
            v-for="track in recentTracks"
            :key="track.source + ':' + track.path"
            :track="track"
            @play="playTrack(track)"
            @click="playTrack(track)"
          />
        </div>
      </section>

      <!-- 专辑 -->
      <section class="section" v-if="libraryStore.albums.length > 0">
        <div class="section__header">
          <h3>专辑</h3>
        </div>
        <div class="tracks-grid">
          <div
            v-for="album in recentAlbums"
            :key="album.name"
            class="album-card"
            v-ripple
            @click="$router.push(`/album/${encodeURIComponent(album.name)}`)">
            <div class="album-card__cover">
              <img v-if="album.cover" :src="album.cover" />
              <div v-else class="cover-placeholder">
                <el-icon size="28"><Folder /></el-icon>
              </div>
            </div>
            <div class="album-card__name truncate">{{ album.name }}</div>
            <div class="album-card__artist truncate">{{ album.artist }}</div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
defineOptions({ name: 'HomeView' })
import { computed, watch, onBeforeUnmount, ref } from 'vue'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import { useAiStore } from '@/stores/ai'
import { useWeatherStore } from '@/stores/weather'
import { showScanNotify, updateScanNotify, closeScanNotify, clearScanNotify } from '@/utils/scanNotify'
import MusicCard from '@/components/music/MusicCard.vue'
import { useScrollMemory } from '@/composables/useScrollMemory'
import { useModal } from '@/composables/useModal'
import { extractCoverColors } from '@/utils/coverColorExtractor'

const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()
const aiStore = useAiStore()
const weatherStore = useWeatherStore()
const modal = useModal()

// 资源筛选
const sourceFilters = [
  { key: 'all', label: '全部' },
  { key: 'local', label: '本地' },
  { key: 'cloud', label: '云端' },
]

// 扫描进度通知
watch(() => libraryStore.isScanning, (scanning) => {
  if (scanning) { showScanNotify() }
})
watch(() => libraryStore.scanProgress, (p) => {
  if (p.total > 0) updateScanNotify(p.current, p.total, p.path)
  if (!p.scanning) {
    closeScanNotify(p, async () => {
      await libraryStore.loadFromApi()
      libraryStore.loadCloudSongs()
    })
  }
})
onBeforeUnmount(clearScanNotify)

useScrollMemory('home', () => document.querySelector('.main-content'))

const hasMusic = computed(() => libraryStore.tracks.length > 0 || libraryStore.cloudTracks.length > 0)
const recentTracks = computed(() => libraryStore.allTracks.slice(0, 12))
const recentAlbums = computed(() => libraryStore.albums.slice(0, 8))

async function handleImport() {
  if (window.electronAPI) {
    await libraryStore.selectAndScan()
  } else {
    // 浏览器模式：提示
    alert('请使用 Electron 桌面版以获得完整功能。\n\n当前浏览器模式仅支持示例体验。')
  }
}

function playTrack(track) {
  const idx = libraryStore.allTracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(libraryStore.allTracks, idx)
  }
}

// ==================== AI 推荐 ====================

const generatingEmbeddings = ref(false)

// 进度条百分比
const textProgressPct = computed(() => {
  const st = aiStore.embeddingStatus
  return st.total > 0 ? (st.done / st.total * 100) : 0
})

const audioProgressPct = computed(() => {
  const st = aiStore.embeddingStatus
  return st.audio_total > 0 ? (st.audio_done / st.audio_total * 100) : 0
})

// 状态文本
const textStatusText = computed(() => {
  const st = aiStore.embeddingStatus
  if (!st.text_processing && st.done === st.total && st.total > 0) return '✅ 已完成'
  if (st.text_provider === 'CPU') return '正在分析文本语义 (CPU) ...'
  if (st.text_provider === 'GPU') return '⚡ 已切换 GPU 加速分析...'
  return ''
})

const audioStatusText = computed(() => {
  const st = aiStore.embeddingStatus
  if (!st.audio_processing && st.audio_done === st.audio_total && st.audio_total > 0) return '✅ 已完成'
  if (st.audio_processing) return '正在分析音频特征 (GPU)...'
  return ''
})

// E5 显示状态（下载中 / 编码中 / 已完成）
const e5DisplayPct = computed(() => {
  const dl = aiStore.embeddingStatus.e5_download
  if (dl && dl.status === 'downloading') return dl.percent || 0
  if (dl && (dl.status === 'checking' || dl.status === 'preparing')) return 1
  return textProgressPct.value
})
const formatDownload = (dlMb, totalMb) => {
  if (!totalMb || totalMb <= 0) return `${dlMb || 0}/~MB`
  if (totalMb >= 1000) {
    return `${(dlMb / 1000).toFixed(2)}/${(totalMb / 1000).toFixed(2)} GB`
  }
  return `${Number(dlMb).toFixed(0)}/${Number(totalMb).toFixed(0)} MB`
}

const e5DisplayCount = computed(() => {
  const dl = aiStore.embeddingStatus.e5_download
  if (dl && (dl.status === 'checking' || dl.status === 'preparing')) return '...'
  if (dl && dl.status === 'downloading') return formatDownload(dl.downloaded_mb || 0, dl.total_mb || 0)
  return `${aiStore.embeddingStatus.done}/${aiStore.embeddingStatus.total}`
})

const e5DisplayText = computed(() => {
  const dl = aiStore.embeddingStatus.e5_download
  if (dl && (dl.status === 'downloading' || dl.status === 'checking' || dl.status === 'preparing' || dl.status === 'retrying'))
    return dl.message || ''
  if (dl && dl.status === 'error') return `下载失败: ${dl.message}`
  if (dl && dl.status === 'completed' && !aiStore.embeddingStatus.text_processing)
    return '正在加载文本分析引擎...'
  return textStatusText.value
})

// MERT 显示状态（下载中 / 导出中 / 编码中 / 已完成）
const mertDisplayPct = computed(() => {
  const dl = aiStore.embeddingStatus.mert_download
  if (dl && dl.status === 'downloading') return dl.percent || 0
  if (dl && (dl.status === 'checking' || dl.status === 'preparing')) return 1
  if (dl && dl.status === 'exporting') return dl.percent || 0
  return audioProgressPct.value
})
const mertDisplayCount = computed(() => {
  const dl = aiStore.embeddingStatus.mert_download
  if (dl && (dl.status === 'checking' || dl.status === 'preparing')) return '...'
  if (dl && dl.status === 'downloading') return formatDownload(dl.downloaded_mb || 0, dl.total_mb || 0)
  if (dl && dl.status === 'exporting') return '...'
  const st = aiStore.embeddingStatus
  if (st.audio_total > 0) return `${st.audio_done}/${st.audio_total}`
  return '...'
})
const mertDisplayText = computed(() => {
  const dl = aiStore.embeddingStatus.mert_download
  if (dl && (dl.status === 'downloading' || dl.status === 'checking' || dl.status === 'preparing' || dl.status === 'retrying'))
    return dl.message || ''
  if (dl && dl.status === 'exporting') return '正在准备音频分析引擎...'
  if (dl && dl.status === 'error') return `下载失败: ${dl.message}`
  // 下载完成但模型还未就绪（wait_for_mert_download 仍在等待 ONNX 导出）
  if (dl && dl.status === 'completed' && !aiStore.embeddingStatus.audio_processing) {
    const st = aiStore.embeddingStatus
    // 如果音频已经全部编码完成（上一轮已生成），直接显示已完成
    if (st.audio_done === st.audio_total && st.audio_total > 0)
      return '✅ 已完成'
    return '正在准备音频分析引擎...'
  }
  return audioStatusText.value
})

// 推荐模式
const moods = [
  { key: 'sad',       label: '伤感', icon: '😢', sub: '雨天的陪伴', gradient: 'linear-gradient(135deg, #2c3e50, #4a6741)' },
  { key: 'energetic', label: '激昂', icon: '🔥', sub: '点燃热情', gradient: 'linear-gradient(135deg, #e74c3c, #e67e22)' },
  { key: 'calm',      label: '舒缓', icon: '🌙', sub: '安静的时光', gradient: 'linear-gradient(135deg, #2c3e50, #3498db)' },
  { key: 'upbeat',    label: '动感', icon: '💃', sub: '跟着节奏摇摆', gradient: 'linear-gradient(135deg, #e91e63, #9c27b0)' },
  { key: 'fresh',     label: '清新', icon: '🍃', sub: '自然的气息', gradient: 'linear-gradient(135deg, #27ae60, #2ecc71)' },
  { key: 'romantic',  label: '浪漫', icon: '💕', sub: '甜蜜的旋律', gradient: 'linear-gradient(135deg, #e91e63, #f06292)' },
  { key: 'inspire',   label: '励志', icon: '🌟', sub: '给你力量', gradient: 'linear-gradient(135deg, #ff9800, #ffc107)' },
]

// 完整语言名称映射
const LANG_NAME_MAP = {
  zh: '中文', 'zh-cn': '中文', 'zh-tw': '中文',
  ja: '日语', en: '英语', ko: '韩语',
  de: '德语', ru: '俄语', fr: '法语', es: '西班牙语',
  pt: '葡萄牙语', it: '意大利语', nl: '荷兰语',
  pl: '波兰语', sv: '瑞典语', no: '挪威语', da: '丹麦语',
  fi: '芬兰语', cs: '捷克语', ro: '罗马尼亚语', hu: '匈牙利语',
  tr: '土耳其语', ar: '阿拉伯语', hi: '印地语', th: '泰语',
  vi: '越南语', id: '印尼语', ms: '马来语',
  tl: '菲律宾语', sw: '斯瓦希里语',
  ca: '加泰罗尼亚语', et: '爱沙尼亚语', hr: '克罗地亚语',
  af: '南非荷兰语', so: '索马里语', bg: '保加利亚语',
  uk: '乌克兰语', sk: '斯洛伐克语', sl: '斯洛文尼亚语',
  el: '希腊语', he: '希伯来语', bn: '孟加拉语', ta: '泰米尔语',
  inst: '纯音乐',
}

// 语言码规范化：zh-cn/zh-tw → zh
function normalizedLangCode(code) {
  if (code?.startsWith('zh')) return 'zh'
  return code
}

// 常见语言（单独展示）
const COMMON_LANG_CODES = new Set([
  'inst', 'zh', 'ja', 'en', 'ko', 'de', 'ru', 'fr', 'es', 'pt', 'it', 'vi', 'nl',
  'sv', 'no', 'da', 'fi', 'tr', 'pl', 'ar', 'th', 'id', 'hi',
])

// 可用的语言列表（从 embedding status 接口获取，去重 zh-cn/zh-tw → 中文）
const availableLangs = computed(() => {
  const langs = aiStore.embeddingStatus.langs || []
  const seen = new Set()
  const common = []
  let hasOther = false
  for (const code of langs) {
    const key = normalizedLangCode(code)
    if (seen.has(key)) continue
    seen.add(key)
    if (COMMON_LANG_CODES.has(key)) {
      common.push({ code: key, label: LANG_NAME_MAP[key] || code })
    } else {
      hasOther = true
    }
  }
  // 按语言名排序
  common.sort((a, b) => a.label.localeCompare(b.label, 'zh'))
  if (hasOther) {
    common.push({ code: 'other', label: '其他' })
  }
  return common
})

const aiRecommendations = computed(() => {
  return aiStore.recommendations.slice(0, 12)
})

// 天气卡片渐变背景
const weatherGradient = computed(() => {
  const mood = weatherStore.mood
  const gradients = {
    sad: 'linear-gradient(135deg, #2c3e50, #4a6741)',
    energetic: 'linear-gradient(135deg, #e74c3c, #e67e22)',
    calm: 'linear-gradient(135deg, #2c3e50, #3498db)',
    upbeat: 'linear-gradient(135deg, #e91e63, #9c27b0)',
    fresh: 'linear-gradient(135deg, #27ae60, #2ecc71)',
    romantic: 'linear-gradient(135deg, #e91e63, #f06292)',
    inspire: 'linear-gradient(135deg, #ff9800, #ffc107)',
  }
  return gradients[mood] || 'linear-gradient(135deg, #6366f1, #818cf8)'
})

// 推荐预览数据（卡片封面）— localStorage 缓存 + 按需刷新
const PREVIEW_CACHE_KEY = 'melodybox_rec_previews'
const PREVIEW_COLORS_KEY = 'melodybox_rec_colors'
const recPreviews = ref({})
const coverColors = ref({})
const hasRecData = computed(() => aiStore.embeddingStatus.pending === 0 || Object.keys(recPreviews.value).length > 0)

// 启动时立即加载缓存
try {
  const cached = localStorage.getItem(PREVIEW_CACHE_KEY)
  if (cached) recPreviews.value = JSON.parse(cached)
  const cachedColors = localStorage.getItem(PREVIEW_COLORS_KEY)
  if (cachedColors) coverColors.value = JSON.parse(cachedColors)
} catch {}

async function loadRecPreviews() {
  try {
    const res = await fetch('http://127.0.0.1:5000/api/ai/recommend/previews')
    if (res.ok) {
      const data = await res.json()
      recPreviews.value = data
      try { localStorage.setItem(PREVIEW_CACHE_KEY, JSON.stringify(data)) } catch {}
      extractAllColors()
    }
  } catch {}
}

async function extractAllColors() {
  const pv = recPreviews.value
  const entries = []
  if (pv.daily?.cover) entries.push(['daily', pv.daily.cover])
  if (pv.hidden_gem?.cover) entries.push(['hidden_gem', pv.hidden_gem.cover])
  if (pv.moods) {
    for (const [key, val] of Object.entries(pv.moods)) {
      if (val?.cover) entries.push([key, val.cover])
    }
  }
  // 预定义 fallback 色板
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
  const BATCH = 3
  for (let i = 0; i < entries.length; i += BATCH) {
    const batch = entries.slice(i, i + BATCH)
    await Promise.all(batch.map(async ([key, url]) => {
      const colors = await extractCoverColors(url)
      coverColors.value[key] = colors || fallbacks[key] || fallbacks.daily
    }))
  }
  // 没有封面的条目也用 fallback
  for (const [key, fb] of Object.entries(fallbacks)) {
    if (!coverColors.value[key]) coverColors.value[key] = fb
  }
  coverColors.value = { ...coverColors.value }
  try { localStorage.setItem(PREVIEW_COLORS_KEY, JSON.stringify(coverColors.value)) } catch {}
}

function getPreview(key) {
  const pv = recPreviews.value
  if (key === 'daily') return pv.daily
  if (key === 'hidden_gem') return pv.hidden_gem
  return pv.moods?.[key] || null
}

function getCoverStyle(key) {
  const c = coverColors.value[key]
  if (!c) return {}
  return { '--card-bg': c.mid || c.shadow }
}

// 顶部语言推荐（取播放量最高的 3 种语言）
const topLangs = computed(() => {
  const langs = aiStore.embeddingStatus.langs || []
  if (langs.length === 0) return []
  const top = langs.slice(0, 3)
  return top.map(code => ({
    code,
    label: LANG_NAME_MAP[code] || code,
  }))
})

async function handleGenerateEmbeddings() {
  // 先获取当前模型路径配置
  let modelPath = '默认路径'
  try {
    const res = await fetch('http://127.0.0.1:5000/api/ai/model-dir')
    if (res.ok) {
      const data = await res.json()
      modelPath = data.model_cache_dir || 'C:\\Users\\用户名\\.cache\\huggingface'
    }
  } catch {}

  try {
    await modal.confirm({
      title: '确认生成 AI 向量',
      message: `即将为所有歌曲生成文本语义与音频特征向量，首次运行需下载两个 AI 模型（共约 2.3GB）。\n\n模型存放路径: ${modelPath}\n\n当前曲库共 ${libraryStore.tracks.length} 首歌曲，生成后可启用AI智能推荐。`,
      confirmText: '开始生成',
    })
  } catch {
    return  // 用户取消
  }

  generatingEmbeddings.value = true
  // 启动模型下载进度轮询（generateEmbeddings 内部先下载模型再生成向量）
  aiStore.pollDownloadProgress(1500)
  await aiStore.generateEmbeddings()
  // 轮询状态直到完成
  const stop = aiStore.pollEmbeddingStatus(2000, async () => {
    generatingEmbeddings.value = false
    await aiStore.loadRecommendations()
  })
  // 如果 generateEmbeddings 已经完成（pending=0 且音频也完成的情况），即时清理
  setTimeout(async () => {
    await aiStore.loadEmbeddingStatus()
    if (aiStore.embeddingStatus.pending === 0 && !aiStore.embeddingStatus.audio_processing) {
      stop()
      generatingEmbeddings.value = false
      await aiStore.loadRecommendations()
    }
  }, 500)
}

async function copyInstallCmd() {
  const cmd = 'pip install fastembed langdetect'
  try {
    await navigator.clipboard.writeText(cmd)
    alert('已复制: ' + cmd)
  } catch {
    prompt('请复制以下命令运行:', cmd)
  }
}

function playAiTrack(track) {
  // 优先在本地曲库查找（指纹去重后本地优先）
  const allTracks = libraryStore.allTracks
  if (allTracks.length === 0) return
  // 先用 file_path 精确匹配
  let idx = allTracks.findIndex(t => t.path === track.file_path)
  // 回退：用 song_id 匹配
  if (idx === -1) {
    idx = allTracks.findIndex(t => t.id === track.song_id)
  }
  if (idx !== -1) {
    playerStore.playAll(allTracks, idx)
  }
}

// 监听曲库变化，曲库更新后自动刷新推荐
watch(() => libraryStore.tracks.length, async (newLen) => {
  if (newLen > 0) {
    await aiStore.loadEmbeddingStatus()
    if (aiStore.embeddingStatus.pending === 0) {
      await aiStore.loadRecommendations()
      loadRecPreviews()
    }
  }
})

// embedding 就绪后加载推荐预览
watch(() => aiStore.embeddingStatus.pending, (pending) => {
  if (pending === 0) loadRecPreviews()
})
</script>

<style scoped>
.home-view { padding-bottom: 120px; }
.home-view__header { margin-bottom: 32px; }
.home-view__header h1 { font-size: 28px; font-weight: 700; margin: 0 0 4px; }
.subtitle { font-size: 14px; color: var(--text-tertiary); margin: 0; }

.welcome-card {
  text-align: center; padding: 64px 32px;
  background: var(--bg-secondary); border-radius: 16px;
  border: 1px dashed var(--border-color);
}
.welcome-card__icon { color: var(--text-tertiary); margin-bottom: 16px; }
.welcome-card h2 { font-size: 20px; margin-bottom: 8px; }
.welcome-card p { color: var(--text-tertiary); margin-bottom: 24px; font-size: 14px; }



.section { margin-bottom: 36px; }
.section__header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.section__header h3 { font-size: 18px; font-weight: 600; margin: 0; }

.tracks-grid { display: flex; flex-wrap: wrap; gap: 4px; }

/* 专辑卡片 */
.album-card {
  width: 170px; cursor: pointer; border-radius: 10px;
  padding: 12px; transition: background 0.2s;
}
.album-card:hover { background: var(--hover-bg); }
.album-card__cover {
  width: 100%; aspect-ratio: 1; border-radius: 8px;
  overflow: hidden; margin-bottom: 10px;
}
.album-card__cover img { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder {
  width: 100%; height: 100%; background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.album-card__name { font-size: 13px; font-weight: 500; margin-bottom: 2px; }
.album-card__artist { font-size: 12px; color: var(--text-tertiary); }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* AI 推荐 */
.section__icon { margin-right: 4px; }

.embedding-banner {
  background: linear-gradient(135deg, var(--accent-color-10, rgba(99, 102, 241, 0.1)), var(--bg-secondary));
  border: 1px solid var(--accent-color-30, rgba(99, 102, 241, 0.3));
  border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
}
.embedding-banner__content {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  font-size: 13px; color: var(--text-secondary);
}

.progress-bar-wrap {
  height: 6px; background: var(--bg-primary); border-radius: 3px; overflow: hidden;
}
.progress-bar {
  height: 100%; background: var(--accent-color, #6366f1); border-radius: 3px;
  transition: width 0.6s ease;
  min-width: 2%;
}
.progress-bar--active {
  background: linear-gradient(90deg, var(--accent-color, #6366f1), #818cf8);
  background-size: 200% 100%;
  animation: progressShimmer 1.5s ease-in-out infinite;
}
.progress-bar--audio {
  background: linear-gradient(90deg, #10b981, #34d399);
  background-size: 200% 100%;
  animation: progressShimmer 1.5s ease-in-out infinite;
}
@keyframes progressShimmer {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.progress-bar--indeterminate {
  width: 40% !important;
  animation: indeterminateSlide 1.8s ease-in-out infinite;
}

@keyframes indeterminateSlide {
  0% { margin-left: 0; }
  50% { margin-left: 55%; }
  100% { margin-left: 0; }
}

.ai-track-card {
  position: relative;
}
.ai-track-card__reason {
  position: absolute; bottom: 8px; left: 8px; right: 8px;
  background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(6px);
  border-radius: 6px; padding: 4px 8px;
  font-size: 11px; color: #fff; text-align: center;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  opacity: 0; transition: opacity 0.2s;
  pointer-events: none;
}
.ai-track-card:hover .ai-track-card__reason {
  opacity: 1;
}

.loading-hint {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 24px; color: var(--text-tertiary); font-size: 13px;
}

/* ---- 推荐入口卡片 ---- */
.rec-entries {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.rec-entry {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  background: var(--bg-secondary);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.25s ease;
  overflow: hidden;
  min-height: 200px;
}


/* 封面卡片样式 */
.rec-entry--cover .rec-entry__cover-bg {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
}
.rec-entry__cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.rec-entry__cover-mask {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40%;
  background: linear-gradient(transparent, rgba(0,0,0,0.4));
  pointer-events: none;
}
.rec-entry__cover-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, var(--accent-color), #818cf8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
}
.rec-entry__cover-placeholder--gem {
  background: linear-gradient(135deg, #7c3aed, #a78bfa);
}

/* 封面取色文字区域 */
.rec-entry--cover .rec-entry__info {
  padding: 12px 14px;
  background: var(--card-bg, var(--bg-secondary));
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  transition: background 0.3s ease;
}
.rec-entry--cover .rec-entry__info .rec-entry__title {
  color: #fff;
}
.rec-entry--cover .rec-entry__info .rec-entry__subtitle {
  color: rgba(255,255,255,0.7);
}

/* 天气卡片特殊样式 */
.rec-entry--weather {
  grid-column: span 2;
  background: none;
  border: none;
  padding: 0;
  overflow: hidden;
  min-height: 100px;
  flex-direction: row;
  align-items: center;
}
.rec-entry--weather .rec-entry__bg {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}
.rec-entry--weather .rec-entry__weather-icon {
  font-size: 48px;
  opacity: 0.3;
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
}
.rec-entry--weather .rec-entry__info {
  position: relative;
  z-index: 1;
  color: #fff;
  padding: 16px;
  background: transparent;
}
.rec-entry--weather .rec-entry__title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 4px;
  text-shadow: 0 1px 4px rgba(0,0,0,0.3);
}
.rec-entry--weather .rec-entry__subtitle {
  font-size: 13px;
  opacity: 0.9;
  text-shadow: 0 1px 4px rgba(0,0,0,0.3);
}
.rec-entry--weather .rec-entry__city {
  position: absolute;
  top: 12px;
  right: 16px;
  font-size: 12px;
  color: rgba(255,255,255,0.7);
  z-index: 1;
}

.rec-entry__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rec-entry__subtitle {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- 语言推荐横排 ---- */
.rec-lang-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.rec-lang-chip {
  padding: 6px 16px;
  border-radius: 20px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
}
.rec-lang-chip:hover {
  border-color: var(--accent-color);
  background: var(--accent-bg);
}
.rec-lang-chip__label {
  font-size: 13px;
  color: var(--text-secondary);
}
.rec-lang-chip:hover .rec-lang-chip__label {
  color: var(--accent-color);
}

/* 资源筛选（全部/本地/云端） */
.src-filter {
  display: flex; gap: 4px;
}
.src-chip {
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.src-chip:hover {
  background: var(--hover-bg);
}
.src-chip--active {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: #fff;
}
</style>
