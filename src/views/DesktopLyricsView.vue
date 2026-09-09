<template>
  <div
    class="lyrics-window"
    :class="{ hovering: hovered }"
    :style="desktopVars"
    @dblclick="handleClose"
    title="双击关闭桌面歌词"
  >
    <!-- hover 悬浮控件 -->
    <div class="dl-controls" :class="{ visible: hovered }" @click.stop>
      <button class="dl-btn" v-ripple @click="prev">⏮</button>
      <button class="dl-btn" v-ripple @click="next">⏭</button>
      <button class="dl-btn" v-ripple @click="toggleLines">
        {{ desktopSettings.viewLines === 1 ? '1行' : '2行' }}
      </button>
      <button class="dl-btn dl-btn--close" v-ripple @click="handleClose">×</button>
    </div>
    <div ref="mainRef" class="lyrics-viewport">
      <div ref="scrollRef" class="lyrics-scroll">
        <!-- 等待数据 -->
        <div v-if="!hasData" class="dl-empty">桌面歌词</div>

        <template v-else>
          <template v-if="parsedLyrics.length > 0">
            <template v-for="(line, index) in parsedLyrics" :key="index">
              <div
                class="dl-line"
                :class="{
                  active: index === currentLineIndex || (upcoming.visible && upcomingPrev < 0 && upcoming.hasSongInfo && index === 0),
                  'has-translation': line.translation,
                  'word-level': index === currentLineIndex && line.wordLevel && line.segments && line.segments.length >= 2
                }"
                :ref="el => setLineRef(el, index)"
              >
                <div class="dl-line__inner" :style="lineStyle(index)">
                  <!-- 活跃行 + 逐字数据：拆分 word-seg 供 rAF 逐字填充 -->
                <p v-if="index === currentLineIndex && line.wordLevel && line.segments && line.segments.length >= 2"
                   class="dl-line__original word-level">
                  <span class="dl-line__text">
                    <span v-for="word in line.words" :key="word.idx" class="word-group">
                      <span v-for="seg in word.chars" :key="seg.idx"
                            class="word-seg" :data-i="seg.idx" :data-text="seg.text">{{ seg.text.replace(/ /g, '\u00A0') }}</span>
                    </span>
                  </span>
                </p>
                  <!-- 普通行 / 活跃但无逐字数据 -->
                  <p v-else class="dl-line__original"><span class="dl-line__text">{{ line.original }}</span></p>
                  <p v-if="line.translation" class="dl-line__translation"><span class="dl-line__text">{{ line.translation }}</span></p>
                  <!-- 常驻注释槽：活跃块内预留，有对白/注释时淡入 -->
                  <p v-if="index === currentLineIndex" class="dl-line__annotation">
                    <template v-for="(ol, oi) in overlap" :key="oi">
                      <span v-if="oi > 0" class="dl-line__annotation-sep"> / </span>
                      <span class="dl-line__annotation-text">{{ ol.original }}<template v-if="ol.translation"> {{ ol.translation }}</template></span>
                    </template>
                  </p>
                </div>
              </div>
              <!-- 三点作为独立行：首句前跟在歌曲信息行之后，句间跟在刚结束行之后 -->
              <div
                v-if="hintVisible && (index === hintAnchor.prevIndex + 1 || (hintAnchor.prevIndex < 0 && hintAnchor.hasSongInfo && index === 0))"
                :ref="setHintTopRef"
                class="dl-hint-line"
                :style="hintStyle"
                :class="{ 'hint-hidden': hintAnchor.prevIndex < 0 && hintStage === 0 && desktopSettings.viewLines === 1, 'hint-leaving': hintLeaving }"
              >
                <span
                  v-for="i in 3"
                  :key="i"
                  class="dl-hint-dot"
                  :class="{ 'dl-hint-dot--fade': dotFading(i) }"
                  :style="{ transform: `scale(${dotScaleFor(i)})` }"
                >·</span>
              </div>
            </template>
          </template>
          <div v-else class="dl-empty">等待歌词数据</div>
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
const overlap = ref([])
const desktopSettings = ref({ fontSize: 24, activeScale: 120, transScale: 60, viewLines: 2 })
const hasData = ref(false)
const upcoming = ref({ visible: false, remaining: 0, prevIndex: -1, nextIndex: -1, hasSongInfo: false })
const latestTime = ref(0)
const hovered = ref(false)
const hintStage = ref(0)
const hintVisible = ref(false)
const hintLeaving = ref(false)
const hintAnchor = ref({ prevIndex: -1, hasSongInfo: false })
let _hintTimer = null
let _hintH = 0
let _hintOffset = 0
let _hintOffsetTimer = null
let _hintLeaveTimer = null

function clearHintTimer() {
  if (_hintTimer) {
    clearTimeout(_hintTimer)
    _hintTimer = null
  }
}

// 结构替换（切歌/歌词变更）时复位旧三点离场流程。
// keepVisible：新结构自身带三点（如新歌首行前长间隙）时保留 hintVisible，
// 只清理旧歌词遗留的滚动偏移补偿与定时器；否则连三点显隐一起复位
function resetHintForStructure(keepVisible = false) {
  clearHintTimer()
  if (_hintOffsetTimer) {
    clearTimeout(_hintOffsetTimer)
    _hintOffsetTimer = null
  }
  if (_hintLeaveTimer) {
    clearTimeout(_hintLeaveTimer)
    _hintLeaveTimer = null
  }
  if (!keepVisible) hintVisible.value = false
  hintLeaving.value = false
  hintStage.value = 0
  _hintOffset = 0
  _hintH = 0
}

