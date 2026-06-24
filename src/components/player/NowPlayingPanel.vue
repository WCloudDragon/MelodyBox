<template>
  <!-- 窗口控制器风格关闭按钮 — Teleport 到 body 确保独立层级 -->
  <Teleport to="body">
    <Transition name="np-close-btn-fade">
      <button v-if="visible" class="np-close-btn" @click.stop="$emit('close')" title="关闭全屏歌词">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round">
          <polyline points="1.5,4.5 6,8.5 10.5,4.5"/>
        </svg>
      </button>
    </Transition>
  </Teleport>

  <transition name="panel-slide" @after-leave="$emit('afterLeave')">
    <div v-if="visible" class="np-overlay" @click.self="$emit('close')">
      <!-- 模糊背景 -->
      <div class="np-bg">
        <img v-if="currentTrack?.cover" :src="currentTrack.cover" class="np-bg__img" />
      </div>

      <!-- 无歌曲时的提示 -->
      <div v-if="!currentTrack" class="np-empty">
        <p class="np-empty__icon">🎵</p>
        <p class="np-empty__text">暂无播放中的歌曲</p>
      </div>

      <!-- Apple Music 风格布局 -->
      <template v-else>
        <div class="np-layout" :style="lyricsVars">
          <!-- 左半屏：封面 -->
          <div class="np-layout__cover">
            <div class="cover-artwork" ref="coverArtRef" :class="{ animate: animating }">
              <img v-if="currentTrack?.cover" :src="currentTrack.cover" class="cover-artwork__img" />
              <div v-else class="cover-artwork__empty">
                <el-icon size="64"><Headset /></el-icon>
              </div>
            </div>
          </div>

          <!-- 右半屏：歌词 -->
          <div class="np-layout__lyrics" ref="mainRef" @wheel.prevent="onLyricsWheel">
            <div v-if="!hasLyrics" class="lyrics-empty-state">
              <p class="lyrics-empty-state__icon">🎵</p>
              <p class="lyrics-empty-state__text">未找到内嵌歌词</p>
            </div>

            <div v-else class="lyrics-scroll" ref="scrollRef">
              <div
                v-for="(line, index) in parsedLyrics"
                :key="index"
                class="lyric-line"
                :class="{
                  active: index === currentLineIndex,
                  sung: currentLineIndex >= 0 && index < currentLineIndex,
                  upcoming: index > currentLineIndex,
                  'has-translation': line.translation,
                  'is-word-level': line.wordLevel
                }"
                :ref="el => setLineRef(el, index)"
                :style="lineStyle(index)"
                @click="seekToLine(line.time)"
              >
                <div class="lyric-line__inner">
                  <p v-if="line.wordLevel && line.segments" class="lyric-line__original word-level">
                    <span
                      v-for="(seg, si) in line.segments"
                      :key="si"
                      class="word-seg"
                      :data-word="seg.text"
                    >{{ seg.text }}</span>
                  </p>
                  <p v-else class="lyric-line__original">{{ line.original }}</p>
                  <p v-if="line.translation" class="lyric-line__translation">{{ line.translation }}</p>
                </div>
              </div>
              <div class="lyrics-padding"></div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, nextTick, inject, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { useSettingsStore } from '@/stores/settings'
import { parseLRC, getCurrentLyricIndex } from '@/utils/format'

const props = defineProps({ visible: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'afterLeave', 'flyComplete'])

const player = usePlayerStore()
const settings = useSettingsStore()
const { currentTrack, currentTime } = storeToRefs(player)
const { lyricsFontSize, lyricsFontWeight } = storeToRefs(settings)
const { lyricsTransScale, lyricsActiveScale } = storeToRefs(settings)
const { enableLyricsBlur, enableDominoScroll, enableWordLift, wordAnimFps } = storeToRefs(settings)
const coverOriginRect = inject('coverOriginRect', ref(null))

const mainRef = ref(null)
const scrollRef = ref(null)
const lineRefs = ref({})
const currentLineIndex = ref(-1)
const coverArtRef = ref(null)
const animating = ref(false)
const windowWidth = ref(window.innerWidth)

function onResize() {
  windowWidth.value = window.innerWidth
  // 强制触发歌词行换行重新计算（CSS 变量依赖窗口宽度）
  requestAnimationFrame(() => {
    if (scrollRef.value) {
      void scrollRef.value.offsetHeight
    }
    // 布局重算后重新居中当前行，避免偏移出视口
    nextTick(() => {
      if (!props.visible || currentLineIndex.value < 0) return
      if (isUserScrolling.value) exitUserScrollMode()
      scrollToLine(currentLineIndex.value, false)
    })
  })
}
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

function setLineRef(el, index) {
  if (el) lineRefs.value[index] = el
}

// ==================== 封面飞行动画（独立 fixed 元素，脱离面板布局） ====================

