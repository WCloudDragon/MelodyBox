<template>
  <div class="history-view">
    <div class="history-view__header">
      <h1>播放历史</h1>
      <div class="header-actions">
        <el-button @click="toggleSelectMode" :type="multiSelectMode ? 'primary' : 'default'">
          <el-icon><Select /></el-icon>
          {{ multiSelectMode ? '退出多选' : '多选' }}
        </el-button>
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 多选工具栏 -->
    <div v-if="multiSelectMode && selected.size > 0" class="batch-toolbar">
      <span>已选 <span class="batch-toolbar__count">{{ selected.size }}</span> 首</span>
      <span class="batch-toolbar__actions">
        <el-button size="small" @click="batchPlay(filtered.filter(t => selected.has(t.path)))">播放选中</el-button>
        <el-button size="small" @click="batchAddQueue(filtered.filter(t => selected.has(t.path)))">添加到队列</el-button>
        <el-button size="small" @click="selectAll(filtered)">全选</el-button>
        <el-button size="small" @click="clearSelection">取消</el-button>
      </span>
    </div>

    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索歌曲、歌手、专辑..."
        clearable
        :prefix-icon="Search"
        class="search-input"
      />
      <el-select v-model="sortKey" placeholder="排序" class="filter-select">
        <el-option label="播放时间" value="played_at" />
        <el-option label="歌名" value="title" />
        <el-option label="歌手" value="artist" />
      </el-select>
      <el-button text @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'">
        <el-icon><SortUp v-if="sortOrder === 'asc'" /><SortDown v-else /></el-icon>
      </el-button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading && !list.length" class="loading-state">
      <el-icon size="32" class="is-loading"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!filtered.length && !loading" class="empty-state">
      <el-icon size="48"><Timer /></el-icon>
      <p>{{ list.length ? '无匹配结果' : '暂无播放记录' }}</p>
      <p class="empty-hint" v-if="!list.length">播放歌曲后会自动记录</p>
    </div>

    <!-- 列表 -->
    <div v-else class="tracks-list">
      <div v-bind="containerProps" class="tracks-list-body">
        <div v-bind="wrapperProps">
          <div
            v-for="{ data: track, index } in virtualList"
            :key="track.path || index"
            class="track-row"
            v-ripple
            :class="{ playing: currentTrack?.path === track.path }"
            @dblclick="playTrack(track)"
            @contextmenu.prevent="showContextMenu($event, track)"
          >
            <span class="col-index">
              <span class="index-num">{{ index + 1 }}</span>
              <el-icon class="play-icon" size="16" @click.stop="playTrack(track)"><VideoPlay /></el-icon>
            </span>
            <span class="col-title">
              <LazyCover v-if="track.cover" :src="track.cover" class="row-cover" :thumb-size="72" />
              <div v-else class="row-cover row-cover--empty"><el-icon size="14"><Headset /></el-icon></div>
              <div class="col-title__text">
                <span class="col-title__name">{{ track.title }}</span>
                <span class="col-title__artist-row">
                  <span class="col-title__artist">{{ (track.artist || '').split('/').map(s => s.trim()).join(' / ') }}</span>
                </span>
              </div>
            </span>
            <span class="col-album">{{ track.album }}</span>
            <span class="col-time-text" :title="showRelative ? '点击查看具体时间' : '点击查看相对时间'" @click="showRelative = !showRelative">{{ showRelative ? formatPlayedTime(track.played_at) : formatAbsoluteTime(track.played_at) }}</span>
            <span class="col-action">
              <el-checkbox v-if="multiSelectMode" :model-value="isSelected(track)" @change="toggleSelect(track)" />
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右键菜单 -->
    <teleport to="body">
      <div v-if="ctxMenu.visible" class="ctx-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }" @click.stop>
        <div class="ctx-menu-item" @click="ctxAction('play')">播放</div>
        <div class="ctx-menu-item" @click="ctxAction('addQueue')">添加到队列</div>
      </div>
      <div v-if="ctxMenu.visible" class="ctx-menu-backdrop" @click="hideContextMenu"></div>
    </teleport>
  </div>
</template>

<script setup>
defineOptions({ name: 'HistoryView' })
import { ref, computed, watch } from 'vue'
import { useVirtualList } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { Search } from '@element-plus/icons-vue'
import { usePlayerStore } from '@/stores/player'
import { useLibraryStore } from '@/stores/library'
import { useTrackList } from '@/composables/useTrackList'
import { ElMessage } from '@/utils/toast'
import LazyCover from '@/components/LazyCover.vue'

const API_BASE = 'http://127.0.0.1:5000/api/music'

let _audioPort = 51234
async function _initAudioPort() {
  try {
    if (window.electronAPI) {
      const port = await window.electronAPI.getAudioServerPort()
      if (port) _audioPort = port
    }
  } catch {}
}
function coverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http://') || coverPath.startsWith('https://')) return coverPath
  return `${API_BASE}/cover?path=${encodeURIComponent(coverPath)}`
}
function pathToUrl(filePath) {
  if (!filePath) return ''
  return `http://127.0.0.1:${_audioPort}/audio?path=${encodeURIComponent(filePath)}`
}

const playerStore = usePlayerStore()
const libraryStore = useLibraryStore()
const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection } = useTrackList()

