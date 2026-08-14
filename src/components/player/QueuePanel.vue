<template>
  <teleport to="body">
    <transition name="queue-drawer" :duration="600" @enter="onPanelEnter" @before-leave="ready = false">
      <div v-if="visible" class="queue-drawer-overlay" @click.self="$emit('close')">
        <div class="queue-card">
          <div class="queue-card__header">
            <span class="queue-card__title">播放列表</span>
            <span class="queue-card__count">{{ queue.length }} 首</span>
            <div class="queue-card__actions">
              <el-button size="small" text @click="player.clearQueue">清空</el-button>
              <button class="queue-close" v-ripple @click="$emit('close')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
            </div>
          </div>
          <div v-bind="containerProps" class="queue-card__list" :class="{ 'queue-dragging': dragIndex >= 0 }" data-queue-container>
            <template v-if="ready">
              <div v-bind="wrapperProps">
                <div
                  v-for="{ data: track, index } in virtualList"
                  :key="track.path"
                  class="queue-item"
                  :class="{ active: index === currentIndex, 'queue-item--dragging': index === dragIndex }"
                  :data-index="index"
                  :style="dragIndex >= 0 ? { transform: `translateY(${dragOffset(index)}px)` } : {}"
                  v-ripple
                  @click="player.play(index)"
                  @contextmenu.prevent="showContextMenu($event, track)"
                >
                  <span class="queue-item__drag" title="拖拽排序" @mousedown.prevent.stop="onDragStart(index, $event)" @click.stop>
                    <svg width="10" height="14" viewBox="0 0 10 16" fill="currentColor">
                      <circle cx="2.5" cy="2" r="1.4"/><circle cx="7.5" cy="2" r="1.4"/>
                      <circle cx="2.5" cy="8" r="1.4"/><circle cx="7.5" cy="8" r="1.4"/>
                      <circle cx="2.5" cy="14" r="1.4"/><circle cx="7.5" cy="14" r="1.4"/>
                    </svg>
                  </span>
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
                    <div class="queue-item__title">
                      <span v-if="track.source === 'cloud'" class="queue-item__src-tag" title="云端歌曲">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>
                      </span>
                      {{ track.title }}
                    </div>
                    <div class="queue-item__artist">{{ track.artist.split('/').map(s => s.trim()).join(' / ') }}</div>
                  </div>
                  <button v-if="index !== currentIndex" class="queue-item__insert" v-ripple @click.stop="player.moveToNext(index)" title="插播至下一曲">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M6 6l8 6-8 6z"/>
                      <rect x="16.5" y="6" width="2.2" height="12" rx="1"/>
                    </svg>
                  </button>
                  <button class="queue-item__remove" v-ripple @click.stop="player.removeFromQueue(index)" title="移除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                  </button>
                  <span class="queue-item__time">{{ formatDuration(track.duration) }}</span>
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
    <ContextMenu
      :visible="ctxMenu.visible"
      :x="ctxMenu.x"
      :y="ctxMenu.y"
      :items="queueMenuItems"
      :submenu="ctxMenu.submenu"
      :animated="true"
      @close="hideContextMenu"
      @action="onQueueCtxAction"
      @sub-action="onQueueSubAction"
      @hover-submenu="openArtistSubmenu"
    />
    <div v-if="dragIndex >= 0" class="queue-drag-ghost" :style="{ left: dragPos.x + 'px', top: dragPos.y + 'px' }">
      <LazyCover v-if="dragTrack?.cover" :src="dragTrack.cover" class="queue-drag-ghost__cover" />
      <span class="queue-drag-ghost__title">{{ dragTrack?.title }}</span>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useVirtualList } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { formatDuration } from '@/utils/format'
import LazyCover from '@/components/LazyCover.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'
import { useTrackList } from '@/composables/useTrackList'
import { closeOverlays } from '@/utils/overlays'

defineProps({ visible: { type: Boolean, default: false } })
defineEmits(['close'])

const player = usePlayerStore()
const router = useRouter()
const { queue, currentIndex, isPlaying } = storeToRefs(player)

// 等滑入动画播完再渲染列表，避免虚拟滚动 layout 打断 CSS 动画
const ready = ref(false)

// 拖拽排序（自定义鼠标拖拽：悬浮幽灵 + 让位动画）
const dragIndex = ref(-1)
const dragOverIndex = ref(-1)
const dragPos = ref({ x: 0, y: 0 })
const dragTrack = computed(() => dragIndex.value >= 0 ? queue.value[dragIndex.value] : null)

// 让位偏移：把 from..to 之间的项整体平移一格，腾出目标位置
function dragOffset(index) {
  const from = dragIndex.value
  const to = dragOverIndex.value
  if (from < 0 || to < 0 || from === to) return 0
  if (from < to) {
    return (index > from && index <= to) ? -56 : 0
  }
  return (index >= to && index < from) ? 56 : 0
}

