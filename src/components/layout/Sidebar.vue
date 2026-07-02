<template>
  <nav class="sidebar">
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
import { Plus, Moon, Sunny, Monitor, UserFilled, Timer, TrendCharts } from '@element-plus/icons-vue'
import { usePlaylistStore } from '@/stores/playlist'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useModal } from '@/composables/useModal'

const playlistStore = usePlaylistStore()
const settings = useSettingsStore()
const auth = useAuthStore()
const modal = useModal()

const themeOptions = [
  { value: 'light', icon: Sunny, label: '浅色' },
  { value: 'dark', icon: Moon, label: '深色' },
  { value: 'system', icon: Monitor, label: '跟随系统' }
]

function setTheme(value) {
  settings.theme = value
  settings.saveSettings()
}

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
  width: 240px;
  margin: 10px 0 10px 10px;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: 14px;
  border: 1px solid var(--border-color);
  flex-shrink: 0;
  overflow: hidden;
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
