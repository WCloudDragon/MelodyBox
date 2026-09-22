<template>
  <div class="search-view">
    <ListPageHeader :title="`搜索「${q}」`" :count="headerCount || null" :show-play-mode="false">
      <el-button v-if="playableTracks.length" @click="playAllResults">
        <el-icon><VideoPlay /></el-icon>
      </el-button>
    </ListPageHeader>

    <!-- 类别 tab（类网易云：全部 + 有结果的类别；关键词变化时归位到"全部"） -->
    <div v-if="q && tabs.length > 1" class="search-tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="search-tab"
        :class="{ active: activeTab === t.key }"
        @click="switchTab(t.key)"
      >{{ t.label }}</button>
    </div>

    <div class="search-view__scroll" ref="scrollEl">
      <!-- 空关键词 -->
      <div v-if="!q" class="search-empty">
        <el-icon size="48"><Search /></el-icon>
        <p>输入关键词开始搜索</p>
        <p class="search-empty__hint">支持歌曲 / 专辑 / 艺术家 / 歌单 / 历史记录 / 播放次数</p>
      </div>

      <!-- 无结果 -->
      <div v-else-if="!sections.length" class="search-empty">
        <el-icon size="48"><Search /></el-icon>
        <p>未找到与「{{ q }}」相关的内容</p>
        <p class="search-empty__hint">试试其他关键词</p>
      </div>

      <!-- 分组结果（按 tab 过滤：全部=分组平铺，单类=仅该组） -->
      <template v-else>
        <section v-for="sec in visibleSections" :key="sec.key" class="search-section">
          <!-- 综合模式：组标题可点（进单类看全部，带箭头）；单类模式：纯标题 -->
          <button
            v-if="activeTab === 'all'"
            class="search-section__title search-section__title--link"
            @click="switchTab(sec.key)"
          >
            {{ sec.label }}
            <span class="search-section__count">{{ sec.items.length }}</span>
            <svg class="search-section__arrow" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3.5L10.5 8 6 12.5"/></svg>
          </button>
          <div v-else class="search-section__title">
            {{ sec.label }}
            <span class="search-section__count">{{ sec.items.length }}</span>
          </div>

          <!-- 歌曲 / 历史 / 播放次数：曲目行 -->
          <div v-if="sec.type === 'tracks'" class="search-section__body">
            <div
              v-for="(t, i) in sec.display"
              :key="sec.key + '-' + t.path"
              class="track-row"
              v-ripple
              :class="{ playing: currentTrack?.path === t.path, 'track-row--ctx-active': contextMenuTarget === t.path }"
              @dblclick="playSection(sec, i)"
              @contextmenu.prevent="showContextMenu($event, t)"
            >
              <span class="track-row__main">
                <LazyCover v-if="t.cover" :src="t.cover" class="row-cover" :thumb-size="72" />
                <div v-else class="row-cover row-cover--empty"><el-icon size="14"><Headset /></el-icon></div>
                <span class="track-row__text">
                  <span class="track-row__name" v-html="hl(t.title)"></span>
                  <span class="track-row__sub">
                    <span v-html="hl(t.artist || '')"></span>
                    <template v-if="t.album"> · <span v-html="hl(t.album)"></span></template>
                  </span>
                </span>
              </span>
              <span class="track-row__meta">{{ sec.meta(t) }}</span>
              <el-icon class="track-row__play" v-ripple size="16" @click.stop="playSection(sec, i)"><VideoPlay /></el-icon>
            </div>
          </div>

          <!-- 专辑 / 艺术家 / 歌单：卡片网格 -->
          <div v-else class="search-section__body">
            <div class="card-grid">
              <router-link
                v-for="c in sec.display"
                :key="sec.key + '-' + c.key"
                :to="c.route"
                class="entity-card"
                v-ripple
              >
                <div class="entity-card__cover">
                  <LazyCover v-if="c.cover" :src="c.cover" :thumb-size="200" />
                  <div v-else class="entity-card__glyph" v-html="c.glyph"></div>
                </div>
                <span class="entity-card__name" v-html="hl(c.title)"></span>
                <span class="entity-card__sub" v-html="hl(c.sub)"></span>
              </router-link>
            </div>
          </div>
        </section>
      </template>
    </div>

    <!-- 右键菜单（歌曲行） -->
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
defineOptions({ name: 'SearchView' })
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { Search, VideoPlay, Headset } from '@element-plus/icons-vue'
import { usePlayerStore } from '@/stores/player'
import { useLibraryStore } from '@/stores/library'
import { usePlaylistStore } from '@/stores/playlist'
import { apiUrl, coverUrl } from '@/config/api'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'
import ListPageHeader from '@/components/music/ListPageHeader.vue'
import { useTrackList } from '@/composables/useTrackList'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const libraryStore = useLibraryStore()
const playlistStore = usePlaylistStore()
const { currentTrack } = storeToRefs(playerStore)