// 首句前三点分阶段：先显示歌曲信息，1 秒后滚动到三点
function syncFirstHint() {
  if (!upcoming.value.visible || upcomingPrev.value >= 0) {
    clearHintTimer()
    hintStage.value = 0
    return
  }
  clearHintTimer()
  hintStage.value = 0
  const single = desktopSettings.value.viewLines === 1
  nextTick(() => scrollToLine(0, false))
  _hintTimer = setTimeout(() => {
    hintStage.value = 1
    scrollToHintTop(true, single ? 0.5 : 0.33)
  }, 1000)
}

const mainRef = ref(null)
const scrollRef = ref(null)
const lineRefs = ref({})
const hintTopRef = ref(null)

function setLineRef(el, index) {
  if (el) lineRefs.value[index] = el
}

function setHintTopRef(el) {
  hintTopRef.value = el
}

// 三点逐点放大/淡出（与全屏逻辑一致：最后 3 秒依次放大，倒数 3/2/1 秒依次淡出）
const DOT_MAX_SCALE = 2.3
function dotScaleFor(i) {
  const rem = upcoming.value.remaining
  const rem0 = Math.max(rem, 3)
  const span = Math.max(0.1, rem0 - 3)
  const segStart = rem0 - ((i - 1) / 3) * span
  const segEnd = rem0 - (i / 3) * span
  if (rem > segStart) return 1
  if (rem <= segEnd) return DOT_MAX_SCALE
  const progress = (segStart - rem) / Math.max(0.05, segStart - segEnd)
  return 1 + (DOT_MAX_SCALE - 1) * progress
}
function dotFading(i) {
  return upcoming.value.remaining <= i
}

// 长间奏三点：索引直接使用主窗口下发的数据（prevIndex 为真实歌词索引）
// 注意：歌曲信息合成行自起播起常驻行首，视图索引 = 真实索引 + 1
const upcomingPrev = computed(() => upcoming.value.visible ? (upcoming.value.prevIndex ?? -1) : -1)
const upcomingNext = computed(() => {
  if (!upcoming.value.visible) return -1
  const n = upcoming.value.nextIndex ?? -1
  return n < 0 ? -1 : n + 1
})
// 三点作为显示主行：放大至 active 比例（透明度由 class 控制，避免覆盖淡出）
const hintStyle = computed(() => {
  const maxScale = (desktopSettings.value.activeScale || 120) / 100
  return { transform: `scale(${maxScale.toFixed(3)})` }
})

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
  const vl = desktopSettings.value.viewLines ?? 2

  // 三点显示期间：三点作为主行(0)，下句为第 1 行；
  // 上一句全程隐藏，歌曲信息行仅在首句前的第一阶段显示，与三点组两行
  if (upcoming.value.visible) {
    const isInfo = upcoming.value.hasSongInfo && upcomingPrev.value < 0 && index === 0
    const isPrev = upcomingPrev.value >= 0 && index === upcomingPrev.value + 1
    const isNext = upcomingNext.value === index
    const showInfo = isInfo && hintStage.value === 0

    let row = -1
    if (isInfo && showInfo) row = 0
    else if (isNext && !showInfo) row = 1
    if (isPrev) row = -1

    if (row < 0 || row >= vl) return { opacity: 0, transform: 'scale(1)' }
    const t = Math.min(row / 6, 1)
    const opacity = Math.max(0.3, 1 - t * 0.7)
    const maxScale = desktopSettings.value.activeScale / 100
    const scale = row === 0
      ? maxScale
      : maxScale - (maxScale - 1) * Math.min(row, 1)
    return { opacity, transform: `scale(${scale.toFixed(3)})` }
  }

  const baseIndex = Math.max(0, currentLineIndex.value)
  const dist = index - baseIndex

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

