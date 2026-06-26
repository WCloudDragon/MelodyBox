<template>
  <div
    class="lyrics-window"
    :style="desktopVars"
    @dblclick="handleClose"
    title="双击关闭桌面歌词"
  >
    <div ref="mainRef" class="lyrics-viewport">
      <div ref="scrollRef" class="lyrics-scroll">
        <!-- 等待数据 -->
        <div v-if="!hasData" class="dl-empty">桌面歌词</div>

        <template v-else>
          <!-- 歌曲信息：未到歌词时间戳时显示 -->
          <div v-if="showSongInfo" class="dl-line active">
            <div class="dl-line__inner">
              <p class="dl-line__original">{{ songInfo?.title || '...' }}</p>
              <p v-if="songInfo?.artist" class="dl-line__translation">{{ songInfo.artist }}</p>
            </div>
          </div>

          <!-- 歌词行 -->
          <template v-if="parsedLyrics.length > 0">
            <div
              v-for="(line, index) in parsedLyrics"
              :key="index"
              class="dl-line"
              :class="{
                active: index === currentLineIndex,
                'has-translation': line.translation,
                'word-level': index === currentLineIndex && line.wordLevel && line.segments && line.segments.length >= 2
              }"
              :ref="el => setLineRef(el, index)"
            >
              <div class="dl-line__inner" :style="lineStyle(index)">
                <!-- 活跃行 + 逐字数据：拆分 word-seg 供 rAF 逐字填充 -->
                <p v-if="index === currentLineIndex && line.wordLevel && line.segments && line.segments.length >= 2"
                   class="dl-line__original word-level">
                  <span v-for="(seg, si) in line.segments" :key="si"
                        class="word-seg" :data-i="si" :data-text="seg.text">{{ seg.text }}</span>
                </p>
                <!-- 普通行 / 活跃但无逐字数据 -->
                <p v-else class="dl-line__original"><span class="dl-line__text">{{ line.original }}</span></p>
                <p v-if="line.translation" class="dl-line__translation"><span class="dl-line__text">{{ line.translation }}</span></p>
              </div>
            </div>
          </template>
        </template>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'

// ===== 状态 =====
const parsedLyrics = ref([])
const currentLineIndex = ref(-1)
const songInfo = ref(null)
const desktopSettings = ref({ fontSize: 24, activeScale: 120, transScale: 60, viewLines: 2 })
const hasData = ref(false)

const mainRef = ref(null)
const scrollRef = ref(null)
const lineRefs = ref({})

function setLineRef(el, index) {
  if (el) lineRefs.value[index] = el
}

const showSongInfo = computed(() =>
  currentLineIndex.value < 0 && songInfo.value !== null
)

// ===== CSS 变量 =====
const desktopVars = computed(() => {
  const base = desktopSettings.value.fontSize
  const trans = Math.round(base * desktopSettings.value.transScale / 100)
  const active = desktopSettings.value.activeScale / 100
  return {
    '--dl-base-original': base + 'px',
    '--dl-base-trans': trans + 'px',
    '--dl-active-original': Math.round(base * active) + 'px',
    '--dl-active-trans': Math.round(trans * active) + 'px',
    '--dl-lh-original': Math.round(base * 1.2) + 'px',
    '--dl-lh-trans': Math.round(trans * 1.2) + 'px'
  }
})

// ===== 行样式 =====
function lineStyle(index) {
  const baseIndex = Math.max(0, currentLineIndex.value)
  const dist = index - baseIndex
  const vl = desktopSettings.value.viewLines ?? 2

  // 硬裁剪：viewLines 范围外的行直接隐藏
  if (dist < 0 || dist >= vl) return { opacity: 0, transform: 'scale(1)' }

  // 连续透明度
  const t = Math.min(dist / 6, 1)
  const opacity = Math.max(0.3, 1 - t * 0.7)

  // 连续缩放：活跃行满 scale → 相邻行渐变回 1.0
  const maxScale = desktopSettings.value.activeScale / 100
  const scaleDist = Math.abs(dist)
  const scale = scaleDist === 0
    ? maxScale
    : maxScale - (maxScale - 1) * Math.min(scaleDist, 1)

  return { opacity, transform: `scale(${scale.toFixed(3)})` }
}