const list = ref([])
const loading = ref(false)
const searchQuery = ref('')
const sortKey = ref('played_at')
const sortOrder = ref('desc')

function formatPlayedTime(raw) {
  if (!raw) return ''
  try {
    const d = new Date(raw)
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60000)
    const diffHour = Math.floor(diffMs / 3600000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    if (diffHour < 24) return `${diffHour} 小时前`
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  } catch {
    return raw
  }
}

const showRelative = ref(true)

function formatAbsoluteTime(raw) {
  if (!raw) return ''
  try {
    const d = new Date(raw)
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return raw
  }
}

const filtered = computed(() => {
  let arr = [...list.value]
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    arr = arr.filter(t =>
      (t.title || '').toLowerCase().includes(q) ||
      (t.artist || '').toLowerCase().includes(q) ||
      (t.album || '').toLowerCase().includes(q)
    )
  }
  arr.sort((a, b) => {
    let va = a[sortKey.value] ?? '', vb = b[sortKey.value] ?? ''
    if (sortKey.value === 'played_at') {
      va = new Date(va).getTime() || 0
      vb = new Date(vb).getTime() || 0
      return sortOrder.value === 'desc' ? vb - va : va - vb
    }
    return sortOrder.value === 'desc'
      ? String(vb).localeCompare(String(va))
      : String(va).localeCompare(String(vb))
  })
  return arr
})

const { list: virtualList, containerProps, wrapperProps, scrollTo } = useVirtualList(
  filtered,
  { itemHeight: 64, overscan: 20 }
)

watch(() => filtered.value.length, () => { scrollTo(0) })

async function refresh() {
  loading.value = true
  try {
    await _initAudioPort()
    const res = await fetch('http://127.0.0.1:5000/api/stats/recent?limit=100')
    const data = await res.json()
    const libMap = new Map(libraryStore.tracks.map(t => [t.path, t]))
    list.value = Array.isArray(data) ? data.map(item => {
      const lib = libMap.get(item.file_path)
      return {
        path: item.file_path || '',
        title: item.title || lib?.title || '未知歌曲',
        artist: item.artist || lib?.artist || '未知歌手',
        album: item.album || lib?.album || '',
        cover: coverUrl(item.cover_url || lib?.cover || ''),
        url: pathToUrl(item.file_path || ''),
        lyrics: lib?.lyrics || '',
        duration: lib?.duration || 0,
        quality: lib?.quality || '',
        played_at: item.played_at,
      }
    }) : []
  } catch {
  } finally {
    loading.value = false
  }
}

function playTrack(track) {
  if (!track.path) return
  const idx = list.value.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(list.value.filter(t => t.path), idx)
  }
}

// 右键菜单动作
function ctxAction(action) {
  const track = ctxMenu.value.track
  hideContextMenu()
  if (!track) return
  if (action === 'play') {
    playTrack(track)
  } else if (action === 'addQueue') {
    playerStore.addToQueue(track)
    ElMessage.success('已添加到播放队列')
  }
}

// 批量操作
function batchPlay(tracks) {
  if (!tracks.length) return
  playerStore.playAll(tracks, 0)
}
function batchAddQueue(tracks) {
  tracks.forEach(t => playerStore.addToQueue(t))
  ElMessage.success(`已添加 ${tracks.length} 首到播放队列`)
  clearSelection()
}

refresh()
</script>

<style scoped>
.history-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.history-view__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.history-view__header h1 { font-size: 28px; font-weight: 700; margin: 0; }
.header-actions { display: flex; gap: 8px; }

.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }
.search-input { width: 260px; }
.filter-select { width: 120px; }

.loading-state, .empty-state { text-align: center; padding: 80px 32px; color: var(--text-tertiary); }
.loading-state p, .empty-state p { margin: 16px 0; font-size: 15px; }
.empty-hint { font-size: 13px !important; }

.tracks-list { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.tracks-list-body { flex: 1; overflow-y: auto; min-height: 0; transform: translateZ(0); }
.tracks-list-body::-webkit-scrollbar { width: 6px; }
.tracks-list-body::-webkit-scrollbar-track { background: transparent; }
.tracks-list-body::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
.tracks-list-body::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

.track-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr 120px 48px;
  align-items: center;
  padding: 0 12px; border-radius: 6px;
  height: 64px; transition: background 0.15s; cursor: default;
}
.track-row:hover { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title__name { color: var(--accent-color); }

.col-index { width: 40px; text-align: center; position: relative; }
.col-index .index-num { font-size: 13px; color: var(--text-tertiary); transition: opacity 0.12s; }
.col-index .play-icon { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); cursor: pointer; color: var(--accent-color); opacity: 0; pointer-events: none; transition: opacity 0.12s; }
.track-row:hover .col-index .index-num { opacity: 0; }
.track-row:hover .col-index .play-icon { opacity: 1; pointer-events: auto; }

.col-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.col-title__text { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.col-title__name { font-size: 15px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-title__artist-row { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-title__artist { font-size: 12px; line-height: 1.3; color: var(--text-secondary); }

.row-cover { width: 44px; height: 44px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty { background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); }
.col-album { font-size: 14px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-time-text { font-size: 13px; color: var(--text-tertiary); white-space: nowrap; cursor: pointer; user-select: none; }
.col-time-text:hover { color: var(--accent-color); }
.col-action { text-align: center; }
</style>
