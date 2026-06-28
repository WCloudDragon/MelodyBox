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
      <!-- 模糊背景：切歌时交叉淡入淡出 -->
      <div class="np-bg">
        <Transition name="bg-fade">
          <img v-if="currentTrack?.cover" :key="currentTrack?.path" :src="currentTrack.cover" class="np-bg__img" decoding="async" />
        </Transition>
        <!-- 动态流光：多色块模糊漂移产生流体流动感 -->
        <div v-if="settings.enableDynamicBg && flowColors" class="np-bg__flow">
          <div class="np-bg__blob np-bg__blob--1" :style="{ '--c': flowColors.highlight }"></div>
          <div class="np-bg__blob np-bg__blob--2" :style="{ '--c': flowColors.mid }"></div>
          <div class="np-bg__blob np-bg__blob--3" :style="{ '--c': flowColors.shadow }"></div>
          <div class="np-bg__blob np-bg__blob--4" :style="{ '--c': flowColors.highlight }"></div>
          <div class="np-bg__blob np-bg__blob--5" :style="{ '--c': flowColors.mid }"></div>
          <div class="np-bg__blob np-bg__blob--6" :style="{ '--c': flowColors.shadow }"></div>
        </div>
      </div>

      <!-- 无歌曲时的提示 -->
      <div v-if="!currentTrack" class="np-empty">
        <p class="np-empty__icon">🎵</p>
        <p class="np-empty__text">暂无播放中的歌曲</p>
      </div>

      <!-- Apple Music 风格布局 -->
      <template v-else>
        <div class="np-layout" :style="lyricsVars">
          <!-- 左半屏：封面 — 切歌时方向感知动画（出入同时执行） -->
          <div class="np-layout__cover">
            <Transition :name="coverAnimName">
              <div class="cover-artwork" :key="currentTrack?.path" ref="coverArtRef">
                <img v-if="currentTrack?.cover" :src="currentTrack.cover" class="cover-artwork__img" decoding="async" />
                <div v-else class="cover-artwork__empty">
                  <el-icon size="64"><Headset /></el-icon>
                </div>
              </div>
            </Transition>
          </div>

          <!-- 右半屏：歌词 -->
          <div class="np-layout__lyrics" ref="mainRef" @wheel.prevent="onLyricsWheel">
            <div v-if="!hasLyrics" class="lyrics-empty-state">
              <p class="lyrics-empty-state__icon">🎵</p>
              <p class="lyrics-empty-state__text">未找到内嵌歌词</p>
            </div>

            <Transition v-else :name="lyricsAnimName">
              <div class="lyrics-scroll" :key="currentTrack?.path" ref="scrollRef">
              <div
                v-for="(line, index) in parsedLyrics"
                :key="index"
                class="lyric-line"
                :class="{
                  active: index === currentLineIndex && jumpPending < 0,
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
                  <p v-if="line.wordLevel && line.segments && Math.abs(index - currentLineIndex) <= 1" class="lyric-line__original word-level">
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
            </Transition>
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
import { extractCoverColors } from '@/utils/coverColorExtractor'

const props = defineProps({ visible: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'afterLeave', 'flyComplete'])

const player = usePlayerStore()
const settings = useSettingsStore()
const { currentTrack, currentTime, songChangeDirection, queue, currentIndex, analyserNode } = storeToRefs(player)
const { lyricsFontSize, lyricsFontWeight } = storeToRefs(settings)
const { lyricsTransScale, lyricsActiveScale } = storeToRefs(settings)
const { enableLyricsBlur, enableDominoScroll, enableWordLift, wordAnimFps } = storeToRefs(settings)
const coverOriginRect = inject('coverOriginRect', ref(null))

const mainRef = ref(null)
const scrollRef = ref(null)
const lineRefs = ref({})
const currentLineIndex = ref(-1)
// 远距离跳转缓冲：存旧行索引，-1 表示无跳转。延迟一帧让 v-if 词级 span 先以非活跃态渲染，
// 然后 lineStyle(opacity) 和 .active(font-size) 在同一帧同步开始过渡，避免视觉脱节
const jumpPending = ref(-1)
const coverArtRef = ref(null)

// ==================== 动态流光背景（封面主色驱动渐变流动） ====================
const flowColors = ref(null)

