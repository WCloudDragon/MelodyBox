/**
 * 歌词滚动动画引擎
 *
 * 职责边界：
 *   1. 唯一持有滚动状态（目标/当前位置、方向缓冲、在跑动画的取消句柄）
 *   2. 唯一写容器 transform（commitContainerScroll）
 *   3. 唯一读取歌词可视区高度（lyricContainerHeight）
 *   4. 提供三种位移策略（instant / smooth / domino）及调度入口 animateScrollTo
 *
 * 不依赖组件内部状态：行元素、行数据、活跃集合、多米诺开关均通过参数注入。
 * 本模块不操作 DOM 结构，只写 transform / transition 等内联样式。
 */

export const STAGGER_DURATION = 700
export const STAGGER_STEP = 0.06

export function useLyricScroll({
    mainRef,
    scrollRef,
    lineRefs,
    jumpPending,
    getLines,
    getActiveIndexes,
    getDominoEnabled
}) {
    // 歌词滚动的动画状态机：唯一持有目标/当前位置、方向缓冲与在跑动画的取消句柄。
    // 不变量：任何一次落位都必须同时更新 currentScrollY 与 targetScrollPos；
    // 有动画在跑时 lyricsScrollCleanup 非空，取消后必须置空。
    const state = {
      // 上一次设定的目标滚动量（内容坐标，不是视觉位置）
      targetScrollPos: 0,
      // 容器 transform 的 Y 值（向下为负）
      currentScrollY: 0,
      // 上一个锚定行，只用于判断方向与「是否首次定位」
      prevLineIndex: -1,
      // 正在执行的大跨度平滑动画目标行；-1 表示无动画
      smoothAnimTarget: -1,
      // 多米诺级联进行中：新定位请求可中途接续（FLIP）
      dominoCascadeActive: false,
      // 当前动画的取消函数；非空表示有动画在跑
      lyricsScrollCleanup: null
    }

    // 歌词可视区高度的唯一读取点：容器结构/内边距若调整，只需改这一处
    function lyricContainerHeight() {
      return mainRef.value ? mainRef.value.clientHeight : 0
    }

    // 容器滚动位置的唯一写入入口：transform 与 state.currentScrollY 永远同步落值。
    // transition 传 undefined 表示沿用当前过渡（滚轮模式或调用方已自行设置）。
    // 例外：大跨度跳转的 WAAPI 仍由 animate() 驱动，但落值同样走这里。
    function commitContainerScroll(transformY, transition) {
      if (!scrollRef.value) return
      if (transition !== undefined) scrollRef.value.style.transition = transition
      scrollRef.value.style.transform = `translate3d(0, ${transformY}px, 0)`
      state.currentScrollY = transformY
    }

    // 每行多米诺滚动动画时长（固定值，不随位移距离/行数/视口变化）

    // 相邻行的触发间隔：固定 60ms/行，级联节奏与视口高度无关；
    // 视口外的行钳制到可见范围边界，避免延迟随总行数无限增长

    // 计算每行延迟：向下播放以视口首行为波前起点、向上播放以末行为起点，
    // 延迟只取决于「行与起点的索引距离」，与视口高度无关
    function staggerDelays(totalLines, viewportTop, viewportH, forward, fallbackIndex) {
      let first = -1
      let last = -1
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (!el) continue
        const rel = (el.offsetTop - viewportTop) / viewportH
        if (rel >= 0 && rel <= 1) {
          if (first < 0) first = i
          last = i
        }
      }
      if (first < 0) first = last = Math.max(0, Math.min(totalLines - 1, fallbackIndex))
      const anchor = forward ? first : last
      const span = Math.max(1, last - first)
      const delays = new Array(totalLines)
      let maxSteps = 0
      for (let i = 0; i < totalLines; i++) {
        if (!lineRefs.value[i]) continue
        const steps = Math.min(Math.abs(i - anchor), span)
        delays[i] = steps * STAGGER_STEP
        if (steps > maxSteps) maxSteps = steps
      }
      return { delays, totalStagger: maxSteps * STAGGER_STEP }
    }

    // 接续捕获：上一次多米诺级联仍在进行时，先读每行当前插值 transform 作为新级联起点（FLIP）。
    // start = cur + scrollDelta 保证容器瞬跳后每行屏幕位置在切换瞬间逐像素连续；
    // 已归位的行 cur=0，退化为普通级联起点。
    function captureHandoverStarts(totalLines, dominoHandover) {
      if (!dominoHandover) return null
      const starts = new Array(totalLines).fill(0)
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (!el) continue
        const m = getComputedStyle(el).transform
        if (!m || m === 'none') continue
        const m3 = m.match(/matrix3d\(([^)]+)\)/)
        if (m3) {
          starts[i] = parseFloat(m3[1].split(',')[14]) || 0
        } else {
          const parts = m.match(/matrix\(([^)]+)\)/)
          if (parts) starts[i] = parseFloat(parts[1].split(',')[5]) || 0
        }
      }
      return starts
    }

    // 取消上一次未完成的清理定时器，并重置行级 transform
    // （不清除 opacity/filter transition，保留 CSS 中的过渡）
    function resetLineTransformsAndAnimations(totalLines) {
      if (state.lyricsScrollCleanup) { state.lyricsScrollCleanup(); state.lyricsScrollCleanup = null }
      state.smoothAnimTarget = -1
      state.dominoCascadeActive = false
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (el) { el.style.transform = '' }
      }
      scrollRef.value.style.transition = 'none'
      void scrollRef.value.offsetHeight  // 强制重排
    }

    // 目标句时长：判定是否降级为普通滚动（密集短句不适用多米诺）。
    // 优先用本行结束时间戳：对白/合唱轨穿插时，数组下一行可能与本行几乎同时开始
    // （如 59.00 主唱与 59.04 对白），用下一行开始算出的 0.04s 假 span 会把正常切句
    // 误判成 60ms 快滚；无结束戳的逐句 LRC 退回下一行开始。
    // 多行同播除外：重叠句的 lineSpan 天然偏短，若照常降级会把双行同播误判为密集快滚。
    function measureAnchorLineSpan(index) {
      const lyricsArr = getLines() || []
      const lineStart = lyricsArr[index]?.time
      const anchorEnd = lyricsArr[index]?.end
      const nextStart = lyricsArr[index + 1]?.time
      const lineSpan = (lineStart != null && anchorEnd != null && anchorEnd > lineStart)
        ? anchorEnd - lineStart
        : (lineStart != null && nextStart != null && nextStart > lineStart
            ? nextStart - lineStart
            : Infinity)
      const multiLine = getActiveIndexes().length > 1
      const shortLine = !multiLine && lineSpan * 1000 < STAGGER_DURATION
      // 降级动画时长与句时间戳长度匹配（下限 60ms 保证可感知，上限即级联阈值）
      const matchedMs = shortLine
        ? Math.max(60, Math.round(lineSpan * 1000))
        : 500
      return { shortLine, matchedMs }
    }

    function animateScrollTo(targetScroll, index, animate = true) {
      const lineEl = lineRefs.value[index]
      if (!lineEl) return
      const containerHeight = lyricContainerHeight()
      const scrollDelta = targetScroll - state.targetScrollPos

      // 平滑动画进行中：跳过相邻位置的小范围滚动，避免打断大跨度动画
      // 不更新 state.targetScrollPos（保持为平滑动画起点），动画完成后由下次自然播放触发多米诺过渡
      // 但仅差1行时不跳过：如 seek 到 A 句尾部 → A 即播完切 B → B 应马上多米诺到位
      if (state.smoothAnimTarget >= 0 && Math.abs(scrollDelta) <= containerHeight && animate
          && Math.abs(index - state.smoothAnimTarget) > 1) {
        state.prevLineIndex = index
        return
      }

      const totalLines = getLines().length
      const dominoHandover = state.dominoCascadeActive && animate
      const handoverStarts = captureHandoverStarts(totalLines, dominoHandover)
      resetLineTransformsAndAnimations(totalLines)

      // 3. 用稳定变量计算差值，避免 DOM 中间态 / translateZ(0) 污染
      const absScrollDelta = Math.abs(scrollDelta)
      // 大跨度已由平滑动画接管，多米诺仅处理 ≤容器高度的中小滚动，无需反转
      const sign = Math.sign(scrollDelta)
      const visualDelta = sign * Math.min(absScrollDelta, containerHeight * 0.3)
      const isInitial = state.prevLineIndex < 0
      state.targetScrollPos = targetScroll

      const { shortLine, matchedMs } = measureAnchorLineSpan(index)

      // 大跨度（>容器高度）用平滑滚动，避免闪现；中小跨度用多米诺；短句一律普通滚动
      const useDomino = getDominoEnabled() && !isInitial && Math.abs(scrollDelta) > 0.5
        && totalLines > 1 && Math.abs(scrollDelta) <= containerHeight && !shortLine
      const ctx = {
        targetScroll, index, containerHeight, totalLines, scrollDelta,
        visualDelta, handoverStarts, dominoHandover, lineEl, matchedMs
      }
      if (animate && useDomino) {
        applyDominoScroll(ctx)
      } else if (animate && Math.abs(scrollDelta) > containerHeight) {
        applySmoothJump(ctx)
      } else if (animate) {
        applyCssScroll(ctx)
      } else {
        applyInstantScroll(ctx)
      }

      state.prevLineIndex = index
    }

    // 多米诺：容器瞬跳到目标位，行级联反向偏移后错峰归位
    function applyDominoScroll(ctx) {
      const {
        targetScroll, index, containerHeight, totalLines, scrollDelta,
        visualDelta, handoverStarts, dominoHandover, lineEl
      } = ctx
      commitContainerScroll(-targetScroll)
      const forward = index > state.prevLineIndex

      // 所有行偏移到反向位置（只禁用 transform 过渡，保留 opacity/filter 过渡）。
      // 级联接续时以捕获的当前插值偏移 + 本次位移为起点（不夹紧，连续性优先，
      // 上限钳到 ±容器高度防止极端叠加；自然播放远达不到），否则用 visualDelta
      const effHeight = Math.max(1, containerHeight)
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (!el) continue
        let start = visualDelta
        if (dominoHandover) {
          start = Math.max(-effHeight, Math.min(effHeight, handoverStarts[i] + scrollDelta))
        }
        el.style.transition = 'transform 0s, opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0), filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
        el.style.transform = `translate3d(0, ${start}px, 0)`
      }
      // 读 computedStyle 强制浏览器 commit transform 起始值
      const csAfterOffset = getComputedStyle(lineEl).transform
      void csAfterOffset

      // 归位编排：固定每行 STAGGER_STEP 的触发间隔——向下播放由视口首行向末行推进、
      // 向上播放由末行向首行推进；视口外行钳制到可见边界（延迟与视口高度无关）
      // 注意：offsetTop 是内容坐标，视口顶部在内容坐标中 = targetScroll（滚动值本身）
      const viewportTop = targetScroll
      const viewportH = Math.max(1, containerHeight)
      const { delays, totalStagger } = staggerDelays(totalLines, viewportTop, viewportH, forward, index)
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (!el) continue
        el.style.transition = `transform ${STAGGER_DURATION}ms cubic-bezier(0.2, 0.9, 0.3, 1.0) ${delays[i]}s, opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0), filter 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0)`
        el.style.transform = 'translate3d(0, 0, 0)'
      }

      const totalDuration = STAGGER_DURATION + totalStagger * 1000 + 60
      state.dominoCascadeActive = true

      const cleanup = () => {
        for (let i = 0; i < totalLines; i++) {
          const el = lineRefs.value[i]
          if (el) { el.style.transform = ''; el.style.transition = '' }
        }
        if (scrollRef.value) { scrollRef.value.style.willChange = ''; scrollRef.value.style.transition = '' }
        // 级联动画完成后再解除激活缓冲，目标行在可视位置放大/淡入
        if (jumpPending.value >= 0) jumpPending.value = -1
        state.dominoCascadeActive = false
        state.lyricsScrollCleanup = null
      }
      const timer = setTimeout(cleanup, totalDuration)
      state.lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
    }

    // 大跨度跳转（> 容器高度）：Web Animations API，避免闪现
    function applySmoothJump(ctx) {
      const { targetScroll, index } = ctx
      state.smoothAnimTarget = index
      const fromTransform = `translate3d(0, ${state.currentScrollY}px, 0)`
      const toTransform = `translate3d(0, ${-targetScroll}px, 0)`
      const anim = scrollRef.value.animate(
        [{ transform: fromTransform }, { transform: toTransform }],
        { duration: 800, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
      )
      anim.onfinish = () => {
        commitContainerScroll(-targetScroll)
        anim.cancel()
        state.smoothAnimTarget = -1
        if (jumpPending.value >= 0) jumpPending.value = -1
        scrollRef.value.style.willChange = ''
        state.lyricsScrollCleanup = null
      }
      state.lyricsScrollCleanup = () => {
        anim.cancel()
        state.smoothAnimTarget = -1
        state.lyricsScrollCleanup = null
      }
    }

    // 关闭多米诺 / 密集短句：CSS transition 简单平滑滚动，零 JS 动画开销；
    // 时长跟随句时间戳长度，使下一次切句到来时本次滚动刚好走完
    function applyCssScroll(ctx) {
      const { targetScroll, matchedMs } = ctx
      commitContainerScroll(-targetScroll, `transform ${matchedMs}ms cubic-bezier(0.2, 0.9, 0.3, 1.0)`)
      const cleanup = () => {
        if (scrollRef.value) scrollRef.value.style.transition = ''
        if (jumpPending.value >= 0) jumpPending.value = -1
        state.lyricsScrollCleanup = null
      }
      const timer = setTimeout(cleanup, matchedMs + 50)
      state.lyricsScrollCleanup = () => { clearTimeout(timer); cleanup() }
    }

    // 立即落位：拖拽预览 / 面板重开等不需要动画的场景
    function applyInstantScroll(ctx) {
      const { targetScroll, totalLines } = ctx
      commitContainerScroll(-targetScroll)
      if (jumpPending.value >= 0) jumpPending.value = -1
      for (let i = 0; i < totalLines; i++) {
        const el = lineRefs.value[i]
        if (el) { el.style.transition = ''; el.style.transform = '' }
      }
      if (scrollRef.value) { scrollRef.value.style.willChange = ''; scrollRef.value.style.transition = '' }
      state.lyricsScrollCleanup = null
    }
    return {
        state,
        staggerDelays,
        animateScrollTo,
        commitContainerScroll,
        lyricContainerHeight
    }
}
