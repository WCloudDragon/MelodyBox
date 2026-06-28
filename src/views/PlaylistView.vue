<template>
  <div class="playlist-view">
    <div class="back-link">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <div v-if="playlist" class="playlist-content">
      <div class="playlist-header">
        <div class="playlist-cover">
          <LazyCover v-if="playlist.cover" :src="playlist.cover" />
          <div v-else class="cover-placeholder">
            <el-icon size="48"><Document /></el-icon>
          </div>
        </div>
        <div class="playlist-info">
          <h1>{{ playlist.name }}</h1>
          <p v-if="playlist.description">{{ playlist.description }}</p>
          <p>{{ playlist.tracks.length }} 首歌曲</p>
          <div class="playlist-actions">
            <el-button type="primary" @click="playAll" :disabled="playlist.tracks.length === 0">
              <el-icon><VideoPlay /></el-icon>
              播放全部
            </el-button>
            <el-button @click="toggleSelectMode" :type="multiSelectMode ? 'primary' : 'default'">
              <el-icon><Select /></el-icon>
              {{ multiSelectMode ? '退出多选' : '多选' }}
            </el-button>
            <el-button @click="showRenameDialog">重命名</el-button>
            <el-button type="danger" plain @click="handleDelete">删除歌单</el-button>
          </div>
        </div>
      </div>

      <!-- 多选工具栏 -->
      <div v-if="multiSelectMode && selected.size > 0" class="batch-toolbar">
        <span>已选 <span class="batch-toolbar__count">{{ selected.size }}</span> 首</span>
        <span class="batch-toolbar__actions">
          <el-button size="small" @click="batchPlay(playlist.tracks.filter(t => selected.has(t.path)))">播放选中</el-button>
          <el-button size="small" @click="batchAddQueueNext(playlist.tracks.filter(t => selected.has(t.path)))">插播至当前播放后</el-button>
          <el-button size="small" @click="batchAddQueue(playlist.tracks.filter(t => selected.has(t.path)))">插播至队列末尾</el-button>
          <el-button size="small" @click="selectAll(playlist.tracks)">全选</el-button>
          <el-button size="small" @click="clearSelection">取消</el-button>
        </span>
      </div>

      <!-- 列表视图（虚拟滚动） -->
      <div class="tracks-list" v-if="playlist.tracks.length > 0">
        <div class="track-table-header">
          <span class="col-index">#</span>
          <span class="col-title">歌曲</span>
          <span class="col-artist">歌手</span>
          <span class="col-album">专辑</span>
          <span class="col-quality">音质</span>
          <span class="col-time">时长</span>
          <span class="col-action"></span>
        </div>
        <div v-bind="containerProps" class="tracks-list-body">
          <div v-bind="wrapperProps">
            <div
              v-for="{ data: track, index } in virtualList"
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
              <span class="col-artist">{{ (track.artist || '').split('/').map(s => s.trim()).join(' / ') }}</span>
              <span class="col-album">{{ track.album || '' }}</span>
              <span class="col-quality">
                <span v-if="track.quality" class="quality-tag" :class="qualityClass(track.quality)">{{ track.quality }}</span>
              </span>
              <span class="col-time">{{ formatDuration(track.duration) }}</span>
              <span class="col-action">
                <el-checkbox v-if="multiSelectMode" :model-value="isSelected(track)" @change="toggleSelect(track)" />
                <el-button v-else text size="small" @click.stop="removeTrack(track)">
                  <el-icon><Close /></el-icon>
                </el-button>
              </span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <el-icon size="48"><Folder /></el-icon>
        <p>歌单为空</p>
        <p class="hint">在音乐库中右键歌曲可以添加到歌单</p>
      </div>
    </div>

    <div v-else class="empty-state">
      <p>未找到该歌单</p>
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
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useVirtualList } from '@vueuse/core'
import { usePlaylistStore } from '@/stores/playlist'
import { usePlayerStore } from '@/stores/player'
import { useTrackList } from '@/composables/useTrackList'
import { formatDuration, qualityClass } from '@/utils/format'
import { ElMessageBox } from 'element-plus'
import { ElMessage } from '@/utils/toast'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'

const route = useRoute()
const router = useRouter()
const playlistStore = usePlaylistStore()
const playerStore = usePlayerStore()
const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)