// HTTP cover URL → thumb:// URL，绕过 Flask 直读本地缩略图，零 HTTP 开销
function toThumbUrl(coverUrl, size = 332) {
  if (!coverUrl) return null
  try {
    const u = new URL(coverUrl)
    const coverPath = u.searchParams.get('path')
    if (coverPath) {
      const basename = decodeURIComponent(coverPath).split(/[/\\]/).pop()
      if (basename) return `thumb://${size}/${basename}`
    }
  } catch {}
  return coverUrl // fallback：非标准 HTTP URL 走原路径
}

// 封面变化时异步提取主色
watch(() => currentTrack.value?.cover, async (cover) => {
  if (!cover || !settings.enableDynamicBg) {
    flowColors.value = null
    return
  }
  const colors = await extractCoverColors(toThumbUrl(cover))
  if (currentTrack.value?.cover !== cover) return // 避免竞态：封面已切换
  flowColors.value = colors
})

// 开关变化时，若关则清除；若开且当前有封面则立即提取
watch(() => settings.enableDynamicBg, async (on) => {
  if (!on) { flowColors.value = null; return }
  const cover = currentTrack.value?.cover
  if (cover) {
    const colors = await extractCoverColors(toThumbUrl(cover))
    flowColors.value = colors
  }
})

// ==================== 音频律动 — 频谱分析驱动光球缩放/透明度 ====================
//  光球缩放：LOW + MID 双通道自适应基线 delta + 能量累积器
//  光球透明度：中频/全频能量 → 氛围渐变
let _rhythmRaf = null
let _flowEl = null                           // 缓存 DOM 引用，避免每帧 querySelector
const _rhythmEnergy = { low: 0, mid: 0, full: 0 }
const _prev = { scale: 0, midOp: 0, hlOp: 0 }     // 值未变时跳过 setProperty
let _lowBaseline = 0                         // LOW 自适应基线
let _midBaseline = 0                         // MID 自适应基线
let _deltaSmoothed = 0                       // 平滑后的 LOW 变化率
let _midDeltaSmoothed = 0                    // 平滑后的 MID 变化率
let _accumulator = 0                         // 能量累积器，密集鼓点持续走高，安静段缓慢衰减

