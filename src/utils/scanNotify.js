/**
 * 扫描/缩略图进度工具
 * 使用全局 ProgressPanel 组件，不再依赖 Element Plus Notification
 */
import { addProgress, updateProgress, completeProgress, removeProgress, addToast } from '@/stores/progress'

const FOLDERS_API = 'http://127.0.0.1:5000/api/folders'

let _scanId = null
let _thumbId = null
let _thumbPollTimer = null

function stopThumbPoll() {
  if (_thumbPollTimer) { clearInterval(_thumbPollTimer); _thumbPollTimer = null }
}

// ==================== 扫描进度 ====================

export function showScanNotify() {
  if (_scanId) removeProgress(_scanId)
  _scanId = addProgress({ type: 'scan', title: '正在扫描...', current: 0, total: 0, path: '准备中...' })
}

export function updateScanNotify(current, total, path) {
  if (!_scanId) return
  updateProgress(_scanId, {
    title: total > 0 ? `正在扫描 ${current}/${total}` : '正在扫描...',
    current,
    total,
    path: path || ''
  })
}

export function closeScanNotify(progress, onDone) {
  const total = progress.total || 0
  const inserted = progress.inserted || 0
  const updated = progress.updated || 0
  const deleted = progress.deleted || 0

  if (_scanId) {
    const parts = []
    if (inserted > 0) parts.push(`新增 ${inserted} 首`)
    if (updated > 0) parts.push(`更新 ${updated} 首`)
    if (deleted > 0) parts.push(`移除 ${deleted} 首`)
    let text
    if (parts.length > 0) {
      text = `扫描完成 · ${total} 首（${parts.join('，')}）`
    } else {
      text = '扫描完成 · 无变化'
    }
    completeProgress(_scanId, text)
    _scanId = null
  }
  if (inserted > 0 || updated > 0) {
    startThumbPoll(onDone)
  } else if (onDone) {
    onDone()
  }
}

// ==================== 缩略图进度 ====================

function startThumbPoll(onDone) {
  stopThumbPoll()

  // 先检查是否已完成，避免一闪而过
  fetch(`${FOLDERS_API}/thumb-progress`).then(r => r.json()).then(p => {
    if (p.scanning && p.total > 0) {
      // 正在生成中 —— 创建进度条
      _thumbId = addProgress({ type: 'thumb', title: `生成缩略图 ${p.current}/${p.total}`, current: p.current, total: p.total, path: p.path })
      startThumbInterval(onDone)
    } else if (p.total > 0) {
      // 已全部完成 —— 仅 toast 通知
      addToast(`缩略图完成 · ${p.total} 张`, 'success')
      if (onDone) onDone()
    } else if (p.scanning) {
      // 后端刚开始，还没统计到数量 —— 等 500ms 重试
      setTimeout(() => {
        _thumbId = addProgress({ type: 'thumb', title: '正在生成缩略图...', current: 0, total: 0, path: '准备中...' })
        startThumbInterval(onDone)
      }, 500)
    } else {
      // scanning=false 且 total=0：无需生成缩略图
      if (onDone) onDone()
    }
  }).catch(() => {
    setTimeout(() => startThumbInterval(onDone), 500)
  })
}

function startThumbInterval(onDone) {
  stopThumbPoll()
  if (!_thumbId) {
    _thumbId = addProgress({ type: 'thumb', title: '正在生成缩略图...', current: 0, total: 0, path: '准备中...' })
  }
  _thumbPollTimer = setInterval(() => pollThumbOnce(onDone), 600)
}

async function pollThumbOnce(onDone) {
  try {
    const res = await fetch(`${FOLDERS_API}/thumb-progress`)
    const p = await res.json()
    if (!_thumbId) return
    updateProgress(_thumbId, { current: p.current, total: p.total, path: p.path })
    updateProgress(_thumbId, {
      title: p.total > 0 ? `生成缩略图 ${p.current}/${p.total}` : '正在生成缩略图...'
    })
    if (!p.scanning) {
      stopThumbPoll()
      if (p.total > 0) {
        completeProgress(_thumbId, `缩略图完成 · ${p.total} 张`)
      } else {
        removeProgress(_thumbId)
      }
      _thumbId = null
      if (onDone) onDone()
    }
  } catch { /* ignore */ }
}

// ==================== 清理 ====================

export function clearScanNotify() {
  if (_scanId) { removeProgress(_scanId); _scanId = null }
  stopThumbPoll()
  if (_thumbId) { removeProgress(_thumbId); _thumbId = null }
}
