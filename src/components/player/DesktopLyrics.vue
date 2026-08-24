<template>
  <!-- 桌面歌词由 Electron 独立歌词窗口显示；非 Electron 环境不可用 -->
  <div v-if="!isElectron" class="desktop-lyrics-unavailable">
    桌面歌词仅在桌面端可用
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { useSettingsStore } from '@/stores/settings'
import { parseLRC, computeActiveSet, LYRIC_GAP_FILL_LIMIT } from '@/utils/format'

const player = usePlayerStore()
const settings = useSettingsStore()
const { currentTrack, currentTime, showDesktopLyrics } = storeToRefs(player)
const { desktopLyricsFontSize, desktopLyricsActiveScale, desktopLyricsTransScale, desktopLyricsViewLines } = storeToRefs(settings)

const isElectron = computed(() => !!window.electronAPI)
// 直接用 location.hash 判断，避免路由初始化时序导致 route.name 为 undefined
const isInLyricsWindow = computed(() => window.location.hash === '#/desktop-lyrics')

const currentLineIndex = ref(-1)
const overlapLines = ref([])

const parsedLyrics = computed(() => {
  const raw = currentTrack.value?.lyrics
  if (!raw) return []
  return parseLRC(raw)
})

// 长间奏"即将开唱"提示（与全屏页同一判定口径）
const hintPrevIndex = computed(() => {
  const list = parsedLyrics.value
  const now = currentTime.value
  if (!list.length || now < list[0].time) return -1
  let prev = -1
  for (let i = 0; i < list.length; i++) {
    if (list[i].time <= now) prev = i
    else break
  }
  return prev
})
const upcomingRemaining = computed(() => {
  const list = parsedLyrics.value
  if (!list.length) return Infinity
  const now = currentTime.value
  let next = Infinity
  for (const l of list) {
    if (l.time > now && l.time < next) next = l.time
  }
  return next - now
})
const showUpcomingHint = computed(() => {
  if (!parsedLyrics.value.length) return false
  if (/纯音乐/.test(currentTrack.value?.lyrics || '')) return false
  if (upcomingRemaining.value <= 0) return false
  const list = parsedLyrics.value
  const now = currentTime.value
  if (now < list[0].time) return list[0].time >= LYRIC_GAP_FILL_LIMIT
  const prev = hintPrevIndex.value
  return prev >= 0 && (list[prev].gap ?? 0) >= LYRIC_GAP_FILL_LIMIT
})

// ==================== 发送到独立歌词窗口 ====================

function buildSettings() {
  return {
    fontSize: desktopLyricsFontSize.value,
    activeScale: desktopLyricsActiveScale.value,
    transScale: desktopLyricsTransScale.value,
    viewLines: desktopLyricsViewLines.value
  }
}

// 构建完整歌词行结构
function buildLines() {
  const idx = currentLineIndex.value
  const total = parsedLyrics.value.length
  const track = currentTrack.value

  // 首个时间戳到达前，把歌曲信息作为一条合成歌词行插入队列开头
  const needsSongInfo = track && (total === 0 || idx < 0)
  const lines = parsedLyrics.value.map(line => ({
    time: line.time,
    end: line.end ?? null,
    original: line.original,
    translation: line.translation || null,
    wordLevel: line.wordLevel || false,
    segments: line.segments || null
  }))
  let lineIndex = idx

  if (needsSongInfo) {
    lines.unshift({
      time: 0,
      original: track.title || '...',
      translation: track.artist || null,
      wordLevel: false,
      segments: null,
      synthetic: true
    })
    lineIndex = idx < 0 ? 0 : idx + 1
  }

  return { lines, lineIndex }
}

// 静态歌词结构：切歌/首帧时推送
function buildStructurePayload() {
  const { lines, lineIndex } = buildLines()
  return {
    type: 'structure',
    lines,
    currentLineIndex: lineIndex,
    currentTime: currentTime.value,
    overlap: overlapLines.value,
    upcoming: {
      visible: showUpcomingHint.value,
      remaining: upcomingRemaining.value,
      prevIndex: hintPrevIndex.value,
      nextIndex: hintPrevIndex.value + 1,
      hasSongInfo: !!currentTrack.value && (parsedLyrics.value.length === 0 || currentLineIndex.value < 0)
    },
    settings: buildSettings()
  }
}

// 运行时状态：行/重叠/设置变化时推送
function buildStatePayload() {
  const { lines } = buildLines()
  return {
    type: 'state',
    // 携带完整结构：窗口加载完成后下次切行即可补上，避免首帧丢失后永久空白
    lines,
    currentLineIndex: currentLineIndex.value,
    currentTime: currentTime.value,
    overlap: overlapLines.value,
    upcoming: {
      visible: showUpcomingHint.value,
      remaining: upcomingRemaining.value,
      prevIndex: hintPrevIndex.value,
      nextIndex: hintPrevIndex.value + 1,
      hasSongInfo: !!currentTrack.value && (parsedLyrics.value.length === 0 || currentLineIndex.value < 0)
    },
    settings: buildSettings()
  }
}

function send(payload) {
  if (!isElectron.value) return
  try {
    // 确保 IPC 收到的是纯 JSON 数据（结构化克隆不接受响应式代理/循环引用）
    window.electronAPI.lyricsUpdate(JSON.parse(JSON.stringify(payload)))
  } catch (e) {
    console.error('[dl-send][err]', payload.type, e)
  }
}

