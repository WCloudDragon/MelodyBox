import { ref, markRaw } from 'vue'
import { ElMessage } from '@/utils/toast'
import { usePlaylistStore } from '@/stores/playlist'
import { useModal } from '@/composables/useModal'
import { apiUrl } from '@/config/api'
import PlaylistPicker from '@/components/music/PlaylistPicker.vue'

/**
 * 共享的曲目列表交互逻辑：右键菜单 + 多选
 */
export function useTrackList() {
  const multiSelectMode = ref(false)
  const selected = ref(new Set())
  // inject 仅在 setup 期间合法，必须在组合函数初始化时获取，不能延迟到事件回调里
  const modal = useModal()

  const ctxMenu = ref({ visible: false, x: 0, y: 0, track: null, submenu: null })
  const contextMenuTarget = ref(null)  // 当前右键目标 track.path，菜单关闭时清空

  // --- 右键菜单（含防出屏） ---
  function showContextMenu(e, track, context = null) {
    const menuW = 180
    const menuH = 260
    let x = e.clientX
    let y = e.clientY
    if (x + menuW > window.innerWidth) x = window.innerWidth - menuW - 8
    if (y + menuH > window.innerHeight) y = window.innerHeight - menuH - 8
    ctxMenu.value = { visible: true, x, y, track, submenu: null, context }
    contextMenuTarget.value = track.path
  }

  function hideContextMenu() {
    ctxMenu.value.visible = false
    ctxMenu.value.submenu = null
    contextMenuTarget.value = null
  }

  /** 打开“选择艺术家”二级页（多个艺术家时返回 true） */
  function openArtistSubmenu() {
    const track = ctxMenu.value.track
    if (!track) return false
    const exclude = ctxMenu.value.context?.artistName
    const names = (track.artist || '')
      .split('/').map(s => s.trim()).filter(Boolean)
      .filter(n => !exclude || n !== exclude)
    if (names.length === 0) return false
    ctxMenu.value.submenu = {
      title: '选择艺术家',
      items: names.map(name => ({ label: name, artist: name }))
    }
    return true
  }

  /**
   * 创建统一的右键菜单操作处理器
   * @param {import('pinia').Store} playerStore
   * @param {import('vue-router').Router} router
   * @returns {(action: string) => boolean} handled
   */
  function createCtxHandler(playerStore, router) {
    return function (action) {
      const track = ctxMenu.value.track
      hideContextMenu()
      if (!track || !action) return false
      switch (action) {
        case 'play':
          playerStore.playAll([track], 0)
          return true
        case 'addQueueEnd':
          playerStore.addToQueue(track)
          ElMessage.success('已插播至队列末尾')
          return true
        case 'addQueueNext':
          playerStore.addToQueueNext(track)
          ElMessage.success('已插播至下一位置')
          return true
        case 'goAlbum':
          if (track.album) router.push('/album/' + encodeURIComponent(track.album))
          return 'navigate'
        case 'goArtist': {
          const names = (track.artist || '').split('/').map(s => s.trim()).filter(Boolean)
          if (names.length === 1) {
            router.push('/artist/' + encodeURIComponent(names[0]))
            return 'navigate'
          }
          if (openArtistSubmenu()) return 'submenu'
          return 'handled'
        }
        case 'trackInfo':
          router.push('/track-info?path=' + encodeURIComponent(track.path))
          return 'navigate'
        case 'goSimilar': {
          if (track?.id) {
            router.push({
              path: '/recommend',
              query: { mode: 'similar', song_id: track.id, title: track.title || '' },
            })
            return 'navigate'
          }
          return false
        }
      }
      return false
    }
  }

  /** 二级页“选择艺术家”的动作处理器 */
  function createSubActionHandler(router) {
    return function (item) {
      hideContextMenu()
      if (item && item.artist) {
        router.push('/artist/' + encodeURIComponent(item.artist))
      }
    }
  }

  /**
   * 根据页面类型构建右键菜单项
   * @param {'library'|'playlist'|'album'|'artist'|'default'} page
   */
  function buildMenuItems(page, track, context = {}) {
    // 失效条目（歌曲已从音乐库移除但保留足迹）：仅允许移除出歌单
    if (page === 'playlist' && track?.missing) {
      return [{ label: '从歌单移除', action: 'remove', danger: true }]
    }
    const artistNames = (track?.artist || '').split('/').map(s => s.trim()).filter(Boolean)
    const hasMultiArtist = artistNames.length > 1
    const currentArtist = context.artistName
    const items = [
      { label: '播放', action: 'play' },
      { label: '插播至当前播放后', action: 'addQueueNext' },
      { label: '插播至队列末尾', action: 'addQueueEnd' },
      '-',
    ]
    if (page !== 'playlist') {
      items.push({ label: '添加到歌单', action: 'addToPlaylist' }, '-')
    } else {
      items.push({ label: '从歌单移除', action: 'remove', danger: true }, '-')
    }
    if (page !== 'album') {
      items.push({ label: '跳转到专辑', action: 'goAlbum' })
    }
    // 艺术家详情页：单艺术家不显示“跳转艺术家”；多艺术家必须二级（剔除当前歌手）
    let showGoArtist = true
    let hasGoArtistSub = hasMultiArtist
    if (page === 'artist') {
      showGoArtist = hasMultiArtist
      if (showGoArtist && currentArtist) {
        hasGoArtistSub = artistNames.some(n => n !== currentArtist)
      }
    }
    if (showGoArtist) {
      items.push({ label: '跳转到艺术家', action: 'goArtist', hasSubmenu: hasGoArtistSub })
    }
    // 相似推荐：仅本地歌曲可用（后端 song_id 指向 songs 表）
    if (track && track.id != null && track.source !== 'cloud') {
      items.push({ label: '相似推荐', action: 'goSimilar' })
    }
    // 从音乐库移除：仅音乐库页提供（不删源文件，弹窗内可选是否保留歌曲足迹）
    if (page === 'library' && track && track.id != null && track.source !== 'cloud') {
      items.push({ label: '从音乐库移除', action: 'removeFromLibrary', danger: true })
    }
    items.push(
      '-',
      { label: '音轨信息', action: 'trackInfo' }
    )
    return items
  }

  // --- 添加到歌单（自研弹窗 + 歌单多选选择器；支持单曲或批量，已存在的自动跳过） ---
  async function showAddPlaylistDialog(trackInput) {
    const playlistStore = usePlaylistStore()
    const tracks = (Array.isArray(trackInput) ? trackInput : [trackInput])
      .filter(t => t && t.path && !t.missing)
    const pls = playlistStore.playlists
    if (!pls.length) {
      ElMessage.warning('暂无歌单，请先创建歌单')
      return
    }
    if (!tracks.length) {
      ElMessage.warning('所选歌曲无法添加到歌单')
      return
    }

    // 预取各歌单包含情况：total=歌单歌曲总数(含失效条目)，contained=选中歌曲已在该歌单的数量
    let status = {}
    try {
      const res = await fetch(apiUrl('/api/playlists/membership'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: tracks.map(t => t.path) })
      })
      if (res.ok) status = await res.json()
    } catch {}

    try {
      const result = await modal.confirm({
        title: '添加到歌单',
        message: tracks.length > 1
          ? `将选中的 ${tracks.length} 首歌曲添加到歌单（可多选）：`
          : '选择要添加到的歌单（可多选）：',
        confirmText: '添加',
        bodyComponent: markRaw(PlaylistPicker),
        bodyProps: { playlists: pls, status, total: tracks.length },
      })
      const ids = Array.isArray(result) ? result : []
      if (!ids.length) return

      // 已存在的歌曲由后端 INSERT OR IGNORE 跳过，前端据此统计提示
      let added = 0
      let skipped = 0
      for (const id of ids) {
        const k = status[id]?.contained || 0
        skipped += k
        added += tracks.length - k
        for (const t of tracks) {
          await playlistStore.addToPlaylist(id, t)
        }
      }
      let msg
      if (ids.length === 1) {
        const name = pls.find(p => p.id === ids[0])?.name || '歌单'
        msg = added > 0 && added < tracks.length
          ? `已添加到「${name}」（新增 ${added} 首，跳过 ${skipped} 首已存在）`
          : `已添加到「${name}」`
      } else {
        msg = `已添加到 ${ids.length} 个歌单（新增 ${added} 首${skipped ? `，跳过 ${skipped} 首已存在` : ''}）`
      }
      ElMessage.success(msg)
    } catch {}
  }

  // --- 多选 ---
  function toggleSelectMode() {
    multiSelectMode.value = !multiSelectMode.value
    if (!multiSelectMode.value) selected.value = new Set()
  }

  function isSelected(track) {
    return selected.value.has(track.path)
  }

  function toggleSelect(track) {
    const next = new Set(selected.value)
    if (next.has(track.path)) {
      next.delete(track.path)
    } else {
      next.add(track.path)
    }
    selected.value = next
  }

  function selectAll(tracks) {
    selected.value = new Set(tracks.map(t => t.path))
  }

  function clearSelection() {
    selected.value = new Set()
  }

  return {
    multiSelectMode,
    selected,
    ctxMenu,
    contextMenuTarget,
    showContextMenu,
    hideContextMenu,
    openArtistSubmenu,
    createCtxHandler,
    createSubActionHandler,
    buildMenuItems,
    showAddPlaylistDialog,
    toggleSelectMode,
    isSelected,
    toggleSelect,
    selectAll,
    clearSelection
  }
}
