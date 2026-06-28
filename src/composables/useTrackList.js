import { ref } from 'vue'

export function useTrackList() {
  const multiSelectMode = ref(false)
  const selected = ref(new Set())

  const ctxMenu = ref({ visible: false, x: 0, y: 0, track: null })

  // --- 右键菜单（含防出屏） ---
  function showContextMenu(e, track) {
    const menuW = 180
    const menuH = 160
    let x = e.clientX
    let y = e.clientY
    if (x + menuW > window.innerWidth) x = window.innerWidth - menuW - 8
    if (y + menuH > window.innerHeight) y = window.innerHeight - menuH - 8
    ctxMenu.value = { visible: true, x, y, track }
  }

  function hideContextMenu() {
    ctxMenu.value.visible = false
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
    toggleSelectMode,
    isSelected,
    toggleSelect,
    selectAll,
    clearSelection
  }
}
