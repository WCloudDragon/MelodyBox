<template>
  <div class="recommend-view">
    <div class="back-link">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <div class="recommend-header" v-if="headerInfo">
      <div class="recommend-header__cover" :style="{ background: headerInfo.gradient }">
        <span class="recommend-header__icon">{{ headerInfo.icon }}</span>
      </div>
      <div class="recommend-header__info">
        <h1>{{ headerInfo.title }}</h1>
        <p v-if="headerInfo.subtitle">{{ headerInfo.subtitle }}</p>
        <p>{{ tracks.length }} 首推荐歌曲</p>
        <div class="recommend-header__actions">
          <el-button type="primary" @click="playAll" :disabled="tracks.length === 0">
            <el-icon><VideoPlay /></el-icon>
            播放全部
          </el-button>
        </div>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="isLoading && tracks.length === 0" class="loading-hint">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在生成推荐...</span>
    </div>

    <!-- 歌曲列表 -->
    <TrackTable
      v-else-if="tracks.length > 0"
      :tracks="tracks"
      :current-path="currentTrack?.path"
      :context-target="contextMenuTarget"
      :show-album="true"
      :show-artist="true"
      :multi-select-mode="multiSelectMode"
      :selected-paths="selected"
      @play="playTrack"
      @contextmenu="showContextMenu"
      @toggle-select="toggleSelect"
    />

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p>暂无推荐结果</p>
      <p class="hint" v-if="!aiStore.embeddingStatus.ready">
        需要先生成 AI 向量才能获得个性化推荐
      </p>
    </div>

    <!-- 右键菜单 -->
    <ContextMenu
      :visible="ctxMenu.visible"
      :x="ctxMenu.x"
      :y="ctxMenu.y"
      :items="menuItems"
      :animated="true"
      @close="hideContextMenu"
      @action="ctxAction"
    />
  </div>
</template>

<script setup>
defineOptions({ name: 'RecommendPlaylistView' })
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { useAiStore } from '@/stores/ai'
import { useTrackList } from '@/composables/useTrackList'
import TrackTable from '@/components/music/TrackTable.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const aiStore = useAiStore()
const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, contextMenuTarget, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems, showAddPlaylistDialog } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)
const menuItems = computed(() => buildMenuItems('default'))

function ctxAction(action) {
  if (ctxHandler(action)) return
  if (action === 'addToPlaylist') showAddPlaylistDialog(ctxMenu.value.track)
}

const tracks = ref([])
const isLoading = ref(false)

// --- 缓存 TTL（秒）---
const CACHE_TTL = {
  comprehensive: 'midnight', // 每日0点刷新
  hidden_gem: 86400,    // 24h
  mood: 21600,          // 6h
  weather: 3600,        // 1h
  language: 43200,       // 12h
}

function getCacheKey() {
  const mode = route.query.mode || 'comprehensive'
  const lang = route.query.lang || ''
  const mood = route.query.mood || ''
  return `rec_${mode}_${lang}_${mood}`
}

function getCacheTTL() {
  const mode = route.query.mode || 'comprehensive'
  const ttl = CACHE_TTL[mode] || 3600
  if (ttl === 'midnight') {
    // 计算距离明天 00:00:00 的秒数
    const now = new Date()
    const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
    return Math.ceil((tomorrow - now) / 1000)
  }
  return ttl
}

function getCachedTracks() {
  try {
    const raw = localStorage.getItem(getCacheKey())
    if (!raw) return null
    const { data, ts } = JSON.parse(raw)
    const ttl = getCacheTTL()
    if (Date.now() - ts > ttl * 1000) return null
    return data
  } catch { return null }
}

function setCachedTracks(data) {
  try {
    localStorage.setItem(getCacheKey(), JSON.stringify({ data, ts: Date.now() }))
  } catch {}
}

// 标题映射
const TITLE_MAP = {
  comprehensive: '每日推荐',
  language: '语言推荐',
  mood: '情绪推荐',
  hidden_gem: '冷门宝藏',
  weather: '天气推荐',
}

const LANG_LABELS = {
  zh: '中文', ja: '日语', en: '英语', ko: '韩语',
  de: '德语', ru: '俄语', fr: '法语', es: '西班牙语',
  pt: '葡萄牙语', it: '意大利语', inst: '纯音乐', other: '其他语言',
}

const MOOD_LABELS = {
  sad: '伤感', energetic: '激昂', calm: '舒缓',
  upbeat: '动感', fresh: '清新', romantic: '浪漫', inspire: '励志',
}

const MOOD_ICONS = {
  sad: '😢', energetic: '🔥', calm: '🌙',
  upbeat: '💃', fresh: '🍃', romantic: '💕', inspire: '🌟',
}

