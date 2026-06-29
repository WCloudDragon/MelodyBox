import { defineStore } from 'pinia'
import { shallowRef, triggerRef, ref, computed, markRaw } from 'vue'

const API_BASE = 'http://127.0.0.1:5000/api/playlists'
const COVER_API = 'http://127.0.0.1:5000/api/music/cover'

function fixCoverUrl(coverPath) {
  if (!coverPath) return null
  if (coverPath.startsWith('http://') || coverPath.startsWith('https://')) return coverPath
  return `${COVER_API}?path=${encodeURIComponent(coverPath)}`
}

export const usePlaylistStore = defineStore('playlist', () => {
  const playlists = shallowRef([])
  const isLoaded = ref(false)

  const tracksCache = new Map()  // playlistId → songs[]
  const loadedPlaylists = new Set()

  // 从后端加载歌单列表
  async function loadPlaylists() {
    try {
      const res = await fetch(API_BASE)
      if (!res.ok) { isLoaded.value = true; return }
      const data = await res.json()
      playlists.value = data.map(pl => {
        if (pl.cover_url) pl.cover_url = fixCoverUrl(pl.cover_url)
        pl.tracks = []
        return pl
      })
      isLoaded.value = true
    } catch { isLoaded.value = true }
  }

  // 加载歌单内歌曲
  async function loadPlaylistTracks(playlistId) {
    if (loadedPlaylists.has(playlistId)) return
    loadedPlaylists.add(playlistId)

    try {
      const res = await fetch(`${API_BASE}/${playlistId}/songs`)
      if (!res.ok) return
      const songs = await res.json()
      songs.forEach(s => {
        if (s.cover) s.cover = fixCoverUrl(s.cover)
      })
      tracksCache.set(playlistId, songs)

      const pl = playlists.value.find(p => p.id === playlistId)
      if (pl) {
        pl.tracks = songs
        pl.trackCount = songs.length
        triggerRef(playlists)
      }
    } catch {}
  }

  function savePlaylists() {
    // 后端已持久化，此方法保留兼容性
  }

  // 创建歌单
  async function createPlaylist(name, description = '') {
    try {
      const res = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
      })
      if (!res.ok) return null
      const pl = await res.json()
      pl.tracks = []
      playlists.value.push(pl)
      triggerRef(playlists)
      return pl
    } catch { return null }
  }

  // 删除歌单
  async function deletePlaylist(id) {
    try {
      const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' })
      if (!res.ok) return
      const idx = playlists.value.findIndex(p => p.id === id)
      if (idx !== -1) {
        playlists.value.splice(idx, 1)
        tracksCache.delete(id)
        loadedPlaylists.delete(id)
        triggerRef(playlists)
      }
    } catch {}
  }

  // 重命名歌单
  async function renamePlaylist(id, name) {
    try {
      await fetch(`${API_BASE}/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      const playlist = playlists.value.find(p => p.id === id)
      if (playlist) {
        playlist.name = name
        triggerRef(playlists)
      }
    } catch {}
  }

  // 添加歌曲到歌单
  async function addToPlaylist(playlistId, track) {
    try {
      // 需要在 songs 表中查找这首歌的 id
      const byPathRes = await fetch(`http://127.0.0.1:5000/api/music/songs/by-path?path=${encodeURIComponent(track.path)}`)
      if (!byPathRes.ok) return
      const songData = await byPathRes.json()
      if (!songData.path) return

      // 用 file_path 反查 song_id（后端表结构支持）
      const res = await fetch(`${API_BASE}/${playlistId}/songs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ song_path: track.path })
      })
      if (!res.ok) return

      // 更新 trackCount
      const pl = playlists.value.find(p => p.id === playlistId)
      if (pl) {
        pl.trackCount = (pl.trackCount || 0) + 1
        if (!pl.cover_url && track.cover) {
          pl.cover_url = track.cover
        }
        triggerRef(playlists)
      }
      // 清除缓存，下次加载时刷新
      loadedPlaylists.delete(playlistId)
    } catch {}
  }

  // 从歌单移除歌曲
  async function removeFromPlaylist(playlistId, trackPath) {
    try {
      // 需要找 song_id: 先查
      const byPathRes = await fetch(`http://127.0.0.1:5000/api/music/songs/by-path?path=${encodeURIComponent(trackPath)}`)
      if (!byPathRes.ok) return
      const songData = await byPathRes.json()
      // 直接在本地 tracks 中找
      const pl = playlists.value.find(p => p.id === playlistId)
      if (!pl) return

      // 用 DELETE 端点
      const res = await fetch(`${API_BASE}/${playlistId}/songs/by-path?path=${encodeURIComponent(trackPath)}`, {
        method: 'DELETE'
      })
      loadedPlaylists.delete(playlistId)
    } catch {}
  }

  // 获取歌单（route.params.id 是字符串，数据库 id 是数字，松散比较）
  function getPlaylist(id) {
    return playlists.value.find(p => p.id == id)
  }

  const totalTracks = computed(() => {
    return playlists.value.reduce((sum, p) => sum + (p.trackCount || 0), 0)
  })

  // 向后兼容: ensureTracksLoaded
  async function ensureTracksLoaded(playlistId) {
    await loadPlaylistTracks(playlistId)
  }

  loadPlaylists()

  return {
    playlists, totalTracks, isLoaded,
    createPlaylist, deletePlaylist, renamePlaylist,
    addToPlaylist, removeFromPlaylist, getPlaylist,
    ensureTracksLoaded, loadPlaylistTracks, savePlaylists
  }
})
