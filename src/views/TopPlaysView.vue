<template>
  <div class="top-plays-view">
    <div class="top-plays-view__header">
      <h1>播放次数</h1>
      <div class="header-actions">
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
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
        <el-option label="播放次数" value="play_count" />
        <el-option label="歌名" value="title" />
        <el-option label="歌手" value="artist" />
        <el-option label="最近播放" value="last_played" />
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
      <el-icon size="48"><Trophy /></el-icon>
      <p>{{ list.length ? '无匹配结果' : '暂无播放统计' }}</p>
      <p class="empty-hint" v-if="!list.length">播放歌曲后会自动统计</p>
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
          >
            <span class="col-index">
              <span v-if="sortKey === 'play_count' && sortOrder === 'desc'" class="rank-badge" :class="rankClass(index)">{{ rankIcon(index) }}</span>
              <span v-else class="index-num">{{ index + 1 }}</span>
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
            <span class="col-count">{{ track.play_count || 0 }} 次</span>
            <span class="col-action">
              <el-button text size="small" @click.stop.prevent="playTrack(track)">
                <el-icon><VideoPlay /></el-icon>
              </el-button>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'TopPlaysView' })
import { ref, computed, watch } from 'vue'
import { useVirtualList } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { Search } from '@element-plus/icons-vue'
import { usePlayerStore } from '@/stores/player'
import LazyCover from '@/components/LazyCover.vue'

const playerStore = usePlayerStore()
const { currentTrack } = storeToRefs(playerStore)

const list = ref([])
const loading = ref(false)
const searchQuery = ref('')
const sortKey = ref('play_count')
const sortOrder = ref('desc')

function rankClass(index) {
  if (index === 0) return 'rank--gold'
  if (index === 1) return 'rank--silver'
  if (index === 2) return 'rank--bronze'
  return ''
}
function rankIcon(index) {
  if (index === 0) return '🥇'
  if (index === 1) return '🥈'
  if (index === 2) return '🥉'
  return index + 1
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
    if (sortKey.value === 'play_count') {
      va = Number(va) || 0
      vb = Number(vb) || 0
      return sortOrder.value === 'desc' ? vb - va : va - vb
    }
    if (sortKey.value === 'last_played') {
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
    const res = await fetch('http://127.0.0.1:5000/api/stats/top?limit=100')
    const data = await res.json()
    list.value = Array.isArray(data) ? data.map(item => ({
      path: item.file_path || '',
      title: item.title || '未知歌曲',
      artist: item.artist || '未知歌手',
      album: item.album || '',
      cover: item.cover_url || '',
      play_count: item.play_count || 0,
      last_played: item.last_played,
      duration: 0,
      quality: ''
    })) : []
  } catch {
    // 后端未启动时静默
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

refresh()
</script>

<style scoped>
.top-plays-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.top-plays-view__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.top-plays-view__header h1 { font-size: 28px; font-weight: 700; margin: 0; }
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
  grid-template-columns: 50px 1fr 1fr 72px 48px;
  align-items: center;
  padding: 0 12px; border-radius: 6px;
  height: 64px; transition: background 0.15s; cursor: default;
}
.track-row:hover { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title__name { color: var(--accent-color); }

.col-index { width: 50px; text-align: center; position: relative; }
.col-index .index-num { font-size: 13px; color: var(--text-tertiary); transition: opacity 0.12s; }
.col-index .play-icon { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); cursor: pointer; color: var(--accent-color); opacity: 0; pointer-events: none; transition: opacity 0.12s; }
.track-row:hover .col-index .index-num, .track-row:hover .col-index .rank-badge { opacity: 0; }
.track-row:hover .col-index .play-icon { opacity: 1; pointer-events: auto; }

.rank-badge { font-size: 18px; transition: opacity 0.12s; }

.col-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.col-title__text { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.col-title__name { font-size: 15px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-title__artist-row { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-title__artist { font-size: 12px; line-height: 1.3; color: var(--text-secondary); }

.row-cover { width: 44px; height: 44px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty { background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); }
.col-album { font-size: 14px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-count { font-size: 14px; color: var(--accent-color); font-weight: 600; text-align: center; }
.col-action { text-align: center; }
</style>
