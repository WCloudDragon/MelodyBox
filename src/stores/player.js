import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAiStore } from './ai'
import { apiUrl } from '@/config/api'
import { useAuthStore } from './auth'
import { ElMessage } from '@/utils/toast'

export const usePlayerStore = defineStore('player', () => {
  // 播放队列
  const queue = ref([])
  const currentIndex = ref(-1)
  const audio = ref(null)

  // 播放状态
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const duration = ref(0)
  const volume = ref(0.7)
  const isMuted = ref(false)
  const bufferedPercent = ref(0)

  // Web Audio API — 频谱分析（音频律动驱动动态背景）
  const audioCtx = ref(null)
  const analyserNode = ref(null)

  // ==================== 音频分析管线预热 ====================
  // AudioContext 创建较慢（约 300ms），若放在首次播放事件里会阻塞播放启动。
  // 策略：启动后空闲时提前创建（挂起状态），首次播放时只需廉价"接线"；
  // 若预热未完成，播放事件内同步兜底创建，行为与旧版完全一致。
  let _warmCtx = null
  let _warmAnalyser = null

  function _warmupAudioPipeline() {
    if (_warmCtx) return
    try {
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 128           // 64 频段，性能优先
      analyser.smoothingTimeConstant = 0.6
      _warmCtx = ctx
      _warmAnalyser = analyser
    } catch {}
  }

  // 应用启动后空闲时预热（不影响首屏渲染与交互）
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(() => _warmupAudioPipeline(), { timeout: 3000 })
  } else {
    setTimeout(_warmupAudioPipeline, 1500)
  }

  // 播放模式: 'sequential' | 'repeat' | 'repeat-one' | 'shuffle'
  const playMode = ref('sequential')

  // 桌面歌词开关
  const showDesktopLyrics = ref(false)

  // 切歌方向：'next' | 'prev' | null，用于全屏歌词页的过渡动画
  const songChangeDirection = ref(null)

  // 保存的播放数据
  const savedTime = ref(0)
  const savedVolume = ref(0.7)

  // 随机模式：备份原始顺序
  const originalQueue = ref([])

  // seek 偏移量：当通过 URL reload 方式 seek 到中途时，Audio 元素内部时间线从 0 开始，
  // 此偏移量用于将 currentTime 映射回完整歌曲的时间轴
  let _seekOffset = 0

  // 返回当前真实播放时间（绕过 timeupdate 节流，适用于逐字歌词动画等高频场景）
  function getLiveTime() {
    return (audio.value?.currentTime || 0) + _seekOffset
  }

  // 深拷贝队列
  function cloneQueue(src) {
    return src.map(t => ({ ...t }))
  }

  // 用 path 在队列中查找索引
  function findIndexByPath(q, track) {
    if (!track || !track.path) return -1
    return q.findIndex(t => t.path === track.path)
  }

  // Fisher-Yates 洗牌
  function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]]
    }
    return arr
  }

  // 初始化音频
  function initAudio() {
    if (audio.value) return
    audio.value = new Audio()
    audio.value.crossOrigin = 'anonymous'    // Web Audio API 取流必备
    audio.value.preload = 'auto'
    audio.value.volume = volume.value

    // 创建 Web Audio 频谱分析管线（只在首次播放时初始化一次）
    audio.value.addEventListener('play', async () => {
      if (audioCtx.value) return
      try {
        let ctx = _warmCtx
        let analyser = _warmAnalyser

        // 预热创建的是挂起状态：先在用户手势内恢复，再接线（避免静音窗口）
        if (ctx && ctx.state === 'suspended') {
          try { await ctx.resume() } catch {}
        }
        // 预热未完成或 resume 失败：手势内同步兜底创建（与旧行为一致）
        if (!ctx || !analyser || ctx.state !== 'running') {
          ctx = new AudioContext()
          analyser = ctx.createAnalyser()
          analyser.fftSize = 128           // 64 频段，性能优先
          analyser.smoothingTimeConstant = 0.6
        }

        const src = ctx.createMediaElementSource(audio.value)
        src.connect(analyser)
        analyser.connect(ctx.destination) // 手动路由到扬声器，否则无声
        audioCtx.value = ctx
        analyserNode.value = analyser
      } catch (e) {
        console.warn('[audio-rhythm] AudioContext 初始化失败:', e)
      }
    }, { once: true })

    audio.value.addEventListener('timeupdate', () => {
      currentTime.value = audio.value.currentTime + _seekOffset
      // 最低试听 30 秒计为一次有效播放（对齐 Spotify 标准）
      if (!_playTracked && audio.value.currentTime >= 30) {
        const track = currentTrack.value
        if (track) {
          _playTracked = true
          _trackPlay(track)
        }
      }
    })
    audio.value.addEventListener('loadedmetadata', () => {
      // seek 偏移时流时长是裁剪后的，不要覆盖完整时长
      if (_seekOffset === 0) {
        duration.value = audio.value.duration
      }
    })
    audio.value.addEventListener('ended', () => {
      // 短曲（不足 30 秒）播完也计为有效播放
      if (!_playTracked) {
        _playTracked = true
        const track = currentTrack.value
        if (track) _trackPlay(track)
      }
      // 听完反馈（画像正样本）
      _reportComplete()
      next()
    })
    audio.value.addEventListener('error', (e) => {
      const a = audio.value
      const codes = { 1: 'MEDIA_ERR_ABORTED', 2: 'MEDIA_ERR_NETWORK', 3: 'MEDIA_ERR_DECODE', 4: 'MEDIA_ERR_SRC_NOT_SUPPORTED' }
      console.error('音频播放错误:', codes[a.error?.code] || a.error?.code, a.error?.message || '', a.src)
      next()
    })
    audio.value.addEventListener('progress', () => {
      if (audio.value.buffered.length > 0) {
        const end = audio.value.buffered.end(audio.value.buffered.length - 1)
        if (audio.value.duration > 0) {
          bufferedPercent.value = Math.min(100, (end / audio.value.duration) * 100)
        }
      }
    })
  }

  // 当前播放的歌曲
  const currentTrack = computed(() => {
    if (currentIndex.value >= 0 && currentIndex.value < queue.value.length) {
      return queue.value[currentIndex.value]
    }
    return null
  })

  // 播放进度百分比
  const progress = computed(() => {
    if (duration.value > 0) return (currentTime.value / duration.value) * 100
    return 0
  })

  // 队列中是否还有下一首
  const hasNext = computed(() => {
    if (playMode.value === 'repeat' || playMode.value === 'repeat-one' || playMode.value === 'shuffle') return true
    return currentIndex.value < queue.value.length - 1
  })

  const hasPrev = computed(() => {
    if (playMode.value === 'repeat' || playMode.value === 'repeat-one' || playMode.value === 'shuffle') return true
    return currentIndex.value > 0
  })

  // 播放追踪：记录到后端统计
  let _playTracked = false
  let _trackStartedAt = 0
  let _lastTrackInfo = null
  const SKIP_THRESHOLD_MS = 15000

  function _reportSkipIfNeeded() {
    const prev = _lastTrackInfo
    if (!prev || _playTracked) return
    if (Date.now() - _trackStartedAt >= SKIP_THRESHOLD_MS) return
    const ratio = duration.value > 0
      ? Math.min(1, currentTime.value / duration.value) : 0
    useAiStore().reportFeedback('skip', prev, { durationRatio: ratio })
  }

  function _reportComplete() {
    const track = _lastTrackInfo || currentTrack.value
    if (!track) return
    const ratio = duration.value > 0
      ? Math.min(1, currentTime.value / duration.value) : 1
    useAiStore().reportFeedback('complete', track, { durationRatio: ratio })
  }

  async function _trackPlay(track) {
    try {
      await fetch(apiUrl('/api/stats/play'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: track.path,
          title: track.title || '',
          artist: track.artist || '',
          album: track.album || '',
          duration_played: Math.round(audio.value?.currentTime || 0),
          duration_ratio: duration.value > 0
            ? Math.min(1, (audio.value?.currentTime || 0) / duration.value) : 0
        })
      })
    } catch { /* 静默失败，不影响播放 */ }
  }

  // 播放指定索引
  function play(index) {
    initAudio()
    if (index < 0 || index >= queue.value.length) return

    // 切换前上报"跳过"反馈（新曲未满 15 秒且未计有效播放）
    _reportSkipIfNeeded()

    _seekOffset = 0
    _playTracked = false
    currentIndex.value = index
    const track = queue.value[index]
    _trackStartedAt = Date.now()
    _lastTrackInfo = track
    if (audio.value) {
      audio.value.src = track.url
      audio.value.play().then(() => {
        isPlaying.value = true
      }).catch(err => {
        if (err.name === 'AbortError') return
        console.error('播放失败:', track.path, track.title, err)
      })
    }
  }

  // 暂停
  function pause() {
    audio.value?.pause()
    isPlaying.value = false
  }

  // 恢复
  function resume() {
    audio.value?.play().then(() => {
      isPlaying.value = true
    }).catch(() => {})
  }

  // 切换播放/暂停
  function togglePlay() {
    if (isPlaying.value) pause()
    else resume()
  }

  // 下一首
  function next() {
    if (queue.value.length === 0) return
    songChangeDirection.value = 'next'
    let nextIndex
    switch (playMode.value) {
      case 'repeat-one':
        nextIndex = currentIndex.value
        break
      default:
        nextIndex = currentIndex.value + 1
        if (nextIndex >= queue.value.length) {
          if (playMode.value === 'repeat' || playMode.value === 'shuffle') {
            nextIndex = 0
          } else {
            pause()
            return
          }
        }
    }
    play(nextIndex)
  }

  // 上一首
  function prev() {
    if (queue.value.length === 0) return
    if (currentTime.value > 3) {
      // 从头播放当前曲目：方向为 null（刷新），不做切歌动画
      // 从头播放当前曲目：直接 seek 到 0 避免 URL 未变时浏览器不重载
      if (audio.value) audio.value.currentTime = 0
      _seekOffset = 0
      currentTime.value = 0
      resume()
      return
    }
    songChangeDirection.value = 'prev'
    let prevIndex
    switch (playMode.value) {
      case 'repeat-one':
        prevIndex = currentIndex.value
        break
      default:
        prevIndex = currentIndex.value - 1
        if (prevIndex < 0) {
          prevIndex = playMode.value === 'repeat' || playMode.value === 'shuffle' ? queue.value.length - 1 : 0
        }
    }
    play(prevIndex)
  }

  // 调整进度
  function seek(percent) {
    if (!audio.value || !duration.value) return
    const target = (percent / 100) * duration.value
    const distance = Math.abs(target - (audio.value.currentTime + _seekOffset))

    const track = currentTrack.value
    const ext = track?.path?.split('.').pop()?.toLowerCase()

    // FLAC：远距离 seek（>5s）或 seek 到当前流起始之前，需通过 URL reload 让 ffmpeg 从目标位置开始解码
    // _seekOffset > 0 时当前 WAV 流从 _seekOffset 秒开始，seek 到该点之前会导致内部时间为负，必须重载
    // 云端歌曲使用浏览器原生 Range seeking，不走 ffmpeg reload 路径
    const isCloud = track?.source === 'cloud'
    if (ext === 'flac' && !isCloud && (distance > 5 || (_seekOffset > 0 && target < _seekOffset))) {
      _seekViaReload(target)
      return
    }

    // 近距离 seek 或非 FLAC：直接设置 currentTime（需减去偏移量映射回 Audio 内部时间线）
    audio.value.currentTime = target - _seekOffset
  }

  // FLAC 远距离 seek：重新请求 ffmpeg 从目标时间开始解码
  function _seekViaReload(targetTime) {
    const a = audio.value
    const track = currentTrack.value
    if (!a || !track?.url) return

    const wasPlaying = !a.paused
    const vol = a.volume

    _seekOffset = targetTime
    // 防御性清理 URL 中旧的 start= 参数，再追加新的
    const baseUrl = track.url.replace(/[&?]start=[\d.]+/g, '')
    const sep = baseUrl.includes('?') ? '&' : '?'
    a.src = baseUrl + sep + 'start=' + targetTime.toFixed(3)

    const onReady = () => {
      a.removeEventListener('loadedmetadata', onReady)
      a.volume = vol
      if (wasPlaying) {
        a.play().catch(() => {})
      }
    }
    a.addEventListener('loadedmetadata', onReady)
  }

  // 调整音量
  function setVolume(val) {
    volume.value = Math.max(0, Math.min(1, val))
    if (audio.value) audio.value.volume = volume.value
    if (volume.value > 0) isMuted.value = false
  }

  // 切换静音
  function toggleMute() {
    if (isMuted.value) {
      isMuted.value = false
      volume.value = savedVolume.value
      if (audio.value) audio.value.volume = volume.value
    } else {
      savedVolume.value = volume.value
      isMuted.value = true
      volume.value = 0
      if (audio.value) audio.value.volume = 0
    }
  }

  // 切换桌面歌词
  function toggleDesktopLyrics() {
    // 桌面歌词为会员功能
    if (!useAuthStore().isVip) {
      ElMessage.warning('桌面歌词为会员专享，请先在用户中心升级')
      return
    }
    showDesktopLyrics.value = !showDesktopLyrics.value
  }

  // 切换播放模式: sequential → repeat-one → shuffle → repeat → ...
  function togglePlayMode() {
    const modes = ['sequential', 'repeat-one', 'shuffle', 'repeat']
    const idx = modes.indexOf(playMode.value)
    const nextMode = modes[(idx + 1) % modes.length]

    // === 进入随机模式：打乱队列，保存原始顺序 ===
    if (nextMode === 'shuffle' && playMode.value !== 'shuffle') {
      const currentTrack = queue.value[currentIndex.value]
      // 保存原始顺序（尚未被 shuffle 过的才保存）
      if (originalQueue.value.length === 0) {
        originalQueue.value = cloneQueue(queue.value)
      }
      // 打乱队列
      shuffle(queue.value)
      // 找到当前歌在新队列中的位置
      if (currentTrack) {
        const newIdx = findIndexByPath(queue.value, currentTrack)
        if (newIdx !== -1) currentIndex.value = newIdx
      }
    }

    // === 退出随机模式：恢复原始顺序 ===
    if (playMode.value === 'shuffle' && nextMode !== 'shuffle') {
      if (originalQueue.value.length > 0) {
        const currentTrack = queue.value[currentIndex.value]
        queue.value = cloneQueue(originalQueue.value)
        originalQueue.value = []
        if (currentTrack) {
          const newIdx = findIndexByPath(queue.value, currentTrack)
          if (newIdx !== -1) currentIndex.value = newIdx
        }
      }
    }

    playMode.value = nextMode
  }

  // 添加到队尾
  function addToQueue(tracks) {
    const arr = Array.isArray(tracks) ? tracks : [tracks]
    queue.value.push(...arr)
  }

  // 添加到下一曲（插入到 currentIndex 之后）
  function addToQueueNext(track) {
    if (currentIndex.value < 0) {
      queue.value.push(track)
    } else {
      queue.value.splice(currentIndex.value + 1, 0, track)
    }
  }

  // 从队列移除
  function removeFromQueue(index) {
    if (index < currentIndex.value) currentIndex.value--
    else if (index === currentIndex.value) {
      audio.value?.pause()
    }
    queue.value.splice(index, 1)
  }

  // 清空队列
  function clearQueue() {
    audio.value?.pause()
    isPlaying.value = false
    queue.value = []
    currentIndex.value = -1
    originalQueue.value = []
  }

  // 拖拽调整队列顺序：保持当前播放曲不变
  function moveInQueue(from, to) {
    const q = queue.value
    if (from < 0 || to < 0 || from >= q.length || to >= q.length || from === to) return
    const c = currentIndex.value
    const curTrack = c >= 0 && c < q.length ? q[c] : null
    const next = [...q]
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    queue.value = next
    if (curTrack) {
      const idx = next.findIndex(t => t === curTrack)
      if (idx !== -1) currentIndex.value = idx
    }
  }

  // 插播到下一曲：把指定项移到当前播放之后
  function moveToNext(index) {
    const q = queue.value
    const c = currentIndex.value
    if (c < 0 || index < 0 || index >= q.length || index === c) return
    const curTrack = q[c]
    const next = [...q]
    const [item] = next.splice(index, 1)
    const curIdx = next.findIndex(t => t === curTrack)
    if (curIdx === -1) return
    next.splice(curIdx + 1, 0, item)
    queue.value = next
  }

  // 播放全部（替换队列）
  function playAll(tracks, startIndex = 0) {
    clearQueue()
    queue.value = [...tracks]
    if (playMode.value === 'shuffle') {
      // 随机模式：保存原始顺序并打乱
      originalQueue.value = cloneQueue(queue.value)
      shuffle(queue.value)
      // 找到起始歌在新队列中的位置
      const target = tracks[startIndex]
      if (target) {
        const newIdx = findIndexByPath(queue.value, target)
        play(newIdx !== -1 ? newIdx : 0)
      } else {
        play(0)
      }
    } else {
      play(startIndex)
    }
  }

  // 保存/加载设置
  function saveSettings() {
    const settings = {
      volume: volume.value,
      playMode: playMode.value
    }
    localStorage.setItem('player-settings', JSON.stringify(settings))
  }

  function loadSettings() {
    try {
      const raw = localStorage.getItem('player-settings')
      if (raw) {
        const settings = JSON.parse(raw)
        volume.value = settings.volume ?? 0.7
        playMode.value = settings.playMode ?? 'sequential'
      }
    } catch {}
  }

  // 保存当前播放进度
  function saveProgress() {
    savedTime.value = currentTime.value
  }

  function restoreProgress() {
    if (savedTime.value > 0 && audio.value) {
      audio.value.currentTime = savedTime.value
    }
  }

  return {
    queue, currentIndex, audio, isPlaying, currentTime, duration,
    volume, isMuted, bufferedPercent, playMode, showDesktopLyrics, savedTime, savedVolume,
    songChangeDirection, audioCtx, analyserNode,
    currentTrack, progress, hasNext, hasPrev,
    initAudio, play, pause, resume, togglePlay,
    next, prev, seek, setVolume, toggleMute, togglePlayMode, toggleDesktopLyrics,
    addToQueue, addToQueueNext, removeFromQueue, clearQueue, moveInQueue, moveToNext, playAll,
    saveSettings, loadSettings, saveProgress, restoreProgress,
    getLiveTime
  }
})
