<template>
  <div class="library-view">
    <div class="library-view__header">
      <h1>音乐库</h1>
      <div class="header-actions">
        <el-button @click="toggleSelectMode" :type="multiSelectMode ? 'primary' : 'default'">
          <el-icon><Select /></el-icon>
          {{ multiSelectMode ? '退出多选' : '多选' }}
        </el-button>
        <el-button @click="handleImport" :loading="libraryStore.isScanning" v-if="isElectron">
          <el-icon><FolderOpened /></el-icon>
          导入音乐
        </el-button>
        <el-button @click="libraryStore.refreshLibrary" :loading="libraryStore.isLoading" v-if="isElectron && libraryStore.scanDirs.length > 0">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 多选工具栏 -->
    <div v-if="multiSelectMode && selected.size > 0" class="batch-toolbar">
      <span>已选 <span class="batch-toolbar__count">{{ selected.size }}</span> 首</span>
      <span class="batch-toolbar__actions">
        <el-button size="small" @click="batchPlay(libraryStore.filteredTracks.filter(t => selected.has(t.path)))">播放选中</el-button>
        <el-button size="small" @click="batchAddQueueNext(libraryStore.filteredTracks.filter(t => selected.has(t.path)))">插播至当前播放后</el-button>
        <el-button size="small" @click="batchAddQueue(libraryStore.filteredTracks.filter(t => selected.has(t.path)))">插播至队列末尾</el-button>
        <el-button size="small" @click="selectAll(libraryStore.filteredTracks)">全选</el-button>
        <el-button size="small" @click="clearSelection">取消</el-button>
      </span>
    </div>

    <!-- 搜索与筛选 -->
    <div class="toolbar">
      <el-input
        v-model="libraryStore.searchQuery"
        placeholder="搜索歌曲、歌手、专辑..."
        clearable
        :prefix-icon="Search"
        class="search-input"
      />
      <el-select
        v-model="libraryStore.filterGenre"
        placeholder="流派"
        clearable
        class="filter-select"
      >
        <el-option v-for="g in libraryStore.genres" :key="g" :label="g" :value="g" />
      </el-select>
      <el-select
        v-model="libraryStore.sortKey"
        placeholder="排序"
        class="filter-select"
      >
        <el-option label="歌名" value="title" />
        <el-option label="歌手" value="artist" />
        <el-option label="专辑" value="album" />
        <el-option label="年份" value="year" />
        <el-option label="时长" value="duration" />
      </el-select>
      <el-button text @click="toggleSortOrder">
        <el-icon><SortUp v-if="libraryStore.sortOrder === 'asc'" /><SortDown v-else /></el-icon>
      </el-button>
      <el-radio-group v-model="sourceFilter" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="local">本地</el-radio-button>
        <el-radio-button value="cloud">云端</el-radio-button>
      </el-radio-group>
      <el-radio-group v-model="libraryStore.viewMode" size="small">
        <el-radio-button value="list">
          <el-icon><List /></el-icon>
        </el-radio-button>
        <el-radio-button value="grid">
          <el-icon><Grid /></el-icon>
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 空状态 -->
    <div v-if="!hasMusic && !libraryStore.isLoading" class="empty-state">
      <el-icon size="48"><Folder /></el-icon>
      <p>音乐库为空</p>
      <el-button type="primary" @click="handleImport" v-if="isElectron">导入本地音乐</el-button>
    </div>

    <div v-else-if="libraryStore.isLoading" class="loading-state">
      <el-icon size="32" class="is-loading"><Loading /></el-icon>
      <p>正在扫描音乐文件...</p>
    </div>

    <!-- 网格视图 -->
    <div v-else-if="libraryStore.viewMode === 'grid'" class="tracks-grid">
      <MusicCard
        v-for="track in libraryStore.filteredTracks"
        :key="track.path"
        :track="track"
        @play="playTrack(track)"
        @click="showTrackDetail(track)"
      />
    </div>

    <!-- 列表视图 -->
    <div v-else class="tracks-list">
      <div v-bind="containerProps" class="tracks-list-body">
        <div v-if="!virtualList.length" class="empty-list-tip">无匹配歌曲</div>
        <div v-bind="wrapperProps">
          <div
            v-for="{ data: track, index } in virtualList"
            :key="track.path"
            class="track-row"
            v-ripple
            :class="{ playing: currentTrack?.path === track.path, 'track-row--ctx-active': contextMenuTarget === track.path }"
            @dblclick="playTrack(track)"
            @contextmenu.prevent="showContextMenu($event, track)"
          >
            <span class="col-index">
              <span class="index-num">{{ index + 1 }}</span>
              <el-icon class="play-icon" v-ripple size="16" @click.stop="playTrack(track)"><VideoPlay /></el-icon>
            </span>
            <span class="col-title">
              <LazyCover v-if="track.cover" :src="track.cover" class="row-cover" :thumb-size="72" />
              <div v-else class="row-cover row-cover--empty"><el-icon size="14"><Headset /></el-icon></div>
              <div class="col-title__text">
                <span class="col-title__name">{{ track.title }}</span>
                <span class="col-title__artist-row">
                  <template v-for="(artist, ai) in track.artist.split('/')" :key="ai">
                    <router-link :to="`/artist/${encodeURIComponent(artist.trim())}`" class="link col-title__artist">{{ artist.trim() }}</router-link>
                    <span v-if="ai < track.artist.split('/').length - 1" class="col-title__sep"> / </span>
                  </template>
                </span>
              </div>
            </span>
            <span class="col-album">
              <router-link :to="`/album/${encodeURIComponent(track.album)}`" class="link">{{ track.album }}</router-link>
            </span>
            <span class="col-quality">
              <span v-if="track.quality" class="quality-tag" :class="qualityClass(track.quality)">{{ track.quality }}</span>
            </span>
            <span class="col-time">{{ formatDuration(track.duration) }}</span>
            <span class="col-action">
              <el-checkbox v-if="multiSelectMode" :model-value="isSelected(track)" @change="toggleSelect(track)" />
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 歌曲详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="detailTrack?.title" width="480px">
      <div class="track-detail" v-if="detailTrack">
        <div class="detail-cover">
          <img v-if="detailTrack.cover" :src="detailTrack.cover" />
          <div v-else class="detail-cover--empty"><el-icon size="48"><Headset /></el-icon></div>
        </div>
        <div class="detail-info">
          <p><strong>歌手：</strong>{{ detailTrack.artist }}</p>
          <p><strong>专辑：</strong>{{ detailTrack.album }}</p>
          <p v-if="detailTrack.year"><strong>年份：</strong>{{ detailTrack.year }}</p>
          <p><strong>流派：</strong>{{ detailTrack.genre }}</p>
          <p><strong>时长：</strong>{{ formatDuration(detailTrack.duration) }}</p>
          <p v-if="detailTrack.bitrate"><strong>比特率：</strong>{{ formatBitrate(detailTrack.bitrate) }}</p>
          <p v-if="detailTrack.sampleRate"><strong>采样率：</strong>{{ formatSampleRate(detailTrack.sampleRate) }}</p>
          <p v-if="detailTrack.bitDepth"><strong>位深：</strong>{{ detailTrack.bitDepth }} bit</p>
          <p v-if="detailTrack.quality"><strong>音质：</strong><span class="quality-tag" :class="qualityClass(detailTrack.quality)">{{ detailTrack.quality }}</span></p>
          <p><strong>路径：</strong><span class="path-text">{{ detailTrack.path }}</span></p>
        </div>
      </div>
      <template #footer>
        <el-button @click="playTrack(detailTrack)" type="primary">播放</el-button>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 定位当前播放按钮 -->
    <div
      v-show="currentTrack"
      class="locate-btn"
      @click="scrollToCurrentTrack"
      title="定位到正在播放"
    >
      <el-icon size="18"><VideoPlay /></el-icon>
    </div>

    <!-- 全局操作菜单 -->
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
defineOptions({ name: 'LibraryView' })
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useVirtualList } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { Search } from '@element-plus/icons-vue'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import { usePlaylistStore } from '@/stores/playlist'
import { formatDuration, formatBitrate, formatSampleRate, qualityClass } from '@/utils/format'
import { showScanNotify, updateScanNotify, closeScanNotify, clearScanNotify } from '@/utils/scanNotify'
import MusicCard from '@/components/music/MusicCard.vue'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'
import { ElMessage } from '@/utils/toast'
import { useScrollMemory } from '@/composables/useScrollMemory'
import { useTrackList } from '@/composables/useTrackList'