let flyerCleanup = null
let lyricsScrollCleanup = null
let wordAnimRaf = null
let prevLineIndex = -1
let targetScrollPos = 0   // 追踪上一次目标位置，避免从 CSS transform（含 translateZ(0)）读脏值
let currentScrollY = 0    // 追踪 scrollRef 当前的 transform Y 值，避免解析 computedStyle（2D/3D matrix 格式不一致）
let smoothAnimTarget = -1 // 正在执行的平滑动画目标行；-1 表示无动画
const isUserScrolling = ref(false)   // 用户正在手动滚动歌词
let userScrollTimer = null           // 5秒空闲定时器


function cleanupFlyer() {
  if (flyerCleanup) { flyerCleanup(); flyerCleanup = null }
}

const FLY_DURATION = 600
const FLY_EASING = [0.2, 0.9, 0.3, 1.0]
const COVER_SHADOW = { y: 20, blur: 60, opacity: 0.5 }

/** cubic-bezier 缓动，与面板过渡曲线一致 */
function easeCubicBezier(t, x1, y1, x2, y2) {
  if (t <= 0) return 0
  if (t >= 1) return 1
  let lo = 0, hi = 1
  for (let i = 0; i < 12; i++) {
    const mid = (lo + hi) / 2
    const x = 3 * (1 - mid) ** 2 * mid * x1 + 3 * (1 - mid) * mid ** 2 * x2 + mid ** 3
    if (x < t) lo = mid
    else hi = mid
  }
  const u = (lo + hi) / 2
  return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u ** 2 * y2 + u ** 3
}

/**
 * 创建飞行分身。渲染在目标尺寸（高分辨率），通过反向缩放模拟起始的小尺寸，
 * 避免 background-size:cover 在 48px 下渲染低分辨率位图再 scale 放大导致的模糊。
 */
function flyCover(fromRect, toRect, fromBR, toBR, { shadowFrom = 0, shadowTo = 1 } = {}) {
  const coverUrl = currentTrack.value?.cover
  if (!coverUrl) return Promise.resolve()

  const toW = toRect.width, toH = toRect.height
  const fromW = fromRect.width, fromH = fromRect.height

  const fromCX = fromRect.left + fromW / 2
  const fromCY = fromRect.top + fromH / 2
  const toCX = toRect.left + toW / 2
  const toCY = toRect.top + toH / 2

  // 以目标尺寸渲染，初始阶段反向缩放和偏移以匹配起始视觉
  const initDX = fromCX - toCX
  const initDY = fromCY - toCY
  const initSX = fromW / toW
  const initSY = fromH / toH
  const startBR = parseFloat(fromBR)
  const endBR = parseFloat(toBR)
  const clipStartBR = startBR / initSX
  const clipEndBR = endBR

  const wrapper = document.createElement('div')
  Object.assign(wrapper.style, {
    position: 'fixed', zIndex: '10000', pointerEvents: 'none',
    left: toRect.left + 'px', top: toRect.top + 'px',
    width: toW + 'px', height: toH + 'px',
    transformOrigin: 'center center',
    willChange: 'transform',
    transform: `translate3d(${initDX}px, ${initDY}px, 0) scale(${initSX}, ${initSY})`
  })

  const shadowEl = document.createElement('div')
  Object.assign(shadowEl.style, {
    position: 'absolute', inset: '0', pointerEvents: 'none',
    borderRadius: `${clipStartBR}px`, boxShadow: 'none', zIndex: '0'
  })

  const imgEl = document.createElement('div')
  Object.assign(imgEl.style, {
    position: 'absolute', inset: '0', zIndex: '1',
    backgroundImage: `url(${coverUrl})`, backgroundSize: 'cover', backgroundPosition: 'center',
    clipPath: `inset(0 round ${clipStartBR}px)`,
    willChange: 'clip-path'
  })

  wrapper.appendChild(shadowEl)
  wrapper.appendChild(imgEl)
  document.body.appendChild(wrapper)
  wrapper.getBoundingClientRect()

  const [bx1, by1, bx2, by2] = FLY_EASING

  return new Promise(resolve => {
    const startTime = performance.now()
    let rafId

    const finish = () => {
      cancelAnimationFrame(rafId)
      wrapper.remove()
      resolve()
    }

    const tick = () => {
      const elapsed = performance.now() - startTime
      const t = Math.min(elapsed / FLY_DURATION, 1)
      const p = easeCubicBezier(t, bx1, by1, bx2, by2)

      const sx = initSX + (1 - initSX) * p
      const sy = initSY + (1 - initSY) * p
      const dx = initDX * (1 - p)
      const dy = initDY * (1 - p)
      const visualBR = startBR + (endBR - startBR) * p
      const clipBR = visualBR / sx

      wrapper.style.transform = `translate3d(${dx}px, ${dy}px, 0) scale(${sx}, ${sy})`
      imgEl.style.clipPath = `inset(0 round ${clipBR}px)`

      const sh = COVER_SHADOW
      const shadowP = shadowFrom + (shadowTo - shadowFrom) * p
      shadowEl.style.borderRadius = `${clipBR}px`
      shadowEl.style.boxShadow = shadowP > 0.01
        ? `0 ${(sh.y / sx) * shadowP}px ${(sh.blur / sx) * shadowP}px rgba(0,0,0,${sh.opacity * shadowP})`
        : 'none'

      if (t < 1) {
        rafId = requestAnimationFrame(tick)
      } else {
        finish()
      }
    }

    rafId = requestAnimationFrame(tick)
    flyerCleanup = () => {
      cancelAnimationFrame(rafId)
      wrapper.remove()
      flyerCleanup = null
    }
  })
}

