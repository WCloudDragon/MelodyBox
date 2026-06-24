<template>
  <teleport to="body">
    <transition name="queue-drawer" @enter="onPanelEnter" @before-leave="ready = false">
      <div v-if="visible" class="queue-drawer-overlay" @click.self="$emit('close')">
        <div class="queue-card">
          <div class="queue-card__header">
            <span class="queue-card__title">播放列表</span>
            <span class="queue-card__count">{{ queue.length }} 首</span>
            <div class="queue-card__actions">
              <el-button size="small" text @click="player.clearQueue">清空</el-button>
              <button class="queue-close" @click="$emit('close')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
            </div>
          </div>
          <div v-bind="containerProps" class="queue-card__list" data-queue-container>
            <template v-if="ready">
              <div v-bind="wrapperProps">
                <div
                  v-for="{ data: track, index } in virtualList"
                  :key="track.path"
                  class="queue-item"
                  :class="{ active: index === currentIndex }"
                  @click="player.play(index)"
                >
                  <div class="queue-item__index">
                    <span v-if="index === currentIndex && isPlaying" class="queue-item__playing">
                      <span class="bar"></span><span class="bar"></span><span class="bar"></span>
                    </span>
                    <span v-else>{{ index + 1 }}</span>
                  </div>
                  <LazyCover v-if="track.cover" :src="track.cover" class="queue-item__cover" :thumb-size="80" />
                  <div v-else class="queue-item__cover queue-item__cover--empty">
                    <el-icon size="16"><Headset /></el-icon>
                  </div>
                  <div class="queue-item__info">
                    <div class="queue-item__title">{{ track.title }}</div>
                    <div class="queue-item__artist">{{ track.artist.split('/').map(s => s.trim()).join(' / ') }}</div>
                  </div>
                  <span class="queue-item__time">{{ formatDuration(track.duration) }}</span>
                  <button class="queue-item__remove" @click.stop="player.removeFromQueue(index)" title="移除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                  </button>
                </div>
              </div>
            </template>
            <div v-if="queue.length === 0" class="queue-empty">
              播放列表为空
            </div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { useVirtualList } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { formatDuration } from '@/utils/format'
import LazyCover from '@/components/LazyCover.vue'

defineProps({ visible: { type: Boolean, default: false } })
defineEmits(['close'])

const player = usePlayerStore()
const { queue, currentIndex, isPlaying } = storeToRefs(player)

// 等滑入动画播完再渲染列表，避免虚拟滚动 layout 打断 CSS 动画
const ready = ref(false)

// 虚拟滚动：仅渲染可见区域 + overscan
const { list: virtualList, containerProps, wrapperProps } = useVirtualList(
  queue,
  { itemHeight: 56, overscan: 10 }
)

// 打开面板时，自动滚动到正在播放歌曲的列表中心
  function scrollToCurrentCenter() {
    // 双 nextTick：T1 等 ready→v-if 渲染 wrapper，T2 等虚拟滚动完成 layout
    nextTick(() => {
      nextTick(() => {
        const container = document.querySelector('[data-queue-container]')
        if (!container || queue.value.length === 0) return
        if (currentIndex.value < 0) return
        const targetTop = currentIndex.value * 56 - container.clientHeight / 2 + 28
        container.scrollTop = Math.max(0, Math.min(targetTop, queue.value.length * 56 - container.clientHeight))
      })
    })
  }

function onPanelEnter() {
  ready.value = true
  scrollToCurrentCenter()
}
</script>

<style scoped>
.queue-drawer-overlay {
  position: fixed; inset: 0; z-index: 1002;
  /* 无压暗背景，仅作点击关闭层 */
  pointer-events: none;
}
.queue-drawer-overlay > .queue-card {
  pointer-events: auto;
}

