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
        <el-button :icon="Plus" size="small" text circle @click="handleCreatePlaylist" />
      </div>
      <div class="playlist-items" v-if="playlistStore.playlists.length > 0">
        <router-link
          v-for="pl in playlistStore.playlists"
          :key="pl.id"
          :to="`/playlist/${pl.id}`"
          class="nav-item"
          v-ripple
          :class="{ active: $route.params.id === pl.id }"
          @mouseenter="playlistStore.ensureTracksLoaded(pl.id)"
        >
          <img v-if="pl.cover_url" :src="pl.cover_url" class="nav-item__cover" />
          <el-icon v-else><Document /></el-icon>
          <span class="truncate">{{ pl.name }}</span>
          <span class="count">{{ pl.trackCount || pl.tracks.length }}</span>
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
      <div class="theme-switch">
        <span
          v-for="opt in themeOptions"
          :key="opt.value"
          class="theme-switch__item"
          :class="{ active: settings.theme === opt.value }"
          :title="opt.label"
          v-ripple
          @click="setTheme(opt.value)"
        >
          <el-icon><component :is="opt.icon" /></el-icon>
        </span>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { Plus, Moon, Sunny, Monitor, UserFilled, Timer, TrendCharts, Expand, Fold, DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
import { usePlaylistStore } from '@/stores/playlist'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useModal } from '@/composables/useModal'

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

function setTheme(value) {
  settings.theme = value
  settings.saveSettings()
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
  overflow: hidden;
  z-index: 90;
  transition: width 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
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
  width: 10px;
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
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
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
.playlist-items {
  max-height: 240px;
  overflow-y: auto;
}
.playlist-items::-webkit-scrollbar { width: 4px; }
.playlist-items::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
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
}

/* 折叠态：仅保留图标，文字/计数/主题开关隐藏 */
.sidebar.collapsed .sidebar__header { justify-content: center; padding: 10px 0 0; }
.sidebar.collapsed .nav-item > span { display: none; }
.sidebar.collapsed .nav-item__cover { width: 20px; height: 20px; }
.sidebar.collapsed .sidebar__label { justify-content: center; padding: 4px 0; }
.sidebar.collapsed .sidebar__label > span { display: none; }
.sidebar.collapsed .theme-switch { display: none; }
.sidebar.collapsed .empty-hint { display: none; }

/* 主题切换开关：与 nav-item 同尺寸、同边界 */
.theme-switch {
  display: flex;
  gap: 2px;
  padding: 0;
  margin-bottom: 2px;
}
.theme-switch__item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 0;
  border-radius: 8px;
  color: var(--text-secondary);
  transition: background 0.2s, color 0.2s;
  cursor: pointer;
}
.theme-switch__item:hover {
  background: var(--hover-bg-strong);
  color: var(--text-primary);
}
.theme-switch__item.active {
  background: var(--accent-bg);
  color: var(--accent-color);
}
</style>
