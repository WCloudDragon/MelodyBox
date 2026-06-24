<template>
  <div class="home-view">
    <div class="home-view__header">
      <h1>欢迎回来</h1>
      <p class="subtitle">沉浸式音乐体验，从这里开始</p>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions" v-if="!hasMusic">
      <div class="welcome-card">
        <div class="welcome-card__icon">
          <el-icon size="48"><Headset /></el-icon>
        </div>
        <h2>您的音乐库为空</h2>
        <p>导入本地音乐文件，开始享受沉浸式音乐体验</p>
        <el-button type="primary" size="large" @click="handleImport" :loading="libraryStore.isLoading">
          导入本地音乐
        </el-button>
      </div>
    </div>

    <template v-else>
      <!-- 概览统计 -->
      <div class="stats-row">
        <div class="stat-card" v-ripple @click="$router.push('/library')">
          <el-icon size="22"><Headset /></el-icon>
          <div class="stat-card__value">{{ libraryStore.tracks.length }}</div>
          <div class="stat-card__label">首歌曲</div>
        </div>
        <div class="stat-card" v-ripple @click="$router.push('/library')">
          <el-icon size="22"><Folder /></el-icon>
          <div class="stat-card__value">{{ libraryStore.albums.length }}</div>
          <div class="stat-card__label">张专辑</div>
        </div>
        <div class="stat-card" v-ripple>
          <el-icon size="22"><User /></el-icon>
          <div class="stat-card__value">{{ libraryStore.artists.length }}</div>
          <div class="stat-card__label">位歌手</div>
        </div>
        <div class="stat-card" v-ripple>
          <el-icon size="22"><Timer /></el-icon>
          <div class="stat-card__value">{{ formatTotalDuration(libraryStore.totalDuration) }}</div>
          <div class="stat-card__label">总时长</div>
        </div>
      </div>

      <!-- 最近播放 / 推荐 -->
      <section class="section">
        <div class="section__header">
          <h3>音乐库</h3>
          <el-button text type="primary" @click="$router.push('/library')">查看全部</el-button>
        </div>
        <div class="tracks-grid">
          <MusicCard
            v-for="track in recentTracks"
            :key="track.path"
            :track="track"
            @play="playTrack(track)"
            @click="playTrack(track)"
          />
        </div>
      </section>

      <!-- 专辑 -->
      <section class="section" v-if="libraryStore.albums.length > 0">
        <div class="section__header">
          <h3>专辑</h3>
        </div>
        <div class="tracks-grid">
          <div
            v-for="album in recentAlbums"
            :key="album.name"
            class="album-card"
            v-ripple
            @click="$router.push(`/album/${encodeURIComponent(album.name)}`)">
            <div class="album-card__cover">
              <img v-if="album.cover" :src="album.cover" />
              <div v-else class="cover-placeholder">
                <el-icon size="28"><Folder /></el-icon>
              </div>
            </div>
            <div class="album-card__name truncate">{{ album.name }}</div>
            <div class="album-card__artist truncate">{{ album.artist }}</div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
defineOptions({ name: 'HomeView' })
import { computed, watch, onBeforeUnmount } from 'vue'
import { useLibraryStore } from '@/stores/library'
import { usePlayerStore } from '@/stores/player'
import { formatTotalDuration } from '@/utils/format'
import { showScanNotify, updateScanNotify, closeScanNotify, clearScanNotify } from '@/utils/scanNotify'
import MusicCard from '@/components/music/MusicCard.vue'
import { useScrollMemory } from '@/composables/useScrollMemory'

const libraryStore = useLibraryStore()
const playerStore = usePlayerStore()

// 扫描进度通知
watch(() => libraryStore.isScanning, (scanning) => {
  if (scanning) showScanNotify()
})
watch(() => libraryStore.scanProgress, (p) => {
  if (!libraryStore.isScanning) return
  if (p.total > 0) updateScanNotify(p.current, p.total, p.path)
  if (!p.scanning && p.total > 0) {
    closeScanNotify(p.total, () => libraryStore.loadFromApi())
  }
})
onBeforeUnmount(clearScanNotify)

useScrollMemory('home', () => document.querySelector('.main-content'))

const hasMusic = computed(() => libraryStore.tracks.length > 0)
const recentTracks = computed(() => libraryStore.tracks.slice(0, 12))
const recentAlbums = computed(() => libraryStore.albums.slice(0, 8))

async function handleImport() {
  if (window.electronAPI) {
    await libraryStore.selectAndScan()
  } else {
    // 浏览器模式：提示
    alert('请使用 Electron 桌面版以获得完整功能。\n\n当前浏览器模式仅支持示例体验。')
  }
}

function playTrack(track) {
  const idx = libraryStore.tracks.findIndex(t => t.path === track.path)
  if (idx !== -1) {
    playerStore.playAll(libraryStore.tracks, idx)
  }
}
</script>

<style scoped>
.home-view { padding-bottom: 120px; }
.home-view__header { margin-bottom: 32px; }
.home-view__header h1 { font-size: 28px; font-weight: 700; margin: 0 0 4px; }
.subtitle { font-size: 14px; color: var(--text-tertiary); margin: 0; }

.welcome-card {
  text-align: center; padding: 64px 32px;
  background: var(--bg-secondary); border-radius: 16px;
  border: 1px dashed var(--border-color);
}
.welcome-card__icon { color: var(--text-tertiary); margin-bottom: 16px; }
.welcome-card h2 { font-size: 20px; margin-bottom: 8px; }
.welcome-card p { color: var(--text-tertiary); margin-bottom: 24px; font-size: 14px; }

.stats-row { display: flex; gap: 16px; margin-bottom: 36px; }
.stat-card {
  flex: 1; background: var(--bg-secondary);
  border-radius: 12px; padding: 20px; text-align: center;
  cursor: pointer; transition: border-color 0.2s, background 0.2s;
  border: 1px solid transparent;
}
.stat-card:hover { border-color: var(--border-color); background: var(--bg-tertiary); }
.stat-card .el-icon { color: var(--accent-color); margin-bottom: 8px; }
.stat-card__value { font-size: 22px; font-weight: 700; }
.stat-card__label { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }

.section { margin-bottom: 36px; }
.section__header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.section__header h3 { font-size: 18px; font-weight: 600; margin: 0; }

.tracks-grid { display: flex; flex-wrap: wrap; gap: 4px; }

/* 专辑卡片 */
.album-card {
  width: 170px; cursor: pointer; border-radius: 10px;
  padding: 12px; transition: background 0.2s;
}
.album-card:hover { background: var(--hover-bg); }
.album-card__cover {
  width: 100%; aspect-ratio: 1; border-radius: 8px;
  overflow: hidden; margin-bottom: 10px;
}
.album-card__cover img { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder {
  width: 100%; height: 100%; background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.album-card__name { font-size: 13px; font-weight: 500; margin-bottom: 2px; }
.album-card__artist { font-size: 12px; color: var(--text-tertiary); }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
