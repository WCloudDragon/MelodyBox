<template>
  <!-- 窗口控制器风格关闭按钮 — Teleport 到 body 确保独立层级 -->
  <Teleport to="body">
    <Transition name="np-close-btn-fade">
      <button v-if="visible && !immersive" class="np-close-btn" v-ripple @click.stop="$emit('close')" title="关闭全屏歌词">
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
          <img v-if="bgBlurCover" :key="currentTrack?.path" :src="bgBlurCover" class="np-bg__img" :style="{ filter: `blur(60px) brightness(${bgBrightness})` }" decoding="async" />
        </Transition>
        <!-- 动态流光：6 张径向渐变 PNG 光球 -->
        <div v-if="settings.enableDynamicBg && flowBlobs" class="np-bg__flow">
          <img :src="flowBlobs[0]" class="np-bg__blob np-bg__blob--1" decoding="async" />
          <img :src="flowBlobs[1]" class="np-bg__blob np-bg__blob--2" decoding="async" />
          <img :src="flowBlobs[2]" class="np-bg__blob np-bg__blob--3" decoding="async" />
          <img :src="flowBlobs[3]" class="np-bg__blob np-bg__blob--4" decoding="async" />
          <img :src="flowBlobs[4]" class="np-bg__blob np-bg__blob--5" decoding="async" />
          <img :src="flowBlobs[5]" class="np-bg__blob np-bg__blob--6" decoding="async" />
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
              <div class="cover-artwork" :key="currentTrack?.path" ref="coverArtRef" :style="coverArtStyle">
                <img v-if="currentTrack?.cover" :src="currentTrack.cover" class="cover-artwork__img" decoding="async" @load="onCoverLoad" />
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
              <!-- 空区长间隔提示（仅三点）：首行前显示在列表顶部 -->
              <div v-if="hintVisible && hintAnchorIndex < 0" :key="'hint-top'"
                   class="upcoming-hint-line" :class="{ 'upcoming-hint-line--leaving': hintLeaving }">
                <p class="upcoming-hint-dots">
                  <span v-for="i in 3" :key="i" class="upcoming-hint-dot"
                        :class="{ 'upcoming-hint-dot--fade': dotFading(i) }">
                    <span class="upcoming-hint-dot__scale" :style="{ '--dot-scale': dotScale(i) / DOT_MAX_SCALE }"></span>
                  </span>
                </p>
              </div>
              <template v-for="(line, index) in parsedLyrics" :key="index">
                <div
                  class="lyric-line"
                  :class="{
                    active: activeIndexes.includes(index) && jumpPending < 0,
                    sung: activeFirst >= 0 && index < activeFirst,
                    upcoming: activeLast >= 0 && index > activeLast,
                    'has-translation': line.translation,
                    'is-word-level': line.wordLevel
                  }"
                  :ref="el => setLineRef(el, index)"
                  :style="lineStyle(index)"
                  v-ripple
                  @click="seekToLine(line.time)"
                >
                  <div class="lyric-line__inner">
                    <p v-if="line.wordLevel && line.segments && (activeIndexes.some(a => Math.abs(index - a) <= 1) || index === fadingLineIndex || (showUpcomingHint && (index === hintLineIndex || index === hintLineIndex + 1)))" class="lyric-line__original word-level">
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
                <!-- 句中空区：三点插在刚结束的上一行之后（上一行保留显示） -->
                <div v-if="hintVisible && index === hintAnchorIndex" :key="'hint-' + index"
                     class="upcoming-hint-line" :class="{ 'upcoming-hint-line--leaving': hintLeaving }">
                  <p class="upcoming-hint-dots">
                    <span v-for="i in 3" :key="i" class="upcoming-hint-dot"
                          :class="{ 'upcoming-hint-dot--fade': dotFading(i) }">
                      <span class="upcoming-hint-dot__scale" :style="{ '--dot-scale': dotScale(i) / DOT_MAX_SCALE }"></span>
                    </span>
                  </p>
                </div>
              </template>
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
import { parseLRC, computeActiveSet, LYRIC_GAP_FILL_LIMIT } from '@/utils/format'
import { extractCoverColors } from '@/utils/coverColorExtractor'

const props = defineProps({
  visible: { type: Boolean, default: false },
  immersive: { type: Boolean, default: false }
})
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
// 当前时刻全部正在播放的歌词行（公平模型，不区分主/副行）
const activeIndexes = ref([])
const activeFirst = computed(() => activeIndexes.value.length ? activeIndexes.value[0] : -1)
const activeLast = computed(() => activeIndexes.value.length ? activeIndexes.value[activeIndexes.value.length - 1] : -1)
function _lastWordIndex(indexes) {
  for (let i = indexes.length - 1; i >= 0; i--) {
    const line = parsedLyrics.value[indexes[i]]
    if (line?.wordLevel) return indexes[i]
  }
  return -1
}
// 远距离跳转缓冲：存旧行索引，-1 表示无跳转。延迟一帧让 v-if 词级 span 先以非活跃态渲染，
// 然后 lineStyle(opacity) 和 .active(font-size) 在同一帧同步开始过渡，避免视觉脱节
const jumpPending = ref(-1)
let fadingTimer = null
const fadingLineIndex = ref(-1)   // 远距离跳转后，旧行逐字 DOM 延后销毁，给过渡动画时间
const coverArtRef = ref(null)
// 封面原始宽高比（w/h），用于全屏页按原比例显示与飞入动画的连续形变
const coverAspect = ref(null)
const coverArtStyle = computed(() => {
  return coverAspect.value ? { '--cover-ratio': coverAspect.value } : {}
})
function onCoverLoad(e) {
  const img = e.target
  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    coverAspect.value = img.naturalWidth / img.naturalHeight
  }
}
// 切歌时重置封面比例，等待新封面加载后再应用
watch(() => currentTrack.value?.cover, () => { coverAspect.value = null })

// ==================== 动态流光背景（封面主色驱动渐变流动） ====================
const flowColors = ref(null)
const flowBlobs = ref(null)   // 6 张预渲染径向渐变 PNG Data URL

// hex → RGB 分量
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return { r, g, b }
}

// Canvas 生成径向渐变 PNG（400×400），中心半透明 → 边缘零透（朦胧效果）
function generateBlobPNG(hex, size = 400) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  const { r, g, b } = hexToRgb(hex)
  const cx = size / 2
  const gradient = ctx.createRadialGradient(cx, cx, 0, cx, cx, cx)
  // 整体透明度适中，略微明显
  gradient.addColorStop(0,    `rgba(${r},${g},${b},0.8)`)   // 中心：明显
  gradient.addColorStop(0.3,  `rgba(${r},${g},${b},0.6)`)   // 30%：较明显
  gradient.addColorStop(0.55, `rgba(${r},${g},${b},0.3)`)   // 55%：中等
  gradient.addColorStop(0.75, `rgba(${r},${g},${b},0.12)`)  // 75%：较淡
  gradient.addColorStop(0.9,  `rgba(${r},${g},${b},0.04)`)  // 90%：很淡
  gradient.addColorStop(1,    `rgba(${r},${g},${b},0)`)     // 边缘：完全透明
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  return canvas.toDataURL('image/png')
}

