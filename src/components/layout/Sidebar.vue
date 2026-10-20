<template>
  <!-- 隐藏模式：左侧贴边热区，移入唤出 -->
  <div v-if="mode === 'hidden'" class="sidebar-hotzone" @mouseenter="onHotzoneEnter" @mouseleave="onHotzoneLeave"></div>
  <nav
    class="sidebar"
    :class="{ collapsed: mode === 'collapsed', hidden: mode === 'hidden', revealed }"
    @mouseenter="onSidebarEnter"
    @mouseleave="onSidebarLeave"
  >
    <!-- 顶部折叠/展开按钮 -->
    <div class="sidebar__header">
      <button
        v-if="mode !== 'collapsed'"
        class="sidebar-toggle"
        :class="{ active: mode === 'hidden' }"
        v-ripple
        :title="mode === 'hidden' ? '取消隐藏' : '隐藏侧边栏'"
        @click="toggleHidden"
      >
        <el-icon><component :is="mode === 'hidden' ? DArrowRight : DArrowLeft" /></el-icon>
      </button>
      <button
        class="sidebar-toggle"
        v-ripple
        :title="mode === 'collapsed' ? '展开侧边栏' : '收起侧边栏'"
        @click="toggleCollapsed"
      >
        <el-icon><component :is="mode === 'collapsed' ? Expand : Fold" /></el-icon>
      </button>
    </div>
    <!-- 主导航 -->
    <div class="sidebar__section">
      <router-link to="/" class="nav-item" v-ripple :class="{ active: $route.path === '/' }">
        <el-icon><HomeFilled /></el-icon>
        <span>首页</span>
      </router-link>
      <router-link to="/library" class="nav-item" v-ripple :class="{ active: $route.path === '/library' }">
        <el-icon><Headset /></el-icon>
        <span>音乐库</span>
      </router-link>
      <router-link to="/albums" class="nav-item" v-ripple :class="{ active: $route.path === '/albums' }">
        <el-icon><FolderOpened /></el-icon>
        <span>专辑</span>
      </router-link>
      <router-link to="/artists" class="nav-item" v-ripple :class="{ active: $route.path === '/artists' }">
        <el-icon><User /></el-icon>
        <span>艺术家</span>
      </router-link>
      <router-link to="/folders" class="nav-item" v-ripple :class="{ active: $route.path === '/folders' }">
        <el-icon><FolderOpened /></el-icon>
        <span>文件夹</span>
      </router-link>
      <router-link to="/history" class="nav-item" v-ripple :class="{ active: $route.path === '/history' }">
        <el-icon><Timer /></el-icon>
        <span>播放历史</span>
      </router-link>
      <router-link to="/top-plays" class="nav-item" v-ripple :class="{ active: $route.path === '/top-plays' }">
        <el-icon><TrendCharts /></el-icon>
        <span>播放次数</span>
      </router-link>
    </div>

    <!-- 歌单 -->
    <div class="sidebar__section">
      <div class="sidebar__label">
        <span>歌单</span>
        <span class="sidebar__label-actions">
          <el-button
            v-if="playlistStore.sortMode === 'custom'"
            :icon="Rank"
            size="small"
            text
            circle
            :type="reorderActive ? 'primary' : 'default'"
            :title="reorderActive ? '完成排序' : '进入排序模式'"
            @click="toggleReorder"
          />
          <el-button :icon="Sort" size="small" text circle title="歌单排序" @click="openSortMenu" />
          <el-button :icon="Plus" size="small" text circle @click="handleCreatePlaylist" />
        </span>
      </div>
      <div v-if="playlistStore.playlists.length > 0" ref="plListEl" class="playlist-items">
        <router-link
          v-for="pl in displayPlaylists"
          :key="pl.id"
          :to="`/playlist/${pl.id}`"
          :data-id="pl.id"
          class="nav-item"
          v-ripple
          :class="{ active: $route.params.id === pl.id, 'is-system-row': pl.is_system }"
          @mouseenter="playlistStore.ensureTracksLoaded(pl.id)"
        >
          <el-icon v-if="pl.is_system"><StarFilled /></el-icon>
          <img v-else-if="pl.cover_url" :src="pl.cover_url" class="nav-item__cover" />
          <el-icon v-else><Document /></el-icon>
          <span class="truncate">{{ pl.name }}</span>
          <span class="count">{{ pl.track_count ?? pl.tracks.length ?? 0 }}</span>
          <!-- 排序模式：把手占位使数字左移让位 -->
          <span v-if="reorderActive && !pl.is_system" class="pl-drag-handle" @click.stop>
            <el-icon size="14"><DCaret /></el-icon>
          </span>
        </router-link>
      </div>
      <div v-else class="empty-hint">暂无歌单，点击 + 创建</div>
    </div>

    <!-- 底部操作 -->
    <div class="sidebar__bottom">
      <!-- 用户区域 -->
      <router-link v-if="auth.isLoggedIn" to="/user" class="nav-item user-item" v-ripple :class="{ active: $route.path === '/user' }">
        <el-icon><UserFilled /></el-icon>
        <span class="truncate">{{ auth.user?.username || '用户' }}</span>
        <span class="user-badge" v-if="auth.isAdmin">管理员</span>
      </router-link>
      <router-link v-else to="/login" class="nav-item" v-ripple :class="{ active: $route.path === '/login' }">
        <el-icon><User /></el-icon>
        <span>登录</span>
      </router-link>

      <router-link to="/settings" class="nav-item" v-ripple :class="{ active: $route.path === '/settings' }">
        <el-icon><Setting /></el-icon>
        <span>设置</span>
      </router-link>
      <button
        class="theme-switch"
        v-ripple
        :title="currentTheme.label"
        @click="cycleTheme"
      >
        <el-icon><component :is="currentTheme.icon" /></el-icon>
        <span class="theme-switch__label">{{ currentTheme.label }}</span>
      </button>
    </div>

    <!-- 歌单排序下拉（复用全局玻璃菜单） -->
    <ContextMenu
      :visible="sortMenu.visible"
      :x="sortMenu.x"
      :y="sortMenu.y"
      :items="sortMenuItems"
      :animated="true"
      @close="sortMenu.visible = false"
      @action="onSortAction"
    />
  </nav>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { Plus, Moon, Sunny, Monitor, UserFilled, Timer, TrendCharts, Expand, Fold, DArrowLeft, DArrowRight, StarFilled, Sort, Rank, DCaret } from '@element-plus/icons-vue'
