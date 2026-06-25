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
          :class="{ 'is-word-level': displayData.activeLine?.wordLevel }"
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
const SCROLL_PX = 52                  // 单行滚动量

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
      const forward = newIdx > oldIdx
      animating.value = true
      pendingData.value = data
      prevIndex.value = newIdx

      const el = scrollRef.value
      if (!el) {
        displayData.value = data
        animating.value = false
        return
      }

      // 与全屏歌词 CSS transition 滚动参数完全一致
      el.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
      el.style.transform = forward
        ? `translate3d(0, ${-SCROLL_PX}px, 0)`
        : `translate3d(0, ${SCROLL_PX}px, 0)`
    })
  }
})

/** 滚动动画结束 */
async function onScrollEnd() {
  const el = scrollRef.value
  if (!el) return

  // 1. 停掉 transition，避免重置 transform 时触发另一次过渡
  el.style.transition = 'none'
  el.style.transform = 'translate3d(0, 0, 0)'

  // 2. 换上最新数据
  const data = pendingData.value
  pendingData.value = null
  animating.value = false
  if (data) {
    displayData.value = data
  }

  // 3. 等下一帧：如果在动画期间已有新数据排队，立即再动画一次
  await nextTick()
  if (pendingData.value) {
    const newIdx = pendingData.value.activeIndex ?? -1
    const curIdx = displayData.value?.activeIndex ?? -1
    if (newIdx !== curIdx) {
      const forward = newIdx > curIdx
      prevIndex.value = newIdx
      animating.value = true
      el.style.transition = 'transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
      el.style.transform = forward
        ? `translate3d(0, ${-SCROLL_PX}px, 0)`
        : `translate3d(0, ${SCROLL_PX}px, 0)`
      displayData.value = pendingData.value
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
  line-height: 1.4;
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
  line-height: 1.3;
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
