<template>
  <div class="global-search" ref="rootRef">
    <div class="global-search__box" :class="{ focused: open }">
      <svg class="global-search__icon" width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        placeholder="搜索歌曲、专辑、艺术家..."
        spellcheck="false"
        @focus="onOpen"
        @keydown="onKeydown"
      />
      <button v-if="query" class="global-search__clear" title="清除" @mousedown.prevent @click="clearQuery">
        <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M9.5 2.5L2.5 9.5M2.5 2.5l7 7"/></svg>
      </button>
      <!-- 跳转搜索结果页（与 Ctrl+Enter 同行为），仅有关键词时出现 -->
      <button v-if="query.trim()" class="global-search__go" title="查看全部结果（Ctrl+Enter）" @mousedown.prevent @click="goSearchPage">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 8h10"/><path d="M9 4l4 4-4 4"/></svg>
      </button>
      <span v-if="!query" class="global-search__kbd">Ctrl K</span>
    </div>

    <Teleport to="body">
      <Transition name="gs-panel">
        <div v-if="open" class="global-search__panel" @mousedown.prevent>
          <div ref="scrollRef" class="global-search__scroll" :style="panelHeight != null ? { height: panelHeight + 'px', overflowY: scrollable ? 'auto' : 'hidden' } : null">
            <Transition name="gs-content" mode="out-in" appear @enter="onContentEnter">
            <div class="global-search__scroll-inner" :key="contentKey">
            <!-- 有输入：分组结果 -->
            <template v-if="query.trim()">
              <template v-if="groups.length">
                <template v-for="g in groups" :key="g.type">
                  <div class="gs-group-label">{{ g.label }}</div>
                  <button
                    v-for="it in g.items"
                    :key="g.type + ':' + it.key"
                    class="gs-item"
                    :class="{ active: it._i === selIdx }"
                    @click="choose(it)"
                    @mouseenter="selIdx = it._i"
                  >
                    <span class="gs-item__media">
                      <img v-if="it.cover" :src="it.cover" alt="" />
                      <span v-else class="gs-item__glyph" v-html="it.glyph"></span>
                    </span>
                    <span class="gs-item__main">
                      <span class="gs-item__title" v-html="hl(it.title)"></span>
                      <span v-if="it.sub" class="gs-item__sub" v-html="hl(it.sub)"></span>
                    </span>
                    <span v-if="it.meta" class="gs-item__meta">{{ it.meta }}</span>
                  </button>
                </template>
              </template>
              <div v-else class="gs-empty">
                <p class="gs-empty__title">未找到相关内容</p>
                <p class="gs-empty__hint">试试其他关键词</p>
              </div>
            </template>

            <!-- 空输入：历史 + 热门 -->
            <template v-else>
              <template v-if="history.length">
                <div class="gs-group-label gs-group-label--row">
                  <span>最近搜索</span>
                  <button class="gs-clear-btn" @click="clearHistory">清除</button>
                </div>
                <div class="gs-tags">
                  <span v-for="(h, hi) in history" :key="'h-' + hi" class="gs-tag">
                    <button class="gs-tag__text" @click="applyTag(h)">{{ h }}</button>
                    <button class="gs-tag__del" title="删除" @click="removeHistory(hi)">
                      <svg width="8" height="8" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.5 2.5L2.5 9.5M2.5 2.5l7 7"/></svg>
                    </button>
                  </span>
                </div>
              </template>
              <template v-if="hotItems.length">
                <div class="gs-group-label">热门播放</div>
                <div class="gs-tags">
                  <button v-for="(t, ti) in hotItems" :key="'hot-' + ti" class="gs-tag__text gs-tag--btn" @click="applyTag(t)">
                    {{ t }}
                  </button>
                </div>
              </template>
              <div v-if="!history.length && !hotItems.length" class="gs-empty">
                <p class="gs-empty__hint">输入关键词，跨歌曲 / 专辑 / 艺术家 / 歌单 / 历史记录检索</p>
              </div>
            </template>
            </div>
            </Transition>
          </div>
          <div class="global-search__footer">
            <span>↑↓ 选择 · Enter 直达 · Ctrl+Enter 查看全部 · Esc 关闭</span>
            <span v-if="flat.length">{{ flat.length }} 条结果</span>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