import Sortable from 'sortablejs'
import { usePlaylistStore } from '@/stores/playlist'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useModal } from '@/composables/useModal'
import ContextMenu from '@/components/music/ContextMenu.vue'

const playlistStore = usePlaylistStore()
const settings = useSettingsStore()
const auth = useAuthStore()
const modal = useModal()

const props = defineProps({
  mode: { type: String, default: 'expanded' }
})
const emit = defineEmits(['update:mode'])

const revealed = ref(false)
let hideTimer = null

const themeOptions = [
  { value: 'light', icon: Sunny, label: '浅色' },
  { value: 'dark', icon: Moon, label: '深色' },
  { value: 'system', icon: Monitor, label: '跟随系统' }
]
const themeOrder = ['light', 'dark', 'system']
const currentTheme = computed(() => themeOptions.find(o => o.value === settings.theme) || themeOptions[2])

function setTheme(value) {
  settings.theme = value
  settings.saveSettings()
}

function cycleTheme() {
  const idx = themeOrder.indexOf(settings.theme)
  const next = themeOrder[(idx + 1) % themeOrder.length]
  setTheme(next)
}

function toggleHidden() {
  clearTimeout(hideTimer)
  if (props.mode === 'hidden') {
    emit('update:mode', 'expanded')
    revealed.value = false
  } else {
    // 切到隐藏态但保持可见：等鼠标离开后再自然滑出，不做原地滑出
    emit('update:mode', 'hidden')
    revealed.value = true
  }
}