const { ctxMenu, showContextMenu, hideContextMenu, createCtxHandler, openArtistSubmenu, createSubActionHandler, contextMenuTarget, buildMenuItems, showAddPlaylistDialog } = useTrackList()
const ctxHandler = createCtxHandler(playerStore, router)
const subActionHandler = createSubActionHandler(router)

const menuItems = computed(() => buildMenuItems('default', ctxMenu.value.track))

function ctxAction(action) {
  if (ctxHandler(action)) return
  if (action === 'addToPlaylist') showAddPlaylistDialog(ctxMenu.value.track)
}

// ==================== 关键词 ====================
const q = computed(() => (route.query.q || '').toString().trim())

// ==================== 行为数据（历史/播放次数：进页惰性拉取一次） ====================
const statsRecent = ref([])
const statsTop = ref([])
let statsLoaded = false

async function ensureStats() {
  if (statsLoaded) return
  statsLoaded = true
  const libMap = new Map(libraryStore.allTracks.map(t => [t.path, t]))
  const mapItem = item => {
    const lib = libMap.get(item.file_path)
    return {
      path: item.file_path || '',
      title: item.title || lib?.title || '未知歌曲',
      artist: item.artist || lib?.artist || '未知歌手',
      album: item.album || lib?.album || '',
      cover: coverUrl(item.cover_url || lib?.cover || ''),
      duration: lib?.duration || 0,
      played_at: item.played_at,
      play_count: item.play_count || 0,
    }
  }
  try {
    const [r1, r2] = await Promise.allSettled([
      fetch(apiUrl('/api/stats/recent?limit=100')).then(r => r.json()),
      fetch(apiUrl('/api/stats/top?limit=100')).then(r => r.json())
    ])
    if (r1.status === 'fulfilled' && Array.isArray(r1.value)) statsRecent.value = r1.value.map(mapItem)
    if (r2.status === 'fulfilled' && Array.isArray(r2.value)) statsTop.value = r2.value.map(mapItem)
  } catch { /* 静默：无后端时两组隐藏 */ }
}
watch(q, (v) => { if (v) ensureStats() }, { immediate: true })

// ==================== 分组匹配（与全局搜索面板同一套匹配语义，展示全量结果） ====================
const GLYPH = {
  album: '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/></svg>',
  artist: '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/></svg>',
  playlist: '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 6h13M3 12h13M3 18h9"/><path d="M19 12v7"/><circle cx="17.5" cy="19" r="1.6"/></svg>',
}

const sections = computed(() => {
  const kw = q.value.toLowerCase()
  if (!kw) return []
  const match = (s) => (s || '').toLowerCase().includes(kw)

  const songs = libraryStore.allTracks.filter(t => match(t.title) || match(t.artist) || match(t.album))
  const albums = libraryStore.albums.filter(a => match(a.name) || match(a.artist))
    .map(a => ({ key: a.name, title: a.name, sub: a.artist, cover: a.cover, route: `/album/${encodeURIComponent(a.name)}` }))
  const artists = libraryStore.artists.filter(a => match(a.name))
    .map(a => ({ key: a.name, title: a.name, sub: `${a.tracks.length} 首歌曲`, cover: a.tracks?.[0]?.cover || '', glyph: GLYPH.artist, route: `/artist/${encodeURIComponent(a.name)}` }))
  const playlists = playlistStore.playlists.filter(p => match(p.name) || match(p.description))
    .map(p => ({ key: String(p.id), title: p.name, sub: p.description || '歌单', cover: p.cover_url || '', glyph: GLYPH.playlist, route: `/playlist/${p.id}` }))
  const hist = statsRecent.value.filter(t => match(t.title) || match(t.artist) || match(t.album))
  const tops = statsTop.value.filter(t => match(t.title) || match(t.artist) || match(t.album))

  const out = []
  if (songs.length) out.push({ type: 'tracks', key: 'song', label: '歌曲', items: songs, meta: fmtDur })
  if (albums.length) out.push({ type: 'cards', key: 'album', label: '专辑', items: albums })
  if (artists.length) out.push({ type: 'cards', key: 'artist', label: '艺术家', items: artists })
  if (playlists.length) out.push({ type: 'cards', key: 'playlist', label: '歌单', items: playlists })
  if (hist.length) out.push({ type: 'tracks', key: 'history', label: '历史记录', items: hist, meta: t => fmtRel(t.played_at) })
  if (tops.length) out.push({ type: 'tracks', key: 'top', label: '播放次数', items: tops, meta: t => `${t.play_count || 0} 次` })
  return out
})

