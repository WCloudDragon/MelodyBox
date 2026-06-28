<template>
  <div class="albums-view">
    <div class="albums-view__header">
      <h1>专辑</h1>
      <span class="albums-view__count" v-if="albums.length">{{ albums.length }} 张专辑</span>
    </div>

    <!-- 空状态 -->
    <div v-if="!hasAlbums" class="empty-state">
      <el-icon size="48"><Folder /></el-icon>
      <p>暂无专辑</p>
      <p class="empty-sub">导入音乐后将自动生成专辑列表</p>
    </div>

    <!-- 专辑网格（虚拟滚动，每行为一个虚拟项） -->
    <div v-else ref="gridRef" class="albums-grid-measure">
      <div v-bind="containerProps" class="albums-grid-virt">
        <div v-bind="wrapperProps">
          <div
            v-for="{ data: row, index: rowIdx } in virtualList"
            :key="rowIdx"
            class="albums-grid__row"
          >
            <div
              v-for="album in row"
              :key="album.name"
              class="album-card"
              v-ripple
              @click="$router.push(`/album/${encodeURIComponent(album.name)}`)"
            >
              <div class="album-card__cover">
                <LazyCover v-if="album.cover" :src="album.cover" class="album-card__img" :thumb-size="332" />
                <div v-else class="cover-placeholder">
                  <el-icon size="36"><Folder /></el-icon>
                </div>
                <div class="cover-overlay" v-ripple @click.stop="playAlbum(album)">
                  <el-icon size="36"><VideoPlay /></el-icon>
                </div>
              </div>
              <div class="album-card__info">
                <div class="album-card__name truncate" :title="album.name">{{ album.name }}</div>
                <div class="album-card__artist truncate" :title="album.artist">{{ album.artist }}</div>
                <div class="album-card__count">{{ album.tracks.length }} 首</div>
              </div>
            </div>
            <template v-for="ph in (perRow - row.length)" :key="'ph-' + ph">
              <div class="album-card album-card--phantom" />
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'AlbumsView' })
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useVirtualList } from '@vueuse/core'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import LazyCover from '@/components/LazyCover.vue'
import { useScrollMemory } from '@/composables/useScrollMemory'

const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()

const gridRef = ref(null)
const albums = computed(() => libraryStore.albums)
const hasAlbums = computed(() => albums.value.length > 0)

// ---- 根据容器宽度实时计算每行卡片数 ----
const gridWidth = ref(0)
let _resizeObs = null
onMounted(() => {
  _resizeObs = new ResizeObserver(entries => {
    for (const e of entries) gridWidth.value = e.contentRect.width
  })
  _resizeObs.observe(gridRef.value)
})
onUnmounted(() => _resizeObs?.disconnect())

// 卡片 min-width + gap → 等价于 flex-wrap 的自动换行
const CARD_MIN = 160
const GAP = 20
const perRow = computed(() => {
  const w = gridWidth.value
  if (!w) return 4 // SSR / 首帧兜底
  return Math.max(1, Math.floor((w + GAP) / (CARD_MIN + GAP)))
})

// ---- 按 perRow 拆分为行 ----
const albumRows = computed(() => {
  const rows = []
  const list = albums.value
  for (let i = 0; i < list.length; i += perRow.value) {
    rows.push(list.slice(i, i + perRow.value))
  }
  return rows
})

// ---- 虚拟滚动 ----
const ROW_HEIGHT = 300
const { list: virtualList, containerProps, wrapperProps, scrollTo } = useVirtualList(
  albumRows,
  { itemHeight: ROW_HEIGHT, overscan: 5 }
)

// 数据变化滚回顶部
watch(() => albums.value.length, () => scrollTo(0))

// 滚动记忆（containerProps 内层才是实际滚动容器）
useScrollMemory('albums', () => gridRef.value?.querySelector('[style*="overflow"]'))

function playAlbum(album) {
  if (album.tracks.length > 0) playerStore.playAll(album.tracks)
}
</script>

<style scoped>
.albums-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.albums-view__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24px;
}
.albums-view__header h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}
.albums-view__count {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 32px;
  color: var(--text-tertiary);
}
.empty-state p {
  margin: 16px 0 0;
  font-size: 15px;
}
.empty-sub {
  font-size: 13px;
  color: var(--text-tertiary);
  opacity: 0.7;
}

/* 外层测量容器（避免 containerProps 内置 ref 冲突） */
.albums-grid-measure {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 虚拟滚动容器 */
.albums-grid-virt {
  width: 100%;
  height: 100%;
  overflow-x: hidden;
  padding: 4px;
}
/* containerProps 已设置 overflow-y: auto 作为行内样式 */
.albums-grid-virt::-webkit-scrollbar {
  width: 6px;
}
.albums-grid-virt::-webkit-scrollbar-track {
  background: transparent;
}
.albums-grid-virt::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 3px;
}
.albums-grid-virt::-webkit-scrollbar-thumb:hover {
  background: var(--scrollbar-thumb-hover);
}

/* 行 = 原专辑网格的一行 */
.albums-grid__row {
  display: flex;
  gap: 20px;
  height: 300px;
  align-items: stretch;
  overflow: hidden;
}

/* 专辑卡片 —— 保持原样式 */
.album-card {
  flex: 1 1 190px;
  min-width: 160px;
  max-width: 100%;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
}
.album-card--phantom {
  visibility: hidden;
  pointer-events: none;
  flex: 0 0 160px;
}
.album-card:hover {
  background: var(--hover-bg);
}
.album-card__cover {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}
.album-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-placeholder {
  width: 100%;
  height: 100%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}
.cover-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s;
}
.album-card:hover .cover-overlay {
  opacity: 1;
}
.album-card__info {
  min-width: 0;
}
.album-card__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}
.album-card__artist {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}
.album-card__count {
  font-size: 12px;
  color: var(--text-tertiary);
}
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