function toggleCollapsed() {
  clearTimeout(hideTimer)
  if (props.mode === 'collapsed') {
    emit('update:mode', 'expanded')
  } else {
    emit('update:mode', 'collapsed')
  }
  revealed.value = false
}

function onHotzoneEnter() {
  if (props.mode !== 'hidden') return
  clearTimeout(hideTimer)
  revealed.value = true
}

function onHotzoneLeave() {
  if (props.mode !== 'hidden') return
  scheduleHide()
}

function onSidebarEnter() {
  if (props.mode !== 'hidden') return
  clearTimeout(hideTimer)
  revealed.value = true
}

function onSidebarLeave() {
  if (props.mode !== 'hidden') return
  scheduleHide()
}

function scheduleHide() {
  clearTimeout(hideTimer)
  hideTimer = setTimeout(() => {
    revealed.value = false
  }, 180)
}

onBeforeUnmount(() => {
  clearTimeout(hideTimer)
})

async function handleCreatePlaylist() {
  try {
    const value = await modal.prompt({
      title: '新建歌单',
      message: '请输入歌单名称',
      confirmText: '创建',
      inputPlaceholder: '我的歌单'
    })
    if (value?.trim()) {
      playlistStore.createPlaylist(value.trim())
    }
  } catch {}
}

// --- 歌单排序：下拉选择模式 + 自定义拖拽 ---
const sortMenu = ref({ visible: false, x: 0, y: 0 })
const reorderActive = ref(false)
const plListEl = ref(null)

const sortMenuItems = computed(() => ([
  { label: '按名称', action: 'name', active: playlistStore.sortMode === 'name' },
  { label: '按修改时间', action: 'updated', active: playlistStore.sortMode === 'updated' },
  { label: '按歌曲数量', action: 'count', active: playlistStore.sortMode === 'count' },
  '-',
  { label: '自定义排序', action: 'custom', active: playlistStore.sortMode === 'custom' },
]))

// 展示顺序：系统歌单（我的收藏）恒置顶，其余按当前模式排序
const displayPlaylists = computed(() => {
  const list = [...playlistStore.playlists]
  const sys = list.filter(p => p.is_system)
  const rest = list.filter(p => !p.is_system)
  const mode = playlistStore.sortMode
  if (mode === 'name') {
    rest.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'zh-Hans-CN'))
  } else if (mode === 'updated') {
    rest.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
  } else if (mode === 'count') {
    rest.sort((a, b) => (b.track_count || 0) - (a.track_count || 0))
  } else {
    // 自定义：sort_order 升序，老数据同为 0 时回退创建时间
    rest.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) ||
      String(b.created_at || '').localeCompare(String(a.created_at || '')))
  }
  return [...sys, ...rest]
})

function openSortMenu(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  // 自按钮左下角展开；ContextMenu 自带实测防出屏
  sortMenu.value = { visible: true, x: rect.left, y: rect.bottom + 6 }
}

function onSortAction(mode) {
  sortMenu.value.visible = false
  playlistStore.setSortMode(mode)
  if (mode !== 'custom') reorderActive.value = false
}

function toggleReorder() {
  reorderActive.value = !reorderActive.value
}

let sortable = null
watch([reorderActive, () => playlistStore.playlists.length], async ([active]) => {
  await nextTick()
  if (active && !sortable && plListEl.value) {
    sortable = Sortable.create(plListEl.value, {
      animation: 150,
      handle: '.pl-drag-handle',
      draggable: '.nav-item',
      filter: '.is-system-row',
      ghostClass: 'pl-ghost',
      chosenClass: 'pl-chosen',
      onEnd() {
        if (!plListEl.value) return
        const ids = [...plListEl.value.querySelectorAll('.nav-item')]
          .map(el => Number(el.dataset.id))
          .filter(Boolean)
        if (ids.length) playlistStore.reorderPlaylists(ids)
      }
    })
  } else if (!active && sortable) {
    sortable.destroy()
    sortable = null
  }
})

onBeforeUnmount(() => {
  sortable?.destroy()
  sortable = null
})
</script>

