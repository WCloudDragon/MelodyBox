import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  apiUrl,
  audioUrl,
  cloudStreamUrl,
  coverUrl,
  initAudioPort,
} from '@/config/api'
import { showScanNotify, updateScanNotify, closeScanNotify } from '@/utils/scanNotify'
import { ElMessage } from '@/utils/toast'

// 本地文件路径 → HTTP 音频流 URL（保留原导出名，内部也使用）
export function pathToUrlSync(filePath) {
  return audioUrl(filePath)
}

// 需要按数值比较的排序字段（其余按字符串比较）
const NUMERIC_SORT_KEYS = new Set(['duration', 'year', 'file_size', 'file_mtime'])

export const useLibraryStore = defineStore('library', () => {
  const tracks = ref([])
  const cloudTracks = ref([])
  const scanDirs = ref([])
  const isLoading = ref(false)
  const sortKey = ref('title')
  const sortOrder = ref('asc')
  const viewMode = ref('list')
  const filterGenre = ref('')
  const filterArtist = ref('')
  const sourceFilter = ref('all')   // 'all' | 'local' | 'cloud'

  const allTracks = computed(() => {
    if (sourceFilter.value === 'local') return tracks.value
    if (sourceFilter.value === 'cloud') return cloudTracks.value
    // 混合模式：指纹去重，同指纹优先保留本地副本
    const seen = new Set()
    const result = []
    for (const t of [...tracks.value, ...cloudTracks.value]) {
      const fp = t.fingerprint || `path:${t.path}`
      if (seen.has(fp)) continue
      seen.add(fp)
      result.push(t)
    }
    return result
  })

  // 从后端加载扫描目录列表
  async function loadScanDirs() {
    try {
      const res = await fetch(apiUrl('/api/folders'))
      if (res.ok) {
        const folders = await res.json()
        scanDirs.value = folders.map(f => f.path)
      }
    } catch {
      // 后端不可用时回退到 localStorage
      try {
        const raw = localStorage.getItem('scan-dirs')
        if (raw) scanDirs.value = JSON.parse(raw)
      } catch {}
    }
  }

  function saveScanDirs() {
    localStorage.setItem('scan-dirs', JSON.stringify(scanDirs.value))
  }

  // 指纹映射：同一歌曲本地优先（云端指纹→本地路径）
  const fingerprintToLocal = {}

  // 修复封面 URL 和播放 URL
  function fixSongUrl(song) {
    if (song.cover) song.cover = coverUrl(song.cover)
    if (!song.url && song.path) {
      // 云端歌曲：优先解析到本地等价副本（同一指纹）
      const fp = song.fingerprint
      if (song.source === 'cloud' && fp !== undefined && fingerprintToLocal[fp]) {
        const local = fingerprintToLocal[fp]
        song.url = pathToUrlSync(local.path)
        if (!song.cover && local.cover) song.cover = coverUrl(local.cover)
        return
      }
      song.url = song.source === 'cloud'
        ? cloudStreamUrl(song.path, localStorage.getItem('auth-token') || '')
        : pathToUrlSync(song.path)
    }
  }

  // 从 Flask API 加载全部歌曲（一次性加载列表，后续前端过滤）
  async function loadFromApi() {
    try {
      await initAudioPort()
      const res = await fetch(apiUrl('/api/music/songs?page=1&page_size=100000&source=local'))
      if (!res.ok) return false
      const data = await res.json()
      if (data.songs) {
        data.songs.forEach(s => {
          s.source = 'local'
          // 从API响应保留 cloud_meta 字段（用于MusicCard差异提示）
          if (!s.cloud_meta) s.cloud_meta = null
          fixSongUrl(s)
          // 建立指纹→本地映射
          if (s.fingerprint) {
            fingerprintToLocal[s.fingerprint] = { path: s.path, cover: s.cover }
          }
        })
        tracks.value = data.songs
      }
      return true
    } catch {
      return false
    }
  }

  // 加载云端歌曲
  async function loadCloudSongs() {
    try {
      // 云端曲库为会员功能：非会员直接置空
      const { useAuthStore } = await import('@/stores/auth')
      if (!useAuthStore().isVip) {
        cloudTracks.value = []
        return false
      }
      const token = localStorage.getItem('auth-token')
      if (!token) return false
      const res = await fetch(apiUrl('/api/music/songs?page=1&page_size=100000&source=cloud'), {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      if (!res.ok) return false
      const data = await res.json()
      if (data.songs) {
        data.songs.forEach(s => {
          s.source = 'cloud'
          fixSongUrl(s)
        })
        cloudTracks.value = data.songs
      }
      return true
    } catch {
      return false
    }
  }

  function setSourceFilter(filter) {
    sourceFilter.value = filter
  }

  // ==================== 扫描流程 ====================

  const isScanning = ref(false)
  const scanProgress = ref({ current: 0, total: 0, path: '' })
  // 缩略图批次版本号：批次完成时 +1，列表里加载失败的封面据此重试并淡入
  const thumbVersion = ref(0)
  function bumpThumbVersion() { thumbVersion.value++ }
  // 文件夹列表版本号：扫描结束后 +1，文件夹管理页据此重新拉取统计
  const foldersVersion = ref(0)
  let _scanPollTimer = null

  /**
   * 扫描进度轮询（全局唯一）：进度面板 + 结束后刷新文件夹列表、曲库与缩略图。
   * 后端在队列未清空时保持 scanning=true，因此批量重扫只会在全部完成后收尾。
   */
  function startScanPolling() {
    if (_scanPollTimer) return
    isScanning.value = true
    showScanNotify()
    _scanPollTimer = setInterval(async () => {
      try {
        const res = await fetch(apiUrl('/api/folders/scan-progress'))
        const p = await res.json()
        scanProgress.value = p
        const prefix = p.batch_total > 1 ? `文件夹 ${p.batch_index}/${p.batch_total} · ` : ''
        updateScanNotify(p.current, p.total, p.path, prefix)
        if (!p.scanning) {
          clearInterval(_scanPollTimer)
          _scanPollTimer = null
          isScanning.value = false
          await loadFoldersList()
          await loadFromApi()
          foldersVersion.value++
          closeScanNotify(p, () => {})
        }
      } catch {}
    }, 250)
  }

  /**
   * 添加音乐文件夹并扫描（文件夹页 / 音乐库空态 / 首页共用同一条路径）
   * 返回新增的文件夹数量；扫描进行中添加的目录会排在队尾等待
   */
  async function addFolders() {
    if (!window.electronAPI) {
      ElMessage.warning('请使用桌面版操作')
      return 0
    }
    const dirs = await window.electronAPI.selectFolder()
    if (!dirs || dirs.length === 0) return 0

    const FOLDERS_API = apiUrl('/api/folders')
    let added = 0

    for (const d of dirs) {
      try {
        const res = await fetch(FOLDERS_API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: d })
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          if (res.status === 409) ElMessage.warning('该文件夹已存在，跳过')
          else ElMessage.error(data.error || '添加失败')
          continue
        }
        added++
      } catch (e) {
        ElMessage.error(e.message || '添加失败')
      }
    }
    if (!added) return 0

    if (isScanning.value) {
      // 已有扫描在跑：后端队列会串行处理新目录，不需要新的进度卡
      ElMessage.info('已加入扫描队列，等待当前扫描完成后开始')
    } else {
      startScanPolling()
    }
    return added
  }

  async function loadFoldersList() {
    try {
      const res = await fetch(apiUrl('/api/folders'))
      if (res.ok) {
        const folders = await res.json()
        scanDirs.value = folders.map(f => f.path)
        saveScanDirs()
      }
    } catch {}
  }

  /** 重新扫描单个文件夹（后台入队，异步执行） */
  async function rescanFolder(id) {
    try {
      const res = await fetch(apiUrl(`/api/folders/${id}/rescan`), { method: 'POST' })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        ElMessage.error(data.error || '扫描失败')
        return false
      }
      startScanPolling()
      return true
    } catch (e) {
      ElMessage.error(e.message || '扫描失败')
      return false
    }
  }

  /** 重新扫描全部已添加文件夹（按添加顺序入队，串行执行） */
  async function rescanAllFolders() {
    try {
      const res = await fetch(apiUrl('/api/folders/rescan-all'), { method: 'POST' })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        ElMessage.warning(data.error || '扫描启动失败')
        return false
      }
      startScanPolling()
      return true
    } catch (e) {
      ElMessage.error(e.message || '扫描启动失败')
      return false
    }
  }

  // ==================== 计算属性（保持兼容） ====================

  const albums = computed(() => {
    const map = new Map()
    for (const t of tracks.value) {
      const key = t.album || '未知专辑'
      if (!map.has(key)) {
        map.set(key, {
          name: key,
          artist: t.artist,
          cover: t.cover,
          tracks: [],
          year: t.year
        })
      }
      map.get(key).tracks.push(t)
    }
    // 按碟号/音轨号排序
    for (const album of map.values()) {
      album.tracks.sort((a, b) => {
        const disc = (a.disc_number || 0) - (b.disc_number || 0)
        if (disc !== 0) return disc
        return (a.track_number || 0) - (b.track_number || 0)
      })
    }
    return Array.from(map.values())
  })

  const artists = computed(() => {
    const map = new Map()
    for (const t of tracks.value) {
      const raw = t.artist || '未知艺术家'
      const names = raw.split('/').map(n => n.trim()).filter(Boolean)
      const artistNames = names.length > 0 ? names : ['未知艺术家']
      for (const name of artistNames) {
        if (!map.has(name)) {
          map.set(name, { name, tracks: [] })
        }
        // 避免重复添加同一首歌
        const entry = map.get(name)
        if (!entry.tracks.find(x => x.path === t.path)) {
          entry.tracks.push(t)
        }
      }
    }
    return Array.from(map.values())
  })

  const genres = computed(() => {
    const set = new Set()
    for (const t of tracks.value) {
      if (t.genre) set.add(t.genre)
    }
    return Array.from(set).sort()
  })

  const filteredTracks = computed(() => {
    let result = [...allTracks.value]

    if (filterGenre.value) {
      result = result.filter(t => t.genre === filterGenre.value)
    }

    if (filterArtist.value) {
      result = result.filter(t => {
        const names = (t.artist || '').split('/').map(n => n.trim())
        return names.includes(filterArtist.value)
      })
    }

    result.sort((a, b) => {
      const key = sortKey.value
      const av = a[key]
      const bv = b[key]
      // 数值字段按数值比较（时长/年份/文件大小等），避免 "100" < "9" 的字符串错误
      if (NUMERIC_SORT_KEYS.has(key)) {
        const aMissing = av === null || av === undefined || av === ''
        const bMissing = bv === null || bv === undefined || bv === ''
        // 缺失值始终排在最后，不随升降序翻转
        if (aMissing || bMissing) {
          if (aMissing && bMissing) return 0
          return aMissing ? 1 : -1
        }
        const diff = Number(av) - Number(bv)
        return sortOrder.value === 'asc' ? diff : -diff
      }
      const va = (av ?? '').toString().toLowerCase()
      const vb = (bv ?? '').toString().toLowerCase()
      return sortOrder.value === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    })

    return result
  })

  const totalDuration = computed(() => {
    return allTracks.value.reduce((sum, t) => sum + (t.duration || 0), 0)
  })

  function getTrackByPath(path) {
    return allTracks.value.find(t => t.path === path)
  }

  // 本地 albums/artists 只聚合本地曲库（云端曲库体量大，并入会淹没列表页）；
  // 详情页查不到时按需从云端回退，保证在线歌曲的专辑/歌手可进入
  function findCloudAlbum(name) {
    const items = cloudTracks.value.filter(t => (t.album || '未知专辑') === name)
    if (!items.length) return null
    const sorted = [...items].sort((a, b) => {
      const disc = (a.disc_number || 0) - (b.disc_number || 0)
      if (disc !== 0) return disc
      return (a.track_number || 0) - (b.track_number || 0)
    })
    return {
      name,
      artist: sorted[0].artist,
      cover: sorted[0].cover,
      year: sorted[0].year,
      tracks: sorted,
      source: 'cloud'
    }
  }

  function findCloudArtist(name) {
    const items = cloudTracks.value.filter(t => {
      const names = (t.artist || '').split('/').map(n => n.trim()).filter(Boolean)
      return (names.length > 0 ? names : ['未知艺术家']).includes(name)
    })
    if (!items.length) return null
    return { name, tracks: items, source: 'cloud' }
  }

  function getAlbum(name) {
    return albums.value.find(a => a.name === name) || findCloudAlbum(name)
  }

  function getArtist(name) {
    return artists.value.find(a => a.name === name) || findCloudArtist(name)
  }

  // ==================== 初始化 ====================
  loadScanDirs()

  // 启动时从 API 加载已入库的歌曲（静默失败，允许无后端运行）
  loadFromApi()
  // 非阻塞加载云端歌曲
  loadCloudSongs()

  return {
    tracks, cloudTracks, allTracks, scanDirs, isLoading,
    sortKey, sortOrder,
    viewMode, filterGenre, filterArtist, sourceFilter,
    albums, artists, genres, filteredTracks, totalDuration,
    isScanning, scanProgress,
    thumbVersion, bumpThumbVersion, foldersVersion,
    addFolders, rescanFolder, rescanAllFolders,
    getTrackByPath, getAlbum, getArtist,
    loadFromApi, loadCloudSongs, setSourceFilter
  }
})
