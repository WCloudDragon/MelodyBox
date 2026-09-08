<template>
  <div class="favorites-view">
    <ListPageHeader
      title="我的收藏"
      :count="filtered.length"
      show-search
      :search-value="searchQuery"
      @update:search-value="searchQuery = $event"
    >
      <el-button v-if="filtered.length" type="primary" plain @click="playAll">
        <el-icon><VideoPlay /></el-icon>
        播放全部
      </el-button>
    </ListPageHeader>

    <!-- 加载中 -->
    <div v-if="!favoritesStore.loaded" class="loading-state">
      <el-icon size="32" class="is-loading"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!filtered.length" class="empty-state">
      <el-icon size="48"><StarFilled /></el-icon>
      <p>还没有收藏的歌曲</p>
      <p class="empty-hint">在歌曲上右键 → 收藏，即可在这里找到</p>
    </div>

    <!-- 列表 -->
    <div v-else class="tracks-list">
      <div
        v-for="(track, index) in filtered"
        :key="track.path || `${track.source}:${track.id}`"
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
              <template v-for="(name, ai) in (track.artist || '').split('/').map(s => s.trim()).filter(Boolean)" :key="ai">
                <span v-if="ai > 0" class="col-title__sep"> / </span>
                <router-link :to="`/artist/${encodeURIComponent(name)}`" class="link col-title__artist">{{ name }}</router-link>
              </template>
            </span>
          </div>
        </span>
        <span class="col-album">
          <router-link v-if="track.album" :to="`/album/${encodeURIComponent(track.album)}`" class="link">{{ track.album }}</router-link>
        </span>
        <span class="col-duration">{{ formatDuration(track.duration) }}</span>
        <span class="col-action">
          <el-icon
            class="fav-icon is-faved"
            title="取消收藏"
            v-ripple
            @click.stop="favoritesStore.toggle(track)"
          ><StarFilled /></el-icon>
        </span>
      </div>
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
defineOptions({ name: 'FavoritesView' })
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { useFavoritesStore } from '@/stores/favorites'
import { pathToUrlSync } from '@/stores/library'
import { useTrackList } from '@/composables/useTrackList'
import { formatDuration } from '@/utils/format'
import { cloudStreamUrl } from '@/config/api'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'
import ListPageHeader from '@/components/music/ListPageHeader.vue'
import { StarFilled, VideoPlay } from '@element-plus/icons-vue'

const router = useRouter()
const player = usePlayerStore()
const favoritesStore = useFavoritesStore()
const { currentTrack } = storeToRefs(player)

const searchQuery = ref('')

const { ctxMenu, showContextMenu, hideContextMenu, openArtistSubmenu, contextMenuTarget, createCtxHandler, createSubActionHandler, buildMenuItems } = useTrackList()
const ctxHandler = createCtxHandler(player, router)
const subActionHandler = createSubActionHandler(router)
const menuItems = computed(() => buildMenuItems('default', ctxMenu.value.track))

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const list = favoritesStore.favorites
  if (!q) return list
  return list.filter(t =>
    (t.title || '').toLowerCase().includes(q) ||
    (t.artist || '').toLowerCase().includes(q) ||
    (t.album || '').toLowerCase().includes(q)
  )
})

function ensureUrl(t) {
  if (!t.url && t.path) {
    t.url = t.source === 'cloud'
      ? cloudStreamUrl(t.path, localStorage.getItem('auth-token') || '')
      : pathToUrlSync(t.path)
  }
  return t
}

function playTrack(track) {
  const list = filtered.value
  const idx = list.findIndex(t => t.path === track.path)
  if (idx === -1) return
  player.playAll(list.map(ensureUrl), idx)
}

function playAll() {
  const list = filtered.value
  if (list.length) player.playAll(list.map(ensureUrl), 0)
}

function ctxAction(action) {
  const result = ctxHandler(action)
  if (result === 'navigate') return
  if (result === 'submenu') return
}

// 进入页面时加载收藏
favoritesStore.load()
</script>

<style scoped>
.favorites-view {
  padding-bottom: 40px;
}

.loading-state, .empty-state {
  text-align: center;
  padding: 80px 32px;
  color: var(--text-tertiary);
}
.loading-state p, .empty-state p { margin: 16px 0; font-size: 15px; }
.empty-hint { font-size: 12px; color: var(--text-tertiary); }

.tracks-list {
  margin-top: 16px;
}
.track-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) minmax(0, 1fr) 72px 40px;
  gap: 12px;
  align-items: center;
  padding: 8px 16px;
  border-radius: 10px;
  transition: background 0.15s;
}
.track-row:hover { background: var(--hover-bg-strong); }
.track-row.playing { background: var(--accent-bg); }
.track-row--ctx-active { background: var(--hover-bg-strong); }

.col-index {
  display: flex;
  align-items: center;
  justify-content: center;
}
.index-num { font-size: 13px; color: var(--text-tertiary); }
.play-icon { display: none; cursor: pointer; color: var(--accent-color); }
.track-row:hover .index-num { display: none; }
.track-row:hover .play-icon { display: inline-flex; }

.col-title {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.row-cover {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--bg-tertiary);
}
.row-cover--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}
.col-title__text { min-width: 0; }
.col-title__name {
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}
.col-title__artist-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.col-title__sep { color: var(--text-tertiary); }
.col-title__artist { color: var(--text-tertiary); text-decoration: none; }
.col-title__artist:hover { color: var(--accent-color); }

.col-album {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-duration {
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: right;
}
.col-action {
  display: flex;
  justify-content: center;
}
.link { color: var(--text-secondary); text-decoration: none; }
.link:hover { color: var(--accent-color); }
.fav-icon {
  cursor: pointer;
  font-size: 18px;
  color: var(--text-tertiary);
}
.fav-icon.is-faved { color: #fbbf24; }
.fav-icon:hover { transform: scale(1.15); }
</style>