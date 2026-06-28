<template>
  <!-- 桌面歌词独立窗口：只渲染路由视图，无应用外壳 -->
  <div v-if="isDesktopLyricsRoute" id="melody-box" class="lyrics-only">
    <router-view />
  </div>

  <!-- 正常应用布局 -->
  <div v-else id="melody-box" :class="{ 'is-electron': isElectron }">
    <TitleBar v-if="isElectron" :lyrics-visible="panelVisible" />
    <div class="app-body">
      <Sidebar />
      <main class="main-content">
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition name="page">
            <keep-alive include="HomeView,LibraryView,AlbumsView,ArtistsView,SettingsView,UserView,FoldersView">
              <component :is="Component" :key="currentRoute.path" />
            </keep-alive>
          </transition>
        </router-view>
      </main>
    </div>
    <PlayerBar ref="playerBarRef" style="z-index: 1001" :panel-open="panelOpen" :panel-fading="panelFading" :text-shifted="textShifted" />

    <ProgressPanel :queue-open="queueOpen" />

    <!-- 全屏播放面板覆盖层 -->
    <NowPlayingPanel
      :visible="panelVisible"
      @close="handleClose"
      @fly-complete="panelOpen = false"
    />

    <!-- 桌面歌词浮窗 -->
    <DesktopLyrics />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useSettingsStore } from '@/stores/settings'
import { initMediaSession } from '@/utils/mediaSession'
import TitleBar from '@/components/layout/TitleBar.vue'
import Sidebar from '@/components/layout/Sidebar.vue'
import PlayerBar from '@/components/player/PlayerBar.vue'
import NowPlayingPanel from '@/components/player/NowPlayingPanel.vue'
import DesktopLyrics from '@/components/player/DesktopLyrics.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'

const playerStore = usePlayerStore()
const settingsStore = useSettingsStore()
const route = useRoute()
// 直接用 location.hash 判断，避免路由初始化时序导致 route.name 为 undefined
const isDesktopLyricsRoute = computed(() => {
  return window.location.hash === '#/desktop-lyrics' || route.name === 'desktopLyrics'
})
const currentTrack = computed(() => playerStore.currentTrack)
const isElectron = computed(() => !!window.electronAPI)

const panelVisible = ref(false)
const panelOpen = ref(false)
const panelFading = ref(false)
const textShifted = ref(false)
const coverOriginRect = ref(null)
const playerBarRef = ref(null)
const queueOpen = computed(() => playerBarRef.value?.showQueue ?? false)

provide('toggleNowPlaying', () => {
  if (!panelOpen.value && playerBarRef.value?.coverEl) {
    coverOriginRect.value = playerBarRef.value.coverEl.getBoundingClientRect()
  }
  if (!panelOpen.value) {
    // 展开：封面隐身 + 文字左移 + 面板显示 + 颜色变白
    panelOpen.value = true
    panelFading.value = true
    textShifted.value = true
    panelVisible.value = true
  } else {
    // 关闭：颜色立即恢复渐变动画，封面保持在位移动画完成后恢复
    panelFading.value = false
    textShifted.value = false
    nextTick(() => { panelVisible.value = false })
    // panelOpen 保持 true → 封面隐身直至飞行结束(@fly-complete)
  }
})
provide('coverOriginRect', coverOriginRect)

function handleClose() {
  panelFading.value = false
  textShifted.value = false
  nextTick(() => { panelVisible.value = false })
}

// ==================== 主题色管理 ====================

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return { r, g, b }
}

function applyAccentColor(hex) {
  const el = document.documentElement
  el.style.setProperty('--accent-color', hex)
  const { r, g, b } = hexToRgb(hex)
  el.style.setProperty('--accent-bg', `rgba(${r}, ${g}, ${b}, 0.12)`)
}

async function fetchAndApplySystemColor() {
  if (!window.electronAPI) return
  const color = await window.electronAPI.getAccentColor()
  if (color) {
    applyAccentColor(color)
  }
}