/** 面板展开：封面从播放栏飞入 */
async function flyCoverIn() {
  cleanupFlyer()
  const origin = coverOriginRect?.value
  if (!origin || !coverArtRef.value) return

  // 获取面板封面的最终视口位置（补偿面板滑动）
  const artEl = coverArtRef.value
  const overlayEl = artEl.closest('.np-overlay')
  const cs = getComputedStyle(overlayEl)
  const m = new DOMMatrixReadOnly(cs.transform)
  const panelSlideY = m.m42
  const raw = artEl.getBoundingClientRect()
  const targetRect = {
    left: raw.left, top: raw.top - panelSlideY,
    width: raw.width, height: raw.height
  }

  // 面板封面先藏起来
  artEl.style.opacity = '0'

  await flyCover(
    { left: origin.left, top: origin.top, width: origin.width, height: origin.height },
    targetRect,
    '5px',  // 播放栏封面圆角
    '12px'  // 面板封面圆角
  )

  // 飞行结束：显示面板封面
  artEl.style.opacity = ''
  flyerCleanup = null
}

/** 面板关闭：封面从面板飞回 */
async function flyCoverOut() {
  cleanupFlyer()
  const origin = coverOriginRect?.value
  if (!origin || !coverArtRef.value) {
    emit('flyComplete')
    return
  }

  const artEl = coverArtRef.value
  const srcRect = artEl.getBoundingClientRect()

  // 面板封面先藏
  artEl.style.opacity = '0'

  await flyCover(
    { left: srcRect.left, top: srcRect.top, width: srcRect.width, height: srcRect.height },
    { left: origin.left, top: origin.top, width: origin.width, height: origin.height },
    '12px',
    '5px',
    { shadowFrom: 1, shadowTo: 0 }
  )

  flyerCleanup = null
  emit('flyComplete')
}

// ==================== 逐字歌词（RAF 驱动：卡拉 OK + 时间戳同步抬升） ====================

const WORD_LIFT_PX = 3

// 已播行逐字歌词从全白渐变回暗淡色（CSS transition 驱动，零 JS 动画开销）
function fadeOutWordSegs(lineIndex) {
  const line = parsedLyrics.value[lineIndex]
  if (!line) return
  if (!line._wordSegEls) {
    const lineEl = lineRefs.value[lineIndex]
    if (!lineEl) return
    line._wordSegEls = [...lineEl.querySelectorAll('.word-seg')]
  }
  const els = line._wordSegEls
  if (!els || els.length === 0) return

  els.forEach(el => {
    el.classList.remove('word-seg--singing', 'word-seg--sung')
    el.style.removeProperty('--word-pct')
    el.style.color = 'rgba(255,255,255,0.25)'
    el.style.transform = ''
  })
  delete line._wordSegEls
}

function segProgress(segments, idx, time, nextLineTime = 0) {
  const seg = segments[idx]
  if (!seg) return 0
  if (time < seg.time) return 0
  const next = segments[idx + 1]
  let duration
  if (next) {
    duration = next.time - seg.time
  } else if (nextLineTime > seg.time) {
    duration = nextLineTime - seg.time
  } else {
    duration = 0.8
  }
  const raw = ((time - seg.time) / Math.max(duration, 0.08)) * 100
  return Math.max(0, Math.min(100, raw))
}

