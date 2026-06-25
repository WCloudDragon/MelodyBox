<template>
  <TransitionGroup
    name="progress"
    tag="div"
    class="progress-panel"
    :style="panelStyle"
  >
    <div
      v-for="(item, index) in items"
      :key="item.id"
      class="progress-item"
      :class="itemClass(item)"
      :style="{ zIndex: index }"
    >
      <!-- header -->
      <div class="progress-item__header">
        <span class="progress-item__icon" :class="`icon--${item.status}`">
          <!-- done -->
          <svg v-if="item.status === 'done'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          <!-- success (toast) -->
          <svg v-else-if="item.status === 'success'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          <!-- error -->
          <svg v-else-if="item.status === 'error'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          <!-- warning -->
          <svg v-else-if="item.status === 'warning'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <!-- info -->
          <svg v-else-if="item.status === 'info'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <!-- running (spinner) -->
          <span v-else class="spinner"></span>
        </span>
        <span class="progress-item__title">{{ item.title }}</span>
        <span class="progress-item__count" v-if="item.status === 'running' && item.total > 0">
          {{ item.current }}/{{ item.total }}
        </span>
      </div>

      <!-- progress bar (only for progress items) -->
      <div class="progress-item__bar" v-if="item.type !== 'toast' && item.status === 'running' && item.total > 0">
        <div class="progress-item__fill" :style="{ width: (item.total > 0 ? Math.round(item.current / item.total * 100) : 0) + '%' }"></div>
      </div>

      <!-- file path (only for progress items) -->
      <div class="progress-item__path" v-if="item.type !== 'toast' && item.path && item.status === 'running'">
        {{ item.path }}
      </div>
    </div>
  </TransitionGroup>
</template>

<script setup>
import { computed } from 'vue'
import { activeItems } from '@/stores/progress'

const props = defineProps({
  queueOpen: { type: Boolean, default: false }
})

const items = computed(() => activeItems.value)

// 播放队列展开 → toast 区左移避让
const panelStyle = computed(() => ({
  right: props.queueOpen ? '442px' : '16px'
}))

function itemClass(item) {
  if (item.type === 'toast') return `is-${item.status}`
  if (item.status === 'done') return 'is-done'
  if (item.status === 'error') return 'is-error'
  return ''
}
</script>

<style scoped>
.progress-panel {
  position: fixed;
  bottom: 88px;
  right: 16px;
  z-index: 2000;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  pointer-events: none;
  max-width: 320px;
  width: 300px;
  /* 与 QueuePanel 一致的位移动画曲线 */
  transition: right 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

.progress-item {
  position: relative;
  background: var(--bg-primary, #1e1e2e);
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 12px;
  padding: 12px 14px;
  pointer-events: auto;
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.progress-item.is-done    { border-color: rgba(34,197,94,0.3); }
.progress-item.is-error   { border-color: rgba(239,68,68,0.3); }
.progress-item.is-success { border-color: rgba(34,197,94,0.3); }
.progress-item.is-warning { border-color: rgba(251,191,36,0.3); }
.progress-item.is-info    { border-color: rgba(99,102,241,0.3); }

.progress-item__header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-item__icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--accent-color, #6366f1);
}
.icon--done    { color: #22c55e; }
.icon--success { color: #22c55e; }
.icon--error   { color: #ef4444; }
.icon--warning { color: #fbbf24; }
.icon--info    { color: #6366f1; }

.progress-item__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.progress-item__count {
  font-size: 11px;
  color: var(--text-tertiary, #888);
  flex-shrink: 0;
}

.progress-item__bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
  margin: 6px 0 4px;
}
.progress-item__fill {
  height: 100%;
  background: var(--accent-color, #6366f1);
  border-radius: 2px;
  transition: width 0.3s ease;
}
.is-error .progress-item__fill { background: #ef4444; }

.progress-item__path {
  font-size: 11px;
  color: var(--text-tertiary, #888);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* spinner */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.15);
  border-top-color: var(--accent-color, #6366f1);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== 入场 / 退场动画 ===== */
/* 与 QueuePanel 使用相同的曲线：0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0) */
.progress-enter-active {
  transition: all 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.progress-leave-active {
  transition: all 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.progress-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.95);
}
.progress-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.95);
}
.progress-move {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
</style>