function startRhythmLoop() {
  const analyser = analyserNode.value
  if (!analyser || _rhythmRaf) return
  const freqData = new Uint8Array(analyser.frequencyBinCount) // 64
  const binCount = freqData.length

  function step() {
    analyser.getByteFrequencyData(freqData)

    // for 循环累加，避免 slice+reduce 每帧分配临时数组（GC 压力）
    // LOW: bins 1-4（约 344~1723Hz），跳过 bin0 常量 DC/sub-bass，抓鼓点 punch 段
    let lowSum = 0
    for (let i = 1; i < 5; i++) lowSum += freqData[i]
    const lowRaw = lowSum / 1020              // 4 * 255

    let midSum = 0
    for (let i = 6; i < 31; i++) midSum += freqData[i]
    const midRaw = midSum / 6375               // 25 * 255

    let fullSum = 0
    for (let i = 0; i < binCount; i++) fullSum += freqData[i]
    const fullRaw = fullSum / (binCount * 255)

    // Lerp 平滑（避免逐帧抖动）
    const lerp = (prev, raw, f = 0.12) => prev + (raw - prev) * f
    _rhythmEnergy.low = lerp(_rhythmEnergy.low, lowRaw)
    _rhythmEnergy.mid = lerp(_rhythmEnergy.mid, midRaw)
    _rhythmEnergy.full = lerp(_rhythmEnergy.full, fullRaw)

    // LOW 自适应基线 delta — 鼓点瞬态脉冲
    // 暖启动：基线为 0 时（切歌首帧）直接快照当前能量，避免从 0 爬升导致的虚高 delta
    if (_lowBaseline === 0) { _lowBaseline = lowRaw; _midBaseline = midRaw }
    _lowBaseline = _lowBaseline + (lowRaw - _lowBaseline) * 0.005
    const lowDelta = Math.min(0.15, Math.max(0, lowRaw - _lowBaseline))
    _deltaSmoothed = _deltaSmoothed + (lowDelta - _deltaSmoothed) * 0.08

    // MID 自适应基线 delta — 吉他/人声等持续乐器增量脉冲
    _midBaseline = _midBaseline + (midRaw - _midBaseline) * 0.005
    const midDelta = Math.max(0, midRaw - _midBaseline)
    _midDeltaSmoothed = _midDeltaSmoothed + (midDelta - _midDeltaSmoothed) * 0.08

    // 能量累积：每次鼓点注入 delta × 0.15，每帧衰减 6%（半衰期 ≈ 11 帧 ≈ 0.18s，强调瞬时脉冲）
    _accumulator += lowDelta * 0.15
    _accumulator *= 0.94
    // scale = 基础 + LOW脉冲 + 累积能量 + MID增量脉冲（替代持续 mid 能量，避免炸裂歌曲顶死上限）
    const sc = Math.round(Math.min(1.5, 1 + _deltaSmoothed * 5.5 + _accumulator * 2 + _midDeltaSmoothed * 0.4) * 100) / 100
    if (sc !== _prev.scale) { _flowEl.style.setProperty('--flow-scale', sc); _prev.scale = sc }

    // 中频能量 → mid 层透明度
    const mo = Math.round((0.6 + _rhythmEnergy.mid * 0.35) * 100) / 100
    if (mo !== _prev.midOp) { _flowEl.style.setProperty('--flow-opacity-mid', mo); _prev.midOp = mo }
    // 全频能量 → highlight 层透明度
    const ho = Math.round((0.55 + _rhythmEnergy.full * 0.4) * 100) / 100
    if (ho !== _prev.hlOp) { _flowEl.style.setProperty('--flow-opacity-hl', ho); _prev.hlOp = ho }

    // 发送数据到律动日志窗口（仅调试模式）
    if (settings.debugMode) {
      window.electronAPI?.rhythmUpdate({
        lowRaw, midRaw, fullRaw,
        lowSmoothed: _rhythmEnergy.low, midSmoothed: _rhythmEnergy.mid, fullSmoothed: _rhythmEnergy.full,
        lowBaseline: _lowBaseline, midBaseline: _midBaseline,
        lowDelta, deltaSmoothed: _deltaSmoothed, midDelta, midDeltaSmoothed: _midDeltaSmoothed,
        accumulator: _accumulator,
        scale: String(sc), midOp: String(mo), hlOp: String(ho),
        flowElFound: true
      })
    }

    _rhythmRaf = requestAnimationFrame(step)
  }

  // 延迟一帧缓存 DOM（Vue v-if 异步渲染，首帧可能不在 DOM）
  _rhythmRaf = requestAnimationFrame(() => {
    _flowEl = document.querySelector('.np-overlay .np-bg__flow')
    if (!_flowEl) return
    // 调试模式：自动打开律动日志窗口
    if (settings.debugMode) window.electronAPI?.rhythmOpen()
    _rhythmRaf = requestAnimationFrame(step)
  })
}

function stopRhythmLoop() {
  if (_rhythmRaf) { cancelAnimationFrame(_rhythmRaf); _rhythmRaf = null }
  _flowEl = null
  _rhythmEnergy.low = 0; _rhythmEnergy.mid = 0; _rhythmEnergy.full = 0
  _prev.scale = 0; _prev.midOp = 0; _prev.hlOp = 0
  _lowBaseline = 0; _midBaseline = 0; _deltaSmoothed = 0; _midDeltaSmoothed = 0; _accumulator = 0
  if (settings.debugMode) {
    window.electronAPI?.rhythmUpdate({ lowRaw:0,midRaw:0,fullRaw:0, lowSmoothed:0,midSmoothed:0,fullSmoothed:0, lowBaseline:0,midBaseline:0,lowDelta:0,deltaSmoothed:0,midDelta:0,midDeltaSmoothed:0,accumulator:0, scale:'1',midOp:'0.7',hlOp:'0.55', flowElFound:false })
  }
}

// 动态背景开关/可见性/律动开关变化时控制 RAF 循环
watch([() => settings.enableDynamicBg, () => settings.enableAudioRhythm, () => props.visible], ([bgOn, rhythmOn, visible]) => {
  if (bgOn && rhythmOn && visible) startRhythmLoop()
  else stopRhythmLoop()
})

// 切歌动画方向：null = 无动画, 'next' = 下一曲, 'prev' = 上一曲
const coverAnimDir = ref(null)

// 封面过渡动画名称，与歌曲信息现有位移动画时长/曲线一致 (0.6s cubic-bezier)
const coverAnimName = computed(() => {
  if (!coverAnimDir.value) return 'cover-none'
  return `cover-${coverAnimDir.value}`
})

