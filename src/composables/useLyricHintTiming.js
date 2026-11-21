import { computed, ref } from 'vue'
import { LYRIC_GAP_FILL_LIMIT } from '@/utils/format'

/**
 * 三点提示的时序与缩放
 *
 * 只负责「什么时候该显示三点、每个点该多大、倒计时还剩多久」：
 *   - 空区判定（首行前 / 句中 gap）
 *   - 逐点生长区间与淡出顺序
 *   - 基于音频实时时钟的平滑倒计时
 *   - 每帧写 --dot-scale 的 rAF 循环
 *
 * 不负责滚动与交接（那部分留在组件/后续 composable）。
 */

export const DOT_MAX_SCALE = 2.3

export function useLyricHintTiming({
  getLines,
  getActiveIndexes,
  getCurrentTime,
  getLiveTime,
  getTrackLyrics,
  hasLyrics,
  visible,
  getScrollRef
}) {
  // 三点行的显示/收起状态：收起时保持挂载做 0.25s 平滑折叠，避免下方行闪现
  const hintVisible = ref(false)
  const hintLeaving = ref(false)
  // 三点行展开动画开关：切歌时三点与新歌词同帧以最终高度出现（不做高度动画，
  // 否则切歌重活阻塞首帧时，0.3s 展开动画会被跳帧压缩成瞬间让位）；仅句中空区后插入时才展开
  const dotsEntering = ref(false)
  // 三点行位置锚点：显示时冻结，收起期间不随时间变化，避免位置被“偷换”导致闪烁
  const hintAnchorIndex = ref(-1)

  // 提示所在行：空区前刚结束的一行（首行前为 -1）
  const hintLineIndex = computed(() => {
    const list = getLines()
    const now = getCurrentTime()
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
    const list = getLines()
    if (!list.length) return Infinity
    const now = getCurrentTime()
    let next = Infinity
    for (const line of list) {
      if (line.time > now && line.time < next) next = line.time
    }
    return next - now
  })

  // 当前空区的总长度（首行前 = 首行开始时间；句中 = 上一行的 gap）
  const upcomingZoneLength = computed(() => {
    const list = getLines()
    if (!list.length) return 0
    const now = getCurrentTime()
    if (now < list[0].time) return list[0].time
    const prev = hintLineIndex.value
    return prev >= 0 ? (list[prev].gap ?? 0) : 0
  })

  // 长间隔“即将开唱”提示：仅当进入无活跃行的空区（该空区总长度 ≥ 填缝上限）时显示。
  // 空区长度由模型层预计算（line.gap / 首行开始时间），显示状态稳定，不随时间翻转。
  const showUpcomingHint = computed(() => {
    if (!hasLyrics()) return false
    if (getActiveIndexes().length > 0) return false
    // 纯音乐等无演唱内容：不显示提示
    if (/纯音乐/.test(getTrackLyrics() || '')) return false
    // 左边第一个点完全消失即下句开始：到点时元素无动画移除
    if (upcomingRemaining.value <= 0) return false
    const list = getLines()
    const now = getCurrentTime()
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
    const list = getLines()
    if (!list.length) return Infinity
    const now = getLiveTime()
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
      const scrollEl = getScrollRef()
      if (!visible() || !hintVisible.value || hintLeaving.value || !scrollEl) {
        _dotsScaleRaf = null
        return
      }
      const rem = liveUpcomingRemaining()
      const dots = scrollEl.querySelectorAll('.upcoming-hint-dot__scale')
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

  // 句中空区后插入：先以 max-height:0 挂载，下一帧撤掉 --enter 触发高度过渡
  function playDotsEnter() {
    dotsEntering.value = true
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { dotsEntering.value = false })
    })
  }

  return {
    DOT_MAX_SCALE,
    hintVisible,
    hintLeaving,
    dotsEntering,
    hintAnchorIndex,
    hintLineIndex,
    upcomingRemaining,
    upcomingZoneLength,
    showUpcomingHint,
    dotScale,
    dotFading,
    liveUpcomingRemaining,
    startDotsScaleLoop,
    stopDotsScaleLoop,
    playDotsEnter
  }
}
