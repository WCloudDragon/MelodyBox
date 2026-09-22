import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAiStore } from './ai'
import { useLibraryStore } from './library'
import { apiUrl, audioUrl } from '@/config/api'
import { useAuthStore } from './auth'
import { ElMessage } from '@/utils/toast'

// ==================== 播放模式注册表（单一定义源） ====================
// inList: 是否出现在「列表页顶栏」的模式菜单中——
// 单曲循环是「对当前这首歌」的播放控制，只属于播放器（播放栏），列表菜单不提供
export const PLAY_MODES = [
  { key: 'sequential', label: '顺序播放', inList: true },
  { key: 'repeat', label: '列表循环', inList: true },
  { key: 'repeat-one', label: '单曲循环', inList: false },
  { key: 'shuffle', label: '随机播放', inList: true }
]
const PLAY_MODE_KEYS = PLAY_MODES.map(m => m.key)

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

  // 播放模式 key 见顶部 PLAY_MODES 注册表（默认列表循环）
  const playMode = ref('repeat')

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
  // 会话恢复：等待元数据加载完成后跳转到上次进度
  let _pendingSeek = 0

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
      // 单曲循环：显式归零重播。同 src 再次赋值浏览器不重载、从末尾 resume 会立即再 ended，
      // play(同 index) 是失效的（历史 bug：单曲循环表现为播完即停）
      if (playMode.value === 'repeat-one') {
        _playTracked = false
        _trackStartedAt = Date.now()
        _seekOffset = 0
        currentTime.value = 0
        if (audio.value) {
          audio.value.currentTime = 0
          audio.value.play().then(() => { isPlaying.value = true }).catch(() => {})
        }
        return
      }
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

    // 切歌方向：next/prev 已显式设置则沿用；双击起播等直接播放按索引推断
    // （index 后移=next、前移=prev、同曲重播不设方向即无切歌动画）
    if (!songChangeDirection.value) {
      if (index > currentIndex.value) songChangeDirection.value = 'next'
      else if (index < currentIndex.value) songChangeDirection.value = 'prev'
    }

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

  // 下一首（手动切歌，不受模式影响；单曲循环只约束自然结束的重播行为）
  function next() {
    if (queue.value.length === 0) return
    songChangeDirection.value = 'next'
    let nextIndex = currentIndex.value + 1
    if (nextIndex >= queue.value.length) {
      if (playMode.value === 'repeat' || playMode.value === 'shuffle') {
        nextIndex = 0
      } else {
        pause()
        return
      }
    }
    play(nextIndex)
  }

  // 上一首
  function prev() {
    if (queue.value.length === 0) return
    if (currentTime.value > 3) {
      // 从头播放当前曲目：直接 seek 到 0 避免 URL 未变时浏览器不重载
      if (audio.value) audio.value.currentTime = 0
      _seekOffset = 0
      currentTime.value = 0
      resume()
      return
    }
    songChangeDirection.value = 'prev'
    let prevIndex = currentIndex.value - 1
    if (prevIndex < 0) {
      prevIndex = playMode.value === 'repeat' || playMode.value === 'shuffle' ? queue.value.length - 1 : 0
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

  // === 随机模式进入/退出（toggle 与 set 共用，行为统一：保持当前曲不打断） ===
  function applyShuffleOn() {
    // 保存原始顺序（尚未被 shuffle 过的才保存）
    if (originalQueue.value.length === 0) {
      originalQueue.value = cloneQueue(queue.value)
    }
    const cur = queue.value[currentIndex.value]
    shuffle(queue.value)
    // 当前歌跟随到新队列中的位置，不打断播放
    if (cur) {
      const newIdx = findIndexByPath(queue.value, cur)
      if (newIdx !== -1) currentIndex.value = newIdx
    }
  }

  function applyShuffleOff() {
    if (originalQueue.value.length === 0) return
    const cur = queue.value[currentIndex.value]
    queue.value = cloneQueue(originalQueue.value)
    originalQueue.value = []
    if (cur) {
      const newIdx = findIndexByPath(queue.value, cur)
      if (newIdx !== -1) currentIndex.value = newIdx
    }
  }

  // 循环切换播放模式（播放栏按钮）：顺序 → 列表循环 → 单曲循环 → 随机 → ...
  function togglePlayMode() {
    const idx = PLAY_MODE_KEYS.indexOf(playMode.value)
    const nextMode = PLAY_MODE_KEYS[(idx + 1) % PLAY_MODE_KEYS.length]
    if (nextMode === 'shuffle' && playMode.value !== 'shuffle') applyShuffleOn()
    else if (playMode.value === 'shuffle' && nextMode !== 'shuffle') applyShuffleOff()
    playMode.value = nextMode
  }

  // 设定播放模式（列表页右键菜单选中：仅设定偏好，起播由调用方对目标列表执行）
  function setPlayMode(mode) {
    if (!PLAY_MODE_KEYS.includes(mode) || mode === playMode.value) return
    if (mode === 'shuffle' && playMode.value !== 'shuffle') applyShuffleOn()
    else if (playMode.value === 'shuffle' && mode !== 'shuffle') applyShuffleOff()
    playMode.value = mode
  }

  // 列表页一键起播：以当前播放模式起播传入列表的全部歌曲。
  // 随机模式 = 打乱整个列表后从打乱序的第一首播（原序存入 originalQueue 供退出随机时恢复）
  function playListByMode(tracks) {
    if (!Array.isArray(tracks) || tracks.length === 0) return
    if (playMode.value === 'shuffle') {
      clearQueue()
      originalQueue.value = cloneQueue(tracks)
      queue.value = cloneQueue(tracks)
      shuffle(queue.value)
      currentIndex.value = 0
      play(0)
    } else {
      playAll(tracks, 0)
    }
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

  // 播放全部（替换队列）。
  // 入口兜底：歌单/收藏等来源的曲目对象可能缺 url（后端只给 path），一律先按 path
  // 从曲库换出完整对象（含 audioUrl 音频流地址），否则 audio.src=undefined → error → 无限跳歌
  function playAll(tracks, startIndex = 0) {
    const lib = useLibraryStore()
    const resolved = (Array.isArray(tracks) ? tracks : []).map(t => {
      if (t && !t.url && t.path) {
        const full = lib.getTrackByPath(t.path)
        if (full) return full
      }
      return t
    }).filter(t => t && t.url)
    if (!resolved.length) return
    clearQueue()
    queue.value = [...resolved]
    const startIndexTracks = resolved
    if (playMode.value === 'shuffle') {
      // 随机模式：保存原始顺序并打乱
      originalQueue.value = cloneQueue(queue.value)
      shuffle(queue.value)
      // 找到起始歌在新队列中的位置
      const target = startIndexTracks[startIndex]
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
      playMode: playMode.value,
      showDesktopLyrics: showDesktopLyrics.value
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
        showDesktopLyrics.value = settings.showDesktopLyrics ?? false
      }
    } catch {}
    // 启动时恢复上次播放会话（队列/当前歌曲/进度，不自动播放）
    loadSession()
  }

  // 播放器设置变化时落盘（音量/播放模式/桌面歌词开关）
  watch([volume, playMode, showDesktopLyrics], saveSettings)

  // 保存当前播放进度
  function saveProgress() {
    savedTime.value = currentTime.value
  }

  // ==================== 播放会话持久化 ====================
  const SESSION_KEY = 'player-session'
  let _sessionSaveTimer = null
  let _sessionLastSave = 0

  function _buildSessionData() {
    return {
      queue: queue.value
        .map(t => {
          if (!t || typeof t !== 'object') return null
          try { return JSON.parse(JSON.stringify(t)) } catch { return null }
        })
        .filter(Boolean),
      currentIndex: currentIndex.value,
      currentTime: currentTime.value
    }
  }

  async function persistSession(data) {
    // Electron 环境：写主进程文件（不受开发端口/刷新影响）；浏览器环境回退 localStorage
    try {
      if (window.electronAPI?.savePlaybackSession) {
        await window.electronAPI.savePlaybackSession(data)
        return
      }
    } catch {}
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(data))
    } catch {}
  }

  function saveSession() {
    persistSession(_buildSessionData())
  }

  function saveSessionSoon() {
    // 节流：播放中每 1 秒落盘一次（防抖会被 timeupdate 高频触发一直重置）
    const now = Date.now()
    if (now - _sessionLastSave >= 1000) {
      _sessionLastSave = now
      saveSession()
      return
    }
    if (_sessionSaveTimer) clearTimeout(_sessionSaveTimer)
    _sessionSaveTimer = setTimeout(() => {
      _sessionSaveTimer = null
      _sessionLastSave = Date.now()
      saveSession()
    }, 1000 - (now - _sessionLastSave))
  }

  async function loadSession() {
    let data = null
    try {
      if (window.electronAPI?.loadPlaybackSession) {
        data = await window.electronAPI.loadPlaybackSession()
      } else {
        const raw = localStorage.getItem(SESSION_KEY)
        if (raw) data = JSON.parse(raw)
      }
    } catch {}
    if (!data || !Array.isArray(data.queue) || data.queue.length === 0) return

    queue.value = data.queue
    const idx = Number.isInteger(data.currentIndex)
      ? data.currentIndex
      : data.currentIndex >= 0 && data.currentIndex < data.queue.length
        ? Math.floor(data.currentIndex)
        : -1
    if (idx < 0 || idx >= queue.value.length) {
      currentIndex.value = -1
      return
    }
    currentIndex.value = idx
    currentTime.value = Math.max(0, Number(data.currentTime) || 0)
    isPlaying.value = false

    // 准备好音频但不自动播放：用户点击播放即可从上次进度继续
    initAudio()
    const track = queue.value[currentIndex.value]
    if (audio.value && track) {
      if (!track.url && track.path) track.url = audioUrl(track.path)
      audio.value.src = track.url
      const resumeAt = currentTime.value
      if (resumeAt > 0) {
        if (audio.value.readyState >= 1) {
          audio.value.currentTime = resumeAt
        } else {
          _pendingSeek = resumeAt
          audio.value.addEventListener('loadedmetadata', () => {
            if (_pendingSeek > 0) {
              audio.value.currentTime = _pendingSeek
              _pendingSeek = 0
          }
          }, { once: true })
        }
      }
    }
  }

  // 队列/当前歌曲/进度变化时节流保存；窗口关闭前尽力兜底
  watch(queue, saveSessionSoon, { deep: true })
  watch(currentIndex, saveSessionSoon)
  watch(currentTime, saveSessionSoon)
  if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', saveSession)
    window.addEventListener('beforeunload', saveSession)
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
    next, prev, seek, setVolume, toggleMute, togglePlayMode, setPlayMode, playListByMode, toggleDesktopLyrics,
    addToQueue, addToQueueNext, removeFromQueue, clearQueue, moveInQueue, moveToNext, playAll,
    saveSettings, loadSettings, saveProgress, restoreProgress,
    getLiveTime
  }
})
