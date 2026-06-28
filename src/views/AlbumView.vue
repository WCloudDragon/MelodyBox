<template>
  <div class="album-view">
    <div class="back-link">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <div v-if="album" class="album-content">
      <div class="album-header">
        <div class="album-cover">
          <LazyCover v-if="album.cover" :src="album.cover" />
          <div v-else class="cover-placeholder">
            <el-icon size="48"><Folder /></el-icon>
          </div>
        </div>
        <div class="album-info">
          <h1>{{ album.name }}</h1>
          <p>{{ album.artist }} · {{ album.tracks.length }} 首歌曲</p>
          <p v-if="album.year">发行年份：{{ album.year }}</p>
        </div>
      </div>

      <div class="section-header">
        <h3>歌曲列表</h3>
        <div class="section-header__actions">
          <el-button type="primary" @click="playAll">播放全部</el-button>
          <el-button @click="toggleSelectMode" :type="multiSelectMode ? 'primary' : 'default'">
            <el-icon><Select /></el-icon>
            {{ multiSelectMode ? '退出多选' : '多选' }}
          </el-button>
        </div>
      </div>

      <!-- 多选工具栏 -->
      <div v-if="multiSelectMode && selected.size > 0" class="batch-toolbar">
        <span>已选 <span class="batch-toolbar__count">{{ selected.size }}</span> 首</span>
        <span class="batch-toolbar__actions">
          <el-button size="small" @click="batchPlay(album.tracks.filter(t => selected.has(t.path)))">播放选中</el-button>
          <el-button size="small" @click="batchAddQueueNext(album.tracks.filter(t => selected.has(t.path)))">插播至当前播放后</el-button>
          <el-button size="small" @click="batchAddQueue(album.tracks.filter(t => selected.has(t.path)))">插播至队列末尾</el-button>
          <el-button size="small" @click="selectAll(album.tracks)">全选</el-button>
          <el-button size="small" @click="clearSelection">取消</el-button>
        </span>
      </div>

      <div class="tracks-list">
        <template v-for="(group, gi) in discGroups" :key="gi">
          <div v-if="discGroups.length > 1" class="disc-header">Disc {{ group.disc }}</div>
          <div
            v-for="(track, index) in group.tracks"
            :key="track.path"
            class="track-row"
            v-ripple
            :class="{ playing: currentTrack?.path === track.path, 'track-row--ctx-active': contextMenuTarget === track.path }"
            @dblclick="playTrack(track)"
            @contextmenu.prevent="showContextMenu($event, track)"
          >
            <span class="col-index">
              <span class="index-num">{{ track.track_number || index + 1 + gi * 100 }}</span>
              <el-icon class="play-icon" v-ripple size="16" @click.stop="playTrack(track)"><VideoPlay /></el-icon>
            </span>
            <span class="col-title">
              <span>{{ track.title }}</span>
            </span>
            <span class="col-artist">{{ track.artist.split('/').map(s => s.trim()).join(' / ') }}</span>
            <span class="col-quality">
              <span v-if="track.quality" class="quality-tag" :class="qualityClass(track.quality)">{{ track.quality }}</span>
            </span>
            <span class="col-time">{{ formatDuration(track.duration) }}</span>
            <span class="col-action">
              <el-checkbox v-if="multiSelectMode" :model-value="isSelected(track)" @change="toggleSelect(track)" />
            </span>
          </div>
        </template>
      </div>
    </div>

    <div v-else class="empty-state">
      <p>未找到该专辑信息</p>
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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import { useTrackList } from '@/composables/useTrackList'
import { formatDuration, qualityClass } from '@/utils/format'
import { ElMessage } from '@/utils/toast'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'

const route = useRoute()
const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()
const router = useRouter()
const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, contextMenuTarget, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)

const menuItems = computed(() => buildMenuItems('default'))

const album = computed(() => {
  const name = route.params.id
  if (!name) return null
  return libraryStore.getAlbum(decodeURIComponent(name))
})

// 按碟号分组（空值视为 Disc 1）
const discGroups = computed(() => {
  if (!album.value) return []
  const groups = []
  const discMap = new Map()
  for (const t of album.value.tracks) {
    const d = t.disc_number || 1
    if (!discMap.has(d)) discMap.set(d, [])
    discMap.get(d).push(t)
  }
  for (const [disc, tracks] of discMap) {
    groups.push({ disc, tracks })
  }
  return groups.sort((a, b) => a.disc - b.disc)
})

function playTrack(track) {
  if (!album.value) return
  const idx = album.value.tracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(album.value.tracks, idx)
  }
}

function playAll() {
  if (album.value) {
    playerStore.playAll(album.value.tracks)
  }
}

function ctxAction(action) {
  ctxHandler(action)
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
.album-view { padding-bottom: 100px; }
.back-link { margin-bottom: 20px; }

.album-header {
  display: flex; align-items: flex-end; gap: 24px;
  margin-bottom: 32px;
}
.album-cover {
  width: 200px; height: 200px; border-radius: 12px;
  overflow: hidden; flex-shrink: 0;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.album-cover img,
.album-cover .lazy-cover { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder {
  width: 100%; height: 100%;
  background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.album-info h1 { font-size: 28px; font-weight: 700; margin: 0 0 8px; }
.album-info p { color: var(--text-tertiary); margin: 0 0 2px; font-size: 14px; }

.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.section-header h3 { font-size: 18px; margin: 0; }
.section-header__actions { display: flex; gap: 8px; align-items: center; }

.disc-header {
  display: flex; align-items: center;
  padding: 16px 12px 6px;
  font-size: 13px; font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
  content-visibility: auto;
  contain-intrinsic-size: 38px;
}

.track-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr 52px 60px 40px;
  align-items: center;
  padding: 0 12px;
  height: 64px;
  border-radius: 6px;
  transition: background 0.15s;
  content-visibility: auto;
  contain-intrinsic-size: 64px;
  contain: layout style paint;
}
.track-row:hover, .track-row--ctx-active { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title { color: var(--accent-color); }
.track-row--ctx-active { background: var(--hover-bg); }

.col-index { width: 40px; text-align: center; }
.col-index .index-num { font-size: 13px; color: var(--text-tertiary); }
.col-index .play-icon { display: none; cursor: pointer; color: var(--accent-color); }
.track-row:hover .col-index .index-num, .track-row--ctx-active .col-index .index-num { display: none; }
.track-row:hover .col-index .play-icon, .track-row--ctx-active .col-index .play-icon { display: inline-flex; }

.col-title { min-width: 0; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-artist { font-size: 14px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; }
.col-time { width: 60px; text-align: right; font-size: 13px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.col-action { text-align: center; }

.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); }
</style>
