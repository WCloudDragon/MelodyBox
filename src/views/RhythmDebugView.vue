<template>
  <div class="rhythm-debug" @dblclick="handleClose" title="双击关闭">
    <header class="rd-header">
      <span class="rd-title">律动日志</span>
      <span class="rd-fps">{{ fps }} FPS</span>
      <button class="rd-close" @click="handleClose">&times;</button>
    </header>

    <template v-if="!hasData">
      <div class="rd-empty">等待数据...</div>
    </template>

    <template v-else>
      <!-- 能量条 -->
      <section class="rd-section">
        <div class="rd-section__title">频谱能量</div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#f87171">LOW</span>
          <span class="rd-bar-val">{{ fmt(data.lowSmoothed) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: (data.lowSmoothed * 100) + '%', background: '#f87171' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#fbbf24">MID</span>
          <span class="rd-bar-val">{{ fmt(data.midSmoothed) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: (data.midSmoothed * 100) + '%', background: '#fbbf24' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#60a5fa">FULL</span>
          <span class="rd-bar-val">{{ fmt(data.fullSmoothed) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: (data.fullSmoothed * 100) + '%', background: '#60a5fa' }"></div>
          </div>
        </div>
      </section>

      <!-- CSS 变量 -->
      <section class="rd-section">
        <div class="rd-section__title">CSS 变量</div>
        <div class="rd-kv">
          <span>--flow-scale</span><span>{{ data.scale }}</span>
        </div>
        <div class="rd-kv">
          <span>--flow-opacity-mid</span><span>{{ data.midOp }}</span>
        </div>
        <div class="rd-kv">
          <span>--flow-opacity-hl</span><span>{{ data.hlOp }}</span>
        </div>
        <div class="rd-kv">
          <span>flowEl</span><span :class="data.flowElFound ? 'rd-ok' : 'rd-err'">{{ data.flowElFound ? 'OK' : 'MISSING' }}</span>
        </div>
      </section>

      <!-- 原始值 -->
      <section class="rd-section">
        <div class="rd-section__title">原始频域</div>
        <div class="rd-kv"><span>lowRaw</span><span>{{ fmt(data.lowRaw) }}</span></div>
        <div class="rd-kv"><span>midRaw</span><span>{{ fmt(data.midRaw) }}</span></div>
        <div class="rd-kv"><span>fullRaw</span><span>{{ fmt(data.fullRaw) }}</span></div>
      </section>

      <!-- 能量变化率（加速度） -->
      <section class="rd-section">
        <div class="rd-section__title">能量变化率 Δ（驱动缩放）</div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#6ee7b7">L基线</span>
          <span class="rd-bar-val">{{ fmt(data.lowBaseline) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: (data.lowBaseline * 100) + '%', background: '#6ee7b7' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#a78bfa">ΔRaw</span>
          <span class="rd-bar-val">{{ fmt(data.lowDelta) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: Math.min(100, (data.lowDelta || 0) * 500) + '%', background: '#a78bfa' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#c084fc">ΔSmt</span>
          <span class="rd-bar-val">{{ fmt(data.deltaSmoothed) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: Math.min(100, (data.deltaSmoothed || 0) * 500) + '%', background: '#c084fc' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#f97316">Acc</span>
          <span class="rd-bar-val">{{ fmt(data.accumulator) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: Math.min(100, (data.accumulator || 0) * 100) + '%', background: '#f97316' }"></div>
          </div>
        </div>
        <div class="rd-bar-row" style="margin-top:4px;border-top:1px solid #2d2d4a;padding-top:6px">
          <span class="rd-bar-label" style="color:#34d399">M基线</span>
          <span class="rd-bar-val">{{ fmt(data.midBaseline) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: (data.midBaseline * 100) + '%', background: '#34d399' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#2dd4bf">MΔRaw</span>
          <span class="rd-bar-val">{{ fmt(data.midDelta) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: Math.min(100, (data.midDelta || 0) * 500) + '%', background: '#2dd4bf' }"></div>
          </div>
        </div>
        <div class="rd-bar-row">
          <span class="rd-bar-label" style="color:#14b8a6">MΔSmt</span>
          <span class="rd-bar-val">{{ fmt(data.midDeltaSmoothed) }}</span>
          <div class="rd-bar">
            <div class="rd-bar__fill" :style="{ width: Math.min(100, (data.midDeltaSmoothed || 0) * 500) + '%', background: '#14b8a6' }"></div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const hasData = ref(false)
const fps = ref(0)
const data = ref({
  lowRaw: 0, midRaw: 0, fullRaw: 0,
  lowSmoothed: 0, midSmoothed: 0, fullSmoothed: 0,
  lowBaseline: 0, midBaseline: 0,
  midDelta: 0, midDeltaSmoothed: 0,
  scale: '1', midOp: '0.7', hlOp: '0.55',
  flowElFound: false
})

let _frameCount = 0
let _lastFpsTime = performance.now()

function fmt(v) {
  return typeof v === 'number' ? v.toFixed(3) : String(v)
}

function handleClose() {
  window.electronAPI?.rhythmClose()
}

onMounted(() => {
  if (window.electronAPI?.onRhythmData) {
    window.electronAPI.onRhythmData((d) => {
      data.value = d
      hasData.value = true
      _frameCount++
      const now = performance.now()
      if (now - _lastFpsTime >= 1000) {
        fps.value = _frameCount
        _frameCount = 0
        _lastFpsTime = now
      }
    })
  }
})

onBeforeUnmount(() => {
  window.electronAPI?.rhythmClose()
})
</script>

<style>
/* 重置页面默认样式 */
html, body { margin: 0; padding: 0; overflow: hidden; }
</style>
<style scoped>
.rhythm-debug {
  height: 100vh;
  background: #1a1a2e;
  color: #e2e8f0;
  font-family: 'MiSans VF', 'PingFang SC', system-ui, sans-serif;
  font-size: 12px;
  padding: 10px 14px;
  overflow-y: auto;
  user-select: none;
}
.rd-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid #2d2d4a;
}
.rd-title {
  font-size: 14px;
  font-weight: 600;
  flex: 1;
}
.rd-fps {
  font-size: 11px;
  color: #4ade80;
  font-weight: 600;
  min-width: 40px;
  text-align: right;
}
.rd-close {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.rd-close:hover { color: #f87171; }
.rd-empty {
  text-align: center;
  color: #64748b;
  margin-top: 40px;
}
.rd-section {
  margin-bottom: 16px;
}
.rd-section__title {
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}
.rd-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.rd-bar-label {
  font-size: 10px;
  font-weight: 600;
  width: 30px;
}
.rd-bar-val {
  width: 42px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #94a3b8;
}
.rd-bar {
  flex: 1;
  height: 8px;
  background: #2d2d4a;
  border-radius: 4px;
  overflow: hidden;
}
.rd-bar__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 80ms linear;
}
.rd-kv {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  color: #94a3b8;
}
.rd-kv span:last-child {
  font-variant-numeric: tabular-nums;
  color: #e2e8f0;
}
.rd-ok { color: #4ade80 !important; }
.rd-err { color: #f87171 !important; }
</style>
