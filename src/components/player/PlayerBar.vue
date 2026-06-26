<template>
  <div class="player-bar" @mouseenter="hovered = true" @mouseleave="hovered = false" :class="{ 'cover-hidden': panelOpen, 'text-shifted': textShifted, 'panel-active': panelFading }">
    <!-- 顶部进度条（全宽） -->
    <div class="progress-top" ref="progressRef"
         @mousedown="onProgressMouseDown"
         @mouseenter="progressHovered = true" @mouseleave="progressHovered = false">
      <div class="progress-top__bg" :style="{ transform: 'scaleX(' + (displayProgress / 100) + ')' }"></div>
      <div class="progress-top__time progress-top__time--current" v-show="progressHovered">
        {{ formatDuration(displayCurrentTime) }}
      </div>
      <div class="progress-top__time progress-top__time--total" v-show="progressHovered">
        {{ formatDuration(duration) }}
      </div>
    </div>

    <div class="player-bar__inner">
      <!-- 左侧：封面 + 歌名歌手 -->
      <div class="player-bar__left" v-ripple @click="toggleNowPlaying" title="点击查看歌词">
        <div class="now-playing">
          <img v-if="currentTrack?.cover" :src="currentTrack.cover" class="cover" ref="coverRef" />
          <div v-else class="cover cover--empty" ref="coverRef">
            <el-icon size="22"><Headset /></el-icon>
          </div>
          <Transition :name="infoAnimName">
            <div class="info" :key="currentTrack?.path">
              <div class="info__title">{{ currentTrack?.title || '未选择歌曲' }}</div>
              <div class="info__artist">{{ currentTrack?.artist || '' }}</div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- 中间：控制按钮（hover 可见） -->
      <div class="player-bar__center">
        <transition name="fade">
          <div class="controls" v-show="hovered">
            <button class="ctrl-btn" :class="{ active: playMode !== 'sequential' }" @click="player.togglePlayMode" :title="playModeLabel">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <template v-if="playMode === 'sequential'">
                  <path d="M2 3h2v10H2V3zm4 0h8v2H6V3zm0 4h6v2H6V7zm0 4h8v2H6v-2z"/>
                </template>
                <template v-else-if="playMode === 'repeat-one'">
                  <path d="M8 2a6 6 0 100 12A6 6 0 008 2zM6.5 9.5V7h2v2.5h1.5V7a1 1 0 00-1-1h-2a1 1 0 00-1 1v2.5h.5zm1.5 1a.75.75 0 110-1.5.75.75 0 010 1.5z"/>
                </template>
                <template v-else-if="playMode === 'shuffle'">
                  <path d="M11 2l3 3-3 3V6H8.5C7.12 6 6 7.12 6 8.5V9H5v-.5C5 6.57 6.57 5 8.5 5H11V2zM5 14l-3-3 3-3v2h2.5c.68 0 1.3-.19 1.83-.52L7.66 8.17A4.48 4.48 0 007.5 8C6.57 7.19 5.34 7 4.5 7H3v1h1.5c.69 0 1.67.07 2.33.62.28.23.5.5.5.88 0 .38-.22.65-.5.88C6.17 10.93 5.19 11 4.5 11H3v1h1.5c.84 0 2.07-.19 2.83-.83A3.5 3.5 0 009.5 10H11v2z"/>
                </template>
                <template v-else>
                  <path d="M2 12l2-2 2 2 1-1-2-2 2-2-1-1-2 2-2-2-1 1 2 2-2 2 1 1zm6-6h6v2H8V6zm0 4h4v2H8v-2z"/>
                </template>
              </svg>
            </button>
            <button class="ctrl-btn" :disabled="!hasPrev" @click="player.prev">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
              </svg>
            </button>
            <button class="ctrl-btn ctrl-btn--play" @click="player.togglePlay">
              <svg v-if="isPlaying" width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
              </svg>
              <svg v-else width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
            </button>
            <button class="ctrl-btn" :disabled="!hasNext" @click="player.next">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16 18h2V6h-2zm-11-7l8.5 6V6z"/>
              </svg>
            </button>
            <button class="ctrl-btn" :class="{ active: showQueue }" @click="showQueue = !showQueue" title="播放列表">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 14h8v2H3v-2zm10 0h8v6h-8v-6zm2 2h4v2h-4v-2z"/>
              </svg>
              <span class="queue-count" v-if="queue.length">{{ queue.length }}</span>
            </button>
            <button class="ctrl-btn" :class="{ active: showDesktopLyrics }" @click="player.toggleDesktopLyrics" :title="showDesktopLyrics ? '关闭桌面歌词' : '打开桌面歌词'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 14h8v2H3v-2zm10 0h2v2h-2v-2zm4-4h2v8h-2v-8z"/>
              </svg>
            </button>
          </div>
        </transition>
      </div>

      <!-- 右侧：音量按钮 + 弹出面板（hover 可见） -->
      <div class="player-bar__right">
        <transition name="fade">
          <div class="volume-area" v-show="hovered">
            <div class="volume-btn" @click="showVolumePop = !showVolumePop" ref="volumeBtnRef">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <template v-if="isMuted || volume === 0">
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.47 4.47 0 002.5-3.5zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                  <line x1="2" y1="2" x2="22" y2="22" stroke="currentColor" stroke-width="2"/>
                </template>
                <template v-else-if="volume < 0.5">
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.47 4.47 0 002.5-3.5z"/>
                </template>
                <template v-else>
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.47 4.47 0 002.5-3.5zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                </template>
              </svg>
              <span class="volume-btn__text">{{ Math.round(volume * 100) }}</span>
            </div>

            <!-- 音量弹出面板 -->
            <transition name="volume-pop">
              <div v-if="showVolumePop" class="volume-pop" @click.stop>
                <div class="volume-pop__slider" :class="{ dragging: isDraggingVolume }" ref="volumeRef" @mousedown="onVolumeMouseDown">
                  <div class="volume-pop__track">
                    <div class="volume-pop__fill" :style="{ transform: 'scaleY(' + displayVolume + ')' }"></div>
                    <div class="volume-pop__thumb" :style="{ bottom: (displayVolume * 100) + '%' }"></div>
                  </div>
                </div>
                <p class="volume-pop__val">{{ Math.round(volume * 100) }}%</p>
              </div>
            </transition>
          </div>
        </transition>
      </div>
    </div>

    <!-- 播放列表侧边抽屉 -->
    <QueuePanel :visible="showQueue" @close="showQueue = false" />
  </div>
