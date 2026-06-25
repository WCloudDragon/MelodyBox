<template>
  <transition name="dl-fade">
    <div v-if="showDesktopLyrics && currentTrack && hasLyrics && currentLineIndex >= 0" class="desktop-lyrics" :style="lyricsVars">
      <!-- 当前行（活跃） -->
      <div class="dl-line dl-line--active" :class="{ 'has-translation': activeLine?.translation, 'is-word-level': activeLine?.wordLevel }">
        <div class="dl-line__inner">
          <p v-if="activeLine?.wordLevel && activeLine?.segments" class="dl-line__original word-level">
            <span
              v-for="(seg, si) in activeLine.segments"
              :key="si"
              class="word-seg"
              :data-word="seg.text"
            >{{ seg.text }}</span>
          </p>
          <p v-else class="dl-line__original">{{ activeLine?.original || '' }}</p>
          <p v-if="activeLine?.translation" class="dl-line__translation">{{ activeLine.translation }}</p>
        </div>
      </div>

      <!-- 下一行（即将播放） -->
      <div v-if="nextLine" class="dl-line dl-line--next" :class="{ 'has-translation': nextLine.translation }">
        <div class="dl-line__inner">
          <p class="dl-line__original">{{ nextLine.original }}</p>
          <p v-if="nextLine.translation" class="dl-line__translation">{{ nextLine.translation }}</p>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'
import { useSettingsStore } from '@/stores/settings'
import { parseLRC, getCurrentLyricIndex } from '@/utils/format'

const player = usePlayerStore()
const settings = useSettingsStore()
const { currentTrack, currentTime, showDesktopLyrics } = storeToRefs(player)
const { lyricsFontSize, lyricsFontWeight, lyricsTransScale, lyricsActiveScale } = storeToRefs(settings)

const currentLineIndex = ref(-1)
const windowWidth = ref(window.innerWidth)

function onResize() { windowWidth.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

// 解析后的歌词数组
const parsedLyrics = computed(() => {
  const raw = currentTrack.value?.lyrics
  if (!raw) return []
  return parseLRC(raw)
})

const hasLyrics = computed(() => parsedLyrics.value.length > 0)

// 当前活跃行
const activeLine = computed(() => {
  if (currentLineIndex.value < 0 || currentLineIndex.value >= parsedLyrics.value.length) return null
  return parsedLyrics.value[currentLineIndex.value]
})

// 下一行
const nextLine = computed(() => {
  const idx = currentLineIndex.value + 1
  if (idx < 0 || idx >= parsedLyrics.value.length) return null
  return parsedLyrics.value[idx]
})

// 跟踪当前歌词行
watch(currentTime, (time) => {
  if (!hasLyrics.value) {
    currentLineIndex.value = -1
    return
  }
  const idx = getCurrentLyricIndex(parsedLyrics.value, time)
  currentLineIndex.value = idx
})

// 切歌时重置
watch(() => currentTrack.value?.path, () => {
  currentLineIndex.value = -1
})

// 歌词 CSS 变量（基于设置和窗口宽度）
const lyricsVars = computed(() => {
  const base = lyricsFontSize.value
  const trans = Math.round(base * lyricsTransScale.value / 100)
  const active = lyricsActiveScale.value / 100
  const activeFont = Math.round(base * active)
  const transActiveFont = Math.round(trans * active)
  // 桌面歌词可用宽度约窗口宽度的80%
  const availWidth = Math.max(300, windowWidth.value * 0.8)
  const activeChars = Math.max(5, Math.floor(availWidth / (activeFont + 1)))
  const safetyPx = 4
  const nonActiveMaxEm = (activeChars * (base + 1) + safetyPx) / base
  const activeMaxEm = (activeChars * (activeFont + 1) + safetyPx) / activeFont
  const transActiveChars = Math.max(3, Math.floor(availWidth / (transActiveFont + 1)))
  const transNonActiveMaxEm = (transActiveChars * (trans + 1) + safetyPx) / trans
  const transActiveMaxEm = (transActiveChars * (transActiveFont + 1) + safetyPx) / transActiveFont
  return {
    '--dl-base-original': base + 'px',
    '--dl-base-trans': trans + 'px',
    '--dl-active-original': Math.round(base * active) + 'px',
    '--dl-active-trans': Math.round(trans * active) + 'px',
    '--dl-weight': lyricsFontWeight.value,
    '--dl-ch-limit': nonActiveMaxEm + 'em',
    '--dl-active-ch-limit': activeMaxEm + 'em',
    '--dl-trans-ch-limit': transNonActiveMaxEm + 'em',
    '--dl-trans-active-ch-limit': transActiveMaxEm + 'em'
  }
})
</script>

<style scoped>
.desktop-lyrics {
  position: fixed;
  bottom: 88px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  pointer-events: none;
  max-width: 80vw;
  text-align: center;
}

.dl-line {
  text-align: center;
  user-select: none;
  letter-spacing: 1px;
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

.dl-line__inner {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
}

.dl-line__original {
  margin: 0;
  font-size: var(--dl-base-original, 16px);
  line-height: 1.3;
  font-weight: var(--dl-weight, 700);
  color: var(--text-primary);
  opacity: 0.4;
  max-width: var(--dl-ch-limit);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  transition: font-size 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              color 0.4s;
}

.dl-line__translation {
  margin: 0;
  font-size: var(--dl-base-trans, 10px);
  line-height: 1.2;
  font-weight: var(--dl-weight, 700);
  color: var(--text-primary);
  opacity: 0.2;
  max-width: var(--dl-trans-ch-limit);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  transition: font-size 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              color 0.4s;
}

/* 活跃行 */
.dl-line--active .dl-line__original {
  opacity: 1;
  color: var(--text-primary);
  font-size: var(--dl-active-original, 24px);
  max-width: var(--dl-active-ch-limit);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
}
.dl-line--active .dl-line__translation {
  opacity: 0.55;
  color: var(--text-secondary);
  font-size: var(--dl-active-trans, 14px);
  max-width: var(--dl-trans-active-ch-limit);
}

/* 下一行 */
.dl-line--next .dl-line__original {
  opacity: 0.5;
  transform: translateY(0);
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
  color: var(--text-primary);
  opacity: 0.4;
  transition: opacity 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              color 0.4s;
}
.dl-line--active .word-seg {
  opacity: 1;
  color: var(--text-primary);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
}

/* 显隐动画 */
.dl-fade-enter-active {
  transition: opacity 0.4s ease, transform 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.dl-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.dl-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
.dl-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
</style>
