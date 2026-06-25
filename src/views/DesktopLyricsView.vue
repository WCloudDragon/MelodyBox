<template>
  <div
    class="lyrics-window"
    :style="desktopVars"
    @dblclick="handleClose"
    title="双击关闭桌面歌词"
  >
    <!-- 视口裁剪器 — 高度由 JS 动态计算，保证只显示 2 行 -->
    <div ref="viewportRef" class="scroll-viewport">
      <!-- 滚动容器 — translate3d 模拟全屏歌词滚动 -->
      <div
        ref="scrollRef"
        class="scroll-container"
        @transitionend="onScrollEnd"
      >
      <template v-if="displayData">
        <!-- 当前行（活跃）— 在上方 -->
        <div
          class="dl-line dl-line--active"
          :class="{ 'has-translation': displayData.activeLine?.translation, 'is-word-level': displayData.activeLine?.wordLevel }"
        >
          <div class="dl-line__inner">
            <p v-if="displayData.activeLine?.wordLevel && displayData.activeLine?.segments" class="dl-line__original word-level dl-marquee" :class="{ 'is-scrolling': isMarqueeScrolling }">
              <span class="dl-marquee__text" ref="marqueeTextRef">
                <span
                  v-for="(seg, si) in displayData.activeLine.segments"
                  :key="si"
                  class="word-seg"
                  :data-word="seg.text"
                >{{ seg.text }}</span>
              </span>
            </p>
            <p v-else class="dl-line__original dl-marquee" :class="{ 'is-scrolling': isMarqueeScrolling }">
              <span class="dl-marquee__text" ref="marqueeTextRef">{{ displayData.activeLine?.original || '' }}</span>
            </p>
            <p v-if="displayData.activeLine?.translation" class="dl-line__translation">{{ displayData.activeLine.translation }}</p>
          </div>
        </div>

        <!-- 下一行（即将播放）— 翻译词居上对齐 -->
        <div v-if="displayData.nextLine" class="dl-line dl-line--next">
          <div class="dl-line__inner">
            <p class="dl-line__original">{{ displayData.nextLine.original }}</p>
            <p v-if="displayData.nextLine.translation" class="dl-line__translation">{{ displayData.nextLine.translation }}</p>
          </div>
        </div>

        <!-- 下下行 — 视口外，滚动动画时滑入 -->
        <div v-if="displayData.afterNextLine" class="dl-line dl-line--future">
          <div class="dl-line__inner">
            <p class="dl-line__original">{{ displayData.afterNextLine.original }}</p>
            <p v-if="displayData.afterNextLine.translation" class="dl-line__translation">{{ displayData.afterNextLine.translation }}</p>
          </div>
        </div>
      </template>
    </div>
    </div>

    <div v-if="!displayData" class="dl-empty">桌面歌词</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'

const displayData = ref(null)
const pendingData = ref(null)       // 动画期间新到的排队数据（链式调用）
let targetData = null               // 当前动画目标数据，结束后 swap
const animating = ref(false)
let activeAnimations = []            // 当前动画的 Animation 对象，结束后取消
const scrollRef = ref(null)
const viewportRef = ref(null)
const marqueeTextRef = ref(null)
const isMarqueeScrolling = ref(false)
let marqueeAnim = null               // 横向滚动动画
const prevIndex = ref(-1)
const GAP = 2                        // flex gap 间距

// 当前行时长（秒），用于计算跑马灯滚动速度
const lineDuration = computed(() => {
  const t1 = displayData.value?.activeLineTime ?? 0
  const t2 = displayData.value?.nextLineTime ?? 0
  return t2 > t1 ? t2 - t1 : 5
})

// 桌面歌词设置（默认值，与后端一致）
const desktopSettings = ref({ fontSize: 24, activeScale: 120, transScale: 60 })

// CSS 变量
const desktopVars = computed(() => {
  const base = desktopSettings.value.fontSize
  const trans = Math.round(base * desktopSettings.value.transScale / 100)
  const active = desktopSettings.value.activeScale / 100
  return {
    '--dl-base-original': base + 'px',
    '--dl-base-trans': trans + 'px',
    '--dl-active-original': Math.round(base * active) + 'px',
    '--dl-active-trans': Math.round(trans * active) + 'px',
    '--dl-lh-original': Math.round(base * 1.55) + 'px',
    '--dl-lh-trans': Math.round(trans * 1.4) + 'px'
  }
})

// 动画用字号（保持响应式）
const animFontSizes = computed(() => {
  const base = desktopSettings.value.fontSize
  const trans = Math.round(base * desktopSettings.value.transScale / 100)
  const active = desktopSettings.value.activeScale / 100
  return {
    base, trans,
    activeFont: Math.round(base * active),
    transActiveFont: Math.round(trans * active)
  }
})

