import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSettingsStore } from './settings'

const BENCH_MS = 5000
const BENCH_KEY = 'melodybox_benchmark'

export const usePerformanceStore = defineStore('performance', () => {
  const status = ref('idle') // idle | running | done
  const progress = ref(0)
  const liveFps = ref(0)
  const result = ref(null)

  function tierOf(score) {
    if (score >= 0.8) return 'high'
    if (score >= 0.55) return 'medium'
    return 'low'
  }

  function cachedResult() {
    try {
      const raw = localStorage.getItem(BENCH_KEY)
      if (!raw) return null
      const c = JSON.parse(raw)
      const dpr = window.devicePixelRatio || 1
      if (c.device === dpr && Date.now() - c.ts < 24 * 3600 * 1000) return c
    } catch {}
    return null
  }

  /**
   * 运行性能基准测试：
   * 在页面叠加一层"全屏歌词页同款"的模糊渐变压测层（纯 CSS transform/opacity），
   * 采样 5 秒真实帧率 + 长任务时长，输出 0-100 性能分与推荐档位。
   */
  function runBenchmark() {
    return new Promise((resolve) => {
      status.value = 'running'
      progress.value = 0
      liveFps.value = 0
      result.value = null

      // 压测层：3 层柔和渐变 + 慢速漂移，模拟全屏歌词页的动态流光负载
      const wrap = document.createElement('div')
      wrap.style.cssText = 'position:fixed;inset:0;z-index:2147483000;pointer-events:none;opacity:0.22;mix-blend-mode:screen;'
      const colors = ['rgba(99,102,241,0.65)', 'rgba(34,197,94,0.55)', 'rgba(239,68,68,0.5)']
      for (let i = 0; i < 3; i++) {
        const g = document.createElement('div')
        g.style.cssText = [
          'position:absolute;border-radius:50%;',
          `width:${110 + i * 25}%;height:${110 + i * 25}%;`,
          `top:-5%;left:${i * 8}%;`,
          `background:radial-gradient(circle at 50% 50%, ${colors[i]} 0%, transparent 70%);`,
          'mix-blend-mode:screen;will-change:transform;',
          `animation:perfStress ${42 + i * 12}s ease-in-out infinite alternate;`,
        ].join('')
        wrap.appendChild(g)
      }
      const styleEl = document.createElement('style')
      styleEl.textContent = '@keyframes perfStress { 0% { transform: translate3d(-4%, -3%, 0) scale(1); } 100% { transform: translate3d(4%, 3%, 0) scale(1.1); } }'
      document.head.appendChild(styleEl)
      document.body.appendChild(wrap)

      // 长任务统计
      let longMs = 0
      let observer = null
      try {
        observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) longMs += entry.duration
        })
        observer.observe({ entryTypes: ['longtask'] })
      } catch {}

      const frames = []
      let raf = 0
      const start = performance.now()

      const finish = () => {
        cancelAnimationFrame(raf)
        wrap.remove()
        styleEl.remove()
        if (observer) observer.disconnect()

        const totalMs = frames.length > 1 ? frames[frames.length - 1] - frames[0] : 0
        const fps = totalMs > 0 ? (frames.length - 1) / (totalMs / 1000) : 0
        const dpr = window.devicePixelRatio || 1
        const fpsScore = Math.min(1, Math.max(0, fps / 60))
        const longScore = Math.min(1, Math.max(0, 1 - longMs / (BENCH_MS * 0.25)))
        let score = fpsScore * 0.7 + longScore * 0.3
        // 高分屏负载修正
        if (dpr > 1.5) score *= Math.max(0.6, 1 - (dpr - 1.5) * 0.1)

        const res = {
          fps: Math.round(fps),
          longMs: Math.round(longMs),
          score: Math.round(Math.min(1, Math.max(0, score)) * 100),
          tier: tierOf(score),
        }
        result.value = res
        try {
          localStorage.setItem(BENCH_KEY, JSON.stringify({ ...res, device: dpr, ts: Date.now() }))
        } catch {}
        status.value = 'done'
        resolve(res)
      }

      const tick = (now) => {
        frames.push(now)
        const elapsed = now - start
        const secs = elapsed / 1000
        if (secs >= 1 && frames.length > 1) {
          liveFps.value = Math.round((frames.length - 1) / secs)
        }
        progress.value = Math.min(100, Math.round((elapsed / BENCH_MS) * 100))
        if (elapsed < BENCH_MS) {
          raf = requestAnimationFrame(tick)
        } else {
          finish()
        }
      }
      raf = requestAnimationFrame(tick)
    })
  }

  /** 应用推荐档位到设置 */
  function applyTier(tier) {
    useSettingsStore().applyQualityPreset(tier)
  }

  return {
    status, progress, liveFps, result,
    runBenchmark, applyTier, cachedResult, tierOf,
  }
})
