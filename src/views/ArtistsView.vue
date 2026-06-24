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

    <!-- 歌手网格 -->
    <div v-else class="artists-grid">
      <div
        v-for="artist in artists"
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
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'ArtistsView' })
import { computed } from 'vue'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import LazyCover from '@/components/LazyCover.vue'
import { useScrollMemory } from '@/composables/useScrollMemory'

const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()

useScrollMemory('artists', () => document.querySelector('.artists-grid'))
const artists = computed(() => libraryStore.artists)
const hasArtists = computed(() => artists.value.length > 0)

function playArtist(artist) {
  if (artist.tracks.length > 0) {
    playerStore.playAll(artist.tracks)
  }
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

/* 歌手网格 */
.artists-grid {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  overflow-y: auto;
  min-height: 0;
  padding: 4px;
}

.artists-grid::-webkit-scrollbar {
  width: 6px;
}
.artists-grid::-webkit-scrollbar-track {
  background: transparent;
}
.artists-grid::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 3px;
}
.artists-grid::-webkit-scrollbar-thumb:hover {
  background: var(--scrollbar-thumb-hover);
}

/* 歌手卡片 */
.artist-card {
  flex: 1 1 180px;
  min-width: 150px;
  max-width: 100%;
  padding: 16px 12px;
  border-radius: 10px;
  text-align: center;
  cursor: pointer;
  transition: background 0.2s;
  content-visibility: auto;
  contain-intrinsic-size: auto 260px;
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