function onDragStart(index, e) {
  if (index < 0) return
  dragIndex.value = index
  dragOverIndex.value = index
  dragPos.value = { x: e.clientX, y: e.clientY }
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}
function onDragMove(e) {
  dragPos.value = { x: e.clientX, y: e.clientY }
  const item = document.elementFromPoint(e.clientX, e.clientY)?.closest?.('.queue-item')
  if (item && item.dataset.index != null) {
    const idx = Number(item.dataset.index)
    if (!Number.isNaN(idx) && idx !== dragOverIndex.value) dragOverIndex.value = idx
  }
}
function onDragEnd() {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  if (dragOverIndex.value >= 0 && dragOverIndex.value !== dragIndex.value) {
    player.moveInQueue(dragIndex.value, dragOverIndex.value)
  }
  dragIndex.value = -1
  dragOverIndex.value = -1
}
onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
})

// 右键菜单（复用主列表交互；除“添加到歌单”外，其余动作执行后自动关闭队列）
const { ctxMenu, showContextMenu, hideContextMenu, openArtistSubmenu, createCtxHandler, createSubActionHandler, showAddPlaylistDialog } = useTrackList()
const ctxHandler = createCtxHandler(player, router)
const subActionHandler = createSubActionHandler(router)
const queueMenuItems = computed(() => {
  const names = (ctxMenu.value.track?.artist || '').split('/').map(s => s.trim()).filter(Boolean)
  return [
    { label: '添加到歌单', action: 'addToPlaylist' },
    '-',
    { label: '跳转到专辑', action: 'goAlbum' },
    { label: '跳转到艺术家', action: 'goArtist', hasSubmenu: names.length > 1 },
    '-',
    { label: '音轨信息', action: 'trackInfo' }
  ]
})
function onQueueCtxAction(action) {
  const result = ctxHandler(action)
  if (result === 'navigate') {
    closeOverlays()
    return
  }
  if (result === 'submenu') {
    return
  }
  if (action === 'addToPlaylist') showAddPlaylistDialog(ctxMenu.value.track)
}
function onQueueSubAction(item) {
  subActionHandler(item)
  closeOverlays()
}

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
  right: 10px; top: 46px; bottom: 82px;
  width: 420px; max-width: 100vw;
  background:
    radial-gradient(120% 80% at 20% 0%, var(--glass-specular), transparent 55%),
    var(--glass-bg-strong);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-radius: 14px;
  border: 1px solid var(--glass-border);
  display: flex; flex-direction: column;
  box-shadow: inset 0 1px 0 var(--glass-highlight), var(--glass-shadow);
  overflow: hidden;
}
.queue-card__header {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border-color);
  user-select: none;
}
.queue-card__title { font-size: 15px; font-weight: 600; }
.queue-card__count { font-size: 12px; color: var(--text-secondary); font-weight: 400; }
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
/* 拖拽中：列表项平滑“让位” */
.queue-card__list.queue-dragging .queue-item {
  transition: background 0.15s, transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

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
  font-size: 12px; color: var(--text-secondary);
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
  display: flex; align-items: center; gap: 4px;
}
.queue-item__src-tag {
  color: var(--text-tertiary); flex-shrink: 0; display: flex;
}
.queue-item__artist {
  font-size: 11px; color: var(--text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-top: 2px;
}
.queue-item__time {
  font-size: 11px; color: var(--text-secondary);
  font-variant-numeric: tabular-nums; flex-shrink: 0;
}

.queue-item__drag {
  color: var(--text-tertiary);
  cursor: grab;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  opacity: 0;
  transition: opacity 0.15s;
}
.queue-item__drag:active { cursor: grabbing; }
.queue-item:hover .queue-item__drag { opacity: 1; }

.queue-item__insert {
  background: none; border: none; color: var(--text-secondary);
  cursor: pointer; padding: 4px; border-radius: 4px;
  display: flex; align-items: center;
  flex-shrink: 0;
  opacity: 0; transition: opacity 0.15s;
}
.queue-item:hover .queue-item__insert { opacity: 1; }
.queue-item__insert:hover { background: var(--hover-bg-strong); color: var(--accent-color); }

.queue-item--dragging { opacity: 0; pointer-events: none; }

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

/* 拖拽悬浮幽灵：跟随鼠标的整行缩略 */
.queue-drag-ghost {
  position: fixed;
  z-index: 1003;
  pointer-events: none;
  transform: translate(10px, -28px);
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 300px;
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}
.queue-drag-ghost__cover {
  width: 28px; height: 28px; border-radius: 4px; object-fit: cover; flex-shrink: 0;
}
.queue-drag-ghost__title {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== 动画 ===== */
/* 玻璃壳用 right 做布局位移，不碰 transform，backdrop-filter 全程有效 */
.queue-drawer-enter-active .queue-card {
  animation: qd-slide-in-right 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) forwards;
}
.queue-drawer-leave-active .queue-card {
  animation: qd-slide-out-right 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) forwards;
}

@keyframes qd-slide-in-right {
  from { right: -440px; }
  to { right: 10px; }
}
@keyframes qd-slide-out-right {
  from { right: 10px; }
  to { right: -440px; }
}
</style>
