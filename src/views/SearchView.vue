<template>
  <div class="search-view">
    <ListPageHeader :title="`搜索「${q}」`" :show-play-mode="false" show-back back-fallback="/">
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
      >{{ t.label }}<span v-if="t.count != null" class="search-tab__count">{{ t.count }}</span></button>
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

          <!-- 歌曲 / 历史 / 播放次数：多列曲目行（与列表页 track-row 同一套结构：序号/歌曲/专辑/音质/时长） -->
          <div v-if="sec.type === 'tracks'" class="search-section__body">
            <div
              v-for="(t, i) in sec.display"
              :key="sec.key + '-' + t.path"
              class="track-row"
              v-ripple
              :class="{ playing: currentTrack?.path === t.path, 'track-row--ctx-active': contextMenuTarget === t.path }"
              :style="{ gridTemplateColumns: trackGrid(sec) }"
              @dblclick="playSection(sec, i)"
              @contextmenu.prevent="showContextMenu($event, t)"
            >
              <span class="col-index">
                <span class="index-num">{{ i + 1 }}</span>
                <el-icon class="play-icon" v-ripple size="16" @click.stop="playSection(sec, i)"><VideoPlay /></el-icon>
              </span>
              <span class="col-title">
                <LazyCover v-if="t.cover" :src="t.cover" class="row-cover" :thumb-size="72" />
                <div v-else class="row-cover row-cover--empty"><el-icon size="14"><Headset /></el-icon></div>
                <div class="col-title__text">
                  <span class="col-title__name" v-html="hl(t.title)"></span>
                  <span class="col-title__artist-row">
                    <template v-for="(name, ai) in (t.artist || '').split('/').map(s => s.trim()).filter(Boolean)" :key="ai">
                      <router-link :to="`/artist/${encodeURIComponent(name)}`" class="link col-title__artist"><span v-html="hl(name)"></span></router-link>
                      <span v-if="ai < (t.artist || '').split('/').map(s => s.trim()).filter(Boolean).length - 1" class="col-title__sep"> / </span>
                    </template>
                  </span>
                </div>
              </span>
              <span class="col-album">
                <router-link v-if="t.album" :to="`/album/${encodeURIComponent(t.album)}`" class="link"><span v-html="hl(t.album)"></span></router-link>
              </span>
              <span v-if="sec.key === 'song'" class="col-quality">
                <span v-if="t.quality" class="quality-tag" :class="qualityClass(t.quality)">{{ t.quality }}</span>
              </span>
              <span v-if="sec.key === 'song'" class="col-time">{{ fmtDur(t) }}</span>
              <span v-else class="col-time-text">{{ sec.meta(t) }}</span>
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
import { rankPick } from '@/utils/pinyinSearch'
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
import { qualityClass } from '@/utils/format'

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

  // 各分组统一走「原文 / 全拼 / 首字母」三级匹配，并按匹配分值排序
  const fields = t => [t.title, t.artist, t.album]
  const songs = rankPick(libraryStore.allTracks, fields, kw)
  const albums = rankPick(libraryStore.albums, a => [a.name, a.artist], kw)
    .map(a => ({ key: a.name, title: a.name, sub: a.artist, cover: a.cover, route: `/album/${encodeURIComponent(a.name)}` }))
  const artists = rankPick(libraryStore.artists, a => [a.name], kw)
    .map(a => ({ key: a.name, title: a.name, sub: `${a.tracks.length} 首歌曲`, cover: a.tracks?.[0]?.cover || '', glyph: GLYPH.artist, route: `/artist/${encodeURIComponent(a.name)}` }))
  const playlists = rankPick(playlistStore.playlists, p => [p.name, p.description], kw)
    .map(p => ({ key: String(p.id), title: p.name, sub: p.description || '歌单', cover: p.cover_url || '', glyph: GLYPH.playlist, route: `/playlist/${p.id}` }))
  const hist = rankPick(statsRecent.value, fields, kw)
  const tops = rankPick(statsTop.value, fields, kw)

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
// 「综合」+ 有结果的类别（空类别不出现 tab，避免点击后全是空态）；tab 带数量徽标
const tabs = computed(() => [
  { key: 'all', label: '综合', count: null },
  ...sections.value.map(s => ({ key: s.key, label: s.label, count: s.items.length }))
])
const visibleSections = computed(() => {
  if (activeTab.value === 'all') {
    // 综合模式：每组仅预览一部分，避免单页过长（组标题「>」进单类）
    return sections.value.map(s => ({
      ...s,
      display: s.type === 'tracks' ? s.items.slice(0, TRACK_PREVIEW) : s.items.slice(0, CARD_PREVIEW)
    }))
  }
  // 单类模式：仅当前组的全量
  const cur = sections.value.find(s => s.key === activeTab.value)
  return cur ? [{ ...cur, display: cur.items }] : []
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
// 列模板与音乐库页完全对齐：歌曲=音质52+时长60，历史/播放次数=合并统计列112；
// 末尾固定 40px 操作占位列（搜索页无多选，留白以保持与其它列表行宽一致）
function trackGrid(sec) {
  return sec.key === 'song'
    ? '40px 1fr 1fr 52px 60px 40px'
    : '40px 1fr 1fr 112px 40px'
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
/* 页头吸附基准对齐全站：默认 sticky top 为 --content-top，会整体下移一个页头上方背景带 */
.search-view :deep(.list-page-header) { top: 0; }

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
/* tab 数量徽标（与艺术家详情页完全同款：纯文字次级色，active 跟随强调色） */
.search-tab__count {
  margin-left: 4px;
  font-size: 12px; font-weight: 400;
  color: var(--text-tertiary);
}
.search-tab.active .search-tab__count { color: var(--accent-color); }

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

/* 曲目行：与列表页 track-row 完全同规格（网格列由 trackGrid 按组注入、64px 行高、hover 序号换播放图标） */
.track-row {
  display: grid;
  align-items: center;
  height: 64px;
  padding: 0 var(--page-pad-x, 12px); border-radius: 6px;
  transition: background 0.15s; cursor: default;
  content-visibility: auto;
  contain-intrinsic-size: 64px;
}
.track-row:hover, .track-row--ctx-active { background: var(--hover-bg); }
.track-row.playing .col-title__name,
.track-row.playing .col-title__artist,
.track-row.playing .col-title__sep,
.track-row.playing .col-album,
.track-row.playing .col-album .link,
.track-row.playing .col-time,
.track-row.playing .col-time-text,
.track-row.playing .col-index .index-num { color: var(--accent-color); }

.col-index { text-align: center; position: relative; }
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
.row-cover--empty { background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); }
.col-album { font-size: 14px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-quality { width: 52px; display: flex; align-items: center; justify-content: flex-end; }
.col-time { width: 60px; text-align: right; font-size: 13px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.col-time-text { width: 112px; font-size: 13px; color: var(--text-tertiary); white-space: nowrap; text-align: right; font-variant-numeric: tabular-nums; }
.col-action { width: 40px; text-align: center; }
.link { color: var(--text-secondary); text-decoration: none; }
.link:hover { color: var(--accent-color); text-decoration: underline; }

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