function updateWordSegStyles(lineIndex, time) {
  const line = parsedLyrics.value[lineIndex]
  if (!line?.segments) return

  const nextLine = parsedLyrics.value[lineIndex + 1]
  const nextLineTime = nextLine ? nextLine.time : 0

  for (let i = 0; i < line.segments.length; i++) {
    const el = line._wordSegEls?.[i]
    if (!el) continue
    const state = segState(line.segments, i, time, nextLineTime)
    const pct = segProgress(line.segments, i, time, nextLineTime)

    if (state === 'sung') {
      el.classList.remove('word-seg--singing')
      el.classList.add('word-seg--sung')
      el.style.removeProperty('--word-pct')
      el.style.transform = enableWordLift.value ? `translate3d(0, ${-WORD_LIFT_PX}px, 0)` : ''
    } else if (state === 'singing') {
      el.classList.add('word-seg--singing')
      el.classList.remove('word-seg--sung')
      el.style.setProperty('--word-pct', Math.round(pct))
      const lift = enableWordLift.value ? -WORD_LIFT_PX * (pct / 100) : 0
      el.style.transform = lift ? `translate3d(0, ${lift}px, 0)` : ''
    } else {
      el.classList.remove('word-seg--singing', 'word-seg--sung')
      el.style.removeProperty('--word-pct')
      el.style.transform = ''
    }
  }
}

/** 仅更新 transform 上浮位移，每帧调用确保平滑；class/CSS var 走 updateWordSegStyles 降频 */
function updateWordSegTransforms(lineIndex, time) {
  const line = parsedLyrics.value[lineIndex]
  if (!line?.segments || !line._wordSegEls) return

  const nextLine = parsedLyrics.value[lineIndex + 1]
  const nextLineTime = nextLine ? nextLine.time : 0

  for (let i = 0; i < line.segments.length; i++) {
    const el = line._wordSegEls[i]
    if (!el) continue
    const state = segState(line.segments, i, time, nextLineTime)
    if (state === 'sung') {
      el.style.transform = `translate3d(0, ${-WORD_LIFT_PX}px, 0)`
    } else if (state === 'singing') {
      const pct = segProgress(line.segments, i, time, nextLineTime)
      const lift = -WORD_LIFT_PX * (pct / 100)
      el.style.transform = `translate3d(0, ${lift}px, 0)`
    }
  }
}

function startWordAnimLoop() {
  if (wordAnimRaf) return
  let lastStyleTime = 0
  const loop = () => {
    const idx = currentLineIndex.value
    const line = parsedLyrics.value[idx]
    const fpz = wordAnimFps.value
    if (!props.visible || idx < 0 || !line?.wordLevel || fpz <= 0) {
      wordAnimRaf = null
      return
    }
    // 首次进入该行时缓存 .word-seg 元素引用，避免每帧 querySelectorAll
    if (!line._wordSegEls) {
      const lineEl = lineRefs.value[idx]
      line._wordSegEls = lineEl ? [...lineEl.querySelectorAll('.word-seg')] : []
    }

    const now = performance.now()
    const interval = 1000 / fpz
    // CSS var / class（卡拉OK扫过）按用户设定帧率节流
    if (now - lastStyleTime >= interval) {
      updateWordSegStyles(idx, player.getLiveTime())
      lastStyleTime = now
    }
    // transform 上浮位移每 RAF 帧更新，与显示器刷新率同步，保证丝滑
    if (enableWordLift.value) {
      updateWordSegTransforms(idx, player.getLiveTime())
    }
    wordAnimRaf = requestAnimationFrame(loop)
  }
  wordAnimRaf = requestAnimationFrame(loop)
}

function stopWordAnimLoop() {
  if (wordAnimRaf) { cancelAnimationFrame(wordAnimRaf); wordAnimRaf = null }
}

function segState(segments, idx, time, nextLineTime = 0) {
  const seg = segments[idx]
  if (!seg) return ''
  if (time < seg.time) return ''
  const next = segments[idx + 1]
  let endTime
  if (next) {
    endTime = next.time
  } else if (nextLineTime > seg.time) {
    endTime = nextLineTime
  } else {
    endTime = seg.time + 1.5
  }
  return time >= endTime ? 'sung' : 'singing'
}

// 跳转到指定歌词行的播放时间
function seekToLine(time) {
  exitUserScrollMode()
  if (player.duration > 0) {
    player.seek((time / player.duration) * 100)
  }
}

// ==================== 用户滚轮滚动歌词 ====================
function exitUserScrollMode() {
  isUserScrolling.value = false
  if (scrollRef.value) scrollRef.value.style.transition = ''
  if (userScrollTimer) { clearTimeout(userScrollTimer); userScrollTimer = null }
}

function resetUserScroll() {
  exitUserScrollMode()
  // 同步用户滚动到的实际位置，使 scrollToLine 感知真实距离从而走平滑动画分支
  targetScrollPos = -currentScrollY
  scrollToLine(currentLineIndex.value, true)
}