// ===== 窗口高度 =====
function computeWindowHeight() {
  const base = desktopSettings.value.fontSize
  const viewLines = desktopSettings.value.viewLines
  const activeScale = desktopSettings.value.activeScale / 100
  const transBase = Math.round(base * desktopSettings.value.transScale / 100)

  const activeOriginalLH = Math.round(base * activeScale * 1.2)
  const activeTransLH = Math.round(transBase * activeScale * 1.2)
  const normalOriginalLH = Math.round(base * 1.2)
  const normalTransLH = Math.round(transBase * 1.2)
  const lineOverhead = 14  // padding(6*2) + gap(2)
  const gap = 2

  // 每行预留原文+翻译高度，避免翻译文本被裁切
  let contentH = activeOriginalLH + activeTransLH + gap + lineOverhead
  if (viewLines >= 2) {
    contentH += normalOriginalLH + normalTransLH + gap + lineOverhead
  }

  const wh = Math.max(60, Math.round(32 + contentH))
  return wh
}

let _resizeTimer = null
function requestResize() {
  clearTimeout(_resizeTimer)
  const h = computeWindowHeight()
  if (window.electronAPI?.lyricsResize) {
    window.electronAPI.lyricsResize(300, h)
  }
  // 等待窗口 resize 完成后重新对齐滚动位置
  _resizeTimer = setTimeout(() => {
    const idx = currentLineIndex.value
    if (idx >= 0) {
      scrollToLine(idx, false)
    }
  }, 200)
}

// ===== 滚动 =====
let currentScrollY = 0
let currentScrollTarget = 0

// 视口高度：从设置参数直接算出，不依赖 DOM 测量
const viewportHeight = computed(() => computeWindowHeight() - 32)