defineOptions({ name: 'GlobalSearch' })
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLibraryStore } from '@/stores/library'
import { usePlaylistStore } from '@/stores/playlist'
import { usePlayerStore } from '@/stores/player'
import { apiUrl, audioUrl, coverUrl } from '@/config/api'

const route = useRoute()
const router = useRouter()
const libraryStore = useLibraryStore()
const playlistStore = usePlaylistStore()
const playerStore = usePlayerStore()

const rootRef = ref(null)
const inputRef = ref(null)
const query = ref('')
const open = ref(false)
const selIdx = ref(-1)

// ==================== 搜索历史（localStorage 持久化） ====================
const HISTORY_KEY = 'melodybox.globalSearchHistory'
const history = ref([])
try { history.value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { history.value = [] }

function saveHistory() {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value)) } catch { /* 忽略 */ }
}
function addHistory(q) {
  const t = q.trim()
  if (!t) return
  const i = history.value.indexOf(t)
  if (i > -1) history.value.splice(i, 1)
  history.value.unshift(t)
  if (history.value.length > 10) history.value.pop()
  saveHistory()
}
function removeHistory(i) {
  history.value.splice(i, 1)
  saveHistory()
}
function clearHistory() {
  history.value = []
  saveHistory()
}
function applyTag(text) {
  query.value = text
  inputRef.value?.focus()
}

// ==================== 行为数据（历史/播放次数：面板首次打开时惰性拉取） ====================
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
      url: audioUrl(item.file_path || ''),
      lyrics: lib?.lyrics || '',
      duration: lib?.duration || 0,
      played_at: item.played_at,
      play_count: item.play_count || 0,
      last_played: item.last_played,
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