function onLyricsWheel(e) {
  if (!scrollRef.value || !mainRef.value) return
  e.preventDefault()

  // 进入用户滚动模式
  if (!isUserScrolling.value) {
    isUserScrolling.value = true
    scrollRef.value.style.transition = 'transform 0.15s ease-out'
  }
  if (userScrollTimer) clearTimeout(userScrollTimer)

  // 从当前 computed transform 读取位置
  const currentTransform = getComputedStyle(scrollRef.value).transform
  const match = currentTransform.match(/matrix\(1,\s*0,\s*0,\s*1,\s*0,\s*(-?[\d.]+)\)/)
  const currentY = match ? parseFloat(match[1]) : -targetScrollPos

  let newY = currentY - e.deltaY * 2

  // 边界钳制
  const contentHeight = scrollRef.value.scrollHeight
  const containerHeight = mainRef.value.clientHeight
  const minY = -(contentHeight - containerHeight) - 20
  const maxY = 20
  newY = Math.max(minY, Math.min(maxY, newY))

  scrollRef.value.style.transform = `translate3d(0, ${newY}px, 0)`
  currentScrollY = newY

  // 5秒无操作后自动回位
  userScrollTimer = setTimeout(resetUserScroll, 5000)
}

function lineStyle(index) {
  const dist = index - currentLineIndex.value
  const absDist = Math.abs(dist)
  const t = Math.min(absDist / 6, 1)
  const opacity = isUserScrolling.value ? 1 : Math.max(0.12, 1 - t * 0.88)

  // Apple Music 风格模糊：越远离当前行越模糊，用户滚动时取消模糊
  const blurAmount = (isUserScrolling.value || !enableLyricsBlur.value) ? 0 : Math.min(absDist * 1.5, 6)
  const filter = blurAmount > 0.5 ? `blur(${blurAmount}px)` : 'none'

  return { opacity, filter }
}

const parsedLyrics = computed(() => {
  const raw = currentTrack.value?.lyrics
  if (!raw) return []
  return parseLRC(raw)
})

const hasLyrics = computed(() => parsedLyrics.value.length > 0)

// 从设置中按比例计算各字号级别，利用 MiSans VF 可变轴字重
const lyricsVars = computed(() => {
  const base = lyricsFontSize.value
  const trans = Math.round(base * lyricsTransScale.value / 100)
  const active = lyricsActiveScale.value / 100
  const activeFont = Math.round(base * active)
  // 以活跃行（字号更大、容纳更少）为瓶颈，计算两行各自的 em max-width，确保换行位置绝对一致
  const availWidth = Math.max(200, windowWidth.value * 0.5 - 72)
  const activeChars = Math.max(5, Math.floor(availWidth / (activeFont + 1)))
  // +4px 安全余量，统一吸收亚像素渲染波动，避免活跃/非活跃态切换时边界字符闪烁
  const safetyPx = 4
  const nonActiveMaxEm = (activeChars * (base + 1) + safetyPx) / base
  const activeMaxEm = (activeChars * (activeFont + 1) + safetyPx) / activeFont
  // 翻译行同理，基于翻译活跃字号计算
  const transActiveFont = Math.round(trans * active)
  const transActiveChars = Math.max(3, Math.floor(availWidth / (transActiveFont + 1)))
  const transNonActiveMaxEm = (transActiveChars * (trans + 1) + safetyPx) / trans
  const transActiveMaxEm = (transActiveChars * (transActiveFont + 1) + safetyPx) / transActiveFont
  return {
    '--lyrics-base-original': base + 'px',
    '--lyrics-base-trans': trans + 'px',
    '--lyrics-active-original': Math.round(base * active) + 'px',
    '--lyrics-active-trans': Math.round(trans * active) + 'px',
    '--lyrics-weight': lyricsFontWeight.value,
    '--lyrics-ch-limit': nonActiveMaxEm + 'em',
    '--lyrics-active-ch-limit': activeMaxEm + 'em',
    '--lyrics-trans-ch-limit': transNonActiveMaxEm + 'em',
    '--lyrics-trans-active-ch-limit': transActiveMaxEm + 'em'
  }
})

// 面板打开时初始化歌词定位 + 封面飞行动画
watch(() => props.visible, async (val) => {
  if (val) {
    await nextTick()
    await nextTick()
    flyCoverIn()
    if (!hasLyrics.value || !scrollRef.value) return
    const idx = getCurrentLyricIndex(parsedLyrics.value, player.getLiveTime())
    currentLineIndex.value = idx
    if (idx >= 0) {
      scrollToLine(idx, false)
      await nextTick()
      if (parsedLyrics.value[idx]?.wordLevel) startWordAnimLoop()
    }
  } else {
    flyCoverOut()
    stopWordAnimLoop()
    // 清除逐字缓存的 DOM 引用，否则重新打开面板时会复用已销毁的旧元素
    for (const line of parsedLyrics.value) {
      delete line._wordSegEls
    }
    if (lyricsScrollCleanup) { lyricsScrollCleanup(); lyricsScrollCleanup = null }
    exitUserScrollMode()
    targetScrollPos = 0
    prevLineIndex = -1
  }
})

