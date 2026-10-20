/**
 * 扫描/缩略图进度工具
 * 使用全局 ProgressPanel 组件，不再依赖 Element Plus Notification
 */
import { addProgress, updateProgress, completeProgress, removeProgress } from '@/stores/progress'

import { apiUrl } from '@/config/api'

const FOLDERS_API = apiUrl('/api/folders')

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
  const errors = progress.errors || 0

  if (_scanId) {
    const parts = []
    if (inserted > 0) parts.push(`新增 ${inserted} 首`)
    if (updated > 0) parts.push(`更新 ${updated} 首`)
    if (deleted > 0) parts.push(`移除 ${deleted} 首`)
    if (errors > 0) parts.push(`解析失败 ${errors} 首`)
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

// 停滞看门狗：进度 60 秒无任何变化则主动收尾，避免孤儿卡永久停留
const THUMB_STALL_MS = 60000
let _thumbLastChange = 0
let _thumbLastSig = ''

function startThumbPoll(onDone) {
  stopThumbPoll()

  // 防止并发调用（HomeView / LibraryView 的 watcher 会在同一次状态更新里
  // 各触发一次 closeScanNotify）：先同步占位 _thumbId，第二次调用会在这里
  // 被拦截。旧实现是"先查后等 fetch"，两次调用都在 fetch 返回前通过检查，
  // 各建一张进度卡，未被引用的那张从此无人更新 —— 卡死在创建时的快照。
  if (_thumbId) return
  _thumbId = addProgress({ type: 'thumb', title: '正在生成缩略图...', current: 0, total: 0, path: '准备中...' })
  _thumbLastChange = Date.now()
  _thumbLastSig = ''

  fetch(`${FOLDERS_API}/thumb-progress`).then(r => r.json()).then(p => {
    if (!_thumbId) return  // 期间被 clearScanNotify 清理
    if (p.scanning && p.total > 0) {
      // 正在生成中 —— 更新占位卡并开始轮询
      updateProgress(_thumbId, {
        title: `生成缩略图 ${p.current}/${p.total}`,
        current: p.current, total: p.total, path: p.path
      })
      startThumbInterval(onDone)
    } else if (p.total > 0 && !p.scanning) {
      // 已全部完成（或本次无可生成的缩略图）
      completeProgress(_thumbId, `缩略图完成 · ${p.total} 张`)
      _thumbId = null
      if (onDone) onDone()
    } else if (p.scanning) {
      // 后端刚开始，还没统计到数量 —— 稍后由轮询更新数字
      startThumbInterval(onDone)
    } else {
      // scanning=false 且 total=0：无需生成缩略图
      removeProgress(_thumbId)
      _thumbId = null
      if (onDone) onDone()
    }
  }).catch(() => {
    if (!_thumbId) return
    startThumbInterval(onDone)
  })
}

function startThumbInterval(onDone) {
  stopThumbPoll()
  if (!_thumbId) {
    _thumbId = addProgress({ type: 'thumb', title: '正在生成缩略图...', current: 0, total: 0, path: '准备中...' })
    _thumbLastChange = Date.now()
    _thumbLastSig = ''
  }
  _thumbPollTimer = setInterval(() => pollThumbOnce(onDone), 600)
}

async function pollThumbOnce(onDone) {
  try {
    const res = await fetch(`${FOLDERS_API}/thumb-progress`)
    const p = await res.json()
    if (!_thumbId) return
    // 停滞检测：内容签名（数字+文件名）连续 60 秒无变化则主动收尾
    const sig = `${p.current}/${p.total}|${p.path}`
    if (sig !== _thumbLastSig) {
      _thumbLastSig = sig
      _thumbLastChange = Date.now()
    }
    updateProgress(_thumbId, {
      current: p.current, total: p.total, path: p.path,
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
    } else if (Date.now() - _thumbLastChange > THUMB_STALL_MS) {
      stopThumbPoll()
      completeProgress(_thumbId, `缩略图已停滞，已处理 ${p.current}/${p.total}`)
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
