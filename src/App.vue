<template>
  <!-- 桌面歌词独立窗口：只渲染路由视图，无应用外壳 -->
  <div v-if="isDesktopLyricsRoute" id="melody-box" class="lyrics-only">
    <router-view />
  </div>

  <!-- 正常应用布局 -->
  <div v-else id="melody-box" :class="{ 'is-electron': isElectron }">
    <TitleBar v-if="isElectron" :lyrics-visible="panelVisible" />
    <div class="app-body">
      <Sidebar :mode="sidebarMode" @update:mode="sidebarMode = $event" />
      <main class="main-content" :style="{ marginLeft: sidebarMarginLeft }">
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition name="page" @before-leave="onPageBeforeLeave" @after-enter="onPageAfterEnter">
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

    <!-- 全局模态弹窗 -->
    <ModalDialog
      :visible="modalState.visible"
      :title="modalState.title"
      :message="modalState.message"
      :mode="modalState.mode"
      :confirm-text="modalState.confirmText"
      :cancel-text="modalState.cancelText"
      :danger="modalState.danger"
      :input-type="modalState.inputType"
      :input-placeholder="modalState.inputPlaceholder"
      :input-default="modalState.inputDefault"
      :input-validator="modalState.inputValidator"
      @confirm="handleModalConfirm"
      @cancel="handleModalCancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useSettingsStore } from '@/stores/settings'
import { initMediaSession } from '@/utils/mediaSession'
import TitleBar from '@/components/layout/TitleBar.vue'
import Sidebar from '@/components/layout/Sidebar.vue'
import PlayerBar from '@/components/player/PlayerBar.vue'
import NowPlayingPanel from '@/components/player/NowPlayingPanel.vue'
import DesktopLyrics from '@/components/player/DesktopLyrics.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { createModalProvider } from '@/composables/useModal'
import { registerOverlaysCloser } from '@/utils/overlays'

const playerStore = usePlayerStore()
const settingsStore = useSettingsStore()
const route = useRoute()
const router = useRouter()
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
const sidebarMode = ref('expanded')
const sidebarMarginLeft = computed(() => {
  return {
    expanded: '250px',
    collapsed: '74px',
    hidden: '0px'
  }[sidebarMode.value]
})

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

// 全局模态弹窗
const { state: modalState, handleConfirm: handleModalConfirm, handleCancel: handleModalCancel } = createModalProvider()

function handleClose() {
  panelFading.value = false
  textShifted.value = false
  nextTick(() => { panelVisible.value = false })
}

// 跳转到专辑/艺术家/音轨信息时，统一收回全屏播放页与播放队列
registerOverlaysCloser(() => {
  handleClose()
  playerBarRef.value?.closeQueue?.()
})

// ==================== 页面切换过渡动画 ====================

// 记录每个路由路径的 .main-content 滚动位置
const pageScrollMap = {}
// 路由切换前捕获的离开/进入页滚动（beforeEach 写入，过渡钩子读取）
let pendingLeaveScroll = 0
let pendingEnterScroll = 0
// 过渡序列号：快速切换时过滤掉过期回调
let transitionSeq = 0
// 安全兜底定时器
let transitionSafetyTimer = null

/**
 * 在路由真正切换之前保存滚动位置。
 * 注意：快速切换时，上一个过渡的 before-leave 已将 scrollTop 清零且尚未恢复
 * （page-transitioning class 仍在），此时若覆盖 pageScrollMap 会丢失该页的真实位置。
 * 因此过渡窗口期沿用已保存的位置，仅稳定状态下才更新记录。
 */
router.beforeEach((to, from) => {
  if (from.path && from.path !== to.path) {
    const main = document.querySelector('.main-content')
    if (main) {
      const isTransitioning = main.classList.contains('page-transitioning')
      const scroll = isTransitioning ? (pageScrollMap[from.path] ?? main.scrollTop) : main.scrollTop
      pendingLeaveScroll = scroll
      if (!isTransitioning) pageScrollMap[from.path] = scroll
      pendingEnterScroll = pageScrollMap[to.path] ?? 0
    }
  }
  return true
})

/** 统一清理过渡态 */
function _cleanupTransition() {
  if (transitionSafetyTimer) { clearTimeout(transitionSafetyTimer); transitionSafetyTimer = null }
  const main = document.querySelector('.main-content')
  if (!main) return
  const targetScroll = pageScrollMap[route.path] ?? 0
  const capturedSeq = transitionSeq
  main.classList.remove('page-transitioning')
  main.style.removeProperty('--leave-scroll')
  main.style.removeProperty('--enter-scroll')
  // 优先同步恢复滚动：确保内容高度已足够（否则 scrollTop 会被 clamp 到 0，导致位置丢失）。
  // 首页有异步内容渲染时高度可能不足，则延迟到下一帧重试。
  if (main.scrollHeight > targetScroll) {
    main.scrollTop = targetScroll
  } else {
    requestAnimationFrame(() => {
      // 若期间又触发了新过渡（seq 变化），跳过本次恢复，由新过渡完成后统一恢复
      if (transitionSeq === capturedSeq) {
        main.scrollTop = targetScroll
      }
    })
  }
  pendingLeaveScroll = 0
  pendingEnterScroll = 0
}

/**
 * leave 过渡开始：设置 CSS 变量，锁定 overflow，scrollTop 归零。
 */
function onPageBeforeLeave() {
  const main = document.querySelector('.main-content')
  if (!main) return

  const seq = ++transitionSeq
  if (transitionSafetyTimer) { clearTimeout(transitionSafetyTimer); transitionSafetyTimer = null }

  main.classList.add('page-transitioning')
  main.style.setProperty('--leave-scroll', `${pendingLeaveScroll}px`)
  main.style.setProperty('--enter-scroll', `${pendingEnterScroll}px`)
  main.scrollTop = 0

  const spacer = document.getElementById('page-transition-spacer')
  if (spacer) spacer.remove()

  // 兜底：800ms 后强制清理，防止 @after-enter 因取消/中断永不触发
  const capturedSeq = seq
  transitionSafetyTimer = setTimeout(() => {
    if (transitionSeq === capturedSeq) _cleanupTransition()
  }, 800)
}

/**
 * enter 过渡完成：恢复目标页 scrollTop，清理过渡态。
 * 快速切换时旧过渡的 after-enter 可能晚到，延迟一帧再检查 seq：
 * 若期间又有新过渡开始（seq 变化），跳过本次清理，由最后一次过渡负责恢复。
 */
function onPageAfterEnter() {
  const seqAtEnter = transitionSeq
  requestAnimationFrame(() => {
    if (transitionSeq === seqAtEnter) {
      _cleanupTransition()
    }
  })
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
  position: relative; /* 供隐藏模式侧边栏/热区做绝对定位 */
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
  transition: margin-left 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.main-content.page-transitioning {
  overflow: hidden;
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
/* absolute 子元素相对 .main-content 滚动视口定位，不随 scrollTop 移动。
   首页等在 main-content 上滚动的页面，离开时用 top 负向偏移复现滚后视觉位置；
   音乐库等页面 main-content 几乎不滚动（--leave-scroll ≈ 0），故不受影响。 */
.page-enter-active {
  animation: page-enter 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0) both;
  position: absolute;
  top: calc(24px - var(--enter-scroll, 0px));
  left: 32px;
  right: 32px;
}
.page-leave-active {
  animation: page-leave 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0) both;
  position: absolute;
  top: calc(24px - var(--leave-scroll, 0px));
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