// 播放中行切换
watch(currentTime, async (time) => {
  if (!props.visible || !hasLyrics.value || !scrollRef.value) return

  const idx = getCurrentLyricIndex(parsedLyrics.value, time)
  if (idx !== currentLineIndex.value) {
    const oldIdx = currentLineIndex.value
    stopWordAnimLoop()
    currentLineIndex.value = idx
    // 旧行逐字高亮渐变消失（无论是否在滚动模式都要执行）
    if (oldIdx >= 0 && parsedLyrics.value[oldIdx]?.wordLevel) fadeOutWordSegs(oldIdx)
    if (idx >= 0) {
      if (isUserScrolling.value) {
        // 用户滚轮滚动中：不滚动面板，但需要为新行启动逐字动画
        await nextTick()
        if (parsedLyrics.value[idx]?.wordLevel) startWordAnimLoop()
        return
      }
      await nextTick()
      scrollToLine(idx, true)
      await nextTick()
      if (parsedLyrics.value[idx]?.wordLevel) startWordAnimLoop()
    } else if (parsedLyrics.value.length > 0) {
      // 进度条移动到首句之前（-1），滚动到第一句等待
      await nextTick()
      if (!isUserScrolling.value) scrollToLine(0, true)
    }
  }
})

const STAGGER_MS = 38
const STAGGER_DURATION = 480
const MAX_STAGGER_LINES = 18

function scrollToLine(index, animate = true) {
  if (index < 0 || !scrollRef.value || !mainRef.value) return
  const lineEl = lineRefs.value[index]
  if (!lineEl) return

  const containerHeight = mainRef.value.clientHeight
  const targetScroll = lineEl.offsetTop - containerHeight / 2 + lineEl.offsetHeight / 2
  const scrollDelta = targetScroll - targetScrollPos

  // 平滑动画进行中：跳过相邻位置的小范围滚动，避免打断大跨度动画
  // 不更新 targetScrollPos（保持为平滑动画起点），动画完成后由下次自然播放触发多米诺过渡
  // 但仅差1行时不跳过：如 seek 到 A 句尾部 → A 即播完切 B → B 应马上多米诺到位
  if (smoothAnimTarget >= 0 && Math.abs(scrollDelta) <= containerHeight && animate
      && Math.abs(index - smoothAnimTarget) > 1) {
    prevLineIndex = index
    return
  }

  // 1. 取消上一次未完成的清理定时器，重置所有行残留内联样式
  if (lyricsScrollCleanup) { lyricsScrollCleanup(); lyricsScrollCleanup = null }
  smoothAnimTarget = -1

  const totalLines = parsedLyrics.value.length
  // 重置行级 transform（不清除 opacity/filter transition，保留 CSS 中的过渡）
  for (let i = 0; i < totalLines; i++) {
    const el = lineRefs.value[i]
    if (el) { el.style.transform = '' }
  }
  scrollRef.value.style.transition = 'none'
  void scrollRef.value.offsetHeight  // 强制重排

  // 2. 用稳定变量计算差值，避免 DOM 中间态 / translateZ(0) 污染
  const absScrollDelta = Math.abs(scrollDelta)
  // 大跨度已由平滑动画接管，多米诺仅处理 ≤容器高度的中小滚动，无需反转
  const sign = Math.sign(scrollDelta)
  const visualDelta = sign * Math.min(absScrollDelta, containerHeight * 0.3)
  const isInitial = prevLineIndex < 0
  const branch = !animate ? 'instant'
    : (isInitial ? 'initial' : (Math.abs(scrollDelta) > containerHeight ? 'smooth' : 'domino'))
  targetScrollPos = targetScroll

  // 大跨度（>容器高度）用平滑滚动，避免闪现；中小跨度用多米诺
  const useDomino = enableDominoScroll.value && !isInitial && Math.abs(scrollDelta) > 0.5 && totalLines > 1 && Math.abs(scrollDelta) <= containerHeight
  if (animate && useDomino) {
    // 多米诺分支：先瞬跳 scrollRef，再由行级联动画接管视觉效果
    scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
    currentScrollY = -targetScroll
    const forward = index > prevLineIndex

    // 所有行偏移到反向位置（只禁用 transform 过渡，保留 opacity/filter 过渡）
    for (let i = 0; i < totalLines; i++) {
      const el = lineRefs.value[i]
      if (!el) continue
      el.style.transition = 'transform 0s, opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0), filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
      el.style.transform = `translate3d(0, ${visualDelta}px, 0)`
    }
    // 读 computedStyle 强制浏览器 commit transform 起始值
    const csAfterOffset = getComputedStyle(lineEl).transform
    void csAfterOffset

    for (let i = 0; i < totalLines; i++) {
      const el = lineRefs.value[i]
      if (!el) continue
      // staggerIdx 基于与级联起点的距离；大跨度 seek 时目标行 delay 仅 ~114ms
      const cascadeOrigin = forward
        ? Math.max(0, index - 3)                         // 前进：从目标上方3行开始向下级联
        : Math.min(totalLines - 1, index + 3)            // 后退：从目标下方3行开始向上级联
      const staggerIdx = forward
        ? Math.min(Math.max(0, i - cascadeOrigin), MAX_STAGGER_LINES)
        : Math.min(Math.max(0, cascadeOrigin - i), MAX_STAGGER_LINES)
      const delay = staggerIdx * STAGGER_MS / 1000
      el.style.transition = `transform ${STAGGER_DURATION}ms cubic-bezier(0.2, 0.9, 0.3, 1.0) ${delay}s, opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0), filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0)`
      el.style.transform = 'translate3d(0, 0, 0)'
    }

    const maxStagger = MAX_STAGGER_LINES * STAGGER_MS
    const totalDuration = STAGGER_DURATION + maxStagger + 60

    const cleanup = () => {
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (el) { el.style.transform = ''; el.style.transition = '' }
      }
      if (scrollRef.value) { scrollRef.value.style.willChange = ''; scrollRef.value.style.transition = '' }
      lyricsScrollCleanup = null
    }
    const timer = setTimeout(cleanup, totalDuration)
    lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
  } else if (animate) {
    const scrollIsLarge = Math.abs(scrollDelta) > containerHeight
    if (scrollIsLarge) {
      // 大跨度跳转（> 容器高度）：Web Animations API 避免闪现
      smoothAnimTarget = index
      const fromTransform = `translate3d(0, ${currentScrollY}px, 0)`
      const toTransform = `translate3d(0, ${-targetScroll}px, 0)`
      const anim = scrollRef.value.animate(
        [{ transform: fromTransform }, { transform: toTransform }],
        { duration: 800, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
      )
      anim.onfinish = () => {
        scrollRef.value.style.transform = toTransform
        anim.cancel()
        currentScrollY = -targetScroll
        smoothAnimTarget = -1
        scrollRef.value.style.willChange = ''
        lyricsScrollCleanup = null
      }
      lyricsScrollCleanup = () => {
        anim.cancel()
        smoothAnimTarget = -1
        lyricsScrollCleanup = null
      }
    } else {
      // 关闭多米诺时：CSS transition 简单平滑滚动，零 JS 动画开销
      scrollRef.value.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
      scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
      currentScrollY = -targetScroll
      const cleanup = () => {
        if (scrollRef.value) scrollRef.value.style.transition = ''
        lyricsScrollCleanup = null
      }
      const timer = setTimeout(cleanup, 550)
      lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
    }
  } else {
    scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
    currentScrollY = -targetScroll
    for (let i = 0; i < totalLines; i++) {
      const el = lineRefs.value[i]
      if (el) { el.style.transition = ''; el.style.transform = '' }
    }
    if (scrollRef.value) { scrollRef.value.style.willChange = ''; scrollRef.value.style.transition = '' }
    lyricsScrollCleanup = null
  }

  prevLineIndex = index
}