function scrollToLine(index, animate = true) {
  if (index < 0 || !scrollRef.value || !mainRef.value) {
    return
  }
  const lineEl = lineRefs.value[index]
  if (!lineEl) {
    return
  }

  // 取消上一句的跑马灯和逐字动画
  cancelMarquee()
  stopKaraokeLoop()

  // 用 rAF 确保 DOM 布局已完成再读取 offsetTop
  requestAnimationFrame(() => {
    if (!lineEl || !scrollRef.value || !mainRef.value) return

    const containerHeight = viewportHeight.value
    const vl = desktopSettings.value.viewLines ?? 2
    const total = parsedLyrics.value.length
    const isLast = index >= total - 1

    const ratio = (vl >= 2 && !isLast) ? 0.33 : 0.5
    const targetScroll = lineEl.offsetTop - containerHeight * ratio + lineEl.offsetHeight / 2

    if (!animate) {
      scrollRef.value.style.transition = 'none'
      scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
      currentScrollY = -targetScroll
      // 无动画也启动行内效果（切歌场景）
      nextTick(() => afterScrollEffect(index))
      return
    }

    const absScrollDelta = Math.abs(targetScroll - currentScrollTarget)
    currentScrollTarget = targetScroll

    if (absScrollDelta > containerHeight) {
      // 大跨度：Web Animation
      const anim = scrollRef.value.animate(
        [
          { transform: `translate3d(0, ${currentScrollY}px, 0)` },
          { transform: `translate3d(0, ${-targetScroll}px, 0)` }
        ],
        { duration: 800, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
      )
      anim.onfinish = () => {
        if (scrollRef.value) {
          scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
          anim.cancel()
        }
        currentScrollY = -targetScroll
      }
    } else {
      // 小跨度：CSS transition
      scrollRef.value.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
      scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
      currentScrollY = -targetScroll
      setTimeout(() => {
        if (scrollRef.value) scrollRef.value.style.transition = ''
      }, 550)
    }

    // 滚动后启动行内效果（跑马灯 或 逐字卡拉OK）
    setTimeout(() => afterScrollEffect(index), 100)
  })
}

// ===== 重置 =====
function resetScroll() {
  currentScrollY = 0
  currentScrollTarget = 0
  if (scrollRef.value) {
    scrollRef.value.style.transition = 'none'
    scrollRef.value.style.transform = 'translate3d(0, 0, 0)'
  }
}

// ===== 活跃行跑马灯 =====
let marqueeAnims = []

function cancelMarquee() {
  marqueeAnims.forEach(a => { try { a.cancel() } catch (_) { /* noop */ } })
  marqueeAnims = []
}

function lineDuration(index) {
  if (index < 0 || index >= parsedLyrics.value.length) return 5000
  const nextIdx = index + 1
  if (nextIdx >= parsedLyrics.value.length) return 5000
  const dur = (parsedLyrics.value[nextIdx].time - parsedLyrics.value[index].time) * 1000
  return Math.max(2000, Math.min(dur, 12000))
}

function afterScrollEffect(index) {
  const line = parsedLyrics.value[index]
  if (line?.wordLevel && line?.segments && line.segments.length >= 2) {
    startKaraokeLoop(index)
  } else {
    startActiveMarquee()
  }
}

function startActiveMarquee() {
  cancelMarquee()
  const idx = currentLineIndex.value
  if (idx < 0) return
  const lineEl = lineRefs.value[idx]
  if (!lineEl) return

  const duration = lineDuration(idx)

  // 跑原文
  const origP = lineEl.querySelector('.dl-line__original')
  if (origP) {
    const span = origP.querySelector('.dl-line__text')
    if (span && span.scrollWidth > origP.clientWidth + 2) {
      const overflow = span.scrollWidth - origP.clientWidth
      const anim = span.animate([
        { transform: 'translateX(0)', offset: 0 },
        { transform: 'translateX(0)', offset: 0.12 },
        { transform: `translateX(${-overflow}px)`, offset: 0.88 },
        { transform: `translateX(${-overflow}px)`, offset: 1 }
      ], { duration, easing: 'linear', fill: 'forwards' })
      marqueeAnims.push(anim)
    } else if (span) {
      span.style.transform = 'translateX(0)'
    }
  }

  // 跑翻译
  const transP = lineEl.querySelector('.dl-line__translation')
  if (transP) {
    const span = transP.querySelector('.dl-line__text')
    if (span && span.scrollWidth > transP.clientWidth + 2) {
      const overflow = span.scrollWidth - transP.clientWidth
      const anim = span.animate([
        { transform: 'translateX(0)', offset: 0 },
        { transform: 'translateX(0)', offset: 0.12 },
        { transform: `translateX(${-overflow}px)`, offset: 0.88 },
        { transform: `translateX(${-overflow}px)`, offset: 1 }
      ], { duration, easing: 'linear', fill: 'forwards' })
      marqueeAnims.push(anim)
    } else if (span) {
      span.style.transform = 'translateX(0)'
    }
  }
}

// ===== 逐字卡拉 OK（60fps rAF 循环，直接写 DOM，绕过 Vue） =====
let karaokeRafId = null
let songTimeBase = 0
let clockBase = 0

function syncKaraokeClock(songTime) {
  songTimeBase = songTime
  clockBase = performance.now()
}

function estimatedSongTime() {
  return songTimeBase + (performance.now() - clockBase) / 1000
}

function stopKaraokeLoop() {
  if (karaokeRafId) {
    cancelAnimationFrame(karaokeRafId)
    karaokeRafId = null
  }
  _karaEntries = null
}

let _karaEntries = null  // [{ span, wordStart, wordEnd }]
let _karaFrameSkip = 0

function startKaraokeLoop(activeIndex) {
  stopKaraokeLoop()
  const line = parsedLyrics.value[activeIndex]
  if (!line || !line.wordLevel || !line.segments || line.segments.length < 2) return

  const segs = line.segments
  const nextLineTime = activeIndex + 1 < parsedLyrics.value.length
    ? parsedLyrics.value[activeIndex + 1].time
    : line.time + 5

  // 一次性查询 DOM，构建预计算数组（避免每帧 querySelectorAll + parseInt）
  _karaEntries = []
  const spans = document.querySelectorAll('.word-seg')
  for (const span of spans) {
    const i = parseInt(span.getAttribute('data-i'))
    if (isNaN(i) || i >= segs.length) continue
    const wordEnd = i + 1 < segs.length ? segs[i + 1].time : nextLineTime
    _karaEntries.push({ span, wordStart: segs[i].time, wordEnd, dur: wordEnd - segs[i].time })
  }

  _karaFrameSkip = 0

  function tick() {
    if (currentLineIndex.value !== activeIndex) {
      stopKaraokeLoop()
      return
    }

    // 跳帧：每 2 帧更新一次（~30fps），肉眼与 60fps 无区别，CPU 减半
    _karaFrameSkip ^= 1
    if (_karaFrameSkip) {
      karaokeRafId = requestAnimationFrame(tick)
      return
    }

    const now = estimatedSongTime()
    for (const entry of _karaEntries) {
      const fill = entry.dur > 0
        ? Math.max(0, Math.min(1, (now - entry.wordStart) / entry.dur))
        : 0
      entry.span.style.setProperty('--kara-fill', (fill * 100).toFixed(1) + '%')
    }

    karaokeRafId = requestAnimationFrame(tick)
  }

  karaokeRafId = requestAnimationFrame(tick)
}

// ===== IPC 监听（顶层注册，在 Vue 挂载前就绪，确保首帧数据不丢失） =====
if (window.electronAPI) {
  window.electronAPI.onLyricsData((data) => {
    // 更新设置（只在设置真正变化时才调整窗口大小）
    if (data?.settings) {
      const prevSettings = JSON.stringify(desktopSettings.value)
      desktopSettings.value = data.settings
      if (JSON.stringify(data.settings) !== prevSettings) {
        nextTick(() => requestResize())
      }
    }

    const newLyrics = data?.parsedLyrics || []
    const newIndex = data?.currentLineIndex ?? -1
    const newSongInfo = data?.songInfo || null

    const lyricsChanged = JSON.stringify(newLyrics) !== JSON.stringify(parsedLyrics.value)

    // 歌曲信息：始终更新
    songInfo.value = newSongInfo

    if (lyricsChanged) {
      // 切歌：重置滚动
      parsedLyrics.value = newLyrics
      hasData.value = true
      currentLineIndex.value = newIndex

      // 逐字卡拉 OK：切歌时同步时钟
      if (newIndex >= 0) {
        const activeLine = newLyrics[newIndex]
        if (activeLine.wordLevel && activeLine.segments && activeLine.segments.length >= 2 && data.currentTime != null) {
          syncKaraokeClock(data.currentTime)
        }
        nextTick(() => scrollToLine(newIndex, false))
      } else {
        stopKaraokeLoop()
        nextTick(() => resetScroll())
      }
      return
    }

    // 更新歌词行列表（内容未变但索引变了）
    parsedLyrics.value = newLyrics
    hasData.value = true
    currentLineIndex.value = newIndex

    // 逐字卡拉 OK：同步时钟 & 启动 rAF 循环
    if (newIndex >= 0) {
      const activeLine = newLyrics[newIndex]
      if (activeLine.wordLevel && activeLine.segments && activeLine.segments.length >= 2 && data.currentTime != null) {
        syncKaraokeClock(data.currentTime)
      }
      nextTick(() => scrollToLine(newIndex, true))
    }
  })
}

// ===== 挂载后调整窗口尺寸 =====
onMounted(() => {
  if (window.electronAPI) {
    requestResize()
  }
})

function handleClose() {
  if (window.electronAPI) {
    window.electronAPI.lyricsClose()
  }
}

onUnmounted(() => {
  stopKaraokeLoop()
  cancelMarquee()
})
</script>

<style>
/* 全局重置 */
html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  background: transparent !important;
  overflow: hidden;
}
#app {
  width: 100%;
  height: 100%;
  background: transparent !important;
}
</style>

