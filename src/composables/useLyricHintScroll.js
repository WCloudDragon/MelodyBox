import { dotsCenteredScroll, dotsCascadeShifts } from '@/utils/lyricLayout'
import { STAGGER_DURATION } from '@/composables/useLyricScroll'

/**
 * 三点提示的滚动与交接
 *
 * 只处理两种位移：
 *   1. 空区中把三点滚到中心线（scrollToDots）
 *   2. 三点自然结束后，用多米诺级联把下一行上移到中心（runDotsCascade）
 *
 * 显示/倒计时状态由 useLyricHintTiming 提供；本模块只读取锚点与三点高度。
 */
export function useLyricHintScroll({
  mainRef,
  scrollRef,
  lineRefs,
  jumpPending,
  getLines,
  getHintAnchorIndex,
  getDotsHeight,
  scrollState,
  commitContainerScroll,
  lyricContainerHeight,
  staggerDelays
}) {
  // 把三点提示滚到中心线：首行前与句中空区统一处理
  function scrollToDots(animate = true) {
    if (!scrollRef.value || !mainRef.value) return
    const anchorIdx = getHintAnchorIndex()
    const anchorIndex = anchorIdx >= 0 ? anchorIdx + 1 : 0
    const anchorEl = lineRefs.value[anchorIndex]
    if (!anchorEl) return
    const dotsEl = scrollRef.value.querySelector('.upcoming-hint-line')
    const containerHeight = lyricContainerHeight()
    // 句中空区：上一行正从活跃字号收缩回基础字号，会带动三点继续上移，
    // 由 dotsCenteredScroll 用「上一行当前高度 - 下一行高度」预估剩余位移并提前补偿
    const prevEl = anchorIdx >= 0 ? lineRefs.value[anchorIdx] : null
    const targetScroll = dotsCenteredScroll(anchorEl, dotsEl, prevEl, containerHeight)
    scrollState.targetScrollPos = targetScroll
    if (!animate) {
      commitContainerScroll(-targetScroll, 'none')
      return
    }
    commitContainerScroll(-targetScroll, 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)')
    setTimeout(() => { if (scrollRef.value) scrollRef.value.style.transition = '' }, 550)
  }

  // 三点自然结束后：用多米诺级联滚动完成“下一行上移到中心”的位移。
  // 三点行在激活瞬间被移除（此时点已全部淡出），移除造成的布局位移（dotsH）
  // 通过行级反向偏移吸收，再按序错峰归位，形成与普通切句一致的多米诺波浪。
  function runDotsCascade(nextIndex) {
    if (!scrollRef.value || !mainRef.value) return
    const nextEl = lineRefs.value[nextIndex]
    if (!nextEl) return
    const containerHeight = lyricContainerHeight()
    const totalLines = getLines().length
    // 下方行：三点行移除的布局位移 + 滚动差；上方行：仅滚动差（通常≈0）
    const { targetScroll, belowShift, aboveShift } = dotsCascadeShifts(
      nextEl, containerHeight, scrollState.targetScrollPos, getDotsHeight())

    if (scrollState.lyricsScrollCleanup) { scrollState.lyricsScrollCleanup(); scrollState.lyricsScrollCleanup = null }
    scrollState.smoothAnimTarget = -1

    // 容器瞬跳到目标位
    commitContainerScroll(-targetScroll, 'none')
    scrollState.targetScrollPos = targetScroll
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

    // 归位：固定每行 STAGGER_STEP 的触发间隔（三点结束恒向下播放，由视口首行起推进）
    const viewportTop = targetScroll
    const viewportH = Math.max(1, containerHeight)
    const { delays, totalStagger } = staggerDelays(totalLines, viewportTop, viewportH, true, nextIndex)
    for (let i = 0; i < totalLines; i++) {
      const el = lineRefs.value[i]
      if (!el) continue
      el.style.transition = `transform ${STAGGER_DURATION}ms cubic-bezier(0.2, 0.9, 0.3, 1.0) ${delays[i]}s, opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0), filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0)`
      el.style.transform = 'translate3d(0, 0, 0)'
    }

    const totalDuration = STAGGER_DURATION + totalStagger * 1000 + 60
    scrollState.dominoCascadeActive = true
    const cleanup = () => {
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (el) { el.style.transform = ''; el.style.transition = '' }
      }
      if (scrollRef.value) { scrollRef.value.style.willChange = ''; scrollRef.value.style.transition = '' }
      if (jumpPending.value >= 0) jumpPending.value = -1
      scrollState.dominoCascadeActive = false
      scrollState.lyricsScrollCleanup = null
    }
    const timer = setTimeout(cleanup, totalDuration)
    scrollState.lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
  }

  return { scrollToDots, runDotsCascade }
}