// ==================== 深色/浅色主题 ====================

const systemColorSchemeQuery = window.matchMedia?.('(prefers-color-scheme: dark)')

function resolveTheme() {
  const t = settingsStore.theme
  if (t === 'system') {
    return systemColorSchemeQuery?.matches ? 'dark' : 'light'
  }
  return t
}

function applyTheme() {
  const actual = resolveTheme()
  const html = document.documentElement
  html.setAttribute('data-theme', actual)
  if (actual === 'dark') {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
}

watch(() => settingsStore.theme, applyTheme)

// 监听跟随系统主题色开关
watch(() => settingsStore.followSystemTheme, async (val) => {
  if (val) {
    await fetchAndApplySystemColor()
  } else {
    applyAccentColor(settingsStore.accentColor)
  }
  settingsStore.saveSettings()
})

// 监听手动主题色变更（当不跟随系统时生效）
watch(() => settingsStore.accentColor, (val) => {
  if (!settingsStore.followSystemTheme) {
    applyAccentColor(val)
  }
})

// 监听系统主题色变化（事件驱动，零轮询，零开销）

onMounted(() => {
  playerStore.loadSettings()
  initMediaSession()
  // 初始化主题色
  if (settingsStore.followSystemTheme) {
    fetchAndApplySystemColor()
  } else {
    applyAccentColor(settingsStore.accentColor)
  }
  // 监听系统主题色变化（事件驱动）
  if (window.electronAPI?.onAccentColorChanged) {
    window.electronAPI.onAccentColorChanged((color) => {
      if (settingsStore.followSystemTheme && color) {
        applyAccentColor(color)
      }
    })
  }
  // 初始化深色/浅色主题
  applyTheme()
  // 监听系统色彩方案变化
  systemColorSchemeQuery?.addEventListener('change', applyTheme)

  // 窗口大小改变时更新封面起始位置，确保飞行动画在 resize 后不偏移
  window.addEventListener('resize', () => {
    if (panelOpen.value && playerBarRef.value?.coverEl) {
      coverOriginRect.value = playerBarRef.value.coverEl.getBoundingClientRect()
    }
  })
})
</script>

<style>
#melody-box {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-primary);
  color: var(--text-primary);
}

/* 桌面歌词独立窗口：透明背景，无 flex 布局 */
#melody-box.lyrics-only {
  background: transparent;
  color: #fff;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  background: var(--bg-secondary);
}

.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 24px 32px 0;
  scrollbar-gutter: stable;
  content-visibility: auto;
  background: var(--bg-secondary);
  position: relative; /* 为页面过渡动画提供定位参考 */
}

/* 滚动条样式 */
.main-content::-webkit-scrollbar {
  width: 6px;
}
.main-content::-webkit-scrollbar-track {
  background: transparent;
}
.main-content::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 3px;
}
.main-content::-webkit-scrollbar-thumb:hover {
  background: var(--scrollbar-thumb-hover);
}

/* ===== 页面切换过渡动画 ===== */
/* 使用 @keyframes 动画而非 transition，确保每次路由切换都从 from 状态开始，
   避免 keep-alive 缓存页激活时因初始状态已可见导致的"闪现" */
/* 进入/离开元素均设为绝对定位并完全重叠，消除布局跳动 */
.page-enter-active {
  animation: page-enter 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0) both;
  position: absolute;
  top: 24px;
  left: 32px;
  right: 32px;
}
.page-leave-active {
  animation: page-leave 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0) both;
  position: absolute;
  top: 24px;
  left: 32px;
  right: 32px;
  z-index: 1;
  pointer-events: none;
}

@keyframes page-enter {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes page-leave {
  from {
    opacity: 1;
    transform: scale(1);
  }
  to {
    opacity: 0;
    transform: scale(1.03);
  }
}
</style>
