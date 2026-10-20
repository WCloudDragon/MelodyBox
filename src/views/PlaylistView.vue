<template>
  <div class="playlist-view">
    <ListPageHeader
      :title="playlist?.name || '歌单'"
      :show-play-mode="false"
      show-back
      back-fallback="/library"
      fog-title
    />

    <div v-if="playlist" class="playlist-content">
      <div class="playlist-header">
        <div class="playlist-cover">
          <LazyCover v-if="playlist.cover_url" :src="playlist.cover_url" />
          <div v-else class="cover-placeholder">
            <el-icon size="48"><Document /></el-icon>
          </div>
        </div>
        <div class="playlist-info">
          <h2 class="page-content-title">{{ playlist?.name }}</h2>
          <p v-if="playlist.description">{{ playlist.description }}</p>
          <p>{{ playlist.tracks.length }} 首歌曲</p>
        </div>
        <div class="playlist-actions">
          <el-button type="primary" @click="playAll" :disabled="playlist.tracks.length === 0">
            <el-icon><VideoPlay /></el-icon>
            播放全部
          </el-button>
          <el-button @click="toggleSelectMode" :type="multiSelectMode ? 'primary' : 'default'">
            <el-icon><Select /></el-icon>
            {{ multiSelectMode ? '退出多选' : '多选' }}
          </el-button>
          <!-- 系统歌单（我的收藏）不可重命名/删除 -->
          <template v-if="!playlistStore.isSystemPlaylist(playlist.id)">
            <el-button @click="showRenameDialog">重命名</el-button>
            <el-button type="danger" plain @click="handleDelete">删除歌单</el-button>
          </template>
        </div>
      </div>

      <!-- 多选工具栏 -->
      <div v-if="multiSelectMode && selected.size > 0" class="batch-toolbar">
        <span>已选 <span class="batch-toolbar__count">{{ selected.size }}</span> 首</span>
        <span class="batch-toolbar__actions">
          <el-button size="small" @click="batchPlay(playlist.tracks.filter(t => selected.has(t.path)))">播放选中</el-button>
          <el-button size="small" @click="batchAddQueueNext(playlist.tracks.filter(t => selected.has(t.path)))">插播至当前播放后</el-button>
          <el-button size="small" @click="batchAddQueue(playlist.tracks.filter(t => selected.has(t.path)))">插播至队列末尾</el-button>
          <el-button size="small" @click="showAddPlaylistDialog(playlist.tracks.filter(t => selected.has(t.path) && !t.missing))">添加到歌单</el-button>
          <el-button size="small" @click="selectAll(playlist.tracks)">全选</el-button>
          <el-button size="small" @click="clearSelection">取消</el-button>
        </span>
      </div>

      <!-- 列表视图（整页滚动，与专辑/艺术家详情一致；无表头，行规格与列表页统一） -->
      <div class="tracks-list" v-if="playlist.tracks.length > 0">
        <div class="tracks-list-body">
          <div
            v-for="(track, index) in playlist.tracks"
            :key="track.path"
              class="track-row"
              v-ripple
              :class="{ playing: currentTrack?.path === track.path, 'track-row--ctx-active': contextMenuTarget === track.path, 'track-row--selected': multiSelectMode && isSelected(track), 'track-row--missing': track.missing }"
              @dblclick="playTrack(track)"
              @contextmenu.prevent="showContextMenu($event, track)"
            >
              <span class="col-index">
                <span class="index-num">{{ index + 1 }}</span>
                <el-icon v-if="!track.missing" class="play-icon" v-ripple size="16" @click.stop="playTrack(track)"><VideoPlay /></el-icon>
              </span>
              <span class="col-title">
                <LazyCover v-if="track.cover" :src="track.cover" class="row-cover" :thumb-size="72" />
                <div v-else class="row-cover row-cover--empty"><el-icon size="14"><Headset /></el-icon></div>
                <div class="col-title__text">
                  <span class="col-title__name">{{ track.title }}</span>
                  <span class="col-title__artist-row">
                    <template v-for="(name, ai) in (track.artist || '').split('/').map(s => s.trim()).filter(Boolean)" :key="ai">
                      <router-link :to="`/artist/${encodeURIComponent(name)}`" class="link col-title__artist">{{ name }}</router-link>
                      <span v-if="ai < (track.artist || '').split('/').map(s => s.trim()).filter(Boolean).length - 1" class="col-title__sep"> / </span>
                    </template>
                  </span>
                </div>
                <span v-if="track.missing" class="missing-tag">文件缺失</span>
              </span>
              <span class="col-album">
                <router-link v-if="track.album" :to="`/album/${encodeURIComponent(track.album)}`" class="link">{{ track.album }}</router-link>
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
        <el-icon size="48"><Folder /></el-icon>
        <p>歌单为空</p>
        <p class="hint">{{ playlistStore.isSystemPlaylist(playlist.id) ? '在音乐库右键歌曲，选择「添加到歌单」→「我的收藏」' : '在音乐库中右键歌曲可以添加到歌单' }}</p>
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
      :submenu="ctxMenu.submenu"
      :animated="true"
      @close="hideContextMenu"
      @action="ctxAction"
      @sub-action="subActionHandler"
      @hover-submenu="openArtistSubmenu"
    />
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePlaylistStore } from '@/stores/playlist'
import { usePlayerStore } from '@/stores/player'
import { useTrackList } from '@/composables/useTrackList'
import { formatDuration, qualityClass } from '@/utils/format'
import { useModal } from '@/composables/useModal'
import { ElMessage } from '@/utils/toast'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'
import ListPageHeader from '@/components/music/ListPageHeader.vue'

