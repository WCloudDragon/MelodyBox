/**
 * 全局进度条 & Toast 状态管理
 * 支持同时最多 4 条，自动管理生命周期
 */
import { ref, computed } from 'vue'

const MAX_ITEMS = 4
const DONE_TTL = 4000   // 进度完成保留时间
const TOAST_TTL = 3000  // toast 保留时间

const items = ref([])

let _idSeq = 0

/** 添加进度项，返回 id */
export function addProgress(config) {
  const id = `p${++_idSeq}`
  const item = {
    id,
    type: config.type || 'generic',
    title: config.title || '',
    current: config.current ?? 0,
    total: config.total ?? 0,
    path: config.path || '',
    status: config.status || 'running',
    createdAt: Date.now()
  }
  items.value = [item, ...items.value].slice(0, MAX_ITEMS)
  return id
}

/** 添加 toast 通知（自动移除） */
export function addToast(message, level = 'success') {
  const id = `t${++_idSeq}`
  const item = {
    id,
    type: 'toast',
    title: message,
    current: 0, total: 0, path: '',
    status: level,  // success | warning | error | info
    createdAt: Date.now()
  }
  items.value = [item, ...items.value].slice(0, MAX_ITEMS)
  setTimeout(() => removeProgress(id), TOAST_TTL)
  return id
}

/** 更新进度项 */
export function updateProgress(id, updates) {
  const item = items.value.find(i => i.id === id)
  if (!item) return
  Object.assign(item, updates)
}

/** 标记完成（保持显示若干秒后自动移除） */
export function completeProgress(id, title) {
  const item = items.value.find(i => i.id === id)
  if (!item) return
  item.status = 'done'
  if (title) item.title = title
  setTimeout(() => removeProgress(id), DONE_TTL)
}

/** 标记错误 */
export function errorProgress(id, title) {
  const item = items.value.find(i => i.id === id)
  if (!item) return
  item.status = 'error'
  if (title) item.title = title
  setTimeout(() => removeProgress(id), DONE_TTL)
}

/** 移除一项 */
export function removeProgress(id) {
  items.value = items.value.filter(i => i.id !== id)
}

/** 清空全部 */
export function clearProgress() {
  items.value = []
}

/** 活跃项（供组件渲染） */
export const activeItems = computed(() => items.value)
