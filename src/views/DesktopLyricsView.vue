<template>
  <div
    class="lyrics-window"
    @dblclick="handleClose"
    title="双击关闭桌面歌词"
  >
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
            <p v-if="displayData.activeLine?.wordLevel && displayData.activeLine?.segments" class="dl-line__original word-level">
              <span
                v-for="(seg, si) in displayData.activeLine.segments"
                :key="si"
                class="word-seg"
                :data-word="seg.text"
              >{{ seg.text }}</span>
            </p>
            <p v-else class="dl-line__original">{{ displayData.activeLine?.original || '' }}</p>
            <p v-if="displayData.activeLine?.translation" class="dl-line__translation">{{ displayData.activeLine.translation }}</p>
          </div>
        </div>

        <!-- 下一行（即将播放）— 在下方 -->
        <div v-if="displayData.nextLine" class="dl-line dl-line--next">
          <div class="dl-line__inner">
            <p class="dl-line__original">{{ displayData.nextLine.original }}</p>
            <p v-if="displayData.nextLine.translation" class="dl-line__translation">{{ displayData.nextLine.translation }}</p>
          </div>
        </div>
      </template>
    </div>

    <div v-if="!displayData" class="dl-empty">桌面歌词</div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'

const displayData = ref(null)
const pendingData = ref(null)       // 动画进行中的待更新数据
const animating = ref(false)
const scrollRef = ref(null)
const prevIndex = ref(-1)
const SCROLL_PX = 64                  // 活跃行高(58px) + gap(6px)

onMounted(() => {
  if (window.electronAPI) {
    window.electronAPI.onLyricsData((data) => {
      const newIdx = data?.activeIndex ?? -1
      const oldIdx = displayData.value?.activeIndex ?? -1

      // 首次加载 / 首次出现歌词 / index 相同 → 直接更新
      if (oldIdx < 0 || newIdx === oldIdx) {
        displayData.value = data
        prevIndex.value = newIdx
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
 * 核心滚动：数据交换后同时启动容器滑动 + 活跃行缩放动画
 * 两者同时长同缓动，形成连贯的「位移 + 放大」效果
 */
async function performScroll(el, data, forward) {
  if (!el) return

  // 1. 新数据上屏
  displayData.value = data
  await nextTick()

  // 2. 新活跃行：从下一行尺寸 → 活跃行尺寸（element.animate 立即开始）
  const activeOrig = el.querySelector('.dl-line--active .dl-line__original')
  const activeTrans = el.querySelector('.dl-line--active .dl-line__translation')

  if (activeOrig) {
    activeOrig.animate(
      [
        { fontSize: '24px', opacity: '0.45', fontWeight: '700' },
        { fontSize: '34px', opacity: '1', fontWeight: '700' }
      ],
      { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
    )
  }
  if (activeTrans) {
    activeTrans.animate(
      [
        { fontSize: '14px', opacity: '0.2' },
        { fontSize: '20px', opacity: '0.5' }
      ],
      { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
    )
  }

  // 3. 新下一行（曾是活跃行）：活跃行尺寸 → 下一行尺寸 (仅前进时)
  if (forward) {
    const nextOrig = el.querySelector('.dl-line--next .dl-line__original')
    const nextTrans = el.querySelector('.dl-line--next .dl-line__translation')
    if (nextOrig) {
      nextOrig.animate(
        [
          { fontSize: '34px', opacity: '1', fontWeight: '700' },
          { fontSize: '24px', opacity: '0.45', fontWeight: '700' }
        ],
        { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
      )
    }
    if (nextTrans) {
      nextTrans.animate(
        [
          { fontSize: '20px', opacity: '0.5' },
          { fontSize: '14px', opacity: '0.2' }
        ],
        { duration: 500, easing: 'cubic-bezier(0.2, 0.9, 0.3, 1.0)', fill: 'forwards' }
      )
    }
  }

  // 4. 容器滑动 — 先注册 transition，再 force reflow，最后改 transform（避免跳变）
  el.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
  // 强制浏览器在 transition 生效状态下记录当前位置
  getComputedStyle(el).transform
  el.style.transform = forward
    ? `translate3d(0, ${-SCROLL_PX}px, 0)`
    : `translate3d(0, ${SCROLL_PX}px, 0)`
}

/** 滑动结束 → 容器归位 + 链式下一个 */
async function onScrollEnd() {
  const el = scrollRef.value
  if (!el) return

  el.style.transition = 'none'
  el.style.transform = 'translate3d(0, 0, 0)'

  animating.value = false

  // 如果动画期间有新数据排队，立即启动下一轮
  if (pendingData.value) {
    const next = pendingData.value
    const newIdx = next?.activeIndex ?? -1
    const curIdx = displayData.value?.activeIndex ?? -1
    if (newIdx !== curIdx) {
      animating.value = true
      performScroll(el, next, newIdx > curIdx)
      pendingData.value = null
    } else {
      pendingData.value = null
    }
  }
}

function handleClose() {
  if (window.electronAPI) {
    window.electronAPI.lyricsClose()
  }
}
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

.scroll-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
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
  padding: 6px 0;
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
  gap: 4px;
  align-items: center;
}

.dl-line__original {
  margin: 0;
  font-size: 28px;
  line-height: 48px;
  font-weight: 700;
  color: #fff;
  opacity: 0.35;
  max-width: 760px;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.7), 0 1px 8px rgba(0, 0, 0, 0.4);
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
  font-size: 17px;
  line-height: 26px;
  font-weight: 700;
  color: #fff;
  opacity: 0.18;
  max-width: 760px;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              font-size 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 活跃行 */
.dl-line--active {
  padding: 5px 0;
}
.dl-line--active.has-translation {
  padding: 4px 0;
}
.dl-line--active .dl-line__original {
  opacity: 1;
  font-size: 34px;
  max-width: 760px;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.8), 0 2px 12px rgba(0, 0, 0, 0.5);
}
.dl-line--active .dl-line__translation {
  opacity: 0.5;
  font-size: 20px;
}

/* 下一行 */
.dl-line--next .dl-line__original {
  opacity: 0.45;
  font-size: 24px;
}
.dl-line--next .dl-line__translation {
  opacity: 0.2;
  font-size: 14px;
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
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.7), 0 1px 8px rgba(0, 0, 0, 0.4);
  transition: color 0.8s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.04s linear,
              opacity 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.dl-line--active .word-seg {
  opacity: 1;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.8), 0 2px 12px rgba(0, 0, 0, 0.5);
}
</style>