const menuItems = computed(() => buildMenuItems('playlist'))

const playlist = computed(() => {
  return playlistStore.getPlaylist(route.params.id)
})

// L1 骨架渲染 → L2 后台填充详情（网易云策略）
watch([() => route.params.id, () => playlistStore.isLoaded], async ([id, loaded]) => {
  if (id && loaded) await playlistStore.loadPlaylistTracks(id)
}, { immediate: true })

// 虚拟滚动（仅渲染可见 + 缓冲区行数，和 LibraryView 一致的策略）
const { list: virtualList, containerProps, wrapperProps, scrollTo } = useVirtualList(
  computed(() => playlist.value?.tracks ?? []),
  { itemHeight: 52, overscan: 15 }
)

// tracks 数量变化时滚回顶部
watch(() => playlist.value?.tracks.length, () => {
  scrollTo(0)
})

function playTrack(track) {
  if (!playlist.value) return
  const idx = playlist.value.tracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(playlist.value.tracks, idx)
  }
}

function playAll() {
  if (playlist.value) {
    playerStore.playAll(playlist.value.tracks)
  }
}

function removeTrack(track) {
  if (playlist.value) {
    playlistStore.removeFromPlaylist(playlist.value.id, track.path)
  }
}

async function showRenameDialog() {
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名歌单', {
      confirmButtonText: '确认',
      inputValue: playlist.value?.name
    })
    if (value?.trim() && playlist.value) {
      playlistStore.renamePlaylist(playlist.value.id, value.trim())
      ElMessage.success('重命名成功')
    }
  } catch {}
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定要删除该歌单吗？此操作不可恢复。', '删除歌单', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    if (playlist.value) {
      playlistStore.deletePlaylist(playlist.value.id)
      ElMessage.success('歌单已删除')
      router.push('/')
    }
  } catch {}
}

function ctxAction(action) {
  if (ctxHandler(action)) return
  if (action === 'remove') removeTrack(ctxMenu.value.track)
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
.playlist-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; padding-bottom: 100px; }
.back-link { margin-bottom: 20px; flex-shrink: 0; }

.playlist-content { flex: 1; display: flex; flex-direction: column; min-height: 0; }

.playlist-header {
  display: flex; align-items: flex-end; gap: 24px;
  margin-bottom: 24px; flex-shrink: 0;
}
.playlist-cover {
  width: 200px; height: 200px; border-radius: 12px;
  overflow: hidden; flex-shrink: 0;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.playlist-cover img,
.playlist-cover .lazy-cover { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder {
  width: 100%; height: 100%;
  background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.playlist-info h1 { font-size: 28px; font-weight: 700; margin: 0 0 8px; }
.playlist-info p { color: var(--text-tertiary); margin: 0 0 2px; font-size: 14px; }
.playlist-actions { display: flex; gap: 8px; margin-top: 16px; align-items: center; }

/* 列表视图（对齐 LibraryView） */
.track-table-header {
  display: flex; align-items: center;
  padding: 10px 12px; font-size: 11px;
  color: var(--text-tertiary); text-transform: uppercase;
  letter-spacing: 1px; border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.tracks-list { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.tracks-list-body { flex: 1; overflow-y: auto; min-height: 0; transform: translateZ(0); }
.tracks-list-body::-webkit-scrollbar { width: 6px; }
.tracks-list-body::-webkit-scrollbar-track { background: transparent; }
.tracks-list-body::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
.tracks-list-body::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

.track-row {
  display: flex; align-items: center;
  padding: 0 12px; border-radius: 6px;
  height: 52px; transition: background 0.15s; cursor: default;
}
.track-row:hover { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .col-title span { color: var(--accent-color); }

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
.col-title span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-cover { width: 36px; height: 36px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty {
  background: var(--bg-tertiary); display: flex;
  align-items: center; justify-content: center; color: var(--text-tertiary);
}
.col-artist { width: 160px; font-size: 13px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-album { width: 180px; font-size: 13px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; font-size: 11px; }
.col-time { width: 60px; text-align: right; font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.col-action { width: 40px; text-align: center; }

.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); flex-shrink: 0; }
.empty-state p { font-size: 15px; margin: 12px 0; }
.hint { font-size: 13px !important; color: var(--text-tertiary); }
</style>
