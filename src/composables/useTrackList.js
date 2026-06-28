import { ref } from 'vue'

/**
 * 共享的曲目列表交互逻辑：右键菜单 + 多选
 */
export function useTrackList() {
  const multiSelectMode = ref(false)
  const selected = ref(new Set())

  const ctxMenu = ref({ visible: false, x: 0, y: 0, track: null })

  // --- 右键菜单（含防出屏） ---
  function showContextMenu(e, track) {
    const menuW = 180
    const menuH = 260
    let x = e.clientX
    let y = e.clientY
    if (x + menuW > window.innerWidth) x = window.innerWidth - menuW - 8
    if (y + menuH > window.innerHeight) y = window.innerHeight - menuH - 8
    ctxMenu.value = { visible: true, x, y, track }
  }

  function hideContextMenu() {
    ctxMenu.value.visible = false
  }

  /**
   * 根据页面类型构建右键菜单项
   * @param {'library'|'playlist'|'album'|'artist'|'default'} page
   */
  function buildMenuItems(page) {
    const items = [
      { label: '播放', action: 'play' },
      { label: '添加到队尾', action: 'addQueueEnd' },
      { label: '添加到下一曲', action: 'addQueueNext' },
      '-',
    ]
    if (page === 'library') {
      items.push({ label: '添加到歌单', action: 'addToPlaylist' }, '-')
    } else if (page === 'playlist') {
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
    showContextMenu,
    hideContextMenu,
    buildMenuItems,
    toggleSelectMode,
    isSelected,
    toggleSelect,
    selectAll,
    clearSelection
  }
}