const totalCount = computed(() => sections.value.reduce((n, s) => n + s.items.length, 0))

// ==================== 类别 tab ====================
const activeTab = ref('all')
const scrollEl = ref(null)
// 综合模式每组预览条数（超出走「>」进单类看全部）
const TRACK_PREVIEW = 5
const CARD_PREVIEW = 6
// 「综合」+ 有结果的类别（空类别不出现 tab，避免点击后全是空态）
const tabs = computed(() => [
  { key: 'all', label: '综合' },
  ...sections.value.map(s => ({ key: s.key, label: s.label }))
])
const visibleSections = computed(() => {
  if (activeTab.value === 'all') {
    // 综合模式：每组仅预览一部分，避免单页过长（组标题「>」进单类）
    return sections.value.map(s => ({
      ...s,
      display: s.type === 'tracks' ? s.items.slice(0, TRACK_PREVIEW) : s.items.slice(0, CARD_PREVIEW)
    }))
  }
  // 单类模式：全量展示
  return sections.value.map(s => ({ ...s, display: s.items }))
})
// 头部数量跟随当前 tab
const headerCount = computed(() => {
  if (activeTab.value === 'all') return totalCount.value
  return visibleSections.value.reduce((n, s) => n + s.items.length, 0)
})
function switchTab(key) {
  if (activeTab.value === key) return
  activeTab.value = key
  if (scrollEl.value) scrollEl.value.scrollTop = 0
}
watch(q, () => { activeTab.value = 'all' })

// 可播放曲目（歌曲 + 历史 + 播放次数去重），用于「播放全部」
const playableTracks = computed(() => {
  const seen = new Set()
  const arr = []
  for (const sec of sections.value) {
    if (sec.type !== 'tracks') continue
    for (const t of sec.items) {
      if (t.path && !seen.has(t.path)) { seen.add(t.path); arr.push(t) }
    }
  }
  return arr
})

function playAllResults() {
  if (playableTracks.value.length) playerStore.playAll(playableTracks.value, 0)
}

function playSection(sec, idx) {
  const tracks = sec.items.filter(t => t.path)
  const t = sec.items[idx]
  if (!t?.path) return
  const real = tracks.indexOf(t)
  playerStore.playAll(tracks, Math.max(0, real))
}