// 3 色 → 6 张 PNG（每色 2 张）
function generateFlowBlobs(colors) {
  if (!colors) { flowBlobs.value = null; return }
  const { highlight, mid, shadow } = colors
  flowBlobs.value = [
    generateBlobPNG(highlight),
    generateBlobPNG(mid),
    generateBlobPNG(shadow),
    generateBlobPNG(highlight),
    generateBlobPNG(mid),
    generateBlobPNG(shadow),
  ]
}

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

// 模糊背景使用200px缩略图（小图模糊后放大，性能优化）
const bgBlurCover = computed(() => toThumbUrl(currentTrack.value?.cover, 200))

// 封面亮度检测（用于动态调整背景亮度）
const coverBrightness = ref(128) // 默认中等亮度

async function detectCoverBrightness(coverUrl) {
  if (!coverUrl) return 128
  try {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = coverUrl
    await new Promise((resolve, reject) => {
      img.onload = resolve
      img.onerror = reject
    })
    const canvas = document.createElement('canvas')
    const size = 50 // 小尺寸采样，性能优先
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0, size, size)
    const data = ctx.getImageData(0, 0, size, size).data
    let totalBrightness = 0
    for (let i = 0; i < data.length; i += 4) {
      // 人眼感知亮度公式
      totalBrightness += data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114
    }
    return totalBrightness / (size * size)
  } catch {
    return 128 // 出错时返回中等亮度
  }
}

// 动态背景亮度（根据封面亮度自适应）
const bgBrightness = computed(() => {
  const b = coverBrightness.value
  if (b > 180) return 0.3   // 太白，大幅降低
  if (b > 150) return 0.4   // 偏白，降低
  if (b < 40) return 0.8    // 太黑，大幅提高
  if (b < 70) return 0.7    // 偏黑，提高
  return 0.5                 // 正常范围
})

// 封面变化时检测亮度
watch(() => currentTrack.value?.cover, async (cover) => {
  const thumbUrl = toThumbUrl(cover, 200)
  coverBrightness.value = await detectCoverBrightness(thumbUrl)
})

// 封面变化时异步提取主色
watch(() => currentTrack.value?.cover, async (cover) => {
  if (!cover || !settings.enableDynamicBg) {
    flowColors.value = null
    flowBlobs.value = null
    return
  }
  const colors = await extractCoverColors(toThumbUrl(cover))
  if (currentTrack.value?.cover !== cover) return // 避免竞态：封面已切换
  flowColors.value = colors
  generateFlowBlobs(colors)
})

