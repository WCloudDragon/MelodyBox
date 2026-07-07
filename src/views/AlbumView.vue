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

      <!-- 多碟分组 -->
      <template v-if="discGroups.length > 1">
        <div v-for="(group, gi) in discGroups" :key="gi">
          <div class="disc-header">Disc {{ group.disc }}</div>
          <TrackTable
            :tracks="group.tracks"
            :current-path="currentTrack?.path"
            :context-target="contextMenuTarget"
            :show-header="false"
            :show-album="false"
            :show-artist="true"
            :multi-select-mode="multiSelectMode"
            :selected-paths="selected"
            @play="playTrack"
            @contextmenu="showContextMenu"
            @toggle-select="toggleSelect"
          />
        </div>
      </template>

      <!-- 单碟 -->
      <TrackTable
        v-else
        :tracks="album.tracks"
        :current-path="currentTrack?.path"
        :context-target="contextMenuTarget"
        :show-album="false"
        :show-artist="true"
        :multi-select-mode="multiSelectMode"
        :selected-paths="selected"
        @play="playTrack"
        @contextmenu="showContextMenu"
        @toggle-select="toggleSelect"
      />
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
import { ElMessage } from '@/utils/toast'
import LazyCover from '@/components/LazyCover.vue'
import TrackTable from '@/components/music/TrackTable.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'

const route = useRoute()
const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()
const router = useRouter()
const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, contextMenuTarget, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems, showAddPlaylistDialog } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)
const menuItems = computed(() => buildMenuItems('default'))

const album = computed(() => {
  const name = route.params.id
  if (!name) return null
  return libraryStore.getAlbum(decodeURIComponent(name))
})

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
  if (ctxHandler(action)) return
  if (action === 'addToPlaylist') showAddPlaylistDialog(ctxMenu.value.track)
}

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
}

.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); }
</style>