const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()
const router = useRouter()
const playlistStore = usePlaylistStore()

// 扫描进度通知
watch(() => libraryStore.isScanning, (scanning) => {
  if (scanning) { showScanNotify() }
})
watch(() => libraryStore.scanProgress, (p) => {
  if (p.total > 0) updateScanNotify(p.current, p.total, p.path)
  if (!p.scanning) {
    closeScanNotify(p, () => libraryStore.loadFromApi())
  }
})
onBeforeUnmount(clearScanNotify)

const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, contextMenuTarget, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems, showAddPlaylistDialog } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)
const sourceFilter = ref('all')

const menuItems = computed(() => buildMenuItems('library'))

useScrollMemory('library-list', () => document.querySelector('.tracks-list-body'))
useScrollMemory('library-grid', () => document.querySelector('.tracks-grid'))

const isElectron = computed(() => !!window.electronAPI)
const hasMusic = computed(() => libraryStore.tracks.length > 0 || libraryStore.cloudTracks.length > 0)

// 虚拟滚动（仅渲染可见 + 缓冲区行数，初始秒开）
const { list: virtualList, containerProps, wrapperProps, scrollTo } = useVirtualList(
  computed(() => libraryStore.filteredTracks),
  { itemHeight: 64, overscan: 20 }
)