let _resizeTimer = null
let lastResizeW = 0
let lastResizeH = 0
function requestResize(allowResize = false) {
  clearTimeout(_resizeTimer)
  nextTick(() => {
    requestAnimationFrame(() => {
      if (!scrollRef.value || !window.electronAPI?.lyricsResize) return
      const vl = desktopSettings.value.viewLines ?? 2
      const start = Math.max(0, Math.min(currentLineIndex.value, parsedLyrics.value.length - 1))
      const els = Array.from(scrollRef.value.querySelectorAll('.dl-line'))
      const range = els.slice(start, start + vl)

      // 宽度始终使用用户当前拖动的窗口宽度，程序不自动覆盖
      const width = window.innerWidth
      let height = 32
      if (upcoming.value.visible) {
        // 三点期间：只按“三点行 + 可见第二行”测量，避免出现三行
        const hintEl = scrollRef.value.querySelector('.dl-hint-line')
        let h = 32
        if (hintEl) {
          h += hintEl.offsetHeight
        }
        const secondIdx = upcomingPrev.value < 0
          ? (hintStage.value === 0 ? 0 : upcomingNext.value)
          : upcomingNext.value
        if (vl >= 2 && secondIdx >= 0 && lineRefs.value[secondIdx]) {
          h += lineRefs.value[secondIdx].offsetHeight
        }
        height = h
      } else {
        for (const el of range) {
          // 整行受 max-width 限制，需测内部原文/文字节点的真实内容宽度（含跑马灯溢出）
          const nodes = el.querySelectorAll('.dl-line__original, .dl-line__translation, .dl-line__text')
          let contentW = 0
          for (const n of nodes) {
            contentW = Math.max(contentW, n.scrollWidth)
          }
          height += el.offsetHeight
        }
        if (range.length === 0) {
          height = 32 + Math.round(desktopSettings.value.fontSize * 1.2 * 2)
        }
      }

      // 高度按行数/字号（结构/设置变化）调整；切行保持不变；宽度维持用户拖动值
      const finalW = Math.round(width)
      const computedH = Math.max(160, Math.round(height))
      const finalH = allowResize ? computedH : (lastResizeH || computedH)
      const sizeChanged = Math.abs(finalH - lastResizeH) > 2 || Math.abs(finalW - lastResizeW) > 2
      if (sizeChanged) {
        lastResizeW = finalW
        lastResizeH = finalH
        window.electronAPI.lyricsResize(finalW, finalH)
      }
      // 尺寸真实变化或调用方显式请求（结构/设置/三点出现消失）时重对齐滚动位置；
      // 纯切行（allowResize=false 且尺寸未变）不重对齐，避免打断正在进行的行滚动动画
      if (sizeChanged || allowResize) {
        _resizeTimer = setTimeout(() => {
          if (upcoming.value.visible) {
            if (upcomingPrev.value < 0) {
              hintStage.value >= 1 ? scrollToHintTop(false) : scrollToLine(0, false)
            } else if (upcomingNext.value >= 0) {
              scrollToHintTop(false)
            }
            return
          }
          const idx = currentLineIndex.value
          if (idx >= 0) {
            scrollToLine(idx, false)
          }
        }, 200)
      }
    })
  })
}

// ===== 滚动 =====
let currentScrollY = 0
let currentScrollTarget = 0

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

    const containerHeight = Math.max(mainRef.value?.clientHeight || 0, 120)
    const vl = desktopSettings.value.viewLines ?? 2
    const total = parsedLyrics.value.length
    const isLast = index >= total - 1

    const ratio = (vl >= 2 && !isLast) ? 0.33 : 0.5
    // _hintOffset 只在三点行已从 DOM 移除后补偿（此时行的 offsetTop 已不含三点高度）；
    // 三点行还在 DOM（含离场过渡期间）时 offsetTop 已包含其高度，再加会双重补偿把行推出视口
    const hintPad = hintVisible.value ? 0 : _hintOffset
    const targetScroll = lineEl.offsetTop + hintPad - containerHeight * ratio + lineEl.offsetHeight / 2

    if (!animate) {
      scrollRef.value.style.transition = 'none'
      scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
      currentScrollY = -targetScroll
      // 立即启动行内效果（布局已稳定，避免新行以居中裁切状态闪现）
      afterScrollEffect(index)
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

    // 滚动的同时立即启动行内效果（跑马灯贴左定位 / 逐字卡拉OK），消除居中裁切闪现；
    // 测量值均为布局量（offsetLeft/scrollWidth），不受滚动与缩放过渡影响
    afterScrollEffect(index)
  })
}