// 开关变化时，若关则清除；若开且当前有封面则立即提取
watch(() => settings.enableDynamicBg, async (on) => {
  if (!on) { flowColors.value = null; flowBlobs.value = null; return }
  const cover = currentTrack.value?.cover
  if (cover) {
    const colors = await extractCoverColors(toThumbUrl(cover))
    if (currentTrack.value?.cover !== cover) return
    flowColors.value = colors
    generateFlowBlobs(colors)
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

  let lastWork = 0
  function step(now = performance.now()) {
    // 律动响应帧率节流：间隔内跳过分析与样式写入，rAF 保持调度
    if (now - lastWork < 1000 / Math.max(settings.rhythmFps.value, 1)) {
      _rhythmRaf = requestAnimationFrame(step)
      return
    }
    lastWork = now
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
      if (!props.visible || activeIndexes.value.length === 0) return
      if (isUserScrolling.value) exitUserScrollMode()
      scrollToActiveGroup(false)
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

  // 确保封面已解码后再启动动画，消除首次触发时 background-image 实时解码卡顿
  return _ensureCoverReady(coverUrl).then(() => {
  const toW = toRect.width, toH = toRect.height
  const fromW = fromRect.width, fromH = fromRect.height

  const startBR = parseFloat(fromBR)
  const endBR = parseFloat(toBR)

  // 窗口宽高/位置逐帧插值，内层图片保持 object-fit: cover：
  // 窗口比例从源（方形）连续插值到目标（原图比例），cover 的可见区域
  // 随之从中心方形扩展到完整原图，实现无缝“拉远揭示”，全程零变形。
  const wrapper = document.createElement('div')
  Object.assign(wrapper.style, {
    position: 'fixed', zIndex: '10000', pointerEvents: 'none',
    left: fromRect.left + 'px', top: fromRect.top + 'px',
    width: fromW + 'px', height: fromH + 'px',
    willChange: 'left, top, width, height'
  })

  const shadowEl = document.createElement('div')
  Object.assign(shadowEl.style, {
    position: 'absolute', inset: '0', pointerEvents: 'none',
    borderRadius: `${startBR}px`, boxShadow: 'none', zIndex: '0'
  })

  const imgEl = document.createElement('img')
  imgEl.src = coverUrl
  Object.assign(imgEl.style, {
    position: 'absolute', inset: '0', zIndex: '1',
    width: '100%', height: '100%',
    objectFit: 'cover', objectPosition: 'center',
    clipPath: `inset(0 round ${startBR}px)`,
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

      const w = fromW + (toW - fromW) * p
      const h = fromH + (toH - fromH) * p
      const l = fromRect.left + (toRect.left - fromRect.left) * p
      const tp = fromRect.top + (toRect.top - fromRect.top) * p
      const br = startBR + (endBR - startBR) * p

      wrapper.style.left = l + 'px'
      wrapper.style.top = tp + 'px'
      wrapper.style.width = w + 'px'
      wrapper.style.height = h + 'px'
      imgEl.style.clipPath = `inset(0 round ${br}px)`

      const sh = COVER_SHADOW
      const shadowP = shadowFrom + (shadowTo - shadowFrom) * p
      shadowEl.style.borderRadius = `${br}px`
      shadowEl.style.boxShadow = shadowP > 0.01
        ? `0 ${sh.y * shadowP}px ${sh.blur * shadowP}px rgba(0,0,0,${sh.opacity * shadowP})`
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
  }) // _ensureCoverReady().then()
}

/** 面板展开：封面从播放栏飞入 */
async function flyCoverIn() {
  cleanupFlyer()
  const origin = coverOriginRect?.value
  if (!origin || !coverArtRef.value) return

  // 等待封面预解码完成，直接用解码结果的原比例设置容器，
  // 再测量目标矩形（宽图/长图飞到原比例，不再依赖封面 <img> 二次加载）
  const coverUrl = currentTrack.value?.cover
  if (coverUrl) {
    try {
      const preloaded = await _ensureCoverReady(coverUrl)
      if (preloaded && preloaded.naturalWidth > 0 && preloaded.naturalHeight > 0) {
        coverAspect.value = preloaded.naturalWidth / preloaded.naturalHeight
      }
    } catch { /* 忽略 */ }
  }
  await nextTick()

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
  // 末字卡拉OK的结束基准：本行自己的结束时间（缺失时回退到下一行开始）
  const nextLineTime = line.end != null ? line.end : (nextLine ? nextLine.time : line.time + 5)

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
  // 末字上浮结束基准同样以本行结束时间为准
  const nextLineTime = line.end != null ? line.end : (nextLine ? nextLine.time : line.time + 5)

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
    const idx = _lastWordIndex(activeIndexes.value)
    const line = parsedLyrics.value[idx]
    const fpz = Number(settings.effectiveWordAnimFps.value) || 60
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
  scrollToActiveGroup(true)
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
  // 跳转时模糊/透明度立即跟随新的活跃位置，不等待滚动落地；
  // jumpPending 只负责延迟 .active 的放大高亮，避免视觉脱节
  let refs = activeIndexes.value

  // 无活跃行（空区）：以空区锚点（上一行索引，首行前为 -1）为距离基准，
  // 恢复与其他时刻一致的模糊与透明度渐变
  if (refs.length === 0) {
    refs = [hintLineIndex.value]
  }

  // 正在播放的行（公平模型：所有活跃行一律高亮，不区分主/副）
  if (refs.includes(index)) {
    return { opacity: 1, filter: 'none' }
  }

  // 非活跃行：按与最近活跃行的距离渐变
  let minDist = Infinity
  for (const r of refs) {
    const d = Math.abs(index - r)
    if (d < minDist) minDist = d
  }
  if (minDist === Infinity) minDist = 1
  const absDist = minDist
  const t = Math.min(absDist / 6, 1)
  const opacity = isUserScrolling.value ? 1 : Math.max(0.12, 1 - t * 0.88)

  // Apple Music 风格模糊：越远离活跃行越模糊，用户滚动时取消模糊
  const blurAmount = (isUserScrolling.value || !enableLyricsBlur.value) ? 0 : Math.min(absDist * 1.5, 6)
  const filter = blurAmount > 0.5 ? `blur(${blurAmount}px)` : 'none'

  return { opacity, filter }
}

const parsedLyrics = computed(() => {
  const raw = currentTrack.value?.lyrics
  if (!raw) return []
  const list = parseLRC(raw)
  // 纯音乐等无演唱内容：末行代表整首纯音乐，不触发“末行取短”，保持常驻显示
  if (list.length && /纯音乐/.test(raw)) {
    list[list.length - 1].end = null
  }
  return list
})

const hasLyrics = computed(() => parsedLyrics.value.length > 0)

// 提示所在行：空区前刚结束的一行（首行前为 -1）
const hintLineIndex = computed(() => {
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
// 距下一句的剩余时间（秒）
const upcomingRemaining = computed(() => {
  const list = parsedLyrics.value
  if (!list.length) return Infinity
  const now = currentTime.value
  let next = Infinity
  for (const line of list) {
    if (line.time > now && line.time < next) next = line.time
  }
  return next - now
})
// 当前空区的总长度（首行前 = 首行开始时间；句中 = 上一行的 gap）
const upcomingZoneLength = computed(() => {
  const list = parsedLyrics.value
  if (!list.length) return 0
  const now = currentTime.value
  if (now < list[0].time) return list[0].time
  const prev = hintLineIndex.value
  return prev >= 0 ? (list[prev].gap ?? 0) : 0
})
// 长间隔“即将开唱”提示：仅当进入无活跃行的空区（该空区总长度 ≥ 填缝上限）时显示。
// 空区长度由模型层预计算（line.gap / 首行开始时间），显示状态稳定，不随时间翻转。
const showUpcomingHint = computed(() => {
  if (!hasLyrics.value) return false
  if (activeIndexes.value.length > 0) return false
  // 纯音乐等无演唱内容：不显示提示
  if (/纯音乐/.test(currentTrack.value?.lyrics || '')) return false
  // 左边第一个点完全消失即下句开始：到点时元素无动画移除
  if (upcomingRemaining.value <= 0) return false
  const list = parsedLyrics.value
  const now = currentTime.value
  // 首行之前：空区长度 = 首行开始时间
  if (now < list[0].time) {
    return list[0].time >= LYRIC_GAP_FILL_LIMIT
  }
  // 句中空区：长度 = 上一行原词结束到下一行的间隔（line.gap）
  const prev = hintLineIndex.value
  return prev >= 0 && (list[prev].gap ?? 0) >= LYRIC_GAP_FILL_LIMIT
})
// 三点倒计时：进入空区即开始，三个点**严格逐个**放大——
// 每个点独占一段生长区间（前一个到顶后一个才开始），
// 全部最大时为起播前 3 秒；区间按实际空区长度动态三等分
const DOT_MAX_SCALE = 2.3
function dotScaleFor(i, rem) {
  const rem0 = Math.max(upcomingZoneLength.value, rem)
  const span = Math.max(0.1, rem0 - 3)
  const segStart = rem0 - ((i - 1) / 3) * span  // 该点生长区间起点（剩余时间大）
  const segEnd = rem0 - (i / 3) * span          // 该点生长区间终点（剩余时间小）
  if (rem > segStart) return 1                  // 还没轮到该点
  if (rem <= segEnd) return DOT_MAX_SCALE       // 已完成，保持最大
  const progress = (segStart - rem) / Math.max(0.05, segStart - segEnd)
  return 1 + (DOT_MAX_SCALE - 1) * progress
}
function dotScale(i) {
  return dotScaleFor(i, upcomingRemaining.value)
}
// 起播前 3/2/1 秒依次开始模糊消失（dot3→dot2→dot1），每个淡出 1 秒，
// 左边第一个点在下句开始瞬间完全消失
function dotFading(i) {
  return upcomingRemaining.value <= i
}
// 实时剩余时间：基于 audio.currentTime（60fps 平滑），不依赖 250ms 的 timeupdate 节拍
function liveUpcomingRemaining() {
  const list = parsedLyrics.value
  if (!list.length) return Infinity
  const now = player.getLiveTime()
  for (const line of list) {
    if (line.time > now) return line.time - now
  }
  return Infinity
}
// 三点放大 rAF 循环：按帧更新 --dot-scale，transform 亚像素平滑，消除 px 步进卡顿
let _dotsScaleRaf = null
function startDotsScaleLoop() {
  if (_dotsScaleRaf) return
  const step = () => {
    if (!props.visible || !hintVisible.value || hintLeaving.value || !scrollRef.value) {
      _dotsScaleRaf = null
      return
    }
    const rem = liveUpcomingRemaining()
    const dots = scrollRef.value.querySelectorAll('.upcoming-hint-dot__scale')
    for (let i = 0; i < dots.length; i++) {
      // 归一化到 1/2.3 → 1：内层元素按最大尺寸渲染，向下缩放保证任意尺寸清晰
      dots[i].style.setProperty('--dot-scale', (dotScaleFor(i + 1, rem) / DOT_MAX_SCALE).toFixed(4))
    }
    _dotsScaleRaf = requestAnimationFrame(step)
  }
  _dotsScaleRaf = requestAnimationFrame(step)
}
function stopDotsScaleLoop() {
  if (_dotsScaleRaf) { cancelAnimationFrame(_dotsScaleRaf); _dotsScaleRaf = null }
}
// 三点行的显示/收起状态：收起时保持挂载做 0.25s 平滑折叠，避免下方行闪现
const hintVisible = ref(false)
const hintLeaving = ref(false)
// 三点行位置锚点：显示时冻结，收起期间不随时间变化，避免位置被“偷换”导致闪烁
const hintAnchorIndex = ref(-1)
let _dotsScrollDone = false
// 三点自然结束准备（进入最后 0.35s，等待激活瞬间由级联滚动接管位移）
let _dotsHandoff = false
// 三点行已移除、激活时需要用级联滚动完成位移
let _dotsCascadePending = false
// 三点行高度（移除前测量，用于抵消移除瞬间的布局位移）
let _dotsH = 0
// 三点行收起定时器：跳转/切歌时需清除，避免残留定时器把新空区的三点误删
let _dotsLeaveTimer = null
watch(showUpcomingHint, (val) => {
  if (val) {
    _dotsHandoff = false
    hintLeaving.value = false
    hintVisible.value = true
    hintAnchorIndex.value = hintLineIndex.value
    startDotsScaleLoop()
  } else if (hintVisible.value && !hintLeaving.value) {
    if (_dotsHandoff) {
      // 三点自然倒计时结束：点已全部淡出，立即移除（布局位移由激活时的级联滚动吸收）
      _dotsHandoff = false
      _dotsCascadePending = true
      const dotsEl = scrollRef.value?.querySelector('.upcoming-hint-line')
      _dotsH = dotsEl ? dotsEl.offsetHeight : 0
      hintVisible.value = false
      hintLeaving.value = false
    } else {
      // 非自然结束（进度条跳走等）：平滑折叠收起
      hintLeaving.value = true
      if (_dotsLeaveTimer) clearTimeout(_dotsLeaveTimer)
      _dotsLeaveTimer = setTimeout(() => {
        _dotsLeaveTimer = null
        hintVisible.value = false
        hintLeaving.value = false
        _dotsScrollDone = false
      }, 250)
    }
  }
}, { immediate: true })

// 用 canvas 实测 MiSans VF 在当前字重下的平均字形进宽，替代“(字号+1)”的估算模型。
// 可变字体的进宽并不随字号线性变化（例如 37px 的进宽只比 32px 宽约 3%），
// 旧估算会高估活跃行的容量差，导致临界句在两个稳态间换行跳变。
let _measureCtx = null
const CALIB_STR = '0123456789 abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ      '
function measureAdvance(fontPx, weight) {
  try {
    const fontStr = `${weight} ${fontPx}px 'MiSans VF', 'MiSans', sans-serif`
    if (typeof document !== 'undefined' && document.fonts && !document.fonts.check(fontStr)) return null
    if (!_measureCtx) {
      const canvas = document.createElement('canvas')
      _measureCtx = canvas.getContext('2d')
    }
    _measureCtx.font = fontStr
    return _measureCtx.measureText(CALIB_STR).width / CALIB_STR.length
  } catch {
    return null
  }
}
const fontsReady = ref(false)
if (typeof document !== 'undefined' && document.fonts) {
  document.fonts.ready.then(() => { fontsReady.value = true })
}

// 从设置中按比例计算各字号级别，利用 MiSans VF 可变轴字重
const lyricsVars = computed(() => {
  const base = lyricsFontSize.value
  const trans = Math.round(base * lyricsTransScale.value / 100)
  const active = lyricsActiveScale.value / 100
  const activeFont = Math.round(base * active)
  const transActiveFont = Math.round(trans * active)
  const weight = lyricsFontWeight.value
  // 实测字形进宽（+1px letter-spacing）；字体未就绪时退回旧估算模型，就绪后自动重算
  const advBase = measureAdvance(base, weight)
  const advActive = measureAdvance(activeFont, weight)
  const advTrans = measureAdvance(trans, weight)
  const advTransActive = measureAdvance(transActiveFont, weight)
  const measured = fontsReady.value
    && advBase != null && advActive != null && advTrans != null && advTransActive != null
  const effBase = measured ? advBase + 1 : base + 1
  const effActive = measured ? advActive + 1 : activeFont + 1
  const effTrans = measured ? advTrans + 1 : trans + 1
  const effTransActive = measured ? advTransActive + 1 : transActiveFont + 1
  // 以活跃行（字号更大、容纳更少）为瓶颈，计算两行各自的 em max-width，确保换行位置绝对一致
  const availWidth = Math.max(200, windowWidth.value * 0.5 - 72)
  const activeChars = Math.max(5, Math.floor(availWidth / effActive))
  // +4px 安全余量，统一吸收亚像素渲染波动，避免活跃/非活跃态切换时边界字符闪烁
  const safetyPx = 4
  const nonActiveMaxEm = (activeChars * effBase + safetyPx) / base
  const activeMaxEm = (activeChars * effActive + safetyPx) / activeFont
  // 翻译行同理，基于翻译活跃字号计算
  const transActiveChars = Math.max(3, Math.floor(availWidth / effTransActive))
  const transNonActiveMaxEm = (transActiveChars * effTrans + safetyPx) / trans
  const transActiveMaxEm = (transActiveChars * effTransActive + safetyPx) / transActiveFont
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
    startDotsScaleLoop()
    if (jumpPending.value >= 0) jumpPending.value = -1
    if (!hasLyrics.value || !scrollRef.value) return
    // 重新打开面板：按当前时刻重新定位
    const { activeIndexes: act } = computeActiveSet(parsedLyrics.value, player.getLiveTime())
    activeIndexes.value = act
    if (act.length > 0) {
      scrollToActiveGroup(false)
      await nextTick()
      if (_lastWordIndex(act) >= 0) startWordAnimLoop()
    } else {
      // 无活跃行（空区）：首行前 / 三点间奏 / 无三点间奏都要定位到当前位置，
      // 否则重新打开面板时会停留在歌词顶部。
      const list = parsedLyrics.value
      const now = player.getLiveTime()
      if (showUpcomingHint.value) {
        hintAnchorIndex.value = hintLineIndex.value
        hintVisible.value = true
        hintLeaving.value = false
        _dotsScrollDone = false
        await nextTick()
        await nextTick()
        scrollToDots(false)
      } else {
        const target = now < list[0].time ? 0 : hintLineIndex.value
        if (target >= 0 && target < list.length) scrollToLine(target, false)
      }
    }
  } else {
    flyCoverOut()
    stopWordAnimLoop()
    if (jumpPending.value >= 0) jumpPending.value = -1
    // 清除逐字缓存的 DOM 引用，否则重新打开面板时会复用已销毁的旧元素
    for (const line of parsedLyrics.value) {
      delete line._wordSegEls
    }
    if (lyricsScrollCleanup) { lyricsScrollCleanup(); lyricsScrollCleanup = null }
    exitUserScrollMode()
    targetScrollPos = 0
    prevLineIndex = -1
    _dotsHandoff = false
    _dotsCascadePending = false
    _dotsH = 0
    stopDotsScaleLoop()
    if (_dotsLeaveTimer) { clearTimeout(_dotsLeaveTimer); _dotsLeaveTimer = null }
    if (fadingTimer) { clearTimeout(fadingTimer); fadingTimer = null }
    fadingLineIndex.value = -1
  }
})

// 播放中活跃行集合变化（公平模型：多行同时播放时全部保留，滚动中心取组中心）
watch(currentTime, async (time) => {
  if (!props.visible || !hasLyrics.value || !scrollRef.value) return

  if (!showUpcomingHint.value) _dotsScrollDone = false

  // 进度条从一个长空区跳到另一个长空区：showUpcomingHint 全程为 true 不会触发
  // showUpcomingHint 的 watch，三点锚点仍挂在旧空区。检测锚点与当前空区不一致时，
  // 重新锚定到新空区、清除旧收起定时器并复位滚动标记，让新空区的三点重新定位居中。
  if (showUpcomingHint.value && hintAnchorIndex.value !== hintLineIndex.value) {
    if (_dotsLeaveTimer) { clearTimeout(_dotsLeaveTimer); _dotsLeaveTimer = null }
    _dotsHandoff = false
    hintAnchorIndex.value = hintLineIndex.value
    hintLeaving.value = false
    hintVisible.value = true
    _dotsScrollDone = false
    startDotsScaleLoop()
    if (!isUserScrolling.value) {
      await nextTick()
      _dotsScrollDone = true
      scrollToDots(true)
    }
  }

  // 三点倒计时进入最后阶段：标记自然结束，激活瞬间由级联滚动接管（不再提前折叠）
  if (hintVisible.value && !hintLeaving.value && upcomingRemaining.value <= 0.35) {
    _dotsHandoff = true
  }

  const { activeIndexes: nextActive } = computeActiveSet(parsedLyrics.value, time)
  const prevActive = activeIndexes.value
  if (JSON.stringify(prevActive) !== JSON.stringify(nextActive)) {
    activeIndexes.value = nextActive
  } else if (nextActive.length !== 0) {
    return
  }

  // 卡拉OK行：活跃集合中最后一个逐字行；逐字行变化才重启动画
  const prevWord = _lastWordIndex(prevActive)
  const nextWord = _lastWordIndex(nextActive)
  if (nextWord !== prevWord) {
    stopWordAnimLoop()
    if (prevWord >= 0 && parsedLyrics.value[prevWord]?.wordLevel) fadeOutWordSegs(prevWord)
  }

  // 末行（逐字）结束进入无活跃区：保留其逐字 DOM 片刻，让字号收缩过渡可见
  if (nextActive.length === 0 && prevWord >= 0 && parsedLyrics.value[prevWord]?.wordLevel) {
    if (fadingTimer) clearTimeout(fadingTimer)
    fadingLineIndex.value = prevWord
    fadingTimer = setTimeout(() => { fadingLineIndex.value = -1 }, 400)
  }

  // 远距离跳转（seek）：保留旧行淡出缓冲
  const prevFirst = prevActive.length ? prevActive[0] : -1
  const nextFirst = nextActive.length ? nextActive[0] : -1
  if (prevFirst >= 0 && nextFirst >= 0 && Math.abs(nextFirst - prevFirst) > 1) {
    jumpPending.value = prevFirst
    // jumpPending 保持到滚动/级联动画结束（由 animateScrollTo 的完成回调释放），
    // 让目标行的放大/淡入发生在滚动到位、行可见之后，而不是在屏幕外悄悄完成
    // 旧行逐字 DOM 延后销毁，留 0.4s 给 fadeOutWordSegs 的颜色过渡
    if (fadingTimer) clearTimeout(fadingTimer)
    fadingLineIndex.value = prevWord >= 0 ? prevWord : prevFirst
    fadingTimer = setTimeout(() => { fadingLineIndex.value = -1 }, 400)
  }

  if (nextActive.length === 0) {
    if (jumpPending.value >= 0) jumpPending.value = -1
    // 无活跃行（空区）
    if (showUpcomingHint.value) {
      // 三点显示：把三点滚到中心线（首行前与句中空区统一处理）
      if (!_dotsScrollDone && !isUserScrolling.value) {
        _dotsScrollDone = true
        await nextTick()
        scrollToDots(true)
      }
    } else if (time < parsedLyrics.value[0].time) {
      // 无三点：回到第一句等待
      _dotsScrollDone = true
      await nextTick()
      if (!isUserScrolling.value) scrollToLine(0, true)
    }
    return
  }

  if (isUserScrolling.value) {
    if (jumpPending.value >= 0) jumpPending.value = -1
    // 用户滚轮滚动中：不滚动面板，但需要为新行启动逐字动画
    await nextTick()
    if (nextWord >= 0) startWordAnimLoop()
    return
  }

  await nextTick()
  // 三点自然结束后：用多米诺级联滚动完成位移（含三点行移除的布局位移）
  if (_dotsCascadePending) {
    _dotsCascadePending = false
    runDotsCascade(nextFirst)
    prevLineIndex = nextFirst
    if (jumpPending.value >= 0) jumpPending.value = -1
    if (nextWord >= 0) startWordAnimLoop()
    return
  }
  // 三点行收起中：等收起完成后再测量滚动目标，避免布局未定
  if (hintLeaving.value) {
    await new Promise(r => setTimeout(r, 260))
  }
  scrollToActiveGroup(true)
  await nextTick()
  if (nextWord >= 0) startWordAnimLoop()
})

// 三点显示：滚动到“三点收起后下一句恰好居中”的位置。
// 该位置下三点块也正好位于中心线（三点行高≈歌词行高），
// 三点收起后下一句已居中，激活滚动成为零位移，不会出现第二次滚动。
// 首行前与句中空区统一处理（句中锚定下一句，并用上一行剩余收缩量预补偿）。
function scrollToDots(animate = true) {
  if (!scrollRef.value || !mainRef.value) return
  const anchorIndex = hintAnchorIndex.value >= 0 ? hintAnchorIndex.value + 1 : 0
  const anchorEl = lineRefs.value[anchorIndex]
  if (!anchorEl) return
  const dotsEl = scrollRef.value.querySelector('.upcoming-hint-line')
  const dotsH = dotsEl ? dotsEl.offsetHeight : 0
  const containerHeight = mainRef.value.clientHeight
  let targetScroll = Math.max(0,
    anchorEl.offsetTop - dotsH - containerHeight / 2 + anchorEl.offsetHeight / 2)
  // 句中空区：上一行正从活跃字号收缩回基础字号，会带动三点继续上移。
  // 用“上一行当前高度 - 下一行高度(≈收缩后高度)”预估剩余位移，提前补偿，
  // 避免三点滚到中心后又因上一行收缩而偏上。
  if (hintAnchorIndex.value >= 0) {
    const prevEl = lineRefs.value[hintAnchorIndex.value]
    if (prevEl) {
      const drift = Math.max(0, prevEl.offsetHeight - anchorEl.offsetHeight)
      if (drift > 0) targetScroll = Math.max(0, targetScroll - drift)
    }
  }
  targetScrollPos = targetScroll
  currentScrollY = -targetScroll
  if (!animate) {
    scrollRef.value.style.transition = 'none'
    scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
    return
  }
  scrollRef.value.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
  scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
  setTimeout(() => { if (scrollRef.value) scrollRef.value.style.transition = '' }, 550)
}

// 三点自然结束后：用多米诺级联滚动完成“下一行上移到中心”的位移。
// 三点行在激活瞬间被移除（此时点已全部淡出），移除造成的布局位移（_dotsH）
// 通过行级反向偏移吸收，再按序错峰归位，形成与普通切句一致的多米诺波浪。
function runDotsCascade(nextIndex) {
  if (!scrollRef.value || !mainRef.value) return
  const nextEl = lineRefs.value[nextIndex]
  if (!nextEl) return
  const containerHeight = mainRef.value.clientHeight
  const targetScroll = Math.max(0,
    nextEl.offsetTop - containerHeight / 2 + nextEl.offsetHeight / 2)
  const scrollDelta = targetScroll - targetScrollPos
  const totalLines = parsedLyrics.value.length
  // 下方行：三点行移除的布局位移 + 滚动差；上方行：仅滚动差（通常≈0）
  const belowShift = _dotsH - scrollDelta
  const aboveShift = -scrollDelta

  if (lyricsScrollCleanup) { lyricsScrollCleanup(); lyricsScrollCleanup = null }
  smoothAnimTarget = -1

  // 容器瞬跳到目标位
  scrollRef.value.style.transition = 'none'
  scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
  currentScrollY = -targetScroll
  targetScrollPos = targetScroll
  void scrollRef.value.offsetHeight

  // 各行偏移到反向位置（下方行多偏一个三点行高，抵消移除瞬间的布局位移）
  for (let i = 0; i < totalLines; i++) {
    const el = lineRefs.value[i]
    if (!el) continue
    const shift = i >= nextIndex ? belowShift : aboveShift
    el.style.transition = 'transform 0s, opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0), filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
    el.style.transform = `translate3d(0, ${shift}px, 0)`
  }
  // 读 computedStyle 强制浏览器 commit transform 起始值
  const csAfterOffset = getComputedStyle(nextEl).transform
  void csAfterOffset

  // 从下一行开始向下错峰归位（与普通前进切句的多米诺节奏一致）
  for (let i = 0; i < totalLines; i++) {
    const el = lineRefs.value[i]
    if (!el) continue
    const staggerIdx = i >= nextIndex
      ? Math.min(Math.max(0, i - nextIndex), MAX_STAGGER_LINES)
      : Math.min(Math.max(0, nextIndex - i), MAX_STAGGER_LINES)
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
    if (jumpPending.value >= 0) jumpPending.value = -1
    lyricsScrollCleanup = null
  }
  const timer = setTimeout(cleanup, totalDuration)
  lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
}

const STAGGER_MS = 38
const STAGGER_DURATION = 480
const MAX_STAGGER_LINES = 18

function scrollToLine(index, animate = true) {
  if (index < 0 || !scrollRef.value || !mainRef.value) return
  const lineEl = lineRefs.value[index]
  if (!lineEl) return

  const containerHeight = mainRef.value.clientHeight
  const targetScroll = lineEl.offsetTop - containerHeight / 2 + lineEl.offsetHeight / 2
  animateScrollTo(targetScroll, index, animate)
}

// 滚动到当前活跃行组：多行同时播放时，以这些行的中心点为滚动中心
function scrollToActiveGroup(animate = true) {
  if (!scrollRef.value || !mainRef.value) return
  const active = activeIndexes.value
  if (active.length === 0) {
    return
  }
  if (active.length === 1) {
    scrollToLine(active[0], animate)
    return
  }
  const firstEl = lineRefs.value[active[0]]
  const lastEl = lineRefs.value[active[active.length - 1]]
  if (!firstEl || !lastEl) return

  const containerHeight = mainRef.value.clientHeight
  const top = firstEl.offsetTop
  const bottom = lastEl.offsetTop + lastEl.offsetHeight
  let targetScroll
  if (bottom - top > containerHeight * 0.6) {
    // 异常大组（罕见）：退化为以第一行居中，保证可读
    targetScroll = top - containerHeight / 2 + firstEl.offsetHeight / 2
  } else {
    targetScroll = (top + bottom) / 2 - containerHeight / 2
  }
  animateScrollTo(targetScroll, active[active.length - 1], animate)
}

function animateScrollTo(targetScroll, index, animate = true) {
  const lineEl = lineRefs.value[index]
  if (!lineEl) return
  const containerHeight = mainRef.value.clientHeight
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
      // 级联动画完成后再解除激活缓冲，目标行在可视位置放大/淡入
      if (jumpPending.value >= 0) jumpPending.value = -1
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
        if (jumpPending.value >= 0) jumpPending.value = -1
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
        if (jumpPending.value >= 0) jumpPending.value = -1
        lyricsScrollCleanup = null
      }
      const timer = setTimeout(cleanup, 550)
      lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
    }
  } else {
    scrollRef.value.style.transform = `translate3d(0, ${-targetScroll}px, 0)`
    currentScrollY = -targetScroll
    if (jumpPending.value >= 0) jumpPending.value = -1
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

// 确保封面已解码就绪：优先命中 _coverCache，未命中时主动加载。
// 返回解码后的 Image（含 naturalWidth/Height），供飞入动画直接取原比例。
function _ensureCoverReady(url) {
  if (!url) return Promise.resolve(null)
  if (_coverCache.has(url)) return Promise.resolve(_coverCache.get(url))
  return new Promise((resolve) => {
    const img = new Image()
    img.src = url
    img.decode().then(() => {
      _coverCache.set(url, img)
      while (_coverCache.size > PRELOAD_WINDOW * 2 + 1) {
        _coverCache.delete(_coverCache.keys().next().value)
      }
      resolve(img)
    }).catch(() => resolve(null)) // 即使加载失败也不阻塞飞行动画
  })
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
  activeIndexes.value = []
  hintVisible.value = false
  hintLeaving.value = false
  hintAnchorIndex.value = -1
  _dotsScrollDone = false
  _dotsHandoff = false
  _dotsCascadePending = false
  _dotsH = 0
  stopDotsScaleLoop()
  if (_dotsLeaveTimer) { clearTimeout(_dotsLeaveTimer); _dotsLeaveTimer = null }
  if (lyricsScrollCleanup) { lyricsScrollCleanup(); lyricsScrollCleanup = null }
  if (jumpPending.value >= 0) jumpPending.value = -1
  stopWordAnimLoop()
  targetScrollPos = 0
  prevLineIndex = -1
  if (scrollRef.value) { scrollRef.value.style.transform = 'translate3d(0, 0, 0)'; currentScrollY = 0 }
  // 新歌一开始就处于长空区时立即恢复三点显示：
  // 否则 showUpcomingHint 全程无翻转，三点要等播过首行再跳回才会出现
  if (showUpcomingHint.value) {
    hintVisible.value = true
    hintLeaving.value = false
    hintAnchorIndex.value = hintLineIndex.value
    _dotsScrollDone = false
    startDotsScaleLoop()
  }
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
  stopDotsScaleLoop()
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
  /* filter 通过内联样式动态设置，根据封面亮度自适应 */
  will-change: filter;
}

/* 动态流光 — 多色块高斯模糊漂移产生流体流动感 */
.np-bg__flow {
  position: absolute;
  inset: -10%;
  z-index: 1;
  mix-blend-mode: screen;
  pointer-events: none;
  opacity: 0.5;
}
.np-bg__blob {
  position: absolute;
  /* 让 left/top 锚定光球几何中心（PNG 渐变亮点在正中），避免整体右下偏移 */
  transform: translate(-50%, -50%);
  /* 径向渐变已预渲染到 PNG 中，无 blur/filter 开销 */
  opacity: 0.9;
  display: block;
  will-change: top, left, transform;
}
/* 环形布局初始位置 + 大幅错开 delay（约动画周期 1/6） */
.np-bg__blob--1 { --base-dur: 45s; width: 45%; height: 45%; top: 15%; left: 15%; animation: blob-float-1 var(--base-dur) ease-in-out infinite; }
.np-bg__blob--2 { --base-dur: 52s; width: 50%; height: 50%; top: 10%; left: 50%; animation: blob-float-2 var(--base-dur) ease-in-out infinite 8s; }
.np-bg__blob--3 { --base-dur: 48s; width: 38%; height: 38%; top: 20%; left: 85%; animation: blob-float-3 var(--base-dur) ease-in-out infinite 16s; }
.np-bg__blob--4 { --base-dur: 55s; width: 42%; height: 42%; top: 80%; left: 85%; animation: blob-float-4 var(--base-dur) ease-in-out infinite 24s; }
.np-bg__blob--5 { --base-dur: 42s; width: 35%; height: 35%; top: 90%; left: 50%; animation: blob-float-5 var(--base-dur) ease-in-out infinite 32s; }
.np-bg__blob--6 { --base-dur: 58s; width: 48%; height: 48%; top: 80%; left: 15%; animation: blob-float-6 var(--base-dur) ease-in-out infinite 40s; }

/* 分层响应：低频能量 → 所有光球缩放 | 中频能量 → 光球 2/5 透明度 | 全频能量 → 光球 1/4 透明度 */
.np-bg__blob--2, .np-bg__blob--5 { opacity: var(--flow-opacity-mid, 0.7); }
.np-bg__blob--1, .np-bg__blob--4 { opacity: var(--flow-opacity-hl, 0.7); }

/* 环形布局：左上→上→右上→右下→下→左下 */
@keyframes blob-float-1 {
  /* 光球1：重心左上(15%,20%)，可到中右 */
  0%, 100% { top: 15%; left: 15%; transform: translate(-50%, -50%) rotate(0deg)   scale(var(--flow-scale, 1)); }
  16%       { top: 30%; left: 40%; transform: translate(-50%, -50%) rotate(58deg)  scale(var(--flow-scale, 1)); }
  33%       { top: 10%; left: 65%; transform: translate(-50%, -50%) rotate(119deg) scale(var(--flow-scale, 1)); }
  50%       { top: 40%; left: 25%; transform: translate(-50%, -50%) rotate(180deg) scale(var(--flow-scale, 1)); }
  66%       { top: 20%; left: 55%; transform: translate(-50%, -50%) rotate(238deg) scale(var(--flow-scale, 1)); }
  83%       { top: 35%; left: 10%; transform: translate(-50%, -50%) rotate(299deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-2 {
  /* 光球2：重心上(50%,10%)，可到左右 */
  0%, 100% { top: 10%; left: 50%; transform: translate(-50%, -50%) rotate(0deg)    scale(var(--flow-scale, 1)); }
  16%       { top: 25%; left: 25%; transform: translate(-50%, -50%) rotate(-58deg)  scale(var(--flow-scale, 1)); }
  33%       { top: 5%; left: 75%; transform: translate(-50%, -50%) rotate(-119deg) scale(var(--flow-scale, 1)); }
  50%       { top: 30%; left: 45%; transform: translate(-50%, -50%) rotate(-180deg) scale(var(--flow-scale, 1)); }
  66%       { top: 15%; left: 60%; transform: translate(-50%, -50%) rotate(-238deg) scale(var(--flow-scale, 1)); }
  83%       { top: 20%; left: 30%; transform: translate(-50%, -50%) rotate(-299deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-3 {
  /* 光球3：重心右上(85%,20%)，可到中左 */
  0%, 100% { top: 20%; left: 85%; transform: translate(-50%, -50%) rotate(0deg)  scale(var(--flow-scale, 1)); }
  20%       { top: 35%; left: 60%; transform: translate(-50%, -50%) rotate(72deg) scale(var(--flow-scale, 1)); }
  40%       { top: 15%; left: 35%; transform: translate(-50%, -50%) rotate(144deg) scale(var(--flow-scale, 1)); }
  60%       { top: 40%; left: 75%; transform: translate(-50%, -50%) rotate(216deg) scale(var(--flow-scale, 1)); }
  80%       { top: 25%; left: 50%; transform: translate(-50%, -50%) rotate(288deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-4 {
  /* 光球4：重心右下(85%,80%)，可到中左 */
  0%, 100% { top: 80%; left: 85%; transform: translate(-50%, -50%) rotate(0deg)    scale(var(--flow-scale, 1)); }
  16%       { top: 65%; left: 60%; transform: translate(-50%, -50%) rotate(-58deg)  scale(var(--flow-scale, 1)); }
  33%       { top: 90%; left: 35%; transform: translate(-50%, -50%) rotate(-119deg) scale(var(--flow-scale, 1)); }
  50%       { top: 60%; left: 75%; transform: translate(-50%, -50%) rotate(-180deg) scale(var(--flow-scale, 1)); }
  66%       { top: 85%; left: 50%; transform: translate(-50%, -50%) rotate(-238deg) scale(var(--flow-scale, 1)); }
  83%       { top: 70%; left: 65%; transform: translate(-50%, -50%) rotate(-299deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-5 {
  /* 光球5：重心下(50%,90%)，可到左右 */
  0%, 100% { top: 90%; left: 50%; transform: translate(-50%, -50%) rotate(0deg)   scale(var(--flow-scale, 1)); }
  20%       { top: 75%; left: 75%; transform: translate(-50%, -50%) rotate(72deg)  scale(var(--flow-scale, 1)); }
  40%       { top: 95%; left: 25%; transform: translate(-50%, -50%) rotate(144deg) scale(var(--flow-scale, 1)); }
  60%       { top: 70%; left: 60%; transform: translate(-50%, -50%) rotate(216deg) scale(var(--flow-scale, 1)); }
  80%       { top: 85%; left: 40%; transform: translate(-50%, -50%) rotate(288deg) scale(var(--flow-scale, 1)); }
}
@keyframes blob-float-6 {
  /* 光球6：重心左下(15%,80%)，可到中右 */
  0%, 100% { top: 80%; left: 15%; transform: translate(-50%, -50%) rotate(0deg)    scale(var(--flow-scale, 1)); }
  16%       { top: 65%; left: 40%; transform: translate(-50%, -50%) rotate(-58deg)  scale(var(--flow-scale, 1)); }
  33%       { top: 85%; left: 65%; transform: translate(-50%, -50%) rotate(-119deg) scale(var(--flow-scale, 1)); }
  50%       { top: 60%; left: 25%; transform: translate(-50%, -50%) rotate(-180deg) scale(var(--flow-scale, 1)); }
  66%       { top: 75%; left: 55%; transform: translate(-50%, -50%) rotate(-238deg) scale(var(--flow-scale, 1)); }
  83%       { top: 70%; left: 35%; transform: translate(-50%, -50%) rotate(-299deg) scale(var(--flow-scale, 1)); }
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
  /* 默认方形；加载到封面后按原图比例显示，且不超出最大高度 46vh */
  width: min(clamp(240px, 26vw, 520px), calc(46vh * var(--cover-ratio, 1)));
  aspect-ratio: var(--cover-ratio, 1);
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
              font-weight 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              max-width 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lyric-line__translation {
  margin: 0; font-size: var(--lyrics-base-trans, 10px); line-height: 1.3;
  font-weight: var(--lyrics-weight, 700); color: rgba(255,255,255,0.12);
  max-width: var(--lyrics-trans-ch-limit);
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-size 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              max-width 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0);
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

/* 空区长间隔提示：独立行（仅三点，无文字）；不挂 lyric-line，无 hover/指针交互 */
.upcoming-hint-line {
  padding: 8px 0;
  max-height: calc(var(--lyrics-active-original, 24px) * 1.4 + 16px);
  overflow: hidden;
  display: flex;
  align-items: center;
  pointer-events: none;
  user-select: none;
  /* 挂载即播放入场：展开 + 模糊收拢（离场直接 v-if 移除，保证滚动测量布局正确） */
  animation: upcoming-hint-in 0.3s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
@keyframes upcoming-hint-in {
  from {
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
    opacity: 0;
    filter: blur(6px);
    transform: scale(0.92);
  }
  to {
    max-height: calc(var(--lyrics-active-original, 24px) * 1.4 + 16px);
    padding-top: 8px;
    padding-bottom: 8px;
    opacity: 1;
    filter: blur(0);
    transform: scale(1);
  }
}
/* 离场：0.25s 平滑收起（下方行连续上滑）。
   缓动与滚动动画一致（B1 同步滚动），点行高度同步收缩，
   使折叠高度随时间线性变化，与滚动位移合成一条连续运动 */
.upcoming-hint-line--leaving {
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  transition: max-height 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              padding-top 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              padding-bottom 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.upcoming-hint-line--leaving .upcoming-hint-dots {
  height: 0;
  transition: height 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.upcoming-hint-dots {
  margin: 0;
  /* 与正在播放行的原词行同高（仅原词行，不含翻译行），并随歌词字号设置缩放 */
  height: calc(var(--lyrics-active-original, 24px) * 1.4);
  display: inline-flex;
  align-items: center;
  gap: 16px;
  /* 点最大尺寸 = 7px × DOT_MAX_SCALE(2.3)，以大尺寸渲染保证放大后边缘清晰 */
  --dot-max-px: 16.1px;
}
/* 更大的点 + 倒计时缩放（随起播逼近依次变大）。
   外层固定 7px：负责逐个弹出入场与淡出（中心收缩）；
   内层 __scale 用 transform scale 生长：GPU 合成、亚像素平滑，
   原点居左 → 只向右生长，不越界、无裁切，不再有 px 步进卡顿 */
.upcoming-hint-dot {
  width: 7px;
  height: 7px;
  position: relative;
  border-radius: 50%;
  /* 入场：三个点逐个弹出放大（backwards 保证延迟期内不可见，结束后交给倒计时缩放） */
  animation: upcoming-dot-in 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.0) backwards;
}
.upcoming-hint-dot__scale {
  position: absolute;
  left: 0;
  top: 50%;
  width: var(--dot-max-px);
  height: var(--dot-max-px);
  /* 垂直居中：原点位于自身中心（left center），放大时只向右生长 */
  margin-top: calc(var(--dot-max-px) / -2);
  border-radius: 50%;
  background: rgba(255,255,255,0.65);
  /* --dot-scale 已归一化为 1/2.3 → 1：全分辨率渲染后向下缩放，任意尺寸都清晰；
     rAF 按帧更新，无 transition，避免 250ms 节拍追赶造成顿挫 */
  transform: scale(var(--dot-scale, 0.4348));
  transform-origin: left center;
  will-change: transform;
}
.upcoming-hint-dot:nth-child(2) { animation-delay: 0.18s; }
.upcoming-hint-dot:nth-child(3) { animation-delay: 0.36s; }
@keyframes upcoming-dot-in {
  from { transform: scale(0); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
/* 起播前依次模糊消失（dot3→dot2→dot1），每个淡出 1 秒，
   左边第一个点在下句开始瞬间完全消失 */
.upcoming-hint-dot--fade {
  opacity: 0;
  filter: blur(6px);
  transform: scale(0.4);
  transform-origin: center;
  transition: opacity 1s ease,
              filter 1s ease,
              transform 1s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

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
  transition: opacity 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lyrics-next-leave-active,
.lyrics-prev-leave-active {
  transition: opacity 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
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
/* 切歌：新歌词渐显+从模糊到清晰，旧歌词渐隐+模糊（不位移，避免与滚动 transform 冲突） */
.lyrics-next-enter-from { opacity: 0; filter: blur(10px); }
.lyrics-next-leave-to   { opacity: 0; filter: blur(10px); }
.lyrics-prev-enter-from { opacity: 0; filter: blur(10px); }
.lyrics-prev-leave-to   { opacity: 0; filter: blur(10px); }
/* 无动画（初始状态） */
.lyrics-none-enter-active,
.lyrics-none-leave-active {
  transition: none;
}
</style>