// 歌词切歌过渡动画名称，复用 songChangeDirection 方向
const lyricsAnimName = computed(() => {
  if (!coverAnimDir.value) return 'lyrics-none'
  return `lyrics-${coverAnimDir.value}`
})
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
    // 重新缓存（word-seg 仅在活跃行渲染，切句后旧引用失效）
    const lineEl = lineRefs.value[idx]
    line._wordSegEls = lineEl ? [...lineEl.querySelectorAll('.word-seg')] : []

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
  // 远距离跳转缓冲期内以旧行索引计算距离，避免 opacity 抢先过渡
  const refIdx = jumpPending.value >= 0 ? jumpPending.value : currentLineIndex.value
  const dist = index - refIdx
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
    // 远距离跳转：存旧行索引，延迟一帧，lineStyle 与 .active 同步过渡
    if (Math.abs(idx - oldIdx) > 1) {
      jumpPending.value = oldIdx
      nextTick(() => { jumpPending.value = -1 })
    }
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

// 预加载封面到浏览器缓存并强制解码：decode() 确保图片完全就绪，不阻塞过渡动画
// 策略：缓存播放队列中当前曲目前后各 5 首的封面（共最多 11 张），连续切歌几乎零延迟
const _coverCache = new Map()
const PRELOAD_WINDOW = 5

function _preloadOne(url) {
  if (!url || _coverCache.has(url)) return
  const img = new Image()
  img.src = url
  img.decode().then(() => {
    _coverCache.set(url, img)
    // 保留最近 11 张，超出删最旧的
    while (_coverCache.size > PRELOAD_WINDOW * 2 + 1) {
      _coverCache.delete(_coverCache.keys().next().value)
    }
  }).catch(() => {})
}

// 当前索引或队列变化时，预取邻近封面
watch([currentIndex, queue], ([idx, q]) => {
  if (!q.length || idx == null) return
  const start = Math.max(0, idx - PRELOAD_WINDOW)
  const end = Math.min(q.length, idx + PRELOAD_WINDOW + 1)
  for (let i = start; i < end; i++) {
    _preloadOne(q[i]?.cover)
  }
}, { immediate: true })

watch(() => currentTrack.value?.path, () => {
  currentLineIndex.value = -1
  stopWordAnimLoop()
  targetScrollPos = 0
  prevLineIndex = -1
  if (scrollRef.value) { scrollRef.value.style.transform = 'translate3d(0, 0, 0)'; currentScrollY = 0 }
})

// 监听切歌方向，设置封面动画方向，动画结束后清除
watch(songChangeDirection, (dir) => {
  if (dir) {
    coverAnimDir.value = dir
    // 动画结束后清除方向（cover 动画 0.6s + 少许余量）
    setTimeout(() => {
      coverAnimDir.value = null
      player.songChangeDirection = null
    }, 650)
  }
})

