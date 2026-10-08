/**
 * Windows SMTC (System Media Transport Controls) 对接
 * 通过 navigator.mediaSession API 将播放状态同步到系统媒体控件
 */
import { watch, onBeforeUnmount } from 'vue'
import { usePlayerStore } from '@/stores/player'

let positionTimer = null
let actionsRegistered = false

/**
 * 初始化 SMTC 对接
 * 在 App.vue onMounted 中调用一次即可
 */
export function initMediaSession() {
  if (!('mediaSession' in navigator)) {
    return
  }
  // 桌面歌词独立窗口不参与：其 playerStore 为空壳实例，若执行会清空
  // 全局 SMTC 元数据并向主进程发错误播放状态
  if (window.location.hash === '#/desktop-lyrics') {
    return
  }

  const playerStore = usePlayerStore()

  // ==================== 注册动作处理器（仅一次） ====================
  if (!actionsRegistered) {
    navigator.mediaSession.setActionHandler('play', () => {
      playerStore.resume()
    })
    navigator.mediaSession.setActionHandler('pause', () => {
      playerStore.pause()
    })
    navigator.mediaSession.setActionHandler('previoustrack', () => {
      playerStore.prev()
    })
    navigator.mediaSession.setActionHandler('nexttrack', () => {
      playerStore.next()
    })
    navigator.mediaSession.setActionHandler('seekto', (details) => {
      if (details.seekTime != null) {
        playerStore.seek((details.seekTime / playerStore.duration) * 100)
      }
    })
    actionsRegistered = true
  }

  // ==================== 监听歌曲切换 → 更新元数据 ====================
  watch(
    () => playerStore.currentTrack,
    (track) => {
      if (!track) {
        navigator.mediaSession.metadata = null
        clearPositionTimer()
        return
      }

      const artist = track.artist || '未知艺术家'
      const album = track.album || '未知专辑'
      const title = track.title || '未知歌曲'

      const artwork = []
      if (track.cover) {
        artwork.push({
          src: track.cover,
          sizes: '512x512',
          type: track.cover.endsWith('.png') ? 'image/png' : 'image/jpeg'
        })
      }

      navigator.mediaSession.metadata = new MediaMetadata({
        title,
        artist,
        album,
        artwork
      })

      updatePositionState(playerStore)
    },
    { immediate: true }
  )

  // ==================== 监听播放状态 → 开始/停止位置更新 ====================
  watch(
    () => playerStore.isPlaying,
    (playing) => {
      // playbackState 是 MediaSession 规范核心字段，Chromium 据此驱动 SMTC 会话的播放/暂停按钮态
      try { navigator.mediaSession.playbackState = playing ? 'playing' : 'paused' } catch {}
      if (playing) {
        startPositionTimer(playerStore)
      } else {
        updatePositionState(playerStore)
      }
    },
    { immediate: true }
  )

  // ==================== 监听进度 seek ====================
  watch(
    () => playerStore.currentTime,
    () => {
      // 仅在暂停时主动更新 position state
      if (!playerStore.isPlaying) {
        updatePositionState(playerStore)
      }
    }
  )

  // ==================== 清理 ====================
  onBeforeUnmount(() => {
    clearPositionTimer()
  })
}

function updatePositionState(playerStore) {
  if (!('mediaSession' in navigator)) return
  if (!playerStore.currentTrack) return
  if (playerStore.duration > 0) {
    try {
      navigator.mediaSession.setPositionState({
        duration: playerStore.duration,
        playbackRate: 1.0,
        position: Math.min(playerStore.currentTime, playerStore.duration)
      })
    } catch {
      // 某些浏览器可能不支持 setPositionState
    }
  }
}

function startPositionTimer(playerStore) {
  clearPositionTimer()
  positionTimer = setInterval(() => {
    updatePositionState(playerStore)
  }, 1000)
}

function clearPositionTimer() {
  if (positionTimer) {
    clearInterval(positionTimer)
    positionTimer = null
  }
}
