/**
 * 逐字歌词渲染器
 *
 * 负责逐字行的卡拉 OK 扫过效果：
 *   - 每帧读取活跃逐字行，按用户帧率节流更新 CSS 变量与 class
 *   - 上浮位移每帧更新，与显示器刷新同步
 *   - 行退出活跃集合时渐变回暗淡色
 *
 * 不持有歌词数据与行元素：全部通过 getter / ref 注入。
 * 不操作 DOM 结构，只写 class、CSS 变量与 transform。
 */

const WORD_LIFT_PX = 3

export function useKaraokeLyrics({
  lineRefs,
  getLines,
  getActiveIndexes,
  getLiveTime,
  getWordFps,
  getWordLift,
  visible
}) {
  let wordAnimRaf = null

  // 已播行逐字歌词从全白渐变回暗淡色（CSS transition 驱动，零 JS 动画开销）
  function fadeOutLine(lineIndex) {
    const line = getLines()[lineIndex]
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

  function updateWordSegStyles(lineIndex, time) {
    const line = getLines()[lineIndex]
    if (!line?.segments) return

    const nextLine = getLines()[lineIndex + 1]
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
        el.style.transform = getWordLift() ? `translate3d(0, ${-WORD_LIFT_PX}px, 0)` : ''
      } else if (state === 'singing') {
        el.classList.add('word-seg--singing')
        el.classList.remove('word-seg--sung')
        el.style.setProperty('--word-pct', Math.round(pct))
        const lift = getWordLift() ? -WORD_LIFT_PX * (pct / 100) : 0
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
    const line = getLines()[lineIndex]
    if (!line?.segments || !line._wordSegEls) return

    const nextLine = getLines()[lineIndex + 1]
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

  function start() {
    if (wordAnimRaf) return
    let lastStyleTime = 0
    const loop = () => {
      // 多行同播时可能同时有多个逐字行（duet 重叠句），逐行全部驱动
      const wordLines = getActiveIndexes().filter(i => getLines()[i]?.wordLevel)
      const fpz = Number(getWordFps()) || 60
      if (!visible() || !wordLines.length || fpz <= 0) {
        wordAnimRaf = null
        return
      }
      const now = performance.now()
      const interval = 1000 / fpz
      // CSS var / class（卡拉OK扫过）按用户设定帧率节流
      const shouldStyle = now - lastStyleTime >= interval
      if (shouldStyle) lastStyleTime = now
      const time = getLiveTime()
      for (const idx of wordLines) {
        const line = getLines()[idx]
        // 逐字元素缓存：仅在切句（活跃逐字行变化）或旧引用已脱离 DOM 时重建，
        // 避免每帧 querySelectorAll 重新遍历整行字符
        const lineEl = lineRefs.value[idx]
        if (!line._wordSegEls?.length || !line._wordSegEls[0].isConnected) {
          line._wordSegEls = lineEl ? [...lineEl.querySelectorAll('.word-seg')] : []
        }
        if (shouldStyle) updateWordSegStyles(idx, time)
        // transform 上浮位移每 RAF 帧更新，与显示器刷新率同步，保证丝滑
        if (getWordLift()) updateWordSegTransforms(idx, time)
      }
      wordAnimRaf = requestAnimationFrame(loop)
    }
    wordAnimRaf = requestAnimationFrame(loop)
  }

  function stop() {
    if (wordAnimRaf) { cancelAnimationFrame(wordAnimRaf); wordAnimRaf = null }
  }

  return { start, stop, fadeOutLine }
}