.queue-card {
  position: absolute;
  right: 10px; top: 46px; bottom: 10px;
  width: 420px; max-width: 100vw;
  background: var(--bg-primary);
  border-radius: 14px;
  border: 1px solid var(--border-color);
  display: flex; flex-direction: column;
  box-shadow: 0 8px 40px rgba(0,0,0,0.35);
}
.queue-card__header {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border-color);
  user-select: none;
}
.queue-card__title { font-size: 15px; font-weight: 600; }
.queue-card__count { font-size: 12px; color: var(--text-tertiary); font-weight: 400; }
.queue-card__actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.queue-close {
  background: none; border: none; color: var(--text-tertiary);
  cursor: pointer; padding: 4px; border-radius: 4px;
  display: flex;
}
.queue-close:hover { color: var(--text-primary); background: var(--hover-bg-strong); }

.queue-card__list {
  flex: 1; overflow-y: auto;
  padding: 4px 12px;
}
.queue-card__list::-webkit-scrollbar { width: 4px; }
.queue-card__list::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }

.queue-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px; border-radius: 8px;
  height: 56px; box-sizing: border-box; flex-shrink: 0;
  cursor: pointer; transition: background 0.15s;
}
.queue-item:hover { background: var(--hover-bg); }
.queue-item.active {
  background: var(--accent-bg);
}
.queue-item.active .queue-item__title { color: var(--accent-color); }
.queue-item__index {
  width: 24px; text-align: center;
  font-size: 12px; color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.queue-item.active .queue-item__index { color: var(--accent-color); }
.queue-item__playing {
  display: flex; align-items: flex-end; justify-content: center;
  gap: 2px; height: 14px;
}
.queue-item__playing .bar {
  width: 3px; background: var(--accent-color);
  border-radius: 1px; animation: eq 0.8s ease-in-out infinite;
}
.queue-item__playing .bar:nth-child(1) { height: 8px; animation-delay: -0.3s; }
.queue-item__playing .bar:nth-child(2) { height: 14px; animation-delay: -0.15s; }
.queue-item__playing .bar:nth-child(3) { height: 10px; }
@keyframes eq {
  0%, 100% { height: 6px; }
  50% { height: 16px; }
}
.queue-item__cover {
  width: 40px; height: 40px; border-radius: 6px;
  object-fit: cover; flex-shrink: 0;
}
.queue-item__cover--empty {
  background: var(--hover-bg);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.queue-item__info { flex: 1; min-width: 0; }
.queue-item__title {
  font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.queue-item__artist {
  font-size: 11px; color: var(--text-tertiary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-top: 2px;
}
.queue-item__time {
  font-size: 11px; color: var(--text-tertiary);
  font-variant-numeric: tabular-nums; flex-shrink: 0;
}

.queue-item__remove {
  background: none; border: none; color: var(--text-tertiary);
  cursor: pointer; padding: 4px; border-radius: 4px;
  opacity: 0; transition: opacity 0.15s;
  flex-shrink: 0;
}
.queue-item:hover .queue-item__remove { opacity: 1; }
.queue-item__remove:hover { background: var(--hover-bg-strong); color: #e81123; }

.queue-empty {
  text-align: center; padding: 40px;
  color: var(--text-tertiary); font-size: 14px;
}

/* ===== 动画 ===== */
.queue-drawer-enter-active {
  animation: qd-fade-in 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) forwards;
}
.queue-drawer-leave-active {
  animation: qd-fade-out 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) forwards;
}
.queue-drawer-enter-active .queue-card {
  animation: qd-slide-in 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) forwards;
}
.queue-drawer-leave-active .queue-card {
  animation: qd-slide-out 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) forwards;
}

@keyframes qd-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes qd-fade-out {
  from { opacity: 1; }
  to { opacity: 0; }
}
@keyframes qd-slide-in {
  from { transform: translateX(calc(100% + 20px)); }
  to { transform: translateX(0); }
}
@keyframes qd-slide-out {
  from { transform: translateX(0); }
  to { transform: translateX(calc(100% + 20px)); }
}
</style>