onBeforeUnmount(() => {
  stopWordAnimLoop()
  stopRhythmLoop()
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
  background-color: #080808;
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

/* 动态流光 — 多色块高斯模糊漂移产生流体流动感 */
.np-bg__flow {
  position: absolute;
  inset: -10%;
  z-index: 1;
  mix-blend-mode: soft-light;
  pointer-events: none;
  filter: contrast(1.15) saturate(1.4);
}
.np-bg__blob {
  position: absolute;
  border-radius: 50%;
  background: var(--c, transparent);
  filter: blur(45px);
  opacity: 0.7;
  will-change: top, left, transform;
  transition: background 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.np-bg__blob--1 { --base-dur: 14s; width: 45%; height: 45%; top: 10%; left: 10%; animation-name: blob-float-1; animation-timing-function: ease-in-out; animation-iteration-count: infinite; }
.np-bg__blob--2 { --base-dur: 17s; width: 50%; height: 50%; top: 50%; left: 60%; animation: blob-float-2 17s ease-in-out infinite 2s; }
.np-bg__blob--3 { --base-dur: 15s; width: 38%; height: 38%; top: 60%; left: 20%; animation: blob-float-3 15s ease-in-out infinite 4s; }
.np-bg__blob--4 { --base-dur: 19s; width: 42%; height: 42%; top: 0%;  left: 50%; animation: blob-float-4 19s ease-in-out infinite 1s; }
.np-bg__blob--5 { --base-dur: 13s; width: 35%; height: 35%; top: 30%; left: 70%; animation: blob-float-5 13s ease-in-out infinite 5s; }
.np-bg__blob--6 { --base-dur: 21s; width: 48%; height: 48%; top: 70%; left: 40%; animation: blob-float-6 21s ease-in-out infinite 3s; }

/* 分层响应：低频能量 → 所有光球缩放 | 中频能量 → 光球 2/5 透明度 | 全频能量 → 光球 1/4 透明度 */
.np-bg__blob--2, .np-bg__blob--5 { opacity: var(--flow-opacity-mid, 0.7); }
.np-bg__blob--1, .np-bg__blob--4 { opacity: var(--flow-opacity-hl, 0.7); }

@keyframes blob-float-1 {
  0%, 100% { top: 10%; left: 10%; transform: rotate(0deg)   scale(var(--flow-scale, 1)); }
  15%       { top: 35%; left: 20%; transform: rotate(54deg)  scale(var(--flow-scale, 1)); }
  30%       { top: 20%; left: 50%; transform: rotate(108deg) scale(var(--flow-scale, 1)); }
  45%       { top: 45%; left: 40%; transform: rotate(162deg) scale(var(--flow-scale, 1)); }
  60%       { top: 15%; left: 60%; transform: rotate(216deg) scale(var(--flow-scale, 1)); }
  75%       { top: 40%; left: 30%; transform: rotate(270deg) scale(var(--flow-scale, 1)); }
  90%       { top: 5%;  left: 45%; transform: rotate(324deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-2 {
  0%, 100% { top: 50%; left: 60%; transform: rotate(0deg)    scale(var(--flow-scale, 1)); }
  15%       { top: 30%; left: 40%; transform: rotate(-54deg)  scale(var(--flow-scale, 1)); }
  30%       { top: 60%; left: 30%; transform: rotate(-108deg) scale(var(--flow-scale, 1)); }
  45%       { top: 25%; left: 50%; transform: rotate(-162deg) scale(var(--flow-scale, 1)); }
  60%       { top: 55%; left: 70%; transform: rotate(-216deg) scale(var(--flow-scale, 1)); }
  75%       { top: 40%; left: 55%; transform: rotate(-270deg) scale(var(--flow-scale, 1)); }
  90%       { top: 65%; left: 45%; transform: rotate(-324deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-3 {
  0%, 100% { top: 60%; left: 20%; transform: rotate(0deg)  scale(var(--flow-scale, 1)); }
  20%       { top: 40%; left: 45%; transform: rotate(72deg) scale(var(--flow-scale, 1)); }
  40%       { top: 65%; left: 60%; transform: rotate(144deg) scale(var(--flow-scale, 1)); }
  60%       { top: 20%; left: 35%; transform: rotate(216deg) scale(var(--flow-scale, 1)); }
  80%       { top: 50%; left: 15%; transform: rotate(288deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-4 {
  0%, 100% { top: 0%;  left: 50%; transform: rotate(0deg)    scale(var(--flow-scale, 1)); }
  15%       { top: 25%; left: 65%; transform: rotate(-54deg)  scale(var(--flow-scale, 1)); }
  30%       { top: 10%; left: 30%; transform: rotate(-108deg) scale(var(--flow-scale, 1)); }
  45%       { top: 40%; left: 55%; transform: rotate(-162deg) scale(var(--flow-scale, 1)); }
  60%       { top: 5%;  left: 70%; transform: rotate(-216deg) scale(var(--flow-scale, 1)); }
  75%       { top: 30%; left: 35%; transform: rotate(-270deg) scale(var(--flow-scale, 1)); }
  90%       { top: 15%; left: 60%; transform: rotate(-324deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-5 {
  0%, 100% { top: 30%; left: 70%; transform: rotate(0deg)   scale(var(--flow-scale, 1)); }
  20%       { top: 55%; left: 50%; transform: rotate(72deg)  scale(var(--flow-scale, 1)); }
  40%       { top: 40%; left: 20%; transform: rotate(144deg) scale(var(--flow-scale, 1)); }
  60%       { top: 15%; left: 45%; transform: rotate(216deg) scale(var(--flow-scale, 1)); }
  80%       { top: 50%; left: 60%; transform: rotate(288deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-6 {
  0%, 100% { top: 70%; left: 40%; transform: rotate(0deg)    scale(var(--flow-scale, 1)); }
  15%       { top: 45%; left: 25%; transform: rotate(-54deg)  scale(var(--flow-scale, 1)); }
  30%       { top: 60%; left: 55%; transform: rotate(-108deg) scale(var(--flow-scale, 1)); }
  45%       { top: 35%; left: 60%; transform: rotate(-162deg) scale(var(--flow-scale, 1)); }
  60%       { top: 55%; left: 15%; transform: rotate(-216deg) scale(var(--flow-scale, 1)); }
  75%       { top: 65%; left: 50%; transform: rotate(-270deg) scale(var(--flow-scale, 1)); }
  90%       { top: 40%; left: 35%; transform: rotate(-324deg) scale(var(--flow-scale, 1)); }
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
  position: relative;
  overflow: hidden;
}
.cover-artwork {
  width: clamp(260px, 26vw, 520px);
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  transform: translateZ(0);
  backface-visibility: hidden;
  background: #1a1a1a;
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
  left: 0;
  top: 0;
  color: #fff;
  width: calc(var(--word-pct, 0) * 1%);
  overflow: hidden;
  -webkit-mask-image: linear-gradient(to right, #000 0%, #000 calc(100% - 8px), transparent 100%);
  mask-image: linear-gradient(to right, #000 0%, #000 calc(100% - 8px), transparent 100%);
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

/* ===== 切歌动画：背景叠化（叠化 = 出入同步同速，零黑底穿透） ===== */
.bg-fade-enter-active,
.bg-fade-leave-active {
  transition: opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  position: absolute;
  top: -10%;
  left: -10%;
  width: 120%;
  height: 120%;
}
.bg-fade-enter-active { z-index: 1; }
.bg-fade-leave-active { z-index: 0; }
.bg-fade-enter-from { opacity: 0; }
.bg-fade-leave-to { opacity: 0; }

/* ===== 切歌动画：封面 — 与歌曲信息位移动画时长/曲线一致 ===== */
/* 出入同时执行：新封面(enter)在上，旧封面(leave)在下 */
.cover-next-leave-active,
.cover-prev-leave-active {
  position: absolute;
  inset: 0;
  margin: auto;
  z-index: 0;
}
.cover-next-enter-active,
.cover-prev-enter-active {
  position: relative;
  z-index: 1;
}

/* 下一曲：i-旧封面以顶部中心为锚点缩小渐隐  ii-新封面以底部中心为锚点从最小值放大渐显 */
.cover-next-enter-active,
.cover-next-leave-active {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
/* transform-origin 必须在 -active 上才能贯穿整个动画，-from/-to 只在首尾瞬间存在 */
.cover-next-leave-active { transform-origin: top center; }
.cover-next-leave-to   { transform: scale(0.65); opacity: 0; }
 .cover-next-enter-active { transform-origin: bottom center; }
 .cover-next-enter-from   { transform: scale(0.65); opacity: 0; }

/* 上一曲：i-旧封面以底部中心为锚点缩小渐隐  ii-新封面以顶部中心为锚点从最小值放大渐显 */
.cover-prev-enter-active,
.cover-prev-leave-active {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.cover-prev-leave-active { transform-origin: bottom center; }
.cover-prev-leave-to   { transform: scale(0.65); opacity: 0; }
 .cover-prev-enter-active { transform-origin: top center; }
 .cover-prev-enter-from   { transform: scale(0.65); opacity: 0; }

/* 无动画（初始状态） */
.cover-none-enter-active,
.cover-none-leave-active {
  transition: none;
}

/* ===== 歌词切歌过渡动画：方向感知滑入滑出 + 渐隐渐显（出入同时执行） ===== */
.lyrics-next-enter-active,
.lyrics-prev-enter-active {
  transition: transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lyrics-next-leave-active,
.lyrics-prev-leave-active {
  transition: transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  position: absolute;
  top: 0;
  width: 100%;
  z-index: 0;
}
.lyrics-next-enter-active,
.lyrics-prev-enter-active {
  position: relative;
  z-index: 1;
}
/* 下一曲：新歌词从下方 50px 滑入并渐显+从模糊到清晰，旧歌词渐隐+模糊 */
.lyrics-next-enter-from { transform: translateY(50px); opacity: 0; filter: blur(10px); }
.lyrics-next-leave-to   { opacity: 0; filter: blur(10px); }
/* 上一曲：新歌词从上方 50px 滑入并渐显+从模糊到清晰，旧歌词渐隐+模糊 */
.lyrics-prev-enter-from { transform: translateY(-50px); opacity: 0; filter: blur(10px); }
.lyrics-prev-leave-to   { opacity: 0; filter: blur(10px); }
/* 无动画（初始状态） */
.lyrics-none-enter-active,
.lyrics-none-leave-active {
  transition: none;
}
</style>