watch(() => currentTrack.value?.path, () => {
  currentLineIndex.value = -1
  stopWordAnimLoop()
  targetScrollPos = 0
  prevLineIndex = -1
  if (scrollRef.value) { scrollRef.value.style.transform = 'translate3d(0, 0, 0)'; currentScrollY = 0 }
})

onBeforeUnmount(() => {
  stopWordAnimLoop()
  cleanupFlyer()
  if (lyricsScrollCleanup) { lyricsScrollCleanup(); lyricsScrollCleanup = null }
})
</script>

<style scoped>
/* ===== 覆盖面板 ===== */
.np-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  color: #fff;
  overflow: hidden;
}

/* 模糊背景 */
.np-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.np-bg__img {
  width: 120%;
  height: 120%;
  position: absolute;
  top: -10%;
  left: -10%;
  object-fit: cover;
  filter: blur(60px) brightness(0.5);
  will-change: filter;
}
.np-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.6) 100%);
}

/* 窗口控制器风格关闭按钮 */
.np-close-btn {
  position: fixed;
  top: 0;
  left: 0;
  width: 46px;
  height: 36px;
  border: none;
  background: none;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1002;
  transition: background 0.15s, color 0.15s;
  -webkit-app-region: no-drag;
  pointer-events: auto;
}
.np-close-btn:hover {
  background: rgba(255,255,255,0.15);
  color: #fff;
}

/* 无歌曲提示 */
.np-empty {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  user-select: none;
}
.np-empty__icon { font-size: 48px; }
.np-empty__text { font-size: 18px; font-weight: 500; color: rgba(255,255,255,0.8); }

/* ===== Apple Music 布局 ===== */
.np-layout {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  width: 100%;
  padding: 0 40px 72px;
  gap: 0;
  overflow: hidden;
  min-height: 0;
}

