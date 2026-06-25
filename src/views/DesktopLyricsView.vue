<template>
  <div
    class="lyrics-window"
    @dblclick="handleClose"
    title="双击关闭桌面歌词"
  >
    <!-- 滚动动画容器 — 模拟全屏歌词 translate3d 滚动 -->
    <Transition :name="scrollTransitionName" mode="out-in">
      <div
        :key="displayData?.activeIndex ?? -1"
        class="lyrics-content"
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
    </Transition>

    <div v-if="!displayData" class="dl-empty">桌面歌词</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const displayData = ref(null)
const prevIndex = ref(-1)

// 根据 index 变化方向决定过渡动画名称
const scrollTransitionName = computed(() => {
  const cur = displayData.value?.activeIndex ?? -1
  const dir = cur >= prevIndex.value ? 'dl-scroll-forward' : 'dl-scroll-backward'
  return dir
})

onMounted(() => {
  if (window.electronAPI) {
    window.electronAPI.onLyricsData((data) => {
      // 记录方向
      const oldIdx = displayData.value?.activeIndex ?? -1
      prevIndex.value = oldIdx
      displayData.value = data
    })
  }
})

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

.lyrics-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
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

/* ============================ */
/*  滚动过渡动画 — 模拟全屏歌词 translate3d 滚动  */
/*  与全屏歌词一致的参数: 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0) */
/* ============================ */

/* 前进 (歌词向下滚动，文字向上滑动) */
.dl-scroll-forward-enter-active {
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.dl-scroll-forward-enter-from {
  opacity: 0;
  transform: translateY(52px);
}
.dl-scroll-forward-leave-active {
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  position: absolute;
  width: calc(100% - 48px);
}
.dl-scroll-forward-leave-to {
  opacity: 0;
  transform: translateY(-52px);
}

/* 后退 (歌词向上滚动，文字向下滑动) */
.dl-scroll-backward-enter-active {
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.dl-scroll-backward-enter-from {
  opacity: 0;
  transform: translateY(-52px);
}
.dl-scroll-backward-leave-active {
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
  position: absolute;
  width: calc(100% - 48px);
}
.dl-scroll-backward-leave-to {
  opacity: 0;
  transform: translateY(52px);
}
</style>
