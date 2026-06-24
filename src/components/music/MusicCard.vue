<template>
  <div class="music-card" :data-track-path="track.path" v-ripple @dblclick="$emit('play')">
    <div class="music-card__cover" @click="$emit('click')">
      <LazyCover v-if="track.cover" :src="track.cover" class="music-card__img" :thumb-size="292" />
      <div v-else class="cover-placeholder">
        <el-icon size="32"><Headset /></el-icon>
      </div>
      <div class="cover-overlay" @click.stop="$emit('play')">
        <el-icon size="32"><VideoPlay /></el-icon>
      </div>
    </div>
    <div class="music-card__info">
      <div class="music-card__title truncate" :title="track.title">{{ track.title }}</div>
      <div class="music-card__artist truncate" :title="track.artist">{{ track.artist.split('/').map(s => s.trim()).join(' / ') }}</div>
    </div>
  </div>
</template>

<script setup>
import LazyCover from '@/components/LazyCover.vue'
defineProps({
  track: { type: Object, required: true }
})
defineEmits(['click', 'play'])
</script>

<style scoped>
.music-card {
  width: 170px;
  cursor: pointer;
  border-radius: 10px;
  padding: 12px;
  transition: background 0.2s;
  content-visibility: auto;
  contain-intrinsic-size: 200px;
}
.music-card:hover { background: var(--hover-bg); }
.music-card__cover {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}
.music-card__cover img {
  width: 100%; height: 100%;
  object-fit: cover;
}
.cover-placeholder {
  width: 100%; height: 100%;
  background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.cover-overlay {
  position: absolute; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s;
}
.music-card__cover:hover .cover-overlay { opacity: 1; }
.music-card__title { font-size: 13px; font-weight: 500; margin-bottom: 2px; }
.music-card__artist { font-size: 12px; color: var(--text-tertiary); }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