// 三点行对齐：窗口高度已按"三点+下一句"设定（见 requestResize），
// 直接将三点行顶对齐到视口顶部留白处，保证三点与下一句完整可见
function scrollToHintTop(animate = true, ratio = 0.5, retried = false) {
  if (!hintTopRef.value) {
    // 提示行可能尚未挂载完成，下一渲染帧重试一次
    if (!retried) nextTick(() => scrollToHintTop(animate, ratio, true))
    return
  }
  requestAnimationFrame(() => {
    const el = hintTopRef.value
    if (!el || !scrollRef.value || !mainRef.value) return
    const target = el.offsetTop - HINT_TOP_MARGIN
    currentScrollTarget = target
    scrollRef.value.style.transition = animate
      ? 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
      : 'none'
    scrollRef.value.style.transform = `translate3d(0, ${-target}px, 0)`
    currentScrollY = -target
    setTimeout(() => {
      if (scrollRef.value) scrollRef.value.style.transition = ''
    }, animate ? 550 : 0)
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
// 注意：视口 mask 会冻结 WAAPI/合成器驱动的 transform 动画（只渲染首帧），
// 因此跑马灯改用 rAF 主循环直接写 style.transform，强制 masked 内容逐帧重绘。
let _mqRafId = null
let _mqFrameSkip = 0
let _lastMask = ''
let _activeRemeasure = null  // 当前跑马灯的实时重测函数（窗口宽度变化时调用）
let _calTimer = null        // 行位缩放过渡稳定后的自校准定时器

// 复位动态羽化
function resetMarqueeMask() {
  const vp = scrollRef.value?.parentElement
  if (vp && _lastMask) {
    _lastMask = ''
    vp.style.webkitMaskImage = ''
    vp.style.maskImage = ''
  }
}

function cancelMarquee() {
  if (_mqRafId) {
    cancelAnimationFrame(_mqRafId)
    _mqRafId = null
  }
  if (_calTimer) {
    clearTimeout(_calTimer)
    _calTimer = null
  }
  _activeRemeasure = null
  // 复位循环写入的位移（仅活跃行会有值）
  document.querySelectorAll('.dl-line__text').forEach(s => { s.style.transform = '' })
  resetMarqueeMask()
}

// 窗口宽度变化（用户拖拽）：rAF 节流后重测当前跑马灯，滚动进度保持不变；
// 若无活动跑马灯（行此前未溢出），对当前活跃行重新测量，拖窄后现场启动滚动
let _vpResizeRafId = null
function handleViewportResize() {
  if (_vpResizeRafId) return
  _vpResizeRafId = requestAnimationFrame(() => {
    _vpResizeRafId = null
    if (_activeRemeasure) {
      _activeRemeasure()
    } else if (!upcoming.value.visible && !hintVisible.value && currentLineIndex.value >= 0) {
      afterScrollEffect(currentLineIndex.value)
    }
  })
}

// 跑马灯行的实际视觉缩放：与 lineStyle 的行位映射保持一致
// （正常活跃行在 row0=满档；间奏三点期间下一句在 row1=1.0）
function marqueeScaleFor(idx) {
  const maxScale = (desktopSettings.value.activeScale || 100) / 100
  if (upcoming.value.visible && upcomingNext.value === idx) return 1
  return maxScale
}

// 文本起点在"未位移"状态下的视觉 x（视口坐标）：
// inner 绕自身中心做 scale，视觉 x = innerX + (layoutX - innerX) * scale。
// offsetLeft 是布局值、不受 transform 影响，实测反推，杜绝任何居中/坐标假设漂移。
function computeNaturalVisual(span, scale) {
  const inner = span.parentElement.parentElement
  const innerX = inner.offsetLeft + inner.offsetWidth / 2
  return innerX + (span.offsetLeft - innerX) * scale
}

// 测试行在视觉上是否完整容纳（不需跑马灯）。
// 注意必须按视觉宽度（布局宽 × scale）判定：活跃行被 inner scale 放大，
// 布局放得下但视觉放不下时若不启动跑马灯，首尾会被 overflow 硬裁切断
function marqueeFitsVisually(span, scale) {
  const S = span.scrollWidth
  const vw = span.offsetParent.clientWidth
  const visLeft = computeNaturalVisual(span, scale)
  return visLeft >= -2 && visLeft + S * scale <= vw + 2
}

// 测量溢出（布局 px）。scale 必须传该行的实际视觉缩放（见 marqueeScaleFor）
function measureMarqueeSpan(p, scale) {
  const span = p.querySelector('.dl-line__text')
  if (!span) return null
  if (marqueeFitsVisually(span, scale)) {
    span.style.transform = ''
    return null
  }
  const S = span.scrollWidth
  const Wp = p.clientWidth
  return {
    span,
    overflow: S - Wp,
    scale,
    width: S,
    naturalVisual: computeNaturalVisual(span, scale)
  }
}

// 可视对齐范围（布局 px）：行首对齐“左缘+HOLD_PAD” → 行尾对齐“右缘-HOLD_PAD”。
// 基于实测 naturalVisual：静止时行首贴左、无左羽化（用户要求的"居左"），
// 滚动后左侧动态羽化由 applyMarqueeMask 按实际裁剪量给出
const HOLD_PAD = 6
const HINT_TOP_MARGIN = 14  // 三点行顶对齐视口顶部的留白
function marqueeRange(item) {
  const vw = item.span.offsetParent.clientWidth
  const visLeft = item.naturalVisual
  const visW = item.width * item.scale
  return {
    offStart: (HOLD_PAD - visLeft) / item.scale,
    offEnd: (vw - HOLD_PAD - visLeft - visW) / item.scale
  }
}

// 跑马灯位移（layout px）：行首对齐 → 行尾对齐，两端各停留 12% 保证首末可读
function marqueeOffset(progress, rng) {
  if (progress <= 0.12) return rng.offStart
  if (progress >= 0.88) return rng.offEnd
  return rng.offStart + (rng.offEnd - rng.offStart) * ((progress - 0.12) / 0.76)
}

// 动态羽化：按各行的当前视觉裁剪量写入视口 mask（对齐端裁剪量为 0 → 零羽化）
function applyMarqueeMask(items) {
  const vp = scrollRef.value?.parentElement
  if (!vp) return
  const vw = vp.clientWidth
  const FADE = vw * 0.08
  let cL = 0
  let cR = 0
  for (const it of items) {
    const visLeft = it.naturalVisual + it.off * it.scale
    const visRight = visLeft + it.width * it.scale
    cL = Math.max(cL, Math.max(0, -visLeft))
    cR = Math.max(cR, Math.max(0, visRight - vw))
  }
  const fL = Math.min(FADE, cL)
  const fR = Math.min(FADE, cR)
  let img = 'none'
  if (fL >= 1 || fR >= 1) {
    img = `linear-gradient(90deg, transparent 0px, #000 ${fL.toFixed(1)}px, #000 ${(vw - fR).toFixed(1)}px, transparent 100%)`
  }
  if (img !== _lastMask) {
    _lastMask = img
    vp.style.webkitMaskImage = img
    vp.style.maskImage = img
  }
}

function startActiveMarquee() {
  cancelMarquee()
  const idx = currentLineIndex.value
  if (idx < 0) return
  const lineEl = lineRefs.value[idx]
  if (!lineEl) return

  const duration = lineDuration(idx)
  const mqScale = marqueeScaleFor(idx)
  const items = []
  for (const sel of ['.dl-line__original', '.dl-line__translation']) {
    const p = lineEl.querySelector(sel)
    if (!p) continue
    const item = measureMarqueeSpan(p, mqScale)
    if (item) {
      item.rng = marqueeRange(item)
      items.push(item)
    }
  }
  if (!items.length) return

  const start = performance.now()
  const progressOf = (now) => Math.min(1, (now - start) / duration)

  // 窗口宽度实时重测：更新溢出量/对齐范围，保持滚动进度；不再溢出的行退出滚动
  _activeRemeasure = () => {
    const scale = marqueeScaleFor(idx)
    for (let i = items.length - 1; i >= 0; i--) {
      const it = items[i]
      if (marqueeFitsVisually(it.span, scale)) {
        it.span.style.transform = ''
        items.splice(i, 1)
        continue
      }
      it.width = it.span.scrollWidth
      it.scale = scale
      it.overflow = it.width - it.span.parentElement.clientWidth
      it.naturalVisual = computeNaturalVisual(it.span, scale)
      it.rng = marqueeRange(it)
    }
    if (!items.length) {
      cancelMarquee()
      return
    }
    const progress = progressOf(performance.now())
    for (const it of items) {
      it.off = marqueeOffset(progress, it.rng)
      it.span.style.transform = `translateX(${it.off.toFixed(1)}px)`
    }
    applyMarqueeMask(items)
  }
  // 行位缩放（inner 0.5s 过渡）稳定后自校准一次
  _calTimer = setTimeout(() => _activeRemeasure?.(), 600)

  // 立即定位到行首对齐位，避免居中裁剪状态的闪烁
  for (const it of items) {
    it.off = it.rng.offStart
    it.span.style.transform = `translateX(${it.off.toFixed(1)}px)`
  }
  applyMarqueeMask(items)

  function tick(now) {
    // 三点出现时当前行转入隐藏列，停止跑马灯（由三点编排接管滚动）
    if (upcoming.value.visible || currentLineIndex.value !== idx) {
      cancelMarquee()
      return
    }
    // 跳帧至 ~30fps：慢速横滚肉眼无差，减半 masked 重绘开销
    _mqFrameSkip ^= 1
    const progress = progressOf(now)
    if (_mqFrameSkip && progress < 1) {
      _mqRafId = requestAnimationFrame(tick)
      return
    }
    for (const it of items) {
      it.off = marqueeOffset(progress, it.rng)
      it.span.style.transform = `translateX(${it.off.toFixed(1)}px)`
    }
    applyMarqueeMask(items)
    if (progress < 1) {
      _mqRafId = requestAnimationFrame(tick)
    }
  }
  _mqRafId = requestAnimationFrame(tick)
}

function lineDuration(index) {
  const line = parsedLyrics.value[index]
  if (!line) return 5000
  const start = Number(line.time) || 0
  // 有末时间戳按首末滚动；无末时间戳按下句起始；逐字行走逐字高亮
  let dur = line.end != null && line.end > start
    ? (line.end - start) * 1000
    : (index + 1 < parsedLyrics.value.length
        ? (parsedLyrics.value[index + 1].time - start) * 1000
        : 5000)
  return Math.max(2000, dur)
}

function afterScrollEffect(index) {
  const line = parsedLyrics.value[index]
  if (line?.wordLevel && line?.segments && line.segments.length >= 2) {
    startKaraokeLoop(index)
  } else {
    startActiveMarquee()
  }
}

// ===== 逐字卡拉 OK（60fps rAF 循环，直接写 DOM，绕过 Vue） =====
let karaokeRafId = null
let songTimeBase = 0
let clockBase = 0
let clockPlaying = true

function syncKaraokeClock(songTime, playing = true) {
  songTimeBase = songTime
  clockBase = performance.now()
  clockPlaying = playing
}

function estimatedSongTime() {
  if (!clockPlaying) return songTimeBase
  return songTimeBase + (performance.now() - clockBase) / 1000
}

function stopKaraokeLoop() {
  if (karaokeRafId) {
    cancelAnimationFrame(karaokeRafId)
    karaokeRafId = null
  }
  if (_calTimer) {
    clearTimeout(_calTimer)
    _calTimer = null
  }
  _karaEntries = null
  _activeRemeasure = null
}

let _karaEntries = null  // [{ span, wordStart, wordEnd }]
let _karaFrameSkip = 0

function startKaraokeLoop(activeIndex) {
  stopKaraokeLoop()
  const line = parsedLyrics.value[activeIndex]
  if (!line || !line.wordLevel || !line.segments || line.segments.length < 2) return

  const segs = line.segments
  // 末字卡拉OK的结束基准：本行自己的结束时间（缺失时回退到下一行开始）
  const nextLineTime = line.end != null ? line.end
    : (activeIndex + 1 < parsedLyrics.value.length ? parsedLyrics.value[activeIndex + 1].time : line.time + 5)

  // 超长逐字行：滚动位置跟随逐字演唱位置（演唱点锚定在可视区 anchor 处），
  // 唱到哪滚到哪；起止仍对齐行首/行尾，句切换逻辑不变
  let mqItem = null
  const p = lineRefs.value[activeIndex]?.querySelector('.dl-line__original.word-level')
  if (p) {
    mqItem = measureMarqueeSpan(p, marqueeScaleFor(activeIndex))
  }
  const mqRng = mqItem ? marqueeRange(mqItem) : { offStart: 0, offEnd: 0 }
  const mqAnchor = 0.35
  let mqOff = mqItem ? mqRng.offStart : 0  // 起始：行首对齐左缘+HOLD_PAD
  // 逐字行文字布局与视口宽无关（word 位置不变），宽度变化只需更新溢出量与对齐范围
  _activeRemeasure = () => {
    // p 可能已随结构/行切换失效，先守卫再测量
    if (!p) return
    // 此前未溢出（无跑马灯）：拖窄后现场测量，溢出则启动滚动
    if (!mqItem) {
      mqItem = measureMarqueeSpan(p, marqueeScaleFor(activeIndex))
      if (!mqItem) return
      const r = marqueeRange(mqItem)
      mqRng.offStart = r.offStart
      mqRng.offEnd = r.offEnd
      mqOff = mqRng.offStart
      mqItem.off = mqOff
      mqItem.span.style.transform = `translateX(${mqOff.toFixed(1)}px)`
      applyMarqueeMask([mqItem])
      return
    }
    const S = mqItem.span.scrollWidth
    const Wp = p.clientWidth
    if (marqueeFitsVisually(mqItem.span, marqueeScaleFor(activeIndex))) {
      // 拖宽后不再溢出：停止滚动，复位位移与羽化（卡拉OK高亮继续）
      mqItem.span.style.transform = ''
      mqItem = null
      resetMarqueeMask()
      return
    }
    mqItem.scale = marqueeScaleFor(activeIndex)
    mqItem.overflow = S - Wp
    mqItem.naturalVisual = computeNaturalVisual(mqItem.span, mqItem.scale)
    const rng = marqueeRange(mqItem)
    mqRng.offStart = rng.offStart
    mqRng.offEnd = rng.offEnd
  }
  // 行位缩放（inner 0.5s 过渡）稳定后自校准一次
  _calTimer = setTimeout(() => _activeRemeasure?.(), 600)

  // 一次性查询 DOM，构建预计算数组（避免每帧 querySelectorAll + parseInt）
  _karaEntries = []
  const spans = document.querySelectorAll('.word-seg')
  for (const span of spans) {
    const i = parseInt(span.getAttribute('data-i'))
    if (isNaN(i) || i >= segs.length) continue
    const wordEnd = i + 1 < segs.length ? segs[i + 1].time : nextLineTime
    _karaEntries.push({ span, wordStart: segs[i].time, wordEnd, dur: wordEnd - segs[i].time })
  }

  // 逐字 span 相对文本起点的横向位置（布局 px，offsetLeft/offsetWidth 为
  // 精确布局值，不受 inner 的 transform scale 影响）
  if (mqItem && _karaEntries.length) {
    const wrapper = p.querySelector('.dl-line__text')
    const wLeft = wrapper.offsetLeft
    for (const e of _karaEntries) {
      e.left = e.span.offsetLeft - wLeft
      e.width = e.span.offsetWidth
    }
  }

  // 立即定位到行首对齐位，避免居中裁剪状态的闪烁
  if (mqItem && mqRng) {
    mqItem.off = mqRng.offStart
    mqItem.span.style.transform = `translateX(${mqRng.offStart.toFixed(1)}px)`
    applyMarqueeMask([mqItem])
  }

  _karaFrameSkip = 0

  function tick() {
    // 三点出现时当前行转入隐藏列，停止卡拉OK（由三点编排接管滚动）
    if (upcoming.value.visible || currentLineIndex.value !== activeIndex) {
      stopKaraokeLoop()
      return
    }

    // 跳帧：每 2 帧更新一次（~30fps），肉眼与 60fps 无区别，CPU 减半
    _karaFrameSkip ^= 1
    if (_karaFrameSkip) {
      karaokeRafId = requestAnimationFrame(tick)
      return
    }

    // 滚动跟随演唱点：演唱点视觉位置 = naturalVisual + (bx + off)*scale 锚定在
    // anchor*VW 处，解出 off 并 clamp 到行首/行尾对齐范围
    if (mqItem && p) {
      const nowSong = estimatedSongTime()
      let bx = 0  // 演唱点 x（布局 px，相对文本起点）
      for (const e of _karaEntries) {
        if (e.wordStart <= nowSong) {
          const fill = e.dur > 0 ? Math.min(1, (nowSong - e.wordStart) / e.dur) : 1
          bx = e.left + e.width * fill
        } else {
          break
        }
      }
      const VW = p.clientWidth
      const target = (mqAnchor * VW - mqItem.naturalVisual) / mqItem.scale - bx
      const clamped = Math.max(mqRng.offEnd, Math.min(mqRng.offStart, target))
      mqOff += (clamped - mqOff) * 0.25  // 平滑跟随，柔化逐字跳变
      mqItem.off = mqOff
      mqItem.span.style.transform = `translateX(${mqOff.toFixed(1)}px)`
      applyMarqueeMask([mqItem])
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
  window.electronAPI.onLyricsHover((inside) => {
    hovered.value = inside
  })
  window.electronAPI.onLyricsData((data) => {
    // 低频时间心跳：直接校准本地逐字时钟，避免长播放漂移
    if (data?.type === 'tick') {
      latestTime.value = Number(data.time) || 0
      syncKaraokeClock(Number(data.time) || 0, data.playing !== false)
      // 三点剩余时间：最后 1 秒淡出，与全屏“起播前收起”节奏一致
      if (upcoming.value.visible && data.remaining != null) {
        const rem = Number(data.remaining) || 0
        upcoming.value = { ...upcoming.value, remaining: rem }
      }
      // 三点锚点实时校正：state 可能滞后于行推进，tick 心跳兜底刷新锚位，
      // 防止三点滞留旧 DOM 位置被后续滚动拽出视口
      const tu = data.upcoming
      if (upcoming.value.visible && tu) {
        const prev = tu.prevIndex ?? -1
        const prevChanged = prev !== (upcoming.value.prevIndex ?? -1)
        const infoChanged = !!tu.hasSongInfo !== !!upcoming.value.hasSongInfo
        if (prevChanged || infoChanged) {
          upcoming.value = {
            ...upcoming.value,
            prevIndex: prev,
            nextIndex: tu.nextIndex ?? prev + 1,
            hasSongInfo: !!tu.hasSongInfo
          }
          hintAnchor.value = { prevIndex: prev, hasSongInfo: !!tu.hasSongInfo }
          nextTick(() => {
            if (prev < 0) {
              if (hintStage.value >= 1) scrollToHintTop(true)
            } else if (upcomingNext.value >= 0) {
              scrollToHintTop(true)
            }
          })
        }
      }
      return
    }

    // 更新设置（只在设置真正变化时才调整窗口大小）
    if (data?.settings) {
      const prevSettings = JSON.stringify(desktopSettings.value)
      desktopSettings.value = data.settings
      if (JSON.stringify(data.settings) !== prevSettings) {
        nextTick(() => requestResize(true))
      }
    }

    // 长间奏提示状态
    if (data?.upcoming) {
      const prevVisible = hintVisible.value
      upcoming.value = data.upcoming
      if (upcoming.value.visible) {
        // 三点出现：停止上一行的行内效果（其已转入隐藏列），
        // 记录位置快照，保持三点行在 DOM 中稳定
        cancelMarquee()
        stopKaraokeLoop()
        hintAnchor.value = {
          prevIndex: data.upcoming.prevIndex ?? -1,
          hasSongInfo: !!data.upcoming.hasSongInfo
        }
        hintVisible.value = true
        hintLeaving.value = false
        clearTimeout(_hintLeaveTimer)
        _hintOffset = 0
        nextTick(() => {
          const el = scrollRef.value?.querySelector('.dl-hint-line')
          _hintH = el ? el.offsetHeight : 0
        })
        // 三点行较高：窗口高度按"三点行+下一句"增长，否则三点/下一句会被挤出视口
        requestResize(true)
      } else if (prevVisible) {
        // 消失只做透明度过渡，延迟移除，布局保持稳定
        hintLeaving.value = true
        _hintOffset = _hintH
        if (_hintOffsetTimer) clearTimeout(_hintOffsetTimer)
        _hintOffsetTimer = setTimeout(() => {
          // 三点行移除后恢复窗口到正常行数高度（_hintOffset 已于 600ms 移除补偿时清零）
          requestResize(true)
        }, 900)
        if (_hintLeaveTimer) clearTimeout(_hintLeaveTimer)
        _hintLeaveTimer = setTimeout(() => {
          hintVisible.value = false
          hintLeaving.value = false
          // 三点行此刻真正从 DOM 移除：其上方内容整体上移 _hintOffset，
          // 无动画反向补偿滚动量，保持视觉位置不变；补偿完即清零，后续滚动不再受影响
          if (_hintOffset && scrollRef.value) {
            currentScrollTarget = Math.max(0, currentScrollTarget - _hintOffset)
            scrollRef.value.style.transition = 'none'
            scrollRef.value.style.transform = `translate3d(0, ${-currentScrollTarget}px, 0)`
            currentScrollY = -currentScrollTarget
            _hintOffset = 0
          }
        }, 600)
      }
    }

    // 结构更新：structure 或 state 携带 lines 且发生变化时替换整份歌词
    const payloadLines = data?.lines || data?.parsedLyrics || []
    const lyricsChanged = payloadLines.length > 0 &&
      JSON.stringify(payloadLines) !== JSON.stringify(parsedLyrics.value)
    if (payloadLines.length > 0 && lyricsChanged) {
      parsedLyrics.value = payloadLines
      hasData.value = true
    }

    // 确认已收到有效歌词结构：回 ACK，主窗口停止每秒重发
    if (parsedLyrics.value.length > 0 && window.electronAPI?.lyricsAck) {
      window.electronAPI.lyricsAck()
    }

    const newIndex = data?.currentLineIndex ?? -1
    overlap.value = data?.overlap || []

    // 结构变化（含首帧）：先定位，无动画
    if (data?.type === 'structure' || lyricsChanged) {
      // 切歌时若旧三点仍在显示/离场流程中：先复位旧三点离场状态再定位，
      // 防止残留 _hintOffset 被 scrollToLine 计入滚动目标、把新歌词推偏出视口；
      // 新结构自身带三点时保留其显隐（由前面的 upcoming 块重新锚定）
      resetHintForStructure(data?.upcoming?.visible === true)
      currentLineIndex.value = newIndex
      if (newIndex >= 0 && newIndex < parsedLyrics.value.length) {
        const activeLine = parsedLyrics.value[newIndex]
        if (activeLine && activeLine.wordLevel && activeLine.segments && activeLine.segments.length >= 2 && data.currentTime != null) {
          syncKaraokeClock(data.currentTime, data.playing !== false)
        }
        requestResize(true)
        if (upcoming.value.visible && upcomingPrev.value < 0) {
          syncFirstHint()
        } else if (upcoming.value.visible) {
          nextTick(() => scrollToHintTop(false))
        } else {
          nextTick(() => scrollToLine(newIndex, false))
        }
      } else {
        stopKaraokeLoop()
        requestResize(true)
        nextTick(() => resetScroll())
      }
      return
    }

    // 运行时状态：仅行/重叠变化
    if (newIndex !== currentLineIndex.value) {
      currentLineIndex.value = newIndex
      if (newIndex >= 0 && newIndex < parsedLyrics.value.length) {
        const activeLine = parsedLyrics.value[newIndex]
        if (activeLine && activeLine.wordLevel && activeLine.segments && activeLine.segments.length >= 2 && data.currentTime != null) {
          syncKaraokeClock(data.currentTime, data.playing !== false)
        }
        requestResize(false)
        nextTick(() => scrollToLine(newIndex, true))
      }
    }

    // 长间奏：三点行顶对齐（窗口已按三点高度增长，顶对齐保证三点完整可见）
    if (upcoming.value.visible && upcomingPrev.value < 0) {
      syncFirstHint()
    } else if (upcoming.value.visible && upcomingNext.value >= 0) {
      nextTick(() => scrollToHintTop(true))
    } else if (!upcoming.value.visible) {
      clearHintTimer()
      hintStage.value = 0
    }
  })
}

// ===== 挂载后调整窗口尺寸 =====
onMounted(() => {
  window.addEventListener('resize', handleViewportResize)
  if (window.electronAPI) {
    requestResize()
  }
})

function handleClose() {
  if (window.electronAPI) {
    window.electronAPI.lyricsClose()
  }
}

function prev() {
  window.electronAPI?.lyricsPrev?.()
}
function next() {
  window.electronAPI?.lyricsNext?.()
}
function toggleLines() {
  window.electronAPI?.lyricsSetViewLines?.(desktopSettings.value.viewLines === 1 ? 2 : 1)
}

onUnmounted(() => {
  stopKaraokeLoop()
  cancelMarquee()
  clearHintTimer()
  window.removeEventListener('resize', handleViewportResize)
  if (_vpResizeRafId) {
    cancelAnimationFrame(_vpResizeRafId)
    _vpResizeRafId = null
  }
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
  background: transparent;
  border-radius: 14px;
  overflow: hidden;
  transition: background 0.25s ease;
  -webkit-app-region: drag;
  user-select: none;
}
.lyrics-window.hovering {
  background: rgba(15, 15, 20, 0.45);
}

.lyrics-viewport {
  flex: 1;
  width: 100%;
  overflow: hidden;
  min-height: 0;
  position: relative;
  /* 横向羽化由 JS 动态写入（见 applyMarqueeMask）：
     mask 必须挂在 transform 滚动容器之外（合成层内部的 mask 在本窗口不渲染），
     且羽化宽度需跟随跑马灯位移——对齐端零羽化保证首末字符完整可见，
     裁剪端按裁剪量羽化，避免常驻渐变区吃掉行首/行尾文本。 */
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
  transition: color 0.45s ease, font-size 0.45s ease, opacity 0.45s ease;
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
}

.dl-line__translation {
  margin: 0;
  font-size: var(--dl-base-trans, 14px);
  line-height: var(--dl-lh-trans, 20px);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.22);
  transition: color 0.45s ease, font-size 0.45s ease, opacity 0.45s ease;
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
/* 常驻注释槽：始终预留高度，有对白/注释时淡入内容 */
.dl-line__annotation {
  margin: 0;
  min-height: calc(var(--dl-base-original, 24px) * 0.7);
  font-size: calc(var(--dl-base-original, 24px) * 0.58);
  line-height: calc(var(--dl-base-original, 24px) * 0.7);
  font-weight: 400;
  color: rgba(255, 255, 255, 0.55);
  text-shadow:
    -1px -1px 0 rgba(0, 0, 0, 0.25),
     1px -1px 0 rgba(0, 0, 0, 0.25),
    -1px  1px 0 rgba(0, 0, 0, 0.25),
     1px  1px 0 rgba(0, 0, 0, 0.25);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: opacity 0.35s ease;
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
  overflow: hidden;
  white-space: nowrap;
  text-overflow: clip;
}

/* 词分组：桌面歌词不换行（溢出走跑马灯），分组仅保持与全屏页结构一致 */
.word-group {
  display: inline-block;
}

.word-seg {
  position: relative;
  display: inline-block;
  white-space: nowrap;
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

/* 长间奏"即将开唱"三点 */
.dl-hint-line {
  text-align: center;
  padding: 6px 0;
  /* 与含翻译+注释槽的歌词行同高 */
  min-height: calc(12px + var(--dl-lh-original, 38px) + var(--dl-lh-trans, 20px) + var(--dl-base-original, 24px) * 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: calc(var(--dl-base-original, 24px) * 0.6);
  color: rgba(255, 255, 255, 0.6);
  user-select: none;
  transition: opacity 0.3s ease;
}
.dl-hint-dot {
  display: inline-block;
  transform-origin: center;
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.dl-hint-dot--fade {
  opacity: 0;
}
.dl-hint-line.hint-hidden {
  opacity: 0;
}
.dl-hint-line.hint-leaving {
  opacity: 0;
}

/* 悬浮控件栏：鼠标进入歌词区域时显示 */
.dl-controls {
  position: fixed;
  top: 4px;
  left: 50%;
  transform: translateX(-50%) translateY(-14px);
  display: flex;
  gap: 4px;
  padding: 4px 6px;
  background: rgba(15, 15, 20, 0.62);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease, transform 0.25s ease;
  z-index: 100;
  -webkit-app-region: no-drag;
}
.dl-controls.visible {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
  pointer-events: auto;
}
.dl-btn {
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  min-width: 30px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
}
.dl-btn:hover { background: rgba(255, 255, 255, 0.22); }
.dl-btn--close:hover { background: #e81123; }
</style>
