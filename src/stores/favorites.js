/**
 * 收藏（我的收藏）store
 * favorites 列表同时包含本地与云端歌曲，用 source 区分；
 * isFavorite(track) 供任意歌曲卡片/菜单展示“已收藏”状态。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiUrl } from '@/config/api'
import { ElMessage } from '@/utils/toast'

export const useFavoritesStore = defineStore('favorites', () => {
  const favorites = ref([])  // 收藏歌曲列表（含 source / path 字段）
  const loaded = ref(false)
  let loadPromise = null

  const keyOf = (source, id) => `${source}:${id}`
  const keyOfTrack = (t) => {
    if (!t || t.id == null) return null
    return keyOf(t.source === 'cloud' ? 'cloud' : 'local', t.id)
  }
  const favKeySet = computed(() => new Set(favorites.value.map(f => keyOf(f.source, f.id))))

  /** 某歌曲是否已收藏 */
  function isFavorite(track) {
    const k = keyOfTrack(track)
    return !!k && favKeySet.value.has(k)
  }

  async function fetchList() {
    const token = localStorage.getItem('auth-token')
    const res = await fetch(apiUrl('/api/favorites'), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('加载收藏失败')
    const data = await res.json()
    return data.songs || []
  }

  /** 拉取收藏列表（并发去重） */
  async function load(force = false) {
    if (!force && (loaded.value || loadPromise)) return loadPromise
    if (!localStorage.getItem('auth-token')) {
      favorites.value = []
      loaded.value = true
      return Promise.resolve()
    }
    loadPromise = fetchList()
      .then(list => {
        favorites.value = list
        loaded.value = true
      })
      .catch(() => {
        favorites.value = []
        loaded.value = true
      })
      .finally(() => {
        loadPromise = null
      })
    return loadPromise
  }

  /** 收藏 / 取消收藏（幂等 toggle） */
  async function toggle(track) {
    const token = localStorage.getItem('auth-token')
    if (!token) {
      ElMessage.warning('请先登录后再收藏')
      return false
    }
    const k = keyOfTrack(track)
    if (!k) return false
    const [source, songId] = k.split(':')
    const existed = favKeySet.value.has(k)
    const headers = { Authorization: `Bearer ${token}` }

    let ok = true
    try {
      if (existed) {
        const res = await fetch(apiUrl(`/api/favorites/${source}/${songId}`), {
          method: 'DELETE',
          headers,
        })
        if (!res.ok) ok = false
      } else {
        const res = await fetch(apiUrl('/api/favorites'), {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ song_id: Number(songId), source }),
        })
        if (!res.ok) ok = false
      }
    } catch {
      ok = false
    }
    if (!ok) {
      ElMessage.error(existed ? '取消收藏失败' : '收藏失败')
      return false
    }

    if (existed) {
      const i = favorites.value.findIndex(f => keyOf(f.source, f.id) === k)
      if (i !== -1) favorites.value.splice(i, 1)
      ElMessage.success('已取消收藏')
    } else {
      favorites.value.unshift({ ...track })
      ElMessage.success('已收藏到我的收藏')
    }
    return true
  }

  return { favorites, loaded, isFavorite, load, toggle }
})