<style scoped>
.lyrics-window {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px 24px;
  -webkit-app-region: drag;
  user-select: none;
  background: rgba(255, 0, 0, 0.3); /* DEBUG: 临时红色半透明背景 */
  overflow: hidden;
}

.lyrics-viewport {
  flex: 1;
  width: 100%;
  overflow: hidden;
  min-height: 0;
  position: relative;
}

.lyrics-scroll {
  padding: 200px 0 160px;
  width: 100%;
}

.dl-empty {
  font-size: 20px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 2px;
}

.dl-line {
  text-align: center;
  user-select: none;
  letter-spacing: 1px;
  max-width: 100%;
  padding: 6px 0;
  flex-shrink: 0;
  overflow: hidden;
}

.dl-line__inner {
  display: flex;
  flex-direction: column;
  gap: 0;
  align-items: center;
  will-change: transform, opacity;
  transition: transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

.dl-line__original {
  margin: 0;
  font-size: var(--dl-base-original, 24px);
  line-height: var(--dl-lh-original, 38px);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.35);
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.3),
     1px -1px 0 rgba(0, 0, 0, 0.3),
    -1px  1px 0 rgba(0, 0, 0, 0.3),
     1px  1px 0 rgba(0, 0, 0, 0.3);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-line__text {
  display: inline-block;
  white-space: nowrap;
  will-change: transform;
}