// ==================== 分组过滤结果 ====================
const GROUP_META = {
  song:    { label: '歌曲',     glyph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>' },
  album:   { label: '专辑',     glyph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/></svg>' },
  artist:  { label: '艺术家',   glyph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/></svg>' },
  playlist:{ label: '歌单',     glyph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h13M3 12h13M3 18h9"/><path d="M19 12v7"/><circle cx="17.5" cy="19" r="1.6"/></svg>' },
  history: { label: '历史记录', glyph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>' },
  top:     { label: '播放次数', glyph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l2.5 6.5L21 10l-5 4.4L17.5 21 12 17.3 6.5 21 8 14.4 3 10l6.5-.5L12 3z"/></svg>' },
}

const groups = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return []
  const match = (s) => (s || '').toLowerCase().includes(q)
  const mk = (type, items) => {
    if (!items.length) return null
    return { type, label: GROUP_META[type].label, items }
  }

  // 歌曲
  const songs = libraryStore.allTracks.filter(t => match(t.title) || match(t.artist) || match(t.album)).slice(0, 5)
    .map(t => ({ kind: 'song', key: t.path, title: t.title, sub: t.artist, cover: t.cover, glyph: GROUP_META.song.glyph, track: t }))
  // 专辑
  const albums = libraryStore.albums.filter(a => match(a.name) || match(a.artist)).slice(0, 5)
    .map(a => ({ kind: 'album', key: a.name, title: a.name, sub: a.artist, cover: a.cover, glyph: GROUP_META.album.glyph, route: `/album/${encodeURIComponent(a.name)}` }))
  // 艺术家
  const artists = libraryStore.artists.filter(a => match(a.name)).slice(0, 5)
    .map(a => ({ kind: 'artist', key: a.name, title: a.name, sub: `${a.tracks.length} 首歌曲`, cover: '', glyph: GROUP_META.artist.glyph, route: `/artist/${encodeURIComponent(a.name)}` }))
  // 歌单
  const playlists = playlistStore.playlists.filter(p => match(p.name) || match(p.description)).slice(0, 5)
    .map(p => ({ kind: 'playlist', key: String(p.id), title: p.name, sub: p.description || '歌单', cover: p.cover_url || '', glyph: GROUP_META.playlist.glyph, route: `/playlist/${p.id}` }))
  // 历史记录
  const hist = statsRecent.value.filter(t => match(t.title) || match(t.artist) || match(t.album)).slice(0, 5)
    .map(t => ({ kind: 'history', key: 'h-' + t.path + '-' + t.played_at, title: t.title, sub: t.artist, cover: t.cover, glyph: GROUP_META.history.glyph, meta: fmtRel(t.played_at), track: t }))
  // 播放次数
  const tops = statsTop.value.filter(t => match(t.title) || match(t.artist) || match(t.album)).slice(0, 5)
    .map(t => ({ kind: 'top', key: 't-' + t.path, title: t.title, sub: t.artist, cover: t.cover, glyph: GROUP_META.top.glyph, meta: `${t.play_count} 次`, track: t }))

  const list = [mk('song', songs), mk('album', albums), mk('artist', artists), mk('playlist', playlists), mk('history', hist), mk('top', tops)].filter(Boolean)
  let idx = 0
  for (const g of list) for (const it of g.items) it._i = idx++
  return list
})

const flat = computed(() => groups.value.flatMap(g => g.items))

// 空态热门：播放次数前 5 的歌名
const hotItems = computed(() => statsTop.value.slice(0, 5).map(t => t.title).filter(Boolean))

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

// ==================== 关键词高亮 ====================
function hl(text) {
  const kw = query.value.trim()
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

// ==================== 选中与跳转 ====================
function choose(it) {
  addHistory(query.value)
  close()
  if (it.track) {
    // 歌曲/历史/播放次数条目：直接播放（优先用曲库完整元数据）
    const full = libraryStore.getTrackByPath(it.track.path) || it.track
    playerStore.playAll([full], 0)
    return
  }
  if (it.route) router.push(it.route)
}

// 回车（未选中项）：跳转独立搜索结果页查看全部分组结果
function goSearchPage() {
  const kw = query.value.trim()
  if (!kw) return
  addHistory(kw)
  close()
  router.push({ path: '/search', query: { q: kw } })
}

// ==================== 面板开关与键盘 ====================
function onOpen() {
  open.value = true
  selIdx.value = -1
  ensureStats()
}
function close() {
  open.value = false
  selIdx.value = -1
}
function clearQuery() {
  query.value = ''
  selIdx.value = -1
  inputRef.value?.focus()  // 保持焦点，面板切换回历史/热门空态页
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    e.preventDefault()
    if (query.value) { clearQuery() } else { close(); inputRef.value?.blur() }
    return
  }
  if (!open.value && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    open.value = true
    return
  }
  const total = flat.value.length
  if (!total) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selIdx.value = selIdx.value < 0 ? 0 : (selIdx.value + 1) % total
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selIdx.value = selIdx.value <= 0 ? total - 1 : selIdx.value - 1
  } else if (e.key === 'Enter') {
    e.preventDefault()
    // Ctrl/Cmd+Enter：跳转独立搜索结果页查看全部分组结果
    if (e.ctrlKey || e.metaKey) { goSearchPage(); return }
    // Enter：单项直达（无选中时执行第一项，即最相关结果）
    const it = selIdx.value >= 0 ? flat.value[selIdx.value] : flat.value[0]
    if (it) choose(it)
  }
}

// Ctrl+K 全局呼出
function onGlobalKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    open.value = true
    nextTick(() => inputRef.value?.focus())
  }
}
function onDocClick(e) {
  // 目标元素在事件派发途中被移除（如点叉号清词后 v-if 卸载按钮），
  // 此时 target 已游离：contains/closest 都会误判为"外部点击"，直接忽略该事件
  if (!e.target.isConnected) return
  // 面板 Teleport 到 body，点击面板内部不算外部
  if (rootRef.value?.contains(e.target)) return
  if (e.target.closest?.('.global-search__panel')) return
  close()
}

watch(query, () => { selIdx.value = -1 })
watch(() => route.fullPath, () => close())

// ==================== 面板高度动画与内容模糊切换 ====================
// 高度动画：JS 只负责写入目标高度，插值交给 CSS transition（统一曲线），
// 避免手写 rAF 求解 cubic-bezier。打开瞬间 height 直接到位 → 纯模糊渐显，无缩放感。
const scrollRef = ref(null)
const panelHeight = ref(null) // null = height auto（面板刚挂载时不参与过渡）
const scrollable = ref(false) // 仅内容真正超过高度上限才允许滚动，短内容一律 hidden（杜绝任何来源的微小溢出弹出滚动条）
const PANEL_HEIGHT_LIMIT = 440

// 内容标识：关键词或空态内容（历史/热门条数）变化 → 内容模糊切换 + 高度重测
const contentKey = computed(() => {
  const q = query.value.trim()
  if (q) return 'q:' + q.toLowerCase()
  return 'idle:' + history.value.length + ':' + hotItems.value.length
})

function measurePanelHeight() {
  nextTick(() => {
    const inner = scrollRef.value?.querySelector('.global-search__scroll-inner')
    if (!inner) return
    // 测高必须用 offsetHeight（布局值）：面板入场动画 scale(0.88)→1 期间
    // getBoundingClientRect 会被缩放污染（测得 ≈ 实高 × 0.88 → 设高偏小 → 溢出出条）
    const layoutH = inner.offsetHeight
    scrollable.value = layoutH > PANEL_HEIGHT_LIMIT
    const target = Math.min(layoutH, PANEL_HEIGHT_LIMIT)
    if (panelHeight.value !== target) {
      panelHeight.value = target
      // 内容切换后滚动归位，避免残留滚动量
      if (scrollRef.value) scrollRef.value.scrollTop = 0
    }
  })
}

// mode="out-in"：新内容插入 DOM 后才触发（离场完成后），此刻测量高度才准确
function onContentEnter() {
  measurePanelHeight()
}

watch(open, (v) => {
  if (v) panelHeight.value = null // 重新打开时高度直接到位，不播放收缩过渡
})

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onGlobalKeydown)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onGlobalKeydown)
})
</script>