// 筛选/排序变化时自动滚回顶部
watch(() => libraryStore.filteredTracks.length, () => {
  scrollTo(0)
})

// 来源切换器
watch(sourceFilter, (v) => libraryStore.setSourceFilter(v))

function ctxAction(action) {
  if (ctxHandler(action)) return
  if (action === 'addToPlaylist') showAddPlaylistDialog(ctxMenu.value.track)
}

const detailVisible = ref(false)
const detailTrack = ref(null)

function handleImport() {
  libraryStore.selectAndScan()
}

function toggleSortOrder() {
  libraryStore.sortOrder = libraryStore.sortOrder === 'asc' ? 'desc' : 'asc'
}

function playTrack(track) {
  const idx = libraryStore.allTracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(libraryStore.allTracks, idx)
  }
}

function showTrackDetail(track) {
  detailTrack.value = track
  detailVisible.value = true
}

function scrollToCurrentTrack() {
  if (!currentTrack.value) return
  if (libraryStore.viewMode === 'list') {
    // 列表视图：使用虚拟滚动 scrollTo
    const idx = libraryStore.filteredTracks.findIndex(t => t.path === currentTrack.value.path)
    if (idx !== -1) scrollTo(idx)
  } else {
    // 网格视图：通过 data-track-path 查找 DOM 并滚动
    const el = document.querySelector(`.tracks-grid [data-track-path="${currentTrack.value.path}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

// 批量操作
function batchPlay(tracks) {
  if (!tracks.length) return
  playerStore.playAll(tracks, 0)
}
function batchAddQueue(tracks) {
  tracks.forEach(t => playerStore.addToQueue(t))
  ElMessage.success(`已插播 ${tracks.length} 首至队列末尾`)
  clearSelection()
}
function batchAddQueueNext(tracks) {
  tracks.forEach((t, i) => {
    playerStore.addToQueueNext(t)
  })
  ElMessage.success(`已插播 ${tracks.length} 首至下一位置`)
  clearSelection()
}
</script>

<style scoped>
.library-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.library-view__header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 24px;
}
.library-view__header h1 { font-size: 28px; font-weight: 700; margin: 0; }
.header-actions { display: flex; gap: 8px; }

.toolbar {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 24px; flex-wrap: wrap;
}
.search-input { width: 260px; }
.filter-select { width: 120px; }

.empty-state, .loading-state {
  text-align: center; padding: 80px 32px;
  color: var(--text-tertiary);
}
.empty-state p, .loading-state p { margin: 16px 0; font-size: 15px; }

.tracks-grid { display: flex; flex-wrap: wrap; gap: 4px; overflow-y: auto; min-height: 0; will-change: scroll-position; }
.tracks-grid::-webkit-scrollbar { width: 6px; }
.tracks-grid::-webkit-scrollbar-track { background: transparent; }
.tracks-grid::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }

/* 列表视图 */
.tracks-list { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.tracks-list-body { flex: 1; overflow-y: auto; min-height: 0; transform: translateZ(0); }
.tracks-list-body::-webkit-scrollbar { width: 6px; }
.tracks-list-body::-webkit-scrollbar-track { background: transparent; }
.tracks-list-body::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
.tracks-list-body::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
.tracks-list-body .empty-list-tip { padding: 40px; text-align: center; color: var(--text-tertiary); }
.track-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr 52px 60px 40px;
  align-items: center;
  padding: 0 12px; border-radius: 6px;
  height: 64px; transition: background 0.15s; cursor: default;
}
.track-row:hover, .track-row--ctx-active { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title__name { color: var(--accent-color); }
.track-row--ctx-active { background: var(--hover-bg); }

.col-index { width: 40px; text-align: center; position: relative; }
.col-index .index-num { font-size: 13px; color: var(--text-tertiary); transition: opacity 0.12s; }
.col-index .play-icon {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  cursor: pointer; color: var(--accent-color);
  opacity: 0; pointer-events: none; transition: opacity 0.12s;
}
.track-row:hover .col-index .index-num, .track-row--ctx-active .col-index .index-num { opacity: 0; }
.track-row:hover .col-index .play-icon, .track-row--ctx-active .col-index .play-icon { opacity: 1; pointer-events: auto; }

.col-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.col-title__text { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.col-title__name { font-size: 15px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-title__artist-row { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-title__artist { font-size: 12px; line-height: 1.3; }
.col-title__sep { font-size: 12px; color: var(--text-tertiary); }
.row-cover { width: 44px; height: 44px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty {
  background: var(--bg-tertiary); display: flex;
  align-items: center; justify-content: center; color: var(--text-tertiary);
}
.col-album { font-size: 14px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; }
.col-time { width: 60px; text-align: right; font-size: 13px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.col-action { width: 40px; text-align: center; }

.link { color: var(--text-secondary); text-decoration: none; }
.link:hover { color: var(--accent-color); text-decoration: underline; }

/* 详情弹窗 */
.track-detail { display: flex; gap: 24px; }
.detail-cover { width: 160px; height: 160px; border-radius: 10px; overflow: hidden; flex-shrink: 0; }
.detail-cover img { width: 100%; height: 100%; object-fit: cover; }
.detail-cover--empty {
  background: var(--bg-tertiary); display: flex;
  align-items: center; justify-content: center; color: var(--text-tertiary);
}
.detail-info { font-size: 13px; line-height: 2; }
.detail-info p { margin: 0; }
.path-text { font-size: 11px; color: var(--text-tertiary); word-break: break-all; }

.locate-btn {
  position: fixed;
  bottom: 112px;
  right: 40px;
  z-index: 100;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--accent-color);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
  transition: transform 0.2s, opacity 0.2s;
}
.locate-btn:hover {
  transform: scale(1.1);
}
.locate-btn:active {
  transform: scale(0.95);
}
</style>