const route = useRoute()
const router = useRouter()
const playlistStore = usePlaylistStore()
const modal = useModal()
const playerStore = usePlayerStore()
const { currentTrack } = storeToRefs(playerStore)

const { multiSelectMode, selected, ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, openArtistSubmenu, createSubActionHandler, contextMenuTarget, toggleSelectMode, isSelected, toggleSelect, selectAll, clearSelection, buildMenuItems, showAddPlaylistDialog } = useTrackList()

const ctxHandler = createCtxHandler(playerStore, router)
const subActionHandler = createSubActionHandler(router)

const menuItems = computed(() => buildMenuItems('playlist', ctxMenu.value.track))

const playlist = computed(() => {
  return playlistStore.getPlaylist(route.params.id)
})

// L1 骨架渲染 → L2 后台填充详情（网易云策略）
watch([() => route.params.id, () => playlistStore.isLoaded], async ([id, loaded]) => {
  if (id && loaded) await playlistStore.loadPlaylistTracks(id)
}, { immediate: true })

// 歌曲数量变化（添加/移除歌曲）时滚回列表顶部
watch(() => playlist.value?.tracks.length, () => {
  const el = document.querySelector('.main-content')
  if (el) el.scrollTop = 0
})

function playTrack(track) {
  if (track.missing) return // 失效条目无音频源，禁播
  if (!playlist.value) return
  const playable = playlist.value.tracks.filter(t => !t.missing)
  const idx = playable.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(playable, idx)
  }
}

function playAll() {
  if (!playlist.value) return
  const playable = playlist.value.tracks.filter(t => !t.missing)
  if (playable.length) {
    playerStore.playAll(playable)
  }
}

function removeTrack(track) {
  if (playlist.value) {
    playlistStore.removeFromPlaylist(playlist.value.id, track.path)
  }
}

async function showRenameDialog() {
  try {
    const value = await modal.prompt({
      title: '重命名歌单',
      message: '请输入新名称',
      confirmText: '确认',
      inputDefault: playlist.value?.name
    })
    if (value?.trim() && playlist.value) {
      playlistStore.renamePlaylist(playlist.value.id, value.trim())
      ElMessage.success('重命名成功')
    }
  } catch {}
}