.dl-line__translation {
  margin: 0;
  font-size: var(--dl-base-trans, 14px);
  line-height: var(--dl-lh-trans, 20px);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.22);
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.2),
     1px -1px 0 rgba(0, 0, 0, 0.2),
    -1px  1px 0 rgba(0, 0, 0, 0.2),
     1px  1px 0 rgba(0, 0, 0, 0.2);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-line.active .dl-line__original {
  color: #fff;
  /* 活跃行不用省略号，改用跑马灯；仍保留 overflow:hidden 做遮罩 */
  text-overflow: clip;
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.4),
     1px -1px 0 rgba(0, 0, 0, 0.4),
    -1px  1px 0 rgba(0, 0, 0, 0.4),
     1px  1px 0 rgba(0, 0, 0, 0.4);
}

.dl-line.active .dl-line__translation {
  color: rgba(255, 255, 255, 0.85);
  text-overflow: clip;
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.3),
     1px -1px 0 rgba(0, 0, 0, 0.3),
    -1px  1px 0 rgba(0, 0, 0, 0.3),
     1px  1px 0 rgba(0, 0, 0, 0.3);
}

/* ---- 逐字卡拉 OK ---- */
.dl-line__original.word-level {
  text-align: center;
  overflow: visible;
  white-space: normal;
  text-overflow: clip;
}

.word-seg {
  position: relative;
  display: inline-block;
  white-space: pre-wrap;
  /* 未播放颜色 */
  color: rgba(255, 255, 255, 0.35);
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.4),
     1px -1px 0 rgba(0, 0, 0, 0.4),
    -1px  1px 0 rgba(0, 0, 0, 0.4),
     1px  1px 0 rgba(0, 0, 0, 0.4);
}

.word-seg::after {
  content: attr(data-text);
  position: absolute;
  left: 0;
  top: 0;
  /* 已播放颜色 */
  color: #fff;
  width: var(--kara-fill, 0%);
  overflow: hidden;
  white-space: pre;
  -webkit-mask-image: linear-gradient(to right, #000 0%, #000 calc(100% - 8px), transparent 100%);
  mask-image: linear-gradient(to right, #000 0%, #000 calc(100% - 8px), transparent 100%);
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.4),
     1px -1px 0 rgba(0, 0, 0, 0.4),
    -1px  1px 0 rgba(0, 0, 0, 0.4),
     1px  1px 0 rgba(0, 0, 0, 0.4);
}
</style>