<style scoped>
.global-search {
  position: relative;
  -webkit-app-region: no-drag;
  z-index: 1100;
}
.global-search__box {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 320px;
  height: 26px;
  padding: 0 8px 0 10px;
  border-radius: 13px;
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.22);
  transition: border-color 0.2s ease, background 0.2s ease;
}
.global-search__box.focused {
  border-color: var(--accent-color);
  background: rgba(0, 0, 0, 0.32);
}
/* 浅色模式：黑色叠加在浅色顶栏上观感过深，减淡内陷感（深色保持原值） */
[data-theme='light'] .global-search__box { background: rgba(0, 0, 0, 0.06); }
[data-theme='light'] .global-search__box.focused { background: rgba(0, 0, 0, 0.1); }
.global-search__icon { color: var(--text-tertiary); flex-shrink: 0; }
.global-search__box input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 12.5px;
}
.global-search__box input::placeholder { color: var(--text-tertiary); }
.global-search__clear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
}
.global-search__clear:hover { color: var(--text-primary); }
/* 跳转搜索结果页：hover 右移微动效呼应箭头语义 */
.global-search__go {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s;
}
.global-search__go:hover { color: var(--accent-color); }
.global-search__kbd {
  font-size: 10px;
  color: var(--text-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 1px 5px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

/* 面板：Teleport 到 body，fixed 定位由 JS 不需要——用输入框坐标不划算，
   直接水平居中于标题栏下方 */
.global-search__panel {
  position: fixed;
  top: 40px;
  left: 50%;
  transform: translateX(-50%);
  width: 480px;
  max-width: calc(100vw - 40px);
  border-radius: 12px;
  background: var(--glass-bg-strong, rgba(30, 30, 38, 0.92));
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid var(--border-color);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
  z-index: 3000;
  overflow: hidden;
  /* 缩放锚点=顶部中心：面板顶边贴搜索框下方，入场向下生长、出场缩回 */
  transform-origin: top center;
}
/* 面板开合：模糊渐隐渐显 + 缩放（与全局右键菜单同语言）。
   入：从略小尺寸（0.88）生长到位——顶边锚定搜索框下方，从源头"长出来"；
   出：反向缩回搜索框。锚顶边 + 缩小态不产生上溢，顶边全程稳定不裁切 */
.gs-panel-enter-active {
  transition: opacity 0.45s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.45s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.45s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.gs-panel-leave-active {
  transition: opacity 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.gs-panel-enter-from {
  opacity: 0;
  filter: blur(10px);
  transform: translateX(-50%) scale(0.88);
}
.gs-panel-leave-to {
  opacity: 0;
  filter: blur(10px);
  transform: translateX(-50%) scale(0.88);
}

/* 内容切换（关键词/空态变化）：模糊渐隐 → 模糊渐显（out-in 串行）。
   打字高频触发，节奏比开合稍快以免跟不上输入 */
.gs-content-enter-active {
  transition: opacity 0.3s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.3s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.gs-content-leave-active {
  transition: opacity 0.18s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.18s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.gs-content-enter-from, .gs-content-leave-to {
  opacity: 0;
  filter: blur(6px);
}

/* 高度平滑过渡：JS 只写目标高度，插值交给统一曲线 */
.global-search__scroll {
  overflow-y: auto;
  overflow-x: hidden;
  transition: height 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.global-search__scroll-inner { padding: 6px; }
.global-search__scroll::-webkit-scrollbar { width: 6px; }
.global-search__scroll::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }

.gs-group-label {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 6px 10px 4px;
  letter-spacing: 0.5px;
}
.gs-group-label--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.gs-clear-btn {
  border: none;
  background: none;
  color: var(--text-tertiary);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 5px;
}
.gs-clear-btn:hover { color: var(--text-primary); background: var(--hover-bg); }

.gs-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 6px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s;
}
.gs-item:hover, .gs-item.active { background: var(--hover-bg); }
.gs-item.active { background: var(--accent-bg); }

.gs-item__media {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}
.gs-item__media img { width: 100%; height: 100%; object-fit: cover; }
.gs-item__glyph { display: flex; }

.gs-item__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.gs-item__title {
  font-size: 13px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gs-item__sub {
  font-size: 11.5px;
  color: var(--text-secondary);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gs-item__meta {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.gs-item__title :deep(mark) {
  background: transparent;
  color: var(--accent-color);
  font-weight: 600;
}

.gs-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 2px 10px 8px;
}
.gs-tag {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.gs-tag__text {
  border: none;
  background: var(--hover-bg);
  color: var(--text-secondary);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 14px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.gs-tag__text:hover { background: var(--hover-bg-strong); color: var(--text-primary); }
.gs-tag--btn { display: inline-flex; }
.gs-tag__del {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 14px;
  height: 14px;
  display: none;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: rgba(232, 17, 35, 0.75);
  color: #fff;
  cursor: pointer;
  padding: 0;
}
.gs-tag:hover .gs-tag__del { display: flex; }

.gs-empty {
  padding: 28px 16px;
  text-align: center;
  color: var(--text-tertiary);
}
.gs-empty__title { font-size: 13px; margin: 0 0 6px; }
.gs-empty__hint { font-size: 12px; margin: 0; }

.global-search__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 14px;
  border-top: 1px solid var(--border-color);
  font-size: 11px;
  color: var(--text-tertiary);
  background: var(--bg-secondary);
}
</style>