/* 左半屏：封面 — 占视口左 50%，封面在区域内垂直水平居中 */
.np-layout__cover {
  width: 50%; flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 32px;
  user-select: none;
}
.cover-artwork {
  width: clamp(260px, 26vw, 520px);
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  transform: translateZ(0);
  backface-visibility: hidden;
}
.cover-artwork.animate {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.cover-artwork.no-transition {
  transition: none !important;
}
.cover-artwork__img { width: 100%; height: 100%; object-fit: cover; }
.cover-artwork__empty {
  width: 100%; height: 100%;
  background: rgba(255,255,255,0.06);
  display: flex; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.2);
}
/* 右半屏：歌词 — 占视口右 50% */
.np-layout__lyrics {
  width: 50%; padding-left: 32px; flex-shrink: 0;
  overflow: hidden;
  position: relative;
  mask-image: linear-gradient(to bottom, transparent 0%, #000 15%, #000 85%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 15%, #000 85%, transparent 100%);
}
.lyrics-scroll {
  padding: 50vh 0 40vh;
}
.lyric-line {
  text-align: left; padding: 8px 0;
  transition: padding 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              min-height 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              background 0.15s ease,
              transform 0.12s ease;
  letter-spacing: 1px; user-select: none;
  min-height: 48px; display: flex; align-items: center;
  cursor: pointer; border-radius: 10px; position: relative;
}
.lyric-line:hover {
  background: rgba(255,255,255,0.04);
}
.lyric-line:active {
  transform: translateZ(0) scale(0.97) translateY(1px);
  background: rgba(255,255,255,0.08);
}
.lyric-line.has-translation { padding: 6px 0; }
.lyric-line__inner {
  display: flex; flex-direction: column; gap: 4px; width: 100%;
}
.lyric-line__original {
  margin: 0; font-size: var(--lyrics-base-original, 16px); line-height: 1.4;
  font-weight: var(--lyrics-weight, 700); color: rgba(255,255,255,0.25);
  max-width: var(--lyrics-ch-limit);
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-size 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-weight 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lyric-line__translation {
  margin: 0; font-size: var(--lyrics-base-trans, 10px); line-height: 1.3;
  font-weight: var(--lyrics-weight, 700); color: rgba(255,255,255,0.12);
  max-width: var(--lyrics-trans-ch-limit);
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-size 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lyric-line.active .lyric-line__original {
  color: #fff; font-size: var(--lyrics-active-original, 24px); font-weight: var(--lyrics-weight, 700);
  max-width: var(--lyrics-active-ch-limit);
}
.lyric-line.active .lyric-line__translation {
  color: rgba(255,255,255,0.4); font-size: var(--lyrics-active-trans, 14px);
  max-width: var(--lyrics-trans-active-ch-limit);
}

/* 逐字歌词 */
.lyric-line__original.word-level {
  display: inline-flex; flex-wrap: wrap;
  justify-content: flex-start; gap: 0; white-space: pre;
}
.word-seg {
  display: inline-block;
  color: rgba(255,255,255,0.25);
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.04s linear;
}
.lyric-line.active .word-seg {
  color: rgba(255,255,255,0.35);
}
/* 卡拉OK：::before 白色文字叠加在暗色文字上，clip-path 从左侧逐渐露出已唱部分 */
.word-seg--singing {
  position: relative;
  color: rgba(255,255,255,0.35);
}
.word-seg--singing::before {
  content: attr(data-word);
  position: absolute;
  inset: 0;
  color: #fff;
  clip-path: inset(0 calc((100 - var(--word-pct, 0)) * 1%) 0 0);
  pointer-events: none;
  white-space: pre;
}
.word-seg--sung {
  color: #fff !important;
  transition: color 0s, transform 0.04s linear;
}
.lyrics-padding { height: 30vh; }

.lyrics-empty-state {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px; user-select: none;
}
.lyrics-empty-state__icon { font-size: 48px; margin-bottom: 8px; }
.lyrics-empty-state__text { font-size: 18px; font-weight: 500; color: rgba(255,255,255,0.8); }

/* ===== 面板开闭过渡动画：从底部连贯上滑 ===== */
.panel-slide-enter-active {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  will-change: transform;
}

.panel-slide-enter-from {
  transform: translateY(100%);
}

.panel-slide-leave-active {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  will-change: transform;
}

.panel-slide-leave-to {
  transform: translateY(calc(100% - 72px));
}

/* 关闭按钮显隐动画 — 与面板滑入/滑出同步 */
.np-close-btn-fade-enter-active {
  transition: opacity 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.0) 0.3s,
              transform 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.0) 0.3s;
}
.np-close-btn-fade-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}
.np-close-btn-fade-leave-active {
  transition: opacity 0.25s ease-in, transform 0.25s ease-in;
}
.np-close-btn-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