onMounted(() => {
  if (window.electronAPI) {
    window.electronAPI.onLyricsData((data) => {
      // 更新设置（如果提供了）
      if (data?.settings) {
        desktopSettings.value = data.settings
      }

      const newIdx = data?.activeIndex ?? -1
      const oldIdx = displayData.value?.activeIndex ?? -1

      // 首次加载 / 首次出现歌词 / index 相同 → 直接更新
      if (oldIdx < 0 || newIdx === oldIdx) {
        displayData.value = data
        prevIndex.value = newIdx
        syncViewportHeight()
        setupMarquee()
        return
      }

      // 动画进行中 → 缓存最新数据，动画结束后应用
      if (animating.value) {
        pendingData.value = data
        prevIndex.value = newIdx
        return
      }

      // → 启动滚动动画
      animating.value = true
      prevIndex.value = newIdx
      performScroll(scrollRef.value, data, newIdx > oldIdx)
    })
  }
})

/**
 * 核心滚动：先对旧元素做字号动画 + 容器滑动，过渡结束后再 swap 数据
 * 保证旧词在动画全程可见
 */
async function performScroll(el, data, forward) {
  if (!el) return

  // 取消可能残留的旧动画
  activeAnimations.forEach(a => a.cancel())
  activeAnimations = []

  // 取消跑马灯，新行将重新检测
  if (marqueeAnim) { marqueeAnim.cancel(); marqueeAnim = null }
  isMarqueeScrolling.value = false

  const { base, trans, activeFont, transActiveFont } = animFontSizes.value
  const baseStr = base + 'px'
  const transStr = trans + 'px'
  const activeStr = activeFont + 'px'
  const transActiveStr = transActiveFont + 'px'

  // 1. 对当前活跃行（旧词）做缩小动画
  const oldActiveOrig = el.querySelector('.dl-line--active .dl-line__original')
  const oldActiveTrans = el.querySelector('.dl-line--active .dl-line__translation')
  if (oldActiveOrig) {
    const anim = oldActiveOrig.animate(
      [
        { fontSize: activeStr, opacity: '1', fontWeight: '700' },
        { fontSize: baseStr, opacity: '0.45', fontWeight: '700' }
      ],
      { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
    )
    activeAnimations.push(anim)
  }
  if (oldActiveTrans) {
    const anim = oldActiveTrans.animate(
      [
        { fontSize: transActiveStr, opacity: '1' },
        { fontSize: transStr, opacity: '0.2' }
      ],
      { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
    )
    activeAnimations.push(anim)
  }

  // 2. 对当前下一行（旧词）做放大动画 — 变成新的活跃行
  const oldNextOrig = el.querySelector('.dl-line--next .dl-line__original')
  const oldNextTrans = el.querySelector('.dl-line--next .dl-line__translation')
  if (oldNextOrig) {
    const anim = oldNextOrig.animate(
      [
        { fontSize: baseStr, opacity: '0.45', fontWeight: '700' },
        { fontSize: activeStr, opacity: '1', fontWeight: '700' }
      ],
      { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
    )
    activeAnimations.push(anim)
  }
  if (oldNextTrans) {
    const anim = oldNextTrans.animate(
      [
        { fontSize: transStr, opacity: '0.2' },
        { fontSize: transActiveStr, opacity: '1' }
      ],
      { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
    )
    activeAnimations.push(anim)
  }

  // 3. 缓存新数据，动画结束后 swap
  targetData = data

  // 4. 取活跃行实际高度作为滑动距离
  const activeEl = el.querySelector('.dl-line--active')
  const scrollPx = (activeEl ? activeEl.offsetHeight : 64) + GAP

  // 5. 容器滑动 — 与字号动画同时启动
  el.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
  getComputedStyle(el).transform
  el.style.transform = forward
    ? `translate3d(0, ${-scrollPx}px, 0)`
    : `translate3d(0, ${scrollPx}px, 0)`
}

/** 滑动结束 → 容器归位 + 数据 swap + 链式下一个 */
async function onScrollEnd() {
  const el = scrollRef.value
  if (!el) return

  // 1. 先取消 Web Animation，清除 fill:forwards 样式污染
  //    在 swap 数据前执行，避免旧动画样式短暂作用于新内容导致抖动
  activeAnimations.forEach(a => a.cancel())
  activeAnimations = []

  // 2. 容器瞬间归位
  el.style.transition = 'none'
  el.style.transform = 'translate3d(0, 0, 0)'

  // 3. 换上当前动画的目标数据
  if (targetData) {
    displayData.value = targetData
    targetData = null
  }

  animating.value = false

  // 4. 同步视口高度（字号可能变化）
  syncViewportHeight()

  // 5. 检查是否需要跑马灯
  setupMarquee()

  // 检查动画期间是否有新一轮排队数据
  if (pendingData.value) {
    const next = pendingData.value
    pendingData.value = null
    const newIdx = next?.activeIndex ?? -1
    const curIdx = displayData.value?.activeIndex ?? -1
    if (newIdx !== curIdx) {
      animating.value = true
      performScroll(el, next, newIdx > curIdx)
    }
  }
}

function handleClose() {
  if (window.electronAPI) {
    window.electronAPI.lyricsClose()
  }
}

/** 同步视口高度 = 活跃行 + 下一行实际高度 + gap */
async function syncViewportHeight() {
  await nextTick()
  const vp = viewportRef.value
  if (!vp) return
  const activeEl = vp.querySelector('.dl-line--active')
  const nextEl = vp.querySelector('.dl-line--next')
  const activeH = activeEl ? activeEl.offsetHeight : 64
  const nextH = nextEl ? nextEl.offsetHeight : 0
  vp.style.height = (activeH + GAP + nextH) + 'px'
}

/** 启动横向跑马灯：文本溢出容器时根据该句时长自动滚动 */
async function setupMarquee() {
  if (marqueeAnim) { marqueeAnim.cancel(); marqueeAnim = null }
  await nextTick()

  const textEl = marqueeTextRef.value
  if (!textEl) return

  const container = textEl.parentElement
  if (!container) return

  const containerW = container.clientWidth
  const textW = textEl.scrollWidth

  if (textW <= containerW + 4) {
    isMarqueeScrolling.value = false
    return
  }

  isMarqueeScrolling.value = true
  const dist = -(textW - containerW + 30) // 多滚 30px 留白
  const dur = lineDuration.value * 1000

  marqueeAnim = textEl.animate([
    { transform: 'translateX(0px)', offset: 0 },
    { transform: 'translateX(0px)', offset: 0.12 },
    { transform: `translateX(${dist}px)`, offset: 0.82 },
    { transform: 'translateX(0px)', offset: 1 }
  ], {
    duration: dur,
    iterations: Infinity,
    easing: 'linear'
  })
}

// 设置变化时重新计算视口高度
watch(desktopSettings, () => {
  syncViewportHeight()
}, { deep: true })
</script>

<style>
/* 全局重置 - 歌词窗口必须透明 */
html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  background: transparent !important;
  overflow: hidden;
}

#app {
  width: 100%;
  height: 100%;
  background: transparent !important;
}
</style>

<style scoped>
.lyrics-window {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px 24px;
  -webkit-app-region: drag;
  user-select: none;
  background: transparent;
  overflow: hidden;
  position: relative;
}

.scroll-viewport {
  width: 100%;
  /* 高度由 JS 动态计算 = active + next + gap */
  overflow: hidden;
}

.scroll-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  width: 100%;
  /* 初始无过渡，滚动时由 JS 注入 */
  transition: none;
}

.dl-empty {
  font-size: 20px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 2px;
}

/* ===== 逐行样式 ===== */
.dl-line {
  text-align: center;
  user-select: none;
  letter-spacing: 1px;
  max-width: 100%;
  padding: 2px 0;
  flex-shrink: 0;
  overflow: hidden;
  transition: padding 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              min-height 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.12s ease;
}

.dl-line__inner {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
}

.dl-line__original {
  margin: 0;
  font-size: var(--dl-base-original, 24px);
  line-height: var(--dl-lh-original, 38px);
  font-weight: 700;
  color: #fff;
  opacity: 0.35;
  max-width: 760px;
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-size 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-weight 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-line__translation {
  margin: 0;
  font-size: var(--dl-base-trans, 14px);
  line-height: var(--dl-lh-trans, 20px);
  font-weight: 700;
  color: #fff;
  opacity: 0.18;
  max-width: 760px;
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-size 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 活跃行 — 与基础行 padding 一致 */
.dl-line--active,
.dl-line--active.has-translation {
  padding: 2px 0;
}
.dl-line--active .dl-line__original {
  opacity: 1;
  font-size: var(--dl-active-original, 29px);
  max-width: 760px;
}
.dl-line--active .dl-line__translation {
  opacity: 1;
  color: #fff;
  font-size: var(--dl-active-trans, 17px);
}

/* ===== 横向跑马灯 ===== */
.dl-line__original.dl-marquee {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: clip;
}
.dl-marquee__text {
  display: inline-block;
  white-space: nowrap;
}

/* 下一行 */
.dl-line--next .dl-line__original {
  opacity: 0.45;
  font-size: var(--dl-base-original, 24px);
}
.dl-line--next .dl-line__translation {
  opacity: 0.2;
  font-size: var(--dl-base-trans, 14px);
  line-height: 1.1;
}

/* 下下行 — 视口外，样式与下一行一致 */
.dl-line--future .dl-line__original {
  opacity: 0.45;
  font-size: var(--dl-base-original, 24px);
}
.dl-line--future .dl-line__translation {
  opacity: 0.2;
  font-size: var(--dl-base-trans, 14px);
  line-height: 1.1;
}

/* ===== 逐字歌词 ===== */
.dl-line__original.word-level {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0;
  white-space: pre;
}
.word-seg {
  display: inline-block;
  color: #fff;
  opacity: 0.35;
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.04s linear,
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.dl-line--active .word-seg {
  opacity: 1;
}
</style>
