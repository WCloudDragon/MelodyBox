<template>
  <div class="title-bar" @dblclick="onMaximize">
    <div class="title-bar__brand">
      <svg class="title-bar__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
      </svg>
      <span class="title-bar__name">MelodyBox</span>
    </div>
    <div class="title-bar__drag"></div>
    <div class="title-bar__controls" :class="{ 'title-bar__controls--lyrics': lyricsVisible }">
      <button class="title-btn" @click="onFullscreen" :title="isFs ? '退出全屏' : '全屏'">
        <svg v-if="!isFs" width="12" height="12" viewBox="0 0 12 12">
          <polyline points="1,5 1,1 5,1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          <polyline points="7,1 11,1 11,5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          <polyline points="11,7 11,11 7,11" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          <polyline points="5,11 1,11 1,7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
        <svg v-else width="12" height="12" viewBox="0 0 12 12">
          <polyline points="11,5 7,5 7,1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          <polyline points="1,7 5,7 5,11" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
      </button>
      <button class="title-btn" @click="onMinimize" title="最小化">
        <svg width="12" height="12" viewBox="0 0 12 12"><rect y="5" width="12" height="1.5" fill="currentColor"/></svg>
      </button>
      <button class="title-btn" @click="onMaximize" title="最大化">
        <svg v-if="!isMax" width="12" height="12" viewBox="0 0 12 12">
          <rect x="1.5" y="1.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1.5"/>
        </svg>
        <svg v-else width="12" height="12" viewBox="0 0 12 12">
          <rect x="3" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1.5"/>
          <rect x="0" y="3" width="9" height="9" fill="var(--bg-secondary)" stroke="currentColor" stroke-width="1.5"/>
        </svg>
      </button>
      <button class="title-btn title-btn--close" @click="onClose" title="关闭">
        <svg width="12" height="12" viewBox="0 0 12 12">
          <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5"/>
          <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  lyricsVisible: { type: Boolean, default: false }
})

const isMax = ref(false)
const isFs = ref(false)

onMounted(() => {
  if (window.electronAPI) {
    window.electronAPI.isMaximized().then(v => isMax.value = v)
    window.electronAPI.onMaximizeChange(v => isMax.value = v)
    window.electronAPI.isFullscreen().then(v => isFs.value = v)
    window.electronAPI.onFullscreenChange(v => isFs.value = v)
  }
})

function onMinimize() { window.electronAPI?.minimize() }
function onMaximize() { window.electronAPI?.maximize() }
function onFullscreen() { window.electronAPI?.fullscreen() }
function onClose() { window.electronAPI?.close() }
</script>

<style scoped>
.title-bar {
  display: flex;
  align-items: center;
  height: 36px;
  background: var(--bg-secondary);
  -webkit-app-region: drag;
  user-select: none;
  flex-shrink: 0;
}
.title-bar__brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 16px;
  -webkit-app-region: drag;
}
.title-bar__icon {
  color: var(--accent-color);
  flex-shrink: 0;
}
.title-bar__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.3px;
}
.title-bar__drag { flex: 1; }
.title-bar__controls {
  display: flex;
  position: fixed;
  top: 0;
  right: 0;
  z-index: 1001;
  -webkit-app-region: no-drag;
}
.title-btn {
  width: 46px;
  height: 36px;
  border: none;
  background: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.5s ease;
}
.title-btn:hover { background: var(--hover-bg-strong); color: var(--text-primary); }
.title-btn--close:hover { background: #e81123; color: #fff; }

/* 全屏歌词页打开时：按钮颜色与 np-close-btn 统一为白 */
.title-bar__controls--lyrics .title-btn {
  color: rgba(255,255,255,0.7);
  transition: background 0.15s, color 0.5s ease;
}
.title-bar__controls--lyrics .title-btn:hover {
  background: rgba(255,255,255,0.15);
  color: #fff;
}
.title-bar__controls--lyrics .title-btn--close:hover {
  background: #e81123;
  color: #fff;
}
</style>
