import { onBeforeUnmount, ref } from 'vue'
import {
    clampManualScroll,
    anchorScrollForLine
} from '@/utils/lyricLayout'

/**
 * 歌词视口编排
 *
 * 负责「窗口/容器尺寸变化后，把视口重新对回正确位置」以及「用户手动滚动」：
 *   - 布局冻结、幂等重居中、三点/空区两种额外锚点
 *   - 用户滚动内容锚点、5 秒回位、拖窗视为交互
 *   - ResizeObserver 与容器尺寸跟踪
 *
 * 不持有歌词数据与提示状态：行数据、活跃集合、提示锚点均通过 getter 注入。
 */
export function useLyricViewport({
    mainRef,
    scrollRef,
    lineRefs,
    jumpPending,
    isScrubbing,
    windowWidth,
    scrollState,
    scrollToLine,
    scrollToActiveGroup,
    commitContainerScroll,
    lyricContainerHeight,
    getShowHint,
    getHintAnchorIndex,
    getHintLineIndex,
    getLines,
    getActiveIndexes,
    getLiveTime,
    visible
}) {
    const isUserScrolling = ref(false)
    let userScrollTimer = null
    let userScrollAnchor = null
    const isResizing = ref(false)
    let layoutFreezeTimer = null
    let recenterFrame = 0
    let layoutObserver = null
    let observedWidth = 0
    let observedHeight = 0

    function onResize() {
      windowWidth.value = window.innerWidth
      // 冻结会改变行高/换行的过渡，让几何立即收敛到终值；
      // 随后按新几何重新居中，避免校正读到过渡中间态
      freezeLayoutFor(180)
      // 拖动窗口同样算一次交互：持续拖动期间不断顺延回位计时
      armUserScrollIdle()
      scheduleRecenter()
    }

    // 冻结会改变排版的过渡（字号 / 换行宽度 / 内边距 / 最小高度），
    // 让几何立即收敛；颜色、透明度、滤镜等不影响布局的过渡保持不变
    function freezeLayoutFor(ms) {
      isResizing.value = true
      if (layoutFreezeTimer) clearTimeout(layoutFreezeTimer)
      layoutFreezeTimer = setTimeout(() => {
        layoutFreezeTimer = null
        isResizing.value = false
        scheduleRecenter()
        // 校正写入使用的是 transition:none，恢复后不影响后续切句动画；
        // 用户滚动模式下要恢复滚轮滚动自己的过渡，否则下一次滚动会变生硬
        requestAnimationFrame(() => {
          if (!scrollRef.value) return
          scrollRef.value.style.transition = isUserScrolling.value ? 'transform 0.15s ease-out' : ''
        })
      }, ms)
    }

    function scheduleRecenter() {
      if (recenterFrame) return
      recenterFrame = requestAnimationFrame(() => {
        recenterFrame = 0
        recenterNow()
      })
    }

    // 当前应居中的滚动目标：活跃行组 → 三点提示 → 空区锚点。
    // 三套口径分别对齐 scrollToActiveGroup / scrollToDots / repositionToEmptyZoneAnchor
    function computeCenteredTarget() {
      if (!mainRef.value || !scrollRef.value) return null
      const H = lyricContainerHeight()
      const act = getActiveIndexes()

      if (act.length > 0) {
        const firstEl = lineRefs.value[act[0]]
        const lastEl = lineRefs.value[act[act.length - 1]]
        if (!firstEl || !lastEl) return null
        if (act.length === 1) {
          return { y: lineCenteredScroll(firstEl, H), index: act[0] }
        }
        // 异常大组由 activeGroupScroll 内部退化为以第一行居中，保证可读
        return { y: activeGroupScroll(firstEl, lastEl, H), index: act[act.length - 1] }
      }

      if (hintVisible.value) {
        const anchorIndex = getHintAnchorIndex() >= 0 ? getHintAnchorIndex() + 1 : 0
        const anchorEl = lineRefs.value[anchorIndex]
        if (!anchorEl) return null
        const dotsEl = scrollRef.value.querySelector('.upcoming-hint-line')
        // 句中空区：上一行仍从活跃字号收缩，由 dotsCenteredScroll 预留其剩余位移
        const prevEl = getHintAnchorIndex() >= 0 ? lineRefs.value[getHintAnchorIndex()] : null
        return { y: dotsCenteredScroll(anchorEl, dotsEl, prevEl, H), index: anchorIndex }
      }

      const list = getLines()
      if (!list.length) return null
      const now = getLiveTime()
      const target = now < list[0].time ? 0 : getHintLineIndex()
      if (target < 0 || target >= list.length) return null
      const el = lineRefs.value[target]
      if (!el) return null
      return { y: lineCenteredScroll(el, H), index: target }
    }

    function applyCenteredScroll(target) {
      if (!scrollRef.value) return
      // 取消进行中的级联 / 平滑动画，避免两套位移叠加
      if (scrollState.lyricsScrollCleanup) { scrollState.lyricsScrollCleanup(); scrollState.lyricsScrollCleanup = null }
      scrollState.smoothAnimTarget = -1
      scrollState.dominoCascadeActive = false
      commitContainerScroll(-target.y, 'none')
      scrollState.targetScrollPos = target.y
      scrollState.prevLineIndex = target.index
      if (jumpPending.value >= 0) jumpPending.value = -1
    }

    // 记录用户滚动模式的中心锚点：index = 中心落在哪一行，ratio = 行内比例。
    // 用内容坐标而非 scrollY，几何变化后才能把同一处内容重新对回中心
    function captureUserScrollAnchor(scrollY, containerHeight) {
      const list = getLines()
      if (!list.length) { userScrollAnchor = null; return }
      const centerY = -scrollY + containerHeight / 2
      let nearest = null
      let nearestDist = Infinity
      for (let i = 0; i < list.length; i++) {
        const el = lineRefs.value[i]
        if (!el) continue
        const top = el.offsetTop
        const h = el.offsetHeight || 1
        if (centerY >= top && centerY <= top + h) {
          userScrollAnchor = { index: i, ratio: (centerY - top) / h, count: list.length }
          return
        }
        // 中心落在行间空隙（三点提示行 / 内边距）时，取最近一行并钳到边界
        const dist = centerY < top ? top - centerY : centerY - (top + h)
        if (dist < nearestDist) {
          nearestDist = dist
          nearest = { index: i, ratio: centerY < top ? 0 : 1 }
        }
      }
      userScrollAnchor = nearest ? { ...nearest, count: list.length } : null
    }

    // 按锚点推算当前应居中的滚动量；行列表变化或元素丢失时放弃（退回不处理）
    function computeUserScrollTarget() {
      const anchor = userScrollAnchor
      if (!anchor || !mainRef.value) return null
      if (anchor.count !== getLines().length) { userScrollAnchor = null; return null }
      const el = lineRefs.value[anchor.index]
      if (!el) { userScrollAnchor = null; return null }
      const y = anchorScrollForLine(el, anchor.ratio, lyricContainerHeight())
      return Number.isFinite(y) ? { y } : null
    }

    // 用户滚动模式下的重居中：只改位置，不改滚动状态、不重置 5 秒回位计时
    function applyUserScrollRecenter(y) {
      if (!scrollRef.value || !mainRef.value) return
      // 中断可能残留的级联动画，避免两套位移叠加
      if (scrollState.lyricsScrollCleanup) { scrollState.lyricsScrollCleanup(); scrollState.lyricsScrollCleanup = null }
      scrollState.smoothAnimTarget = -1
      scrollState.dominoCascadeActive = false
      // 与滚轮同一套边界钳制，避免把内容推到可视区之外
      const ty = clampManualScroll(-y, scrollRef.value.scrollHeight, lyricContainerHeight())
      commitContainerScroll(ty, 'none')
      // 恢复滚轮滚动应有的过渡，否则下一次滚动会变得生硬
      requestAnimationFrame(() => {
        if (scrollRef.value) scrollRef.value.style.transition = 'transform 0.15s ease-out'
      })
    }

    function recenterNow() {
      if (!visible() || !hasLyrics.value) return
      // 进度条拖拽预览期间由 scrollToLinePreview 接管，不与它抢
      if (isScrubbing.value) return

      // 用户手动滚动中：以「视口中心当前对应的那处内容」为锚点重新居中，
      // 而不是跳回正在播放的行——此时用户关注的是自己滚到的位置
      if (isUserScrolling.value) {
        const anchorTarget = computeUserScrollTarget()
        if (!anchorTarget) return
        // scrollState.currentScrollY 是 transform 值（向下为负），换算成正向滚动量比较
        if (Math.abs(anchorTarget.y + scrollState.currentScrollY) < 0.5) return
        applyUserScrollRecenter(anchorTarget.y)
        return
      }

      const target = computeCenteredTarget()
      if (!target || !Number.isFinite(target.y)) return
      // 已对准就什么都不做，避免打断正常播放中的级联动画
      if (Math.abs(target.y - scrollState.targetScrollPos) < 0.5) return
      applyCenteredScroll(target)
    }

    // 容器尺寸变化的权威来源：覆盖窗口缩放、侧栏开合、内边距变化等
    // window.resize 看不到的情况。只观察容器，不观察内容——内容高度在每次
    // 切句时都会随活跃行字号过渡变化，观察它会误触发校正、打断多米诺
    function syncLayoutObserver() {
      if (layoutObserver) { layoutObserver.disconnect(); layoutObserver = null }
      if (typeof ResizeObserver === 'undefined') return
      if (!visible() || !currentTrack.value || !mainRef.value) return
      observedWidth = mainRef.value.clientWidth
      observedHeight = lyricContainerHeight()
      layoutObserver = new ResizeObserver((entries) => {
        const rect = entries[0] && entries[0].contentRect
        if (!rect) return
        const w = Math.round(rect.width)
        const h = Math.round(rect.height)
        if (w === observedWidth && h === observedHeight) return
        observedWidth = w
        observedHeight = h
        freezeLayoutFor(180)
        // 容器尺寸变化同样视为一次交互（拖动窗口会连续触发，回位计时被持续顺延）
        armUserScrollIdle()
        scheduleRecenter()
      })
      layoutObserver.observe(mainRef.value)
    }

    // ==================== 用户滚轮滚动歌词 ====================
    function exitUserScrollMode() {
      isUserScrolling.value = false
      userScrollAnchor = null
      if (scrollRef.value) scrollRef.value.style.transition = ''
      if (userScrollTimer) { clearTimeout(userScrollTimer); userScrollTimer = null }
    }

    // 重置/顺延「手动滚动自动回位」计时。滚轮与窗口拖动都算交互：
    // 拖动窗口会持续数秒，期间反复调用即可保证松手前不会被拉回播放行
    function armUserScrollIdle() {
      if (!isUserScrolling.value) return
      if (userScrollTimer) clearTimeout(userScrollTimer)
      userScrollTimer = setTimeout(() => {
        userScrollTimer = null
        // 仍在拖动窗口（resize 尚未落定）时继续顺延，避免中途跳回
        if (isResizing.value) { armUserScrollIdle(); return }
        resetUserScroll()
      }, 5000)
    }

    function resetUserScroll() {
      exitUserScrollMode()
      // 同步用户滚动到的实际位置，使 scrollToLine 感知真实距离从而走平滑动画分支
      scrollState.targetScrollPos = -scrollState.currentScrollY
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

      // 从当前 computed transform 读取位置
      const currentTransform = getComputedStyle(scrollRef.value).transform
      const match = currentTransform.match(/matrix\(1,\s*0,\s*0,\s*1,\s*0,\s*(-?[\d.]+)\)/)
      const currentY = match ? parseFloat(match[1]) : -scrollState.targetScrollPos

      let newY = currentY - e.deltaY * 2

      // 边界钳制
      const containerHeight = lyricContainerHeight()
      newY = clampManualScroll(newY, scrollRef.value.scrollHeight, containerHeight)

      commitContainerScroll(newY)
      // 记录视口中心的内容锚点：窗口尺寸变化后据此把同一处内容重新对回中心
      captureUserScrollAnchor(newY, containerHeight)

      // 5秒无操作后自动回位
      armUserScrollIdle()
    }

    // 无活跃行的短空区 / 末尾空区：视口偏离锚点半屏以上时补一次定位。
    // 锚点取空区之后的第一句（末尾空区取最后一句），使其居中显示
    async function repositionToEmptyZoneAnchor() {
      if (isUserScrolling.value || !mainRef.value || !scrollRef.value) return
      const list = getLines()
      const anchor = getHintLineIndex()
      if (anchor < 0) return
      const targetIndex = anchor + 1 < list.length ? anchor + 1 : anchor
      const el = lineRefs.value[targetIndex]
      if (!el) return
      const containerHeight = lyricContainerHeight()
      const desired = lineCenteredScroll(el, containerHeight)
      if (Math.abs(desired - scrollState.targetScrollPos) <= containerHeight * 0.5) return
      await nextTick()
      scrollToLine(targetIndex, true)
    }
    function disposeViewport() {
        if (layoutObserver) { layoutObserver.disconnect(); layoutObserver = null }
        if (layoutFreezeTimer) { clearTimeout(layoutFreezeTimer); layoutFreezeTimer = null }
        if (recenterFrame) { cancelAnimationFrame(recenterFrame); recenterFrame = 0 }
        if (userScrollTimer) { clearTimeout(userScrollTimer); userScrollTimer = null }
    }

    onBeforeUnmount(disposeViewport)

    return {
        isUserScrolling,
        isResizing,
        onResize,
        onLyricsWheel,
        exitUserScrollMode,
        repositionToEmptyZoneAnchor,
        freezeLayoutFor,
        scheduleRecenter,
        syncLayoutObserver,
        disposeViewport
    }
}