</template>

<script setup>
import { ref, computed, inject, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { formatDuration } from '@/utils/format'
import QueuePanel from '@/components/player/QueuePanel.vue'

const props = defineProps({
  panelOpen: { type: Boolean, default: false },
  panelFading: { type: Boolean, default: false },
  textShifted: { type: Boolean, default: false }
})
const toggleNowPlaying = inject('toggleNowPlaying')
const player = usePlayerStore()
const { currentTrack, isPlaying, currentTime, duration, volume, isMuted,
        playMode, progress, queue, hasNext, hasPrev, showDesktopLyrics, songChangeDirection } = storeToRefs(player)

const hovered = ref(false)
const progressHovered = ref(false)
const showQueue = ref(false)
const showVolumePop = ref(false)
const progressRef = ref(null)
const volumeRef = ref(null)
const volumeBtnRef = ref(null)
const coverRef = ref(null)

// 歌曲信息滚动动画方向
const infoAnimDir = ref(null)
const infoAnimName = computed(() => {
  if (!infoAnimDir.value) return 'info-none'
  return `info-${infoAnimDir.value}`
})
watch(songChangeDirection, (dir) => {
  if (dir) {
    infoAnimDir.value = dir
    setTimeout(() => { infoAnimDir.value = null }, 650)
  }
})

defineExpose({ coverEl: coverRef, showQueue })

// 拖拽中的本地即时视觉值
const isDraggingProgress = ref(false)
const isDraggingVolume = ref(false)
const dragProgress = ref(0)
const dragVolume = ref(0.7)

// 拖拽时用本地值即时响应，否则用 store 值
const displayProgress = computed(() => isDraggingProgress.value ? dragProgress.value : progress.value)
const displayVolume = computed(() => isDraggingVolume.value ? dragVolume.value : volume.value)

// 拖拽时显示拖拽位置对应的时间
const displayCurrentTime = computed(() => {
  if (isDraggingProgress.value && duration.value > 0) {
    return (dragProgress.value / 100) * duration.value
  }
  return currentTime.value
})

const playModeLabel = computed(() => {
  const map = { sequential: '顺序播放', 'repeat-one': '单曲循环', shuffle: '随机播放', repeat: '列表循环' }
  return map[playMode.value]
})

// 点击外部关闭音量弹窗
function handleClickOutside(e) {
  if (volumeBtnRef.value && !volumeBtnRef.value.contains(e.target) && volumeRef.value && !volumeRef.value.contains(e.target)) {
    showVolumePop.value = false
  }
}
watch(showVolumePop, (val) => {
  if (val) {
    document.addEventListener('click', handleClickOutside)
  } else {
    document.removeEventListener('click', handleClickOutside)
  }
})

// ===== 进度条拖拽（本地即时视觉） =====
function calcProgress(e) {
  const rect = progressRef.value.getBoundingClientRect()
  return Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
}

function onProgressMouseDown(e) {
  isDraggingProgress.value = true
  dragProgress.value = calcProgress(e)
  document.addEventListener('mousemove', onProgressDrag)
  document.addEventListener('mouseup', onProgressMouseUp)
}

function onProgressDrag(e) {
  dragProgress.value = calcProgress(e)
}

function onProgressMouseUp() {
  player.seek(dragProgress.value)
  isDraggingProgress.value = false
  document.removeEventListener('mousemove', onProgressDrag)
  document.removeEventListener('mouseup', onProgressMouseUp)
}

// ===== 音量拖拽（本地即时视觉） =====
function calcVolume(e) {
  if (!volumeRef.value) return 0.7
  const rect = volumeRef.value.getBoundingClientRect()
  return Math.max(0, Math.min(1, 1 - ((e.clientY - rect.top) / rect.height)))
}

function onVolumeMouseDown(e) {
  isDraggingVolume.value = true
  dragVolume.value = calcVolume(e)
  document.addEventListener('mousemove', onVolumeDrag)
  document.addEventListener('mouseup', onVolumeMouseUp)
}

function onVolumeDrag(e) {
  dragVolume.value = calcVolume(e)
  player.setVolume(dragVolume.value)
}

function onVolumeMouseUp() {
  player.setVolume(dragVolume.value)
  isDraggingVolume.value = false
  document.removeEventListener('mousemove', onVolumeDrag)
  document.removeEventListener('mouseup', onVolumeMouseUp)
}
</script>

<style scoped>
.player-bar {
  position: relative;
  height: 72px;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  z-index: 10;
  transition: background 0.4s, border-top-color 0.4s;
}

/* ===== 顶部全宽进度条 ===== */
.progress-top {
  position: absolute;
  top: -2px;
  left: 0;
  right: 0;
  height: 4px;
  cursor: pointer;
  z-index: 2;
  transition: transform 0.15s, background 0.4s;
  background: var(--bg-tertiary);
  transform-origin: top;
}
.progress-top:hover {
  transform: scaleY(2);
}
.progress-top:hover .progress-top__time {
  transform: scaleY(0.5);
}
.progress-top__bg {
  width: 100%;
  height: 100%;
  background: var(--accent-color);
  border-radius: 0 2px 2px 0;
  transform-origin: left;
  transition: background 0.4s;
}
.progress-top__time {
  position: absolute;
  bottom: 6px;
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  pointer-events: none;
  text-shadow: 0 1px 3px rgba(0,0,0,0.6);
  transition: color 0.4s;
}
.progress-top__time--current { left: 8px; }
.progress-top__time--total { right: 8px; }

/* ===== 内部主体（三栏 Grid 布局） ===== */
.player-bar__inner {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 20px;
  gap: 16px;
  transition: color 0.4s;
}

/* 左侧：封面 + 歌名（在 grid 单元格内限制宽度，文字溢出省略） */
.player-bar__left {
  min-width: 0;
  display: flex;
  align-items: center;
}
.now-playing {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  min-width: 0;
  width: 100%;
  position: relative;
}
.cover {
  width: 48px; height: 48px;
  border-radius: 5px; object-fit: cover; flex-shrink: 0;
}
.player-bar.cover-hidden .cover {
  visibility: hidden;
}
.cover--empty {
  background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.info {
  flex: 1; min-width: 0;
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.player-bar.text-shifted .info {
  transform: translateX(-58px);
}
.info__title { font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color 0.4s; }
.info__artist { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color 0.4s; }

/* 中间：控制按钮始终居中 */
.player-bar__center {
  display: flex;
  align-items: center;
  justify-content: center;
}
.controls { display: flex; align-items: center; gap: 10px; }
.ctrl-btn {
  background: none; border: none; color: var(--text-secondary);
  cursor: pointer; padding: 6px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  transition: color 0.4s, background 0.4s; position: relative;
}
.ctrl-btn:hover { color: var(--text-primary); background: var(--hover-bg-strong); }
.ctrl-btn:disabled { opacity: 0.35; cursor: default; background: none; }
.ctrl-btn.active { color: var(--accent-color); }
.ctrl-btn--play {
  background: var(--accent-bg); color: var(--accent-color); padding: 6px;
  transition: background 0.4s, color 0.4s;
}
.ctrl-btn--play:hover { background: var(--accent-color); color: #fff; }
.queue-count {
  position: absolute; top: -2px; right: -2px;
  font-size: 10px; background: var(--accent-color); color: #fff;
  border-radius: 50%; width: 16px; height: 16px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.4s, color 0.4s;
}

/* 右侧：音量控件，右对齐 */
.player-bar__right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.volume-area {
  display: flex;
  align-items: center;
  position: relative;
}

/* 音量按钮 */
.volume-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: color 0.4s, background 0.4s;
  position: relative;
}
.volume-btn:hover { color: var(--text-primary); background: var(--hover-bg-strong); }
.volume-btn__text {
  font-size: 13px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  min-width: 28px;
}

/* 音量弹出面板 */
.volume-pop {
  position: absolute;
  bottom: 60px;
  right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 14px 10px 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  transition: background 0.4s, border-color 0.4s;
}
.volume-pop__slider {
  width: 24px;
  height: 120px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.volume-pop__track {
  width: 4px;
  height: 100%;
  background: var(--bg-tertiary);
  border-radius: 2px;
  position: relative;
  overflow: visible;
}
.volume-pop__fill {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--accent-color);
  border-radius: 2px;
  transform-origin: bottom;
}
.volume-pop__thumb {
  position: absolute;
  left: 50%;
  transform: translate(-50%, 50%);
  width: 12px;
  height: 12px;
  background: var(--accent-color);
  border: 2px solid #fff;
  border-radius: 50%;
  transition: bottom 0.08s;
}
.volume-pop__slider.dragging .volume-pop__thumb { transition: none; }
.volume-pop__val {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  font-variant-numeric: tabular-nums;
  transition: color 0.4s;
}

/* ===== 过渡动画 ===== */
.fade-enter-active {
  transition: opacity 0.25s ease;
}
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.volume-pop-enter-active {
  transition: opacity 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94),
              transform 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
.volume-pop-leave-active {
  transition: opacity 0.15s cubic-bezier(0.25, 0.46, 0.45, 0.94),
              transform 0.15s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
.volume-pop-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
.volume-pop-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
/* ===== 全屏播放面板激活时 ===== */
.player-bar.panel-active {
  background: transparent;
  border-top-color: transparent;
}
.player-bar.panel-active .player-bar__inner { color: #fff; }
.player-bar.panel-active .info__title { color: #fff; }
.player-bar.panel-active .info__artist { color: rgba(255, 255, 255, 0.7); }
.player-bar.panel-active .ctrl-btn { color: rgba(255, 255, 255, 0.8); }
.player-bar.panel-active .ctrl-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.15); }
.player-bar.panel-active .ctrl-btn:disabled { color: rgba(255, 255, 255, 0.3); }
.player-bar.panel-active .ctrl-btn--play { background: rgba(255, 255, 255, 0.15); color: #fff; }
.player-bar.panel-active .ctrl-btn--play:hover { background: #fff; color: var(--bg-primary); }
.player-bar.panel-active .queue-count { background: #fff; color: var(--bg-primary); }
.player-bar.panel-active .progress-top { background: rgba(255, 255, 255, 0.15); }
.player-bar.panel-active .progress-top__bg { background: #fff; }
.player-bar.panel-active .progress-top__time { color: rgba(255, 255, 255, 0.8); }
.player-bar.panel-active .volume-btn { color: rgba(255, 255, 255, 0.8); }
.player-bar.panel-active .volume-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.15); }
.player-bar.panel-active .volume-pop {
  background: rgba(20, 20, 20, 0.85);
  backdrop-filter: blur(12px);
  border-color: rgba(255, 255, 255, 0.1);
}
.player-bar.panel-active .volume-pop__val { color: rgba(255, 255, 255, 0.8); }

/* ===== 切歌时歌曲信息方向感知滑入动画 ===== */
/* 出入同时执行：新信息从对应方向滑入（在旧信息上方），旧信息仅渐隐 */
.info-next-leave-active,
.info-prev-leave-active {
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  z-index: 0;
}
.info-next-enter-active,
.info-prev-enter-active {
  position: relative;
  z-index: 1;
}

/* 下一曲：旧信息渐隐 | 新信息从右侧 60px 滑入 + 渐显 */
.info-next-leave-active {
  transition: opacity 0.42s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.info-next-leave-to { opacity: 0; }
.info-next-enter-active {
  transition: transform 0.42s cubic-bezier(0.2, 0.9, 0.3, 1.0) !important,
              opacity 0.42s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.info-next-enter-from { transform: translateX(60px) !important; opacity: 0; }

/* 上一曲：旧信息渐隐 | 新信息从左侧 -60px 滑入 + 渐显 */
.info-prev-leave-active {
  transition: opacity 0.42s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.info-prev-leave-to { opacity: 0; }
.info-prev-enter-active {
  transition: transform 0.42s cubic-bezier(0.2, 0.9, 0.3, 1.0) !important,
              opacity 0.42s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.info-prev-enter-from { transform: translateX(-60px) !important; opacity: 0; }

/* 无动画（初始状态） */
.info-none-enter-active,
.info-none-leave-active {
  transition: none;
}
</style>
