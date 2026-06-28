<template>
  <div class="track-info-view">
    <div class="back-link">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <el-icon size="32" class="is-loading"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 未找到 -->
    <div v-else-if="!track" class="empty-state">
      <el-icon size="48"><WarningFilled /></el-icon>
      <p>未找到该音轨信息</p>
    </div>

    <!-- 音轨详情 -->
    <div v-else class="track-detail">
      <!-- 英雄区域 -->
      <div class="hero">
        <div class="hero-cover">
          <LazyCover v-if="track.cover" :src="track.cover" />
          <div v-else class="hero-cover--empty">
            <el-icon size="64"><Headset /></el-icon>
          </div>
        </div>
        <div class="hero-info">
          <h1 class="hero-title">{{ track.title }}</h1>
          <p class="hero-artist">{{ track.artist }}</p>
          <p class="hero-album" v-if="track.album && track.album !== '未知专辑'">{{ track.album }}</p>
          <div class="hero-meta">
            <span v-if="track.year" class="hero-meta__item">{{ track.year }}</span>
            <span v-if="track.genre && track.genre !== '未知'" class="hero-meta__item">{{ track.genre }}</span>
            <span class="hero-meta__item">{{ formatDuration(track.duration) }}</span>
            <span v-if="track.quality" class="quality-tag" :class="qualityClass(track.quality)">{{ track.quality }}</span>
          </div>
        </div>
      </div>

      <!-- 信息卡片网格 -->
      <div class="info-grid">
        <!-- 音质信息 -->
        <div class="info-card">
          <h3 class="info-card__title">
            <el-icon><Headset /></el-icon>
            音质信息
          </h3>
          <div class="info-card__body">
            <div class="info-row">
              <span class="info-row__label">音质等级</span>
              <span class="info-row__value" v-if="track.quality">{{ qualityLabel(track.quality) }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">码率</span>
              <span class="info-row__value" v-if="track.bitrate">{{ formatBitrate(track.bitrate) }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">采样率</span>
              <span class="info-row__value" v-if="track.sampleRate">{{ formatSampleRate(track.sampleRate) }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">位深度</span>
              <span class="info-row__value" v-if="track.bitDepth">{{ track.bitDepth }} bit</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
          </div>
        </div>

        <!-- 文件信息 -->
        <div class="info-card">
          <h3 class="info-card__title">
            <el-icon><Document /></el-icon>
            文件信息
          </h3>
          <div class="info-card__body">
            <div class="info-row">
              <span class="info-row__label">文件名</span>
              <span class="info-row__value" :title="track.path">{{ fileName }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">文件格式</span>
              <span class="info-row__value">{{ fileFormat }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">文件大小</span>
              <span class="info-row__value" v-if="track.file_size">{{ formatFileSize(track.file_size) }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">修改时间</span>
              <span class="info-row__value" v-if="track.file_mtime">{{ formatMtime(track.file_mtime) }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
          </div>
        </div>

        <!-- 专辑/曲目信息 -->
        <div class="info-card">
          <h3 class="info-card__title">
            <el-icon><Collection /></el-icon>
            专辑信息
          </h3>
          <div class="info-card__body">
            <div class="info-row">
              <span class="info-row__label">专辑</span>
              <span class="info-row__value">{{ track.album || '未知' }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">歌手</span>
              <span class="info-row__value">{{ track.artist || '未知' }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">发行年份</span>
              <span class="info-row__value" v-if="track.year">{{ track.year }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">流派</span>
              <span class="info-row__value" v-if="track.genre && track.genre !== '未知'">{{ track.genre }}</span>
              <span class="info-row__value info-row__value--muted" v-else>未知</span>
            </div>
            <div class="info-row" v-if="track.disc_number > 0">
              <span class="info-row__label">碟号 / 曲目号</span>
              <span class="info-row__value">Disc {{ track.disc_number }} · #{{ track.track_number || '-' }}</span>
            </div>
            <div class="info-row" v-else-if="track.track_number > 0">
              <span class="info-row__label">曲目号</span>
              <span class="info-row__value">#{{ track.track_number }}</span>
            </div>
          </div>
        </div>

        <!-- 文件路径 -->
        <div class="info-card">
          <h3 class="info-card__title">
            <el-icon><FolderOpened /></el-icon>
            文件路径
          </h3>
          <div class="info-card__body">
            <div class="info-row info-row--full">
              <span class="info-row__value info-row__value--path">{{ track.path }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'TrackInfoView' })
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useLibraryStore } from '@/stores/library'
import { formatDuration, qualityClass } from '@/utils/format'
import LazyCover from '@/components/LazyCover.vue'

const route = useRoute()
const libraryStore = useLibraryStore()

const track = ref(null)
const loading = ref(true)

const API_BASE = 'http://127.0.0.1:5000/api/music'

const fileName = computed(() => {
  if (!track.value?.path) return ''
  return track.value.path.split(/[/\\]/).pop() || ''
})

const fileFormat = computed(() => {
  if (!track.value?.path) return ''
  const ext = track.value.path.split('.').pop()?.toUpperCase()
  return ext || '未知'
})

function formatBitrate(bps) {
  if (!bps) return ''
  if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps'
  return Math.round(bps / 1000) + ' kbps'
}

function formatSampleRate(hz) {
  if (!hz) return ''
  if (hz >= 1000) return (hz / 1000).toFixed(1) + ' kHz'
  return hz + ' Hz'
}

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(2) + ' GB'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB'
  return bytes + ' B'
}

function formatMtime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function qualityLabel(quality) {
  const map = { 'HQ': '高品质 (有损)', 'CD': 'CD 音质 (无损)', 'CD+': 'CD+ 音质 (无损)', 'Hi-Res': '高解析度 (Hi-Res)' }
  return map[quality] || quality
}

async function fetchTrack(path) {
  loading.value = true
  track.value = null
  try {
    // 优先从 libraryStore 查找（已有全量数据）
    const libTrack = libraryStore.tracks.find(t => t.path === path)
    if (libTrack) {
      track.value = { ...libTrack }
    }
    // 从后端获取完整数据（补全所有字段）
    const res = await fetch(`${API_BASE}/songs/by-path?path=${encodeURIComponent(path)}`)
    const data = await res.json()
    if (data && !data.error) {
      // 合并后端完整数据 + 前端已有的 cover url 等
      track.value = {
        ...data,
        cover: data.cover
          ? (data.cover.startsWith('http') ? data.cover : `${API_BASE}/cover?path=${encodeURIComponent(data.cover)}`)
          : libTrack?.cover || '',
      }
    } else if (libTrack) {
      // 后端无记录但有本地数据
      track.value = libTrack
    }
  } catch {
  } finally {
    loading.value = false
  }
}

watch(() => route.query.path, (p) => {
  if (p) fetchTrack(p)
}, { immediate: true })
</script>

<style scoped>
.track-info-view { padding-bottom: 100px; max-width: 900px; }
.back-link { margin-bottom: 24px; }

.loading-state, .empty-state { text-align: center; padding: 80px 32px; color: var(--text-tertiary); }
.loading-state p, .empty-state p { margin: 16px 0; font-size: 15px; }

/* 英雄区域 */
.hero {
  display: flex; gap: 32px; align-items: center;
  margin-bottom: 40px;
}
.hero-cover {
  width: 280px; height: 280px; border-radius: 16px;
  overflow: hidden; flex-shrink: 0;
  box-shadow: 0 12px 40px rgba(0,0,0,0.4);
}
.hero-cover img, .hero-cover .lazy-cover { width: 100%; height: 100%; object-fit: cover; }
.hero-cover--empty {
  width: 100%; height: 100%;
  background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.hero-info { flex: 1; min-width: 0; }
.hero-title { font-size: 32px; font-weight: 700; margin: 0 0 8px; line-height: 1.2; }
.hero-artist { font-size: 18px; color: var(--text-secondary); margin: 0 0 4px; }
.hero-album { font-size: 15px; color: var(--text-tertiary); margin: 0 0 16px; }
.hero-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.hero-meta__item {
  padding: 4px 10px; font-size: 12px; border-radius: 4px;
  background: var(--bg-tertiary); color: var(--text-secondary);
}
.quality-tag {
  padding: 3px 8px; font-size: 11px; border-radius: 4px;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
}
.quality-tag.HQ { background: rgba(64,158,255,0.15); color: #409EFF; }
.quality-tag.CD { background: rgba(103,194,58,0.15); color: #67c23a; }
.quality-tag.CD\+ { background: rgba(230,162,60,0.15); color: #e6a23c; }
.quality-tag.Hi-Res { background: rgba(245,108,108,0.15); color: #f56c6c; }

/* 信息卡片网格 */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.info-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px; overflow: hidden;
}
.info-card:last-child { grid-column: 1 / -1; }
.info-card__title {
  display: flex; align-items: center; gap: 8px;
  margin: 0; padding: 14px 20px;
  font-size: 14px; font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
}
.info-card__title .el-icon { color: var(--accent-color); }
.info-card__body { padding: 8px 0; }

.info-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 20px;
}
.info-row:hover { background: var(--bg-tertiary); }
.info-row__label {
  font-size: 13px; color: var(--text-tertiary);
  white-space: nowrap; min-width: 80px;
}
.info-row__value { font-size: 14px; color: var(--text-primary); }
.info-row__value--muted { color: var(--text-tertiary); font-style: italic; }
.info-row__value--path {
  font-size: 12px; color: var(--text-secondary);
  word-break: break-all; font-family: 'Consolas', 'Courier New', monospace;
}
.info-row--full { padding: 12px 20px; }
.info-row--full .info-row__label { min-width: auto; }
</style>
