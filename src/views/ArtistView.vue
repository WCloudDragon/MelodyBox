<template>
  <div class="artist-view">
    <div class="back-link">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <div v-if="artist" class="artist-content">
      <div class="artist-header">
        <div class="artist-avatar">
          <LazyCover v-if="artist.tracks[0]?.cover" :src="artist.tracks[0].cover" />
          <div v-else class="avatar-placeholder">
            <el-icon size="48"><User /></el-icon>
          </div>
        </div>
        <div class="artist-info">
          <h1>{{ artist.name }}</h1>
          <p>{{ artist.tracks.length }} 首歌曲</p>
        </div>
      </div>

      <div class="section-header">
        <h3>所有歌曲</h3>
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
          <el-button size="small" @click="batchPlay(artist.tracks.filter(t => selected.has(t.path)))">播放选中</el-button>
          <el-button size="small" @click="batchAddQueueNext(artist.tracks.filter(t => selected.has(t.path)))">插播至当前播放后</el-button>
          <el-button size="small" @click="batchAddQueue(artist.tracks.filter(t => selected.has(t.path)))">插播至队列末尾</el-button>
          <el-button size="small" @click="selectAll(artist.tracks)">全选</el-button>
          <el-button size="small" @click="clearSelection">取消</el-button>
        </span>
      </div>

      <div class="tracks-list">
        <div
          v-for="(track, index) in artist.tracks"
          :key="track.path"
          class="track-row"
          v-ripple
          :class="{ playing: currentTrack?.path === track.path }"
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
            <span>{{ track.title }}</span>
          </span>
          <span class="col-album">
              <router-link :to="`/album/${encodeURIComponent(track.album || '')}`" class="link">{{ track.album || '未知专辑' }}</router-link>
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

    <div v-else class="empty-state">
      <p>未找到该歌手信息</p>
    </div>

    <!-- 右键菜单 -->
    <ContextMenu
      :visible="ctxMenu.visible"
      :x="ctxMenu.x"
      :y="ctxMenu.y"
      :items="menuItems"
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

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)

const menuItems = computed(() => buildMenuItems('default'))

const artist = computed(() => {
  const name = route.params.name
  if (!name) return null
  return libraryStore.getArtist(decodeURIComponent(name))
})

function playTrack(track) {
  if (!artist.value) return
  const idx = artist.value.tracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(artist.value.tracks, idx)
  }
}

function playAll() {
  if (artist.value) {
    playerStore.playAll(artist.value.tracks)
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
.artist-view { padding-bottom: 100px; }
.back-link { margin-bottom: 20px; }

.artist-header {
  display: flex; align-items: center; gap: 24px;
  margin-bottom: 32px;
}
.artist-avatar {
  width: 180px; height: 180px; border-radius: 50%;
  overflow: hidden; flex-shrink: 0;
}
.artist-avatar img,
.artist-avatar .lazy-cover { width: 100%; height: 100%; object-fit: cover; }
.avatar-placeholder {
  width: 100%; height: 100%;
  background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.artist-info h1 { font-size: 32px; font-weight: 700; margin: 0 0 8px; }
.artist-info p { color: var(--text-tertiary); margin: 0; font-size: 14px; }

.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.section-header h3 { font-size: 18px; margin: 0; }
.section-header__actions { display: flex; gap: 8px; align-items: center; }

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
.track-row:hover { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title { color: var(--accent-color); }

.col-index { width: 40px; text-align: center; }
.col-index .index-num { font-size: 13px; color: var(--text-tertiary); }
.col-index .play-icon { display: none; cursor: pointer; color: var(--accent-color); }
.track-row:hover .col-index .index-num { display: none; }
.track-row:hover .col-index .play-icon { display: inline-flex; }

.col-title { display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 15px; overflow: hidden; }
.col-title span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-cover { width: 44px; height: 44px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty {
  background: var(--bg-tertiary); display: flex;
  align-items: center; justify-content: center; color: var(--text-tertiary);
}
.col-album { font-size: 14px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; }
.col-time { width: 60px; text-align: right; font-size: 13px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.col-action { text-align: center; }
.link { color: var(--text-secondary); text-decoration: none; }
.link:hover { color: var(--accent-color); text-decoration: underline; }

.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); }
</style>
