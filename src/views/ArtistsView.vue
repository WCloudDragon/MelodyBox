<template>
  <div class="artists-view">
    <div class="artists-view__header">
      <h1>艺术家</h1>
      <span class="artists-view__count" v-if="artists.length">{{ artists.length }} 位歌手</span>
    </div>

    <!-- 空状态 -->
    <div v-if="!hasArtists" class="empty-state">
      <el-icon size="48"><User /></el-icon>
      <p>暂无歌手</p>
      <p class="empty-sub">导入音乐后将自动生成歌手列表</p>
    </div>

    <!-- 歌手网格（虚拟滚动） -->
    <div v-else ref="gridRef" class="artists-grid-measure">
      <div v-bind="containerProps" class="artists-grid-virt">
        <div v-bind="wrapperProps">
          <div
            v-for="{ data: row, index: rowIdx } in virtualList"
            :key="rowIdx"
            class="artists-grid__row"
          >
            <div
              v-for="artist in row"
              :key="artist.name"
              class="artist-card"
              v-ripple
              @click="$router.push(`/artist/${encodeURIComponent(artist.name)}`)"
            >
              <div class="artist-card__avatar">
                <LazyCover v-if="artist.tracks[0]?.cover" :src="artist.tracks[0].cover" class="artist-card__img" :thumb-size="280" />
                <div v-else class="avatar-placeholder">
                  <el-icon size="40"><User /></el-icon>
                </div>
                <div class="avatar-overlay" @click.stop="playArtist(artist)">
                  <el-icon size="36"><VideoPlay /></el-icon>
                </div>
              </div>
              <div class="artist-card__info">
                <div class="artist-card__name truncate" :title="artist.name">{{ artist.name }}</div>
                <div class="artist-card__count">{{ artist.tracks.length }} 首歌曲</div>
              </div>
            </div>
            <template v-for="ph in (perRow - row.length)" :key="'ph-' + ph">
              <div class="artist-card artist-card--phantom" />
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'ArtistsView' })
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useVirtualList } from '@vueuse/core'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import LazyCover from '@/components/LazyCover.vue'
import { useScrollMemory } from '@/composables/useScrollMemory'

const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()

const gridRef = ref(null)
const artists = computed(() => libraryStore.artists)
const hasArtists = computed(() => artists.value.length > 0)

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

const CARD_MIN = 150
const GAP = 20
const perRow = computed(() => {
  const w = gridWidth.value
  if (!w) return 5
  return Math.max(1, Math.floor((w + GAP) / (CARD_MIN + GAP)))
})

// ---- 按 perRow 拆分为行 ----
const artistRows = computed(() => {
  const rows = []
  const list = artists.value
  for (let i = 0; i < list.length; i += perRow.value) {
    rows.push(list.slice(i, i + perRow.value))
  }
  return rows
})

// ---- 虚拟滚动 ----
const ROW_HEIGHT = 260
const { list: virtualList, containerProps, wrapperProps, scrollTo } = useVirtualList(
  artistRows,
  { itemHeight: ROW_HEIGHT, overscan: 5 }
)

watch(() => artists.value.length, () => scrollTo(0))

// 滚动记忆（containerProps 内层才是实际滚动容器）
useScrollMemory('artists', () => gridRef.value?.querySelector('[style*="overflow"]'))

function playArtist(artist) {
  if (artist.tracks.length > 0) playerStore.playAll(artist.tracks)
}
</script>

<style scoped>
.artists-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.artists-view__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24px;
}
.artists-view__header h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}
.artists-view__count {
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
.artists-grid-measure {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 虚拟滚动容器 */
.artists-grid-virt {
  width: 100%;
  height: 100%;
  overflow-x: hidden;
  padding: 4px;
}
/* containerProps 已设置 overflow-y: auto 作为行内样式 */
.artists-grid-virt::-webkit-scrollbar {
  width: 6px;
}
.artists-grid-virt::-webkit-scrollbar-track {
  background: transparent;
}
.artists-grid-virt::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 3px;
}
.artists-grid-virt::-webkit-scrollbar-thumb:hover {
  background: var(--scrollbar-thumb-hover);
}

/* 行容器 */
.artists-grid__row {
  display: flex;
  gap: 20px;
  height: 260px;
  align-items: stretch;
  overflow: hidden;
}

/* 歌手卡片 —— 保持原样式 */
.artist-card {
  flex: 1 1 180px;
  min-width: 150px;
  max-width: 100%;
  padding: 16px 12px;
  border-radius: 10px;
  text-align: center;
  cursor: pointer;
  transition: background 0.2s;
}
.artist-card--phantom {
  visibility: hidden;
  pointer-events: none;
  flex: 0 0 150px;
}
.artist-card:hover {
  background: var(--hover-bg);
}
.artist-card__avatar {
  position: relative;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  overflow: hidden;
  margin: 0 auto;
  aspect-ratio: 1;
  filter: drop-shadow(0 4px 8px rgba(0,0,0,0.2));
}
.artist-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-placeholder {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}
.avatar-overlay {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s;
}
.artist-card:hover .avatar-overlay {
  opacity: 1;
}
.artist-card__info {
  margin-top: 12px;
}
.artist-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artist-card__count {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