<style scoped>
.sidebar {
  position: absolute;
  top: 10px;
  bottom: 10px;
  left: 10px;
  width: 240px;
  margin: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-radius: 14px;
  border: 1px solid var(--border-color);
  /* 纵向滚动：中部主导航/歌单可滚，头部与底部按钮组通过 sticky 固定在两端 */
  overflow-x: hidden;
  overflow-y: auto;
  z-index: 90;
  transition: width 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.sidebar::-webkit-scrollbar { width: 4px; }
.sidebar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}
.sidebar.collapsed {
  width: 64px;
}

/* 隐藏模式：贴边浮层，移入唤出 */
.sidebar-hotzone {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 40px;
  z-index: 89;
}
.sidebar.hidden {
  background:
    radial-gradient(120% 80% at 18% 0%, var(--glass-specular), transparent 55%),
    var(--glass-bg-strong);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-color: var(--glass-border);
  box-shadow: inset 0 1px 0 var(--glass-highlight), var(--glass-shadow);
  transform: translateX(calc(-100% - 18px));
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.sidebar.hidden.revealed {
  transform: translateX(0);
}
.sidebar__header {
  display: flex;
  justify-content: flex-end;
  padding: 10px 10px 0;
  flex-shrink: 0;
  /* 固定在顶部：滚动时折叠/隐藏按钮始终可点 */
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-secondary);
}
.sidebar-toggle {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.sidebar-toggle:hover {
  background: var(--hover-bg-strong);
  color: var(--text-primary);
}
.sidebar__section:first-child { padding-top: 12px; }
.sidebar__section {
  padding: 8px 12px;
}
.sidebar__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-tertiary);
}
.sidebar__label-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}
.sidebar__label-actions .el-button { margin: 0; }

/* 排序模式：行尾拖拽把手（数字因 auto margin 自然左移让位） */
.pl-drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 28px;
  margin-right: -4px;
  border-radius: 4px;
  color: var(--text-tertiary);
  cursor: grab;
  flex-shrink: 0;
}
.pl-drag-handle:hover { color: var(--text-primary); background: var(--hover-bg-strong); }
.pl-drag-handle:active { cursor: grabbing; }
.pl-ghost { opacity: 0.35; background: var(--accent-bg); }
.pl-chosen { opacity: 0.92; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 12px;
  box-sizing: border-box;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: background 0.2s, color 0.2s;
  cursor: pointer;
  margin-bottom: 2px;
}
.nav-item:hover { background: var(--hover-bg-strong); color: var(--text-primary); }
.nav-item.active { background: var(--accent-bg); color: var(--accent-color); }
.nav-item .count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-tertiary);
}
.nav-item__cover {
  width: 1em; height: 1em;
  border-radius: 3px;
  object-fit: cover;
  flex-shrink: 0;
}
.user-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(251,146,60,0.15);
  color: #fb923c;
  font-weight: 600;
}
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty-hint {
  padding: 12px 8px;
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}
.sidebar__bottom {
  margin-top: auto;
  padding: 8px 12px 12px;
  /* 固定在底部：账号/登录、设置、主题切换三项始终可见，不随歌单滚动 */
  position: sticky;
  bottom: 0;
  z-index: 2;
  background: var(--bg-secondary);
}

/* 折叠态：仅保留图标，文字/计数隐藏 */
.sidebar.collapsed .sidebar__header { justify-content: center; padding: 10px 0 0; }
.sidebar.collapsed .nav-item > span { display: none; }
.sidebar.collapsed .nav-item__cover { width: 20px; height: 20px; }
.sidebar.collapsed .sidebar__label { justify-content: center; padding: 4px 0; }
.sidebar.collapsed .sidebar__label > span { display: none; }
.sidebar.collapsed .theme-switch__label { display: none; }
.sidebar.collapsed .empty-hint { display: none; }

/* 主题切换按钮：单键循环切换，尺寸与 nav-item 一致 */
.theme-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 40px;
  padding: 0 12px;
  box-sizing: border-box;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
  margin-bottom: 2px;
}
.theme-switch:hover {
  background: var(--hover-bg-strong);
  color: var(--text-primary);
}
.theme-switch__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