// 低频时间心跳：让独立歌词窗口持续校准逐字时钟，避免本地估算漂移
let _tickTimer = null
function startTick() {
  if (_tickTimer) return
  _tickTimer = setInterval(() => {
    try {
      if (!showDesktopLyrics.value) {
        stopTick()
        return
      }
      send({
        type: 'tick',
        time: player.getLiveTime(),
        playing: player.isPlaying,
        remaining: showUpcomingHint.value ? upcomingRemaining.value : 0
      })
    } catch {
      stopTick()
    }
  }, 250)
}

function stopTick() {
  if (_tickTimer) {
    clearInterval(_tickTimer)
    _tickTimer = null
  }
}

// ==================== 窗口开关与数据同步 ====================

let _openRetryTimers = []
let _structureAcked = false
let _structureResendTimer = null
function clearOpenRetryTimers() {
  _openRetryTimers.forEach(id => clearTimeout(id))
  _openRetryTimers = []
}
function stopStructureResend() {
  if (_structureResendTimer) {
    clearInterval(_structureResendTimer)
    _structureResendTimer = null
  }
}

// 桌面窗口确认收到结构前，每秒补发一次，彻底规避加载时序问题
function startStructureResend() {
  stopStructureResend()
  _structureResendTimer = setInterval(() => {
    if (_structureAcked) {
      stopStructureResend()
      return
    }
    send(buildStructurePayload())
  }, 1000)
}

watch(showDesktopLyrics, (val) => {
  if (!isElectron.value || isInLyricsWindow.value) return
  if (val) {
    _structureAcked = false
    window.electronAPI.lyricsOpen()
    send(buildStructurePayload())
    // 兜底重试（真正可靠的送达由 lyrics:ready 事件触发）
    clearOpenRetryTimers()
    _openRetryTimers = [500, 1000, 2000, 4000, 8000].map(delay =>
      setTimeout(() => send(buildStructurePayload()), delay)
    )
    startStructureResend()
    startTick()
  } else {
    clearOpenRetryTimers()
    stopStructureResend()
    stopTick()
    window.electronAPI.lyricsClose()
  }
}, { immediate: true })

watch(currentLineIndex, () => {
  if (showDesktopLyrics.value && isElectron.value && !isInLyricsWindow.value) {
    send(buildStatePayload())
  }
})

// 间奏三点进入/退出时同步（首句前 currentLineIndex 可能不变，需单独触发）
watch(showUpcomingHint, () => {
  if (showDesktopLyrics.value && isElectron.value && !isInLyricsWindow.value) {
    send(buildStatePayload())
  }
}, { immediate: true })

// 切歌时推送最新歌词结构
watch(() => currentTrack.value?.path, () => {
  _structureAcked = false
  currentLineIndex.value = -1
  overlapLines.value = []
  if (showDesktopLyrics.value && isElectron.value && !isInLyricsWindow.value) {
    startStructureResend()
    send(buildStructurePayload())
  }
})

// 桌面歌词设置变化时推送
watch([desktopLyricsFontSize, desktopLyricsActiveScale, desktopLyricsTransScale, desktopLyricsViewLines], () => {
  if (showDesktopLyrics.value && isElectron.value && !isInLyricsWindow.value) {
    send(buildStatePayload())
  }
})

// 当前播放时刻：更新主行与重叠附加行（独立窗口据此推进）
watch(currentTime, (time) => {
  const list = parsedLyrics.value
  if (!list.length) {
    if (currentLineIndex.value !== -1) currentLineIndex.value = -1
    return
  }

  const { activeIndexes } = computeActiveSet(list, time)

  // 主行：优先取活跃集合中的逐字歌词行，否则取最后一行
  let mainIndex = -1
  for (let i = activeIndexes.length - 1; i >= 0; i--) {
    if (list[activeIndexes[i]]?.wordLevel) {
      mainIndex = activeIndexes[i]
      break
    }
  }
  if (mainIndex < 0 && activeIndexes.length) {
    mainIndex = activeIndexes[activeIndexes.length - 1]
  }
  if (mainIndex !== currentLineIndex.value) {
    currentLineIndex.value = mainIndex
  }

  const newOverlap = activeIndexes.filter(i => i !== mainIndex).map(i => {
    const line = list[i]
    return { original: line.original, translation: line.translation || null }
  })
  if (JSON.stringify(newOverlap) !== JSON.stringify(overlapLines.value)) {
    overlapLines.value = newOverlap
    if (showDesktopLyrics.value && isElectron.value && !isInLyricsWindow.value) {
      send(buildStatePayload())
    }
  }
})

// 监听独立窗口关闭事件，同步状态回 store
onMounted(() => {
  if (isElectron.value && !isInLyricsWindow.value) {
    // 歌词窗口加载完成后立刻补发首帧结构，避免打开瞬间被丢弃
    window.electronAPI.onLyricsReady(() => {
      clearOpenRetryTimers()
      send(buildStructurePayload())
      startTick()
    })
    window.electronAPI.onLyricsAck(() => {
      _structureAcked = true
      stopStructureResend()
    })
    // 桌面歌词悬浮控件
    window.electronAPI.onLyricsPrev(() => player.prev())
    window.electronAPI.onLyricsNext(() => player.next())
    window.electronAPI.onLyricsViewLines((n) => {
      settings.desktopLyricsViewLines = n === 1 ? 1 : 2
      settings.saveSettings()
    })
    window.electronAPI.onLyricsWindowClosed(() => {
      if (showDesktopLyrics.value) {
        showDesktopLyrics.value = false
      }
    })
  }
})

onBeforeUnmount(() => {
  stopTick()
  stopStructureResend()
})
onUnmounted(() => clearOpenRetryTimers())
</script>

<style scoped>
.desktop-lyrics-unavailable {
  display: none;
}
</style>
