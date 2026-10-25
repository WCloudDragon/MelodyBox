/**
 * 扫描/缩略图进度工具
 * 使用全局 ProgressPanel 组件，不再依赖 Element Plus Notification
 */
import { addProgress, updateProgress, completeProgress, removeProgress } from '@/stores/progress'
import { useLibraryStore } from '@/stores/library'

import { apiUrl } from '@/config/api'

const FOLDERS_API = apiUrl('/api/folders')

// 缩略图批次结束：推进版本号，让列表里之前加载失败的封面重新请求并淡入
function notifyThumbsUpdated(onDone) {
  try { useLibraryStore().bumpThumbVersion() } catch {}
  if (onDone) onDone()
}

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

export function updateScanNotify(current, total, path, prefix = '') {
  if (!_scanId) return
  updateProgress(_scanId, {
    title: total > 0 ? `${prefix}正在扫描 ${current}/${total}` : `${prefix}正在扫描...`,
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
  // 扫描一结束就刷新列表，让用户立刻看到曲目；缩略图在后台继续生成
  if (onDone) onDone()
  if (inserted > 0 || updated > 0) {
    startThumbPoll(onDone)
  }
}

// ==================== 缩略图进度 ====================

// 停滞看门狗：进度 60 秒无任何变化则主动收尾，避免孤儿卡永久停留
const THUMB_STALL_MS = 60000
// 启动宽限：后端在扫描结束前已同步算好批次总数，这里只留极短的防御窗口
const THUMB_GRACE_MS = 2000
let _thumbLastChange = 0
let _thumbLastSig = ''
let _thumbGraceStart = 0
let _thumbFailCount = 0

function startThumbPoll(onDone) {
  // HomeView / LibraryView 的 watcher 会在同一次状态更新里各触发一次 closeScanNotify。
  // 已有卡片时只能确保轮询在跑，绝不能先 stopThumbPoll —— 那会把第一次调用刚启动的
  // 轮询掐掉，卡片从此停在"准备中..."再也不更新。
  if (_thumbId) {
    if (!_thumbPollTimer) startThumbInterval(onDone)
    return
  }

  _thumbId = addProgress({ type: 'thumb', title: '正在生成缩略图...', current: 0, total: 0, path: '准备中...' })
  _thumbLastChange = Date.now()
  _thumbLastSig = ''
  _thumbGraceStart = Date.now()
  _thumbFailCount = 0
  startThumbInterval(onDone)
}

function startThumbInterval(onDone) {
  stopThumbPoll()
  if (!_thumbId) {
    _thumbId = addProgress({ type: 'thumb', title: '正在生成缩略图...', current: 0, total: 0, path: '准备中...' })
    _thumbLastChange = Date.now()
    _thumbLastSig = ''
    _thumbGraceStart = Date.now()
    _thumbFailCount = 0
  }
  _thumbPollTimer = setInterval(() => pollThumbOnce(onDone), 250)
}

async function pollThumbOnce(onDone) {
  try {
    const res = await fetch(`${FOLDERS_API}/thumb-progress`)
    const p = await res.json()
    if (!_thumbId) return
    _thumbFailCount = 0
    // 停滞检测：内容签名（数字+文件名）连续 60 秒无变化则主动收尾
    const sig = `${p.current}/${p.total}|${p.path}`
    if (sig !== _thumbLastSig) {
      _thumbLastSig = sig
      _thumbLastChange = Date.now()
    }

    // 批次尚未开始（未运行且数量为 0）：给一个启动宽限，
    // 避免扫描刚结束、后端线程还未占位时就被误判成"无需生成缩略图"
    if (!p.scanning && p.total === 0) {
      if (Date.now() - _thumbGraceStart < THUMB_GRACE_MS) {
        updateProgress(_thumbId, { title: '正在生成缩略图...', path: '准备中...' })
        return
      }
      stopThumbPoll()
      removeProgress(_thumbId)
      _thumbId = null
      if (onDone) onDone()
      return
    }

    updateProgress(_thumbId, {
      current: p.current, total: p.total, path: p.path,
      title: p.total > 0 ? `生成缩略图 ${p.current}/${p.total}` : '正在生成缩略图...'
    })
    if (!p.scanning) {
      stopThumbPoll()
      completeProgress(_thumbId, `缩略图完成 · ${p.total} 张`)
      _thumbId = null
      notifyThumbsUpdated(onDone)
    } else if (Date.now() - _thumbLastChange > THUMB_STALL_MS) {
      stopThumbPoll()
      completeProgress(_thumbId, `缩略图已停滞，已处理 ${p.current}/${p.total}`)
      _thumbId = null
      notifyThumbsUpdated(onDone)
    }
  } catch {
    // 请求持续失败（后端重启/未就绪）时不能永久卡住：约 5 秒后主动收尾
    _thumbFailCount++
    if (_thumbFailCount >= 20 && _thumbId) {
      stopThumbPoll()
      removeProgress(_thumbId)
      _thumbId = null
      if (onDone) onDone()
    }
  }
}

// ==================== 清理 ====================

export function clearScanNotify() {
  if (_scanId) { removeProgress(_scanId); _scanId = null }
  stopThumbPoll()
  if (_thumbId) { removeProgress(_thumbId); _thumbId = null }
}
