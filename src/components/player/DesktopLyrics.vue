<template>
  <!-- Electron 环境：无内联渲染，由独立窗口展示 -->
  <!-- 非 Electron 环境：内联渲染兜底 -->
  <template v-if="!isElectron">
    <transition name="dl-fade">
      <div v-if="showDesktopLyrics && currentTrack && hasLyrics && currentLineIndex >= 0" class="desktop-lyrics" :style="lyricsVars">
        <div class="dl-line dl-line--active" :class="{ 'has-translation': activeLine?.translation, 'is-word-level': activeLine?.wordLevel }">
          <div class="dl-line__inner">
            <p v-if="activeLine?.wordLevel && activeLine?.segments" class="dl-line__original word-level">
              <span v-for="(seg, si) in activeLine.segments" :key="si" class="word-seg" :data-word="seg.text">{{ seg.text }}</span>
            </p>
            <p v-else class="dl-line__original">{{ activeLine?.original || '' }}</p>
            <p v-if="activeLine?.translation" class="dl-line__translation">{{ activeLine.translation }}</p>
          </div>
        </div>
        <div v-if="nextLine" class="dl-line dl-line--next" :class="{ 'has-translation': nextLine.translation }">
          <div class="dl-line__inner">
            <p class="dl-line__original">{{ nextLine.original }}</p>
            <p v-if="nextLine.translation" class="dl-line__translation">{{ nextLine.translation }}</p>
          </div>
        </div>
      </div>
    </transition>
  </template>
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

const isElectron = computed(() => !!window.electronAPI)

const currentLineIndex = ref(-1)
const windowWidth = ref(window.innerWidth)

function onResize() { windowWidth.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

const parsedLyrics = computed(() => {
  const raw = currentTrack.value?.lyrics
  if (!raw) return []
  return parseLRC(raw)
})
const hasLyrics = computed(() => parsedLyrics.value.length > 0)

const activeLine = computed(() => {
  if (currentLineIndex.value < 0 || currentLineIndex.value >= parsedLyrics.value.length) return null
  return parsedLyrics.value[currentLineIndex.value]
})
const nextLine = computed(() => {
  const idx = currentLineIndex.value + 1
  if (idx < 0 || idx >= parsedLyrics.value.length) return null
  return parsedLyrics.value[idx]
})

// 构建发送给独立窗口的数据
const lyricsPayload = computed(() => {
  return {
    activeLine: activeLine.value ? {
      original: activeLine.value.original,
      translation: activeLine.value.translation || null,
      wordLevel: activeLine.value.wordLevel || false,
      segments: activeLine.value.segments || null
    } : null,
    nextLine: nextLine.value ? {
      original: nextLine.value.original,
      translation: nextLine.value.translation || null
    } : null
  }
})

// 推送数据到独立歌词窗口
function pushToLyricsWindow() {
  if (!isElectron.value) return
  window.electronAPI.lyricsUpdate(lyricsPayload.value)
}

// Electron 模式下：监听开关状态，控制独立窗口
watch(showDesktopLyrics, (val) => {
  if (!isElectron.value) return
  if (val) {
    window.electronAPI.lyricsOpen()
    // 立即推送当前数据
    pushToLyricsWindow()
  } else {
    window.electronAPI.lyricsClose()
  }
}, { immediate: true })

// 监听歌词行变化，推送数据
watch(currentLineIndex, () => {
  if (showDesktopLyrics.value && isElectron.value) {
    pushToLyricsWindow()
  }
})

// 切歌时推送（歌词数据变化）
watch(() => currentTrack.value?.path, () => {
  if (showDesktopLyrics.value && isElectron.value) {
    pushToLyricsWindow()
  }
})

// 监听独立窗口关闭事件，同步状态回 store
onMounted(() => {
  if (isElectron.value) {
    window.electronAPI.onLyricsWindowClosed(() => {
      if (showDesktopLyrics.value) {
        showDesktopLyrics.value = false
      }
    })
  }
})

// 跟踪当前歌词行
watch(currentTime, (time) => {
  if (!hasLyrics.value) {
    if (currentLineIndex.value !== -1) {
      currentLineIndex.value = -1
    }
    return
  }
  const idx = getCurrentLyricIndex(parsedLyrics.value, time)
  if (idx !== currentLineIndex.value) {
    currentLineIndex.value = idx
  }
})

// 切歌时重置
watch(() => currentTrack.value?.path, () => {
  currentLineIndex.value = -1
})

// 歌词 CSS 变量（非 Electron 内联渲染用）
const lyricsVars = computed(() => {
  const base = lyricsFontSize.value
  const trans = Math.round(base * lyricsTransScale.value / 100)
  const active = lyricsActiveScale.value / 100
  const activeFont = Math.round(base * active)
  const transActiveFont = Math.round(trans * active)
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
.dl-line--next .dl-line__original {
  opacity: 0.5;
  transform: translateY(0);
}
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
