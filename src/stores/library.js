import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = 'http://127.0.0.1:5000/api/music'
const CLOUD_API = 'http://127.0.0.1:5000/api/cloud'

// 音频服务器端口（通过 IPC 从主进程获取）
let audioPort = 51234
let portInitialized = false

async function initAudioPort() {
  if (portInitialized) return
  portInitialized = true
  if (window.electronAPI) {
    try {
      const port = await window.electronAPI.getAudioServerPort()
      if (port) audioPort = port
    } catch {}
  }
}

// 本地文件路径 → HTTP 音频流 URL
function pathToUrlSync(filePath) {
  return `http://127.0.0.1:${audioPort}/audio?path=${encodeURIComponent(filePath)}`
}

// 云端歌曲 → Flask 延迟模拟音频流
function cloudUrlSync(filePath) {
  return `http://127.0.0.1:5000/api/cloud/stream?path=${encodeURIComponent(filePath)}`
}

function coverUrl(coverPath) {
  if (!coverPath) return null
  // 如果已经是 HTTP URL 则直接返回
  if (coverPath.startsWith('http://') || coverPath.startsWith('https://')) return coverPath
  // 本地文件路径 → Flask 封面端点
  return `${API_BASE}/cover?path=${encodeURIComponent(coverPath)}`
}

export const useLibraryStore = defineStore('library', () => {
  const tracks = ref([])
  const cloudTracks = ref([])
  const scanDirs = ref([])
  const isLoading = ref(false)
  const searchQuery = ref('')
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
      const res = await fetch('http://127.0.0.1:5000/api/folders')
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
        ? cloudUrlSync(song.path)
        : pathToUrlSync(song.path)
    }
  }

  // 从 Flask API 加载全部歌曲（一次性加载列表，后续前端过滤）
  async function loadFromApi() {
    try {
      await initAudioPort()
      const res = await fetch(`${API_BASE}/songs?page=1&page_size=100000&source=local`)
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
      const token = localStorage.getItem('auth-token')
      if (!token) return false
      const res = await fetch(`${API_BASE}/songs?page=1&page_size=100000&source=cloud`, {
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

  async function scanMusic(dirs) {
    isLoading.value = true
    try {
      // 调用 Flask 扫描（同步，等待完成）
      const res = await fetch(`${API_BASE}/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directories: dirs })
      })
      if (!res.ok) {
        console.error('[store] 扫描失败:', await res.text())
        return
      }
      const result = await res.json()
      console.log(`[store] 扫描完成: 共${result.total}文件, 新增${result.inserted}, 更新${result.updated}, 删除${result.deleted}`)

      scanDirs.value = dirs
      saveScanDirs()

      // 从 DB 重新加载
      await loadFromApi()
    } catch (err) {
      console.error('[store] 扫描出错:', err)
    } finally {
      isLoading.value = false
    }
  }

  const isScanning = ref(false)
  const scanProgress = ref({ current: 0, total: 0, path: '' })
  let _scanPollTimer = null

  async function selectAndScan() {
    if (!window.electronAPI) {
      alert('请使用 Electron 桌面版打开本应用')
      return
    }
    const dirs = await window.electronAPI.selectFolder()
    if (!dirs || dirs.length === 0) return

    const FOLDERS_API = 'http://127.0.0.1:5000/api/folders'
    isScanning.value = true

    for (const d of dirs) {
      try {
        await fetch(FOLDERS_API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: d })
        })
      } catch (e) { console.error('[store] 添加文件夹出错:', e) }
    }

    // 轮询进度
    if (_scanPollTimer) clearInterval(_scanPollTimer)
    _scanPollTimer = setInterval(async () => {
      try {
        const res = await fetch(`${FOLDERS_API}/scan-progress`)
        const p = await res.json()
        scanProgress.value = p
        if (!p.scanning) {
          clearInterval(_scanPollTimer)
          _scanPollTimer = null
          isScanning.value = false
          await loadFoldersList()
          await loadFromApi()
        }
      } catch {}
    }, 500)
  }

  async function loadFoldersList() {
    try {
      const res = await fetch('http://127.0.0.1:5000/api/folders')
      if (res.ok) {
        const folders = await res.json()
        scanDirs.value = folders.map(f => f.path)
        saveScanDirs()
      }
    } catch {}
  }

  async function refreshLibrary() {
    if (scanDirs.value.length > 0) {
      await scanMusic(scanDirs.value)
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

    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      result = result.filter(t =>
        t.title.toLowerCase().includes(q) ||
        (t.artist && t.artist.toLowerCase().includes(q)) ||
        (t.album && t.album.toLowerCase().includes(q))
      )
    }

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
      const va = (a[sortKey.value] || '').toString().toLowerCase()
      const vb = (b[sortKey.value] || '').toString().toLowerCase()
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

  function getAlbum(name) {
    return albums.value.find(a => a.name === name)
  }

  function getArtist(name) {
    return artists.value.find(a => a.name === name)
  }

  // ==================== 初始化 ====================
  loadScanDirs()

  // 启动时从 API 加载已入库的歌曲（静默失败，允许无后端运行）
  loadFromApi()
  // 非阻塞加载云端歌曲
  loadCloudSongs()

  return {
    tracks, cloudTracks, allTracks, scanDirs, isLoading,
    searchQuery, sortKey, sortOrder,
    viewMode, filterGenre, filterArtist, sourceFilter,
    albums, artists, genres, filteredTracks, totalDuration,
    isScanning, scanProgress,
    scanMusic, selectAndScan, refreshLibrary,
    getTrackByPath, getAlbum, getArtist,
    loadFromApi, loadCloudSongs, setSourceFilter
  }
})