const MOOD_GRADIENTS = {
  sad: 'linear-gradient(135deg, #2c3e50, #4a6741)',
  energetic: 'linear-gradient(135deg, #e74c3c, #e67e22)',
  calm: 'linear-gradient(135deg, #2c3e50, #3498db)',
  upbeat: 'linear-gradient(135deg, #e91e63, #9c27b0)',
  fresh: 'linear-gradient(135deg, #27ae60, #2ecc71)',
  romantic: 'linear-gradient(135deg, #e91e63, #f06292)',
  inspire: 'linear-gradient(135deg, #ff9800, #ffc107)',
}

const headerInfo = computed(() => {
  const mode = route.query.mode || 'comprehensive'
  const title = TITLE_MAP[mode] || '推荐'
  const lang = route.query.lang
  const mood = route.query.mood

  if (mode === 'language' && lang) {
    const label = LANG_LABELS[lang] || lang
    return {
      title: `${label}推荐`,
      subtitle: `为你精选${label}歌曲`,
      icon: '🎵',
      gradient: 'linear-gradient(135deg, #6366f1, #818cf8)',
    }
  }

  if ((mode === 'mood' || mode === 'weather') && mood) {
    return {
      title: mode === 'weather' ? '天气推荐' : `${MOOD_LABELS[mood] || mood}推荐`,
      subtitle: mode === 'weather' ? '根据当前天气为你推荐' : `为你精选${MOOD_LABELS[mood] || mood}歌曲`,
      icon: MOOD_ICONS[mood] || '🎵',
      gradient: MOOD_GRADIENTS[mood] || 'linear-gradient(135deg, #6366f1, #818cf8)',
    }
  }

  if (mode === 'hidden_gem') {
    return {
      title: '冷门宝藏',
      subtitle: '那些被忽视的好歌',
      icon: '💎',
      gradient: 'linear-gradient(135deg, #7c3aed, #a78bfa)',
    }
  }

  return {
    title: '每日推荐',
    subtitle: '根据你的听歌偏好',
    icon: '✨',
    gradient: 'linear-gradient(135deg, #6366f1, #818cf8)',
  }
})

function normalizeTracks(data) {
  return data.map(t => ({
    ...t,
    path: t.file_path || t.path,
    cover: t.cover_url ? (t.cover_url.startsWith('http') ? t.cover_url : `http://127.0.0.1:5000/api/music/cover?path=${encodeURIComponent(t.cover_url)}`) : null,
  }))
}

async function fetchRecommendations() {
  const mode = route.query.mode || 'comprehensive'
  const lang = route.query.lang
  const mood = route.query.mood
  const weatherMood = route.query.weatherMood
  const effectiveMood = weatherMood || mood

  // 先显示缓存
  const cached = getCachedTracks()
  if (cached) {
    tracks.value = normalizeTracks(cached)
  }

  let seed = ''
  if (mode === 'comprehensive') {
    const today = new Date().toISOString().slice(0, 10)
    let hash = 0
    for (let i = 0; i < today.length; i++) {
      hash = ((hash << 5) - hash + today.charCodeAt(i)) | 0
    }
    seed = `&seed=${Math.abs(hash)}`
  }

  let url = `http://127.0.0.1:5000/api/ai/recommend?limit=50&mode=${mode}${seed}`
  if (lang) url += `&lang=${encodeURIComponent(lang)}`
  if (effectiveMood) url += `&mood=${encodeURIComponent(effectiveMood)}`

  isLoading.value = true
  try {
    const res = await fetch(url)
    if (!res.ok) {
      if (!cached) tracks.value = []
      return
    }
    const data = await res.json()
    setCachedTracks(data)
    tracks.value = normalizeTracks(data)
  } catch {
    if (!cached) tracks.value = []
  } finally {
    isLoading.value = false
  }
}

function playTrack(track) {
  const allTracks = tracks.value
  const idx = allTracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(allTracks, idx)
  }
}

function playAll() {
  if (tracks.value.length) {
    playerStore.playAll(tracks.value, 0)
  }
}

watch(() => route.fullPath, fetchRecommendations, { immediate: true })
</script>

<style scoped>
.recommend-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; padding-bottom: 100px; }
.back-link { margin-bottom: 20px; flex-shrink: 0; }

.recommend-header {
  display: flex; align-items: flex-end; gap: 24px;
  margin-bottom: 24px; flex-shrink: 0;
}
.recommend-header__cover {
  width: 200px; height: 200px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.recommend-header__icon { font-size: 64px; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.3)); }
.recommend-header__info h1 { font-size: 28px; font-weight: 700; margin: 0 0 8px; }
.recommend-header__info p { color: var(--text-tertiary); margin: 0 0 2px; font-size: 14px; }
.recommend-header__actions { display: flex; gap: 8px; margin-top: 16px; }

.loading-hint {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 80px 0; color: var(--text-tertiary); font-size: 13px;
}
.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); }
.empty-state p { font-size: 15px; margin: 12px 0; }
.hint { font-size: 13px !important; color: var(--text-tertiary); }
</style>
