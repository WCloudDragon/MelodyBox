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
    <div v-if="isLoading" class="loading-hint">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在生成推荐...</span>
    </div>

    <!-- 歌曲列表 -->
    <div v-else-if="tracks.length > 0" class="tracks-list">
      <div class="track-table-header">
        <span class="col-index">#</span>
        <span class="col-title">歌曲</span>
        <span class="col-artist">歌手</span>
        <span class="col-album">专辑</span>
        <span class="col-quality">音质</span>
        <span class="col-time">时长</span>
      </div>
      <div class="tracks-list-body">
        <div
          v-for="(track, index) in tracks"
          :key="track.song_id"
          class="track-row"
          :class="{ playing: currentTrack?.path === track.path }"
          v-ripple
          @dblclick="playTrack(track)"
        >
          <span class="col-index">
            <span class="index-num">{{ index + 1 }}</span>
            <el-icon class="play-icon" v-ripple size="16" @click.stop="playTrack(track)"><VideoPlay /></el-icon>
          </span>
          <span class="col-title">
            <LazyCover v-if="track.cover" :src="track.cover" class="row-cover" :thumb-size="72" />
            <div v-else class="row-cover row-cover--empty"><el-icon size="14"><Headset /></el-icon></div>
            <div class="col-title__text">
              <span>{{ track.title }}</span>
              <span v-if="track.reason" class="track-reason">{{ track.reason }}</span>
            </div>
          </span>
          <span class="col-artist">{{ (track.artist || '').split('/').map(s => s.trim()).join(' / ') }}</span>
          <span class="col-album">{{ track.album || '' }}</span>
          <span class="col-quality">
            <span v-if="track.quality" class="quality-tag" :class="qualityClass(track.quality)">{{ track.quality }}</span>
          </span>
          <span class="col-time">{{ formatDuration(track.duration) }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p>暂无推荐结果</p>
      <p class="hint" v-if="!aiStore.embeddingStatus.ready">
        需要先生成 AI 向量才能获得个性化推荐
      </p>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'RecommendPlaylistView' })
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { useAiStore } from '@/stores/ai'
import { useLibraryStore } from '@/stores/library'
import { formatDuration, qualityClass } from '@/utils/format'
import LazyCover from '@/components/LazyCover.vue'

const route = useRoute()
const playerStore = usePlayerStore()
const aiStore = useAiStore()
const libraryStore = useLibraryStore()
const { currentTrack } = storeToRefs(playerStore)

const tracks = ref([])
const isLoading = ref(false)

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

async function fetchRecommendations() {
  const mode = route.query.mode || 'comprehensive'
  const lang = route.query.lang
  const mood = route.query.mood
  const weatherMood = route.query.weatherMood

  // 天气推荐：用 weatherMood 参数覆盖 mood
  const effectiveMood = weatherMood || mood

  // 每日推荐：使用当日固定种子
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
      tracks.value = []
      return
    }
    const data = await res.json()
    for (const s of data) {
      if (s.cover_url && !s.cover_url.startsWith('http')) {
        s.cover_url = `http://127.0.0.1:5000/api/music/cover?path=${encodeURIComponent(s.cover_url)}`
      }
      s.path = s.file_path
      s.cover = s.cover_url
    }
    tracks.value = data
  } catch {
    tracks.value = []
  } finally {
    isLoading.value = false
  }
}

function playTrack(track) {
  const allTracks = tracks.value
  const idx = allTracks.findIndex(t => t.song_id === track.song_id)
  if (idx !== -1) {
    // 补全 path 用于播放
    const allTracksFixed = allTracks.map(t => ({
      ...t,
      path: t.file_path,
    }))
    playerStore.playAll(allTracksFixed, idx)
  }
}

function playAll() {
  const allTracksFixed = tracks.value.map(t => ({
    ...t,
    path: t.file_path,
  }))
  playerStore.playAll(allTracksFixed, 0)
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

.tracks-list { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.track-table-header {
  display: flex; align-items: center;
  padding: 10px 12px; font-size: 11px;
  color: var(--text-tertiary); text-transform: uppercase;
  letter-spacing: 1px; border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.tracks-list-body { flex: 1; overflow-y: auto; min-height: 0; }
.tracks-list-body::-webkit-scrollbar { width: 6px; }
.tracks-list-body::-webkit-scrollbar-track { background: transparent; }
.tracks-list-body::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }

.track-row {
  display: flex; align-items: center;
  padding: 0 12px; border-radius: 6px;
  height: 52px; transition: background 0.15s; cursor: default;
}
.track-row:hover { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title__text span:first-child { color: var(--accent-color); }

.col-index { width: 40px; text-align: center; position: relative; }
.col-index .index-num { font-size: 12px; color: var(--text-tertiary); transition: opacity 0.12s; }
.col-index .play-icon {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  cursor: pointer; color: var(--accent-color);
  opacity: 0; pointer-events: none; transition: opacity 0.12s;
}
.track-row:hover .col-index .index-num { opacity: 0; }
.track-row:hover .col-index .play-icon { opacity: 1; pointer-events: auto; }

.col-title { flex: 1; display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 13px; overflow: hidden; }
.col-title__text { display: flex; flex-direction: column; min-width: 0; }
.col-title__text span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track-reason { font-size: 11px; color: var(--text-tertiary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-cover { width: 36px; height: 36px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty {
  background: var(--bg-tertiary); display: flex;
  align-items: center; justify-content: center; color: var(--text-tertiary);
}
.col-artist { width: 160px; font-size: 13px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-album { width: 180px; font-size: 13px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; font-size: 11px; }
.col-time { width: 60px; text-align: right; font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }

.loading-hint {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 80px 0; color: var(--text-tertiary); font-size: 13px;
}
.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); }
.empty-state p { font-size: 15px; margin: 12px 0; }
.hint { font-size: 13px !important; color: var(--text-tertiary); }
</style>
