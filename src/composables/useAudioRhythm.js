import { watch } from 'vue'

/**
 * 音频律动：频谱分析驱动动态背景的光球缩放与透明度。
 *
 * 光球缩放：LOW + MID 双通道自适应基线 delta + 能量累积器
 * 光球透明度：中频/全频能量 → 氛围渐变
 *
 * 只依赖 analyser、设置与可见性，输出只写 `.np-bg__flow` 的三个 CSS 变量，
 * 与歌词、滚动、提示互不耦合。
 */
export function useAudioRhythm({ analyserNode, settings, visible }) {
  let _rhythmRaf = null
  let _flowEl = null
  const _rhythmEnergy = { low: 0, mid: 0, full: 0 }
  const _prev = { scale: 0, midOp: 0, hlOp: 0 }
  let _lowBaseline = 0
  let _midBaseline = 0
  let _deltaSmoothed = 0
  let _midDeltaSmoothed = 0
  let _accumulator = 0

  function start() {
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

  function stop() {
    if (_rhythmRaf) { cancelAnimationFrame(_rhythmRaf); _rhythmRaf = null }
    _flowEl = null
    _rhythmEnergy.low = 0; _rhythmEnergy.mid = 0; _rhythmEnergy.full = 0
    _prev.scale = 0; _prev.midOp = 0; _prev.hlOp = 0
    _lowBaseline = 0; _midBaseline = 0; _deltaSmoothed = 0; _midDeltaSmoothed = 0; _accumulator = 0
    if (settings.debugMode) {
      window.electronAPI?.rhythmUpdate({ lowRaw:0,midRaw:0,fullRaw:0, lowSmoothed:0,midSmoothed:0,fullSmoothed:0, lowBaseline:0,midBaseline:0,lowDelta:0,deltaSmoothed:0,midDelta:0,midDeltaSmoothed:0,accumulator:0, scale:'1',midOp:'0.7',hlOp:'0.55', flowElFound:false })
    }
  }

  // 动态背景开关/可见性/律动开关变化时控制 RAF 循环（与原实现一致，非 immediate）
  watch(
    [() => settings.enableDynamicBg, () => settings.enableAudioRhythm, visible],
    ([bgOn, rhythmOn, isVisible]) => {
      if (bgOn && rhythmOn && isVisible) start()
      else stop()
    }
  )

  return { start, stop }
}
