import { ref, h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePlaylistStore } from '@/stores/playlist'

/**
 * 共享的曲目列表交互逻辑：右键菜单 + 多选
 */
export function useTrackList() {
  const multiSelectMode = ref(false)
  const selected = ref(new Set())

  const ctxMenu = ref({ visible: false, x: 0, y: 0, track: null })
  const contextMenuTarget = ref(null)  // 当前右键目标 track.path，菜单关闭时清空

  // --- 右键菜单（含防出屏） ---
  function showContextMenu(e, track) {
    const menuW = 180
    const menuH = 260
    let x = e.clientX
    let y = e.clientY
    if (x + menuW > window.innerWidth) x = window.innerWidth - menuW - 8
    if (y + menuH > window.innerHeight) y = window.innerHeight - menuH - 8
    ctxMenu.value = { visible: true, x, y, track }
    contextMenuTarget.value = track.path
  }

  function hideContextMenu() {
    ctxMenu.value.visible = false
    contextMenuTarget.value = null
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
          return true
        case 'goArtist':
          if (track.artist) router.push('/artist/' + encodeURIComponent(track.artist))
          return true
        case 'trackInfo':
          router.push('/track-info?path=' + encodeURIComponent(track.path))
          return true
      }
      return false
    }
  }

  /**
   * 根据页面类型构建右键菜单项
   * @param {'library'|'playlist'|'album'|'artist'|'default'} page
   */
  function buildMenuItems(page) {
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
    items.push(
      { label: '跳转到专辑', action: 'goAlbum' },
      { label: '跳转到艺术家', action: 'goArtist' },
      '-',
      { label: '音轨信息', action: 'trackInfo' }
    )
    return items
  }

  // --- 添加到歌单（多选弹窗） ---
  function showAddPlaylistDialog(track) {
    const playlistStore = usePlaylistStore()
    const pls = playlistStore.playlists
    if (pls.length === 0) {
      ElMessage.warning('暂无歌单，请先创建歌单')
      return
    }
    if (pls.length === 1) {
      playlistStore.addToPlaylist(pls[0].id, track)
      ElMessage.success(`已添加到「${pls[0].name}」`)
      return
    }

    const selected = new Set()
    const checkItems = pls.map(pl =>
      h('label', { style: 'display:flex;align-items:center;gap:10px;padding:6px 0;cursor:pointer;font-size:14px' }, [
        h('input', {
          type: 'checkbox',
          value: pl.id,
          style: 'width:16px;height:16px;accent-color:var(--accent-color,#6366f1)',
          onChange: (e) => { if (e.target.checked) selected.add(pl.id); else selected.delete(pl.id) }
        }),
        h('span', pl.name)
      ])
    )

    ElMessageBox({
      title: '添加到歌单',
      message: h('div', { style: 'max-height:280px;overflow-y:auto' }, checkItems),
      confirmButtonText: '添加',
      showCancelButton: true,
      cancelButtonText: '取消'
    }).then(() => {
      if (selected.size === 0) {
        ElMessage.warning('未选择任何歌单')
        return
      }
      for (const id of selected) {
        playlistStore.addToPlaylist(id, track)
      }
      ElMessage.success(`已添加到 ${selected.size} 个歌单`)
    }).catch(() => {})
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
    createCtxHandler,
    buildMenuItems,
    showAddPlaylistDialog,
    toggleSelectMode,
    isSelected,
    toggleSelect,
    selectAll,
    clearSelection
  }
}