async function handleDelete() {
  try {
    await modal.confirm({
      title: '删除歌单',
      message: '确定要删除该歌单吗？此操作不可恢复。',
      confirmText: '删除',
      danger: true
    })
    if (playlist.value) {
      const ok = await playlistStore.deletePlaylist(playlist.value.id)
      if (!ok) {
        ElMessage.error('删除失败，请稍后重试')
        return
      }
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
function playableOf(tracks) {
  return tracks.filter(t => !t.missing)
}
function batchPlay(tracks) {
  const playable = playableOf(tracks)
  if (!playable.length) return
  playerStore.playAll(playable, 0)
}
function batchAddQueue(tracks) {
  const playable = playableOf(tracks)
  if (!playable.length) return
  playable.forEach(t => playerStore.addToQueue(t))
  ElMessage.success(`已插播 ${playable.length} 首至队列末尾`)
  clearSelection()
}
function batchAddQueueNext(tracks) {
  const playable = playableOf(tracks)
  if (!playable.length) return
  playable.forEach(t => playerStore.addToQueueNext(t))
  ElMessage.success(`已插播 ${playable.length} 首至下一位置`)
  clearSelection()
}
</script>

<style scoped>
.playlist-view { padding-bottom: 100px; }

/* 矫正 sticky 怪异：absolute 滚动容器 + static 父级组合下，Chromium 把
   sticky top 当作相对流位置的偏移（top:60px → 实际贴到 120px），
   导致页头与其 frost/fade 雾带整体下移。覆盖为 0 使页头贴上滚动视口顶 */
.playlist-view :deep(.list-page-header) { top: 0; }

.playlist-content { min-height: 0; }

.playlist-header {
  display: flex; align-items: flex-end; gap: 24px;
  padding-left: var(--page-pad-x, 12px);
  margin-bottom: 32px;
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
.playlist-info p { color: var(--text-tertiary); margin: 0 0 2px; font-size: 14px; }
.playlist-actions { margin-left: auto; display: flex; gap: 8px; flex-shrink: 0; }

/* 列表视图（与音乐库/专辑/艺术家页同一套行规格，无表头） */
.tracks-list { display: flex; flex-direction: column; }
/* 整页滚动：列表体不再自建滚动容器，交由主内容区滚动 */
.tracks-list-body { }

.track-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr 52px 60px 40px;
  align-items: center;
  /* 内容落在 --page-pad-x 基准线；hover 背景天然从基准线左一个 pad 处开始 */
  padding: 0 var(--page-pad-x, 12px); border-radius: 6px;
  height: 64px; transition: background 0.15s; cursor: default;
  content-visibility: auto;
  contain-intrinsic-size: 64px;
  contain: layout style paint;
}
.track-row:hover, .track-row--ctx-active { background: var(--hover-bg); }
/* 多选选中：整行背景高亮（当前播放只染文本，不染背景） */
.track-row.track-row--selected { background: var(--accent-bg); }
.track-row.playing .col-title__name,
.track-row.playing .col-title__artist,
.track-row.playing .col-title__sep,
.track-row.playing .col-album,
.track-row.playing .col-album .link,
.track-row.playing .col-time,
.track-row.playing .col-index .index-num { color: var(--accent-color); }

/* 失效条目（文件缺失）：整行灰化，重新导入同指纹歌曲后自动恢复正常显示 */
.track-row--missing .col-title__name,
.track-row--missing .col-title__artist,
.track-row--missing .col-album,
.track-row--missing .col-index .index-num,
.track-row--missing .col-time { color: var(--text-tertiary); opacity: 0.6; }
.track-row--missing .col-album .link { color: var(--text-tertiary); }
.track-row--missing .row-cover { opacity: 0.45; filter: grayscale(0.8); }
/* 缺失行 hover 无播放图标可显示，序号保持可见 */
.track-row--missing:hover .col-index .index-num,
.track-row--missing.track-row--ctx-active .col-index .index-num { opacity: 1; }

.missing-tag {
  flex-shrink: 0;
  font-size: 10px; line-height: 1;
  padding: 3px 6px; border-radius: 4px;
  border: 1px dashed var(--border-color);
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  white-space: nowrap;
}

.col-index { width: 40px; text-align: center; position: relative; }
.col-index .index-num { font-size: 13px; color: var(--text-tertiary); transition: opacity 0.12s; }
.col-index .play-icon {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  cursor: pointer; color: var(--accent-color);
  opacity: 0; pointer-events: none; transition: opacity 0.12s;
}
.track-row:hover .col-index .index-num, .track-row--ctx-active .col-index .index-num { opacity: 0; }
.track-row:hover .col-index .play-icon, .track-row--ctx-active .col-index .play-icon { opacity: 1; pointer-events: auto; }

.col-title { display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 15px; overflow: hidden; }
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
.link { color: var(--text-secondary); text-decoration: none; }
.link:hover { color: var(--accent-color); text-decoration: underline; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; }
.col-time { width: 60px; text-align: right; font-size: 13px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.col-action { width: 40px; text-align: center; }

.empty-state { text-align: center; padding: 80px 0; color: var(--text-tertiary); flex-shrink: 0; }
.empty-state p { font-size: 15px; margin: 12px 0; }
.hint { font-size: 13px !important; color: var(--text-tertiary); }
</style>
