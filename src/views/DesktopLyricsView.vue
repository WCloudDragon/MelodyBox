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
              :class="{ active: index === currentLineIndex, 'has-translation': line.translation }"
              :ref="el => setLineRef(el, index)"
              :style="lineStyle(index)"
            >
              <div class="dl-line__inner">
                <p class="dl-line__original">{{ line.original }}</p>
                <p v-if="line.translation" class="dl-line__translation">{{ line.translation }}</p>
              </div>
            </div>
          </template>
        </template>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'

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
    '--dl-lh-original': Math.round(base * 1.55) + 'px',
    '--dl-lh-trans': Math.round(trans * 1.4) + 'px'
  }
})

// ===== 行样式 =====
function lineStyle(index) {
  const baseIndex = Math.max(0, currentLineIndex.value)
  const dist = index - baseIndex
  const vl = desktopSettings.value.viewLines ?? 2

  // 硬裁剪：viewLines 范围外的行直接隐藏
  if (dist < 0 || dist >= vl) return { opacity: 0 }

  // 范围内：距活跃行越远越透明
  const t = Math.min(dist / 6, 1)
  const opacity = Math.max(0.3, 1 - t * 0.7)
  return { opacity }
}

// ===== 窗口高度 =====
function computeWindowHeight() {
  const base = desktopSettings.value.fontSize
  const viewLines = desktopSettings.value.viewLines
  const activeScale = desktopSettings.value.activeScale / 100

  const activeLH = Math.round(base * activeScale * 1.55)
  const normalLH = Math.round(base * 1.55)
  // .dl-line padding 2+2 + .dl-line__inner gap 2
  const lineOverhead = 6

  let contentH = activeLH + lineOverhead
  if (viewLines >= 2) {
    contentH += normalLH + lineOverhead
  }

  // .lyrics-window padding 16px * 2 = 32px
  return Math.max(60, Math.round(32 + contentH))
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

function scrollToLine(index, animate = true) {
  if (index < 0 || !scrollRef.value || !mainRef.value) return
  const lineEl = lineRefs.value[index]
  if (!lineEl) return

  const containerHeight = mainRef.value.clientHeight
  const vl = desktopSettings.value.viewLines ?? 2
  const total = parsedLyrics.value.length
  const isLast = index >= total - 1

  // 2 行模式且非最后一行：活跃行偏上（33%），为下一行留空间
  // 1 行模式 / 最后一行：活跃行居中（50%）
  const ratio = (vl >= 2 && !isLast) ? 0.33 : 0.5
  const targetScroll = lineEl.offsetTop - containerHeight * ratio + lineEl.offsetHeight / 2

  if (!animate) {
    scrollRef.value.style.transition = 'none'
    scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
    currentScrollY = -targetScroll
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
      scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
      anim.cancel()
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

// ===== IPC 监听 =====
onMounted(() => {
  if (window.electronAPI) {
    window.electronAPI.onLyricsData((data) => {
      // 更新设置
      if (data?.settings) {
        desktopSettings.value = data.settings
        // 字号/行数/缩放变动 → 调整窗口高度
        nextTick(() => requestResize())
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

        // 如果已有活跃行，滚动到位
        if (newIndex >= 0) {
          nextTick(() => scrollToLine(newIndex, false))
        } else {
          nextTick(() => resetScroll())
        }
        return
      }

      // 更新歌词行列表（内容未变但索引变了）
      parsedLyrics.value = newLyrics
      hasData.value = true
      currentLineIndex.value = newIndex

      // 滚动到指定行
      if (newIndex >= 0) {
        nextTick(() => scrollToLine(newIndex, true))
      }
    })

    // 初始窗口尺寸
    requestResize()
  }
})

function handleClose() {
  if (window.electronAPI) {
    window.electronAPI.lyricsClose()
  }
}
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
  align-items: center;
  justify-content: center;
  padding: 16px 24px;
  -webkit-app-region: drag;
  user-select: none;
  background: transparent;
  overflow: hidden;
}

.lyrics-viewport {
  flex: 1;
  width: 100%;
  overflow: hidden;
  min-height: 0;
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
  padding: 2px 0;
  flex-shrink: 0;
  overflow: hidden;
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

.dl-line__inner {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
}

.dl-line__original {
  margin: 0;
  font-size: var(--dl-base-original, 24px);
  line-height: var(--dl-lh-original, 38px);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.35);
  max-width: 760px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-line__translation {
  margin: 0;
  font-size: var(--dl-base-trans, 14px);
  line-height: var(--dl-lh-trans, 20px);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.22);
  max-width: 760px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-line.active .dl-line__original {
  color: #fff;
  font-size: var(--dl-active-original, 29px);
  text-shadow: 0 0 12px rgba(255, 255, 255, 0.4);
}

.dl-line.active .dl-line__translation {
  color: rgba(255, 255, 255, 0.85);
  font-size: var(--dl-active-trans, 17px);
}
</style>