// ==================== 高亮 / 格式化 ====================
function hl(text) {
  const kw = q.value
  if (!kw || !text) return escapeHtml(text ?? '')
  const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escapeHtml(String(text)).replace(
    new RegExp(`(${escaped.replace(/ /g, '\\s')})`, 'gi'),
    '<mark>$1</mark>'
  )
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}
function fmtDur(track) {
  const d = track.duration || 0
  if (!d) return ''
  const m = Math.floor(d / 60), s = Math.floor(d % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
function fmtRel(raw) {
  try {
    const diffMs = Date.now() - new Date(raw).getTime()
    const m = Math.floor(diffMs / 60000)
    if (m < 1) return '刚刚'
    if (m < 60) return `${m} 分钟前`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h} 小时前`
    const d = new Date(raw)
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  } catch { return '' }
}
</script>

<style scoped>
.search-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

/* 类别 tab（网易云式：文字 + 底部指示条）。
   容器无 padding，按钮自带 12px 水平内边距 → 首个文字恰落 --page-pad-x 基准线 */
.search-tabs {
  display: flex; align-items: center; gap: 4px;
  flex-shrink: 0;
}
.search-tab {
  position: relative;
  padding: 6px 12px;
  border: none; background: none;
  font-size: 14px; color: var(--text-secondary);
  cursor: pointer; border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}
.search-tab:hover { color: var(--text-primary); background: var(--hover-bg); }
.search-tab.active { color: var(--accent-color); font-weight: 600; }
.search-tab.active::after {
  content: '';
  position: absolute; left: 50%; bottom: 0;
  transform: translateX(-50%);
  width: 18px; height: 3px; border-radius: 2px;
  background: var(--accent-color);
}

.search-view__scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  padding-bottom: 24px;
  transform: translateZ(0);
}
.search-view__scroll::-webkit-scrollbar { width: 6px; }
.search-view__scroll::-webkit-scrollbar-track { background: transparent; }
.search-view__scroll::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
.search-view__scroll::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

/* 空态 */
.search-empty { text-align: center; padding: 96px 32px; color: var(--text-tertiary); }
.search-empty p { margin: 16px 0 0; font-size: 15px; color: var(--text-secondary); }
.search-empty__hint { font-size: 13px !important; color: var(--text-tertiary) !important; }

/* 分组 */
.search-section { margin-top: 20px; }
.search-section__title {
  display: flex; align-items: baseline; gap: 8px;
  font-size: 15px; font-weight: 600; color: var(--text-primary);
  padding: 0 12px; margin-bottom: 8px;
}
.search-section__count { font-size: 12px; font-weight: 500; color: var(--text-tertiary); }
/* 综合模式的可点组标题：hover 提亮 + 箭头右移示意进入单类 */
.search-section__title--link {
  width: calc(100% - 24px);
  border: none; background: none; text-align: left;
  cursor: pointer;
  transition: color 0.15s;
}
.search-section__arrow {
  align-self: center;
  color: var(--text-tertiary);
  transition: transform 0.15s, color 0.15s;
}
.search-section__title--link:hover { color: var(--accent-color); }
.search-section__title--link:hover .search-section__arrow {
  color: var(--accent-color);
  transform: translateX(2px);
}

/* 曲目行（与列表页 track-row 同语言；内容落 --page-pad-x 基准线） */
.track-row {
  display: flex; align-items: center; gap: 12px;
  height: 56px;
  padding: 0 var(--page-pad-x, 12px); border-radius: 6px;
  transition: background 0.15s; cursor: default;
}
.track-row:hover, .track-row--ctx-active { background: var(--hover-bg); }
.track-row.playing { background: var(--accent-bg); }
.track-row.playing .track-row__name { color: var(--accent-color); }

.track-row__main { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.row-cover { width: 40px; height: 40px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.row-cover--empty { background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); }
.track-row__text { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.track-row__name { font-size: 14px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track-row__sub { font-size: 12px; line-height: 1.3; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.track-row__meta { font-size: 12.5px; color: var(--text-tertiary); flex-shrink: 0; }
.track-row__play {
  opacity: 0; pointer-events: none; flex-shrink: 0;
  color: var(--accent-color); cursor: pointer; transition: opacity 0.12s;
}
.track-row:hover .track-row__play { opacity: 1; pointer-events: auto; }

/* 卡片网格（与专辑页卡片同语言；卡片自带 12px 内边距，封面/文字落在基准线） */
.card-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.entity-card {
  flex: 1 1 150px; max-width: 190px; min-width: 140px;
  display: flex; flex-direction: column; align-items: center;
  padding: 14px 12px; border-radius: 10px;
  text-align: center; text-decoration: none; cursor: pointer;
  transition: background 0.2s;
}
.entity-card:hover { background: var(--hover-bg); }
.entity-card__cover {
  width: 110px; height: 110px; border-radius: 8px; overflow: hidden;
  background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary); margin-bottom: 10px;
}
.entity-card__cover :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.entity-card__name {
  font-size: 14px; color: var(--text-primary); line-height: 1.35;
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.entity-card__sub {
  font-size: 12px; color: var(--text-secondary); line-height: 1.35; margin-top: 2px;
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* 关键词高亮（与全局搜索面板一致） */
.search-view :deep(mark) {
  background: transparent;
  color: var(--accent-color);
  font-weight: 600;
}
</style>
