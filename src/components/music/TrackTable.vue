<template>
  <div class="track-table">
    <!-- 表头 -->
    <div v-if="showHeader" class="track-table__header">
      <span class="col-index">#</span>
      <span class="col-title">歌曲</span>
      <span v-if="showAlbum" class="col-album">专辑</span>
      <span class="col-quality">音质</span>
      <span class="col-time">时长</span>
      <span v-if="multiSelectMode" class="col-action"></span>
    </div>

    <!-- 列表体 -->
    <div class="track-table__body" ref="bodyRef">
      <div v-if="!tracks.length" class="track-table__empty">暂无歌曲</div>
      <div
        v-for="(track, index) in tracks"
        :key="track.path || index"
        class="track-row"
        v-ripple
        :class="{
          'track-row--playing': currentPath === track.path,
          'track-row--ctx-active': contextTarget === track.path,
        }"
        @dblclick="$emit('play', track)"
        @contextmenu.prevent="$emit('contextmenu', $event, track)"
      >
        <span class="col-index">
          <span class="index-num">{{ index + 1 }}</span>
          <el-icon class="play-icon" v-ripple size="16" @click.stop="$emit('play', track)">
            <VideoPlay />
          </el-icon>
        </span>
        <span class="col-title">
          <LazyCover v-if="track.cover" :src="track.cover" class="row-cover" :thumb-size="72" />
          <div v-else class="row-cover row-cover--empty">
            <el-icon size="14"><Headset /></el-icon>
          </div>
          <div class="col-title__text">
            <span class="col-title__name">{{ track.title }}</span>
            <span v-if="showArtist" class="col-title__artist">
              {{ (track.artist || '').split('/').map(s => s.trim()).join(' / ') }}
            </span>
            <span v-if="track.reason" class="col-title__reason">{{ track.reason }}</span>
          </div>
        </span>
        <span v-if="showAlbum" class="col-album">{{ track.album || '' }}</span>
        <span class="col-quality">
          <span v-if="track.quality" class="quality-tag" :class="qualityClass(track.quality)">
            {{ track.quality }}
          </span>
        </span>
        <span class="col-time">{{ formatDuration(track.duration) }}</span>
        <span v-if="multiSelectMode" class="col-action">
          <el-checkbox
            :model-value="selectedPaths?.has(track.path)"
            @change="$emit('toggleSelect', track)"
          />
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { formatDuration, qualityClass } from '@/utils/format'
import LazyCover from '@/components/LazyCover.vue'

defineOptions({ name: 'TrackTable' })

const props = defineProps({
  tracks: { type: Array, required: true },
  currentPath: { type: String, default: null },
  contextTarget: { type: String, default: null },
  showAlbum: { type: Boolean, default: true },
  showHeader: { type: Boolean, default: true },
  showArtist: { type: Boolean, default: true },
  multiSelectMode: { type: Boolean, default: false },
  selectedPaths: { type: Set, default: null },
})

defineEmits(['play', 'contextmenu', 'toggleSelect'])

const bodyRef = ref(null)

function scrollToTop() {
  if (bodyRef.value) bodyRef.value.scrollTop = 0
}

defineExpose({ scrollToTop, bodyRef })
</script>

<style scoped>
.track-table {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.track-table__header {
  display: grid;
  grid-template-columns: 40px 1fr 52px 60px;
  align-items: center;
  padding: 10px 12px;
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.track-table__header:has(.col-album) {
  grid-template-columns: 40px 1fr 1fr 52px 60px;
}
.track-table__header:has(.col-action) {
  grid-template-columns: 40px 1fr 1fr 52px 60px 40px;
}

.track-table__body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.track-table__body::-webkit-scrollbar { width: 6px; }
.track-table__body::-webkit-scrollbar-track { background: transparent; }
.track-table__body::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
.track-table__body::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

.track-table__empty {
  padding: 40px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 14px;
}

.track-row {
  display: grid;
  grid-template-columns: 40px 1fr 52px 60px;
  align-items: center;
  padding: 0 12px;
  height: 64px;
  border-radius: 6px;
  transition: background 0.15s;
  cursor: default;
  content-visibility: auto;
  contain-intrinsic-size: 64px;
}
/* 当有专辑列时 */
.track-row:has(.col-album) {
  grid-template-columns: 40px 1fr 1fr 52px 60px;
}
/* 当有多选列时 */
.track-row:has(.col-action) {
  grid-template-columns: 40px 1fr 1fr 52px 60px 40px;
}

.track-row:hover,
.track-row--ctx-active {
  background: var(--hover-bg);
}
.track-row--playing {
  background: var(--accent-bg);
}
.track-row--playing .col-title__name {
  color: var(--accent-color);
}

/* 序号列 */
.col-index {
  width: 40px;
  text-align: center;
  position: relative;
}
.col-index .index-num {
  font-size: 13px;
  color: var(--text-tertiary);
  transition: opacity 0.12s;
}
.col-index .play-icon {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  cursor: pointer;
  color: var(--accent-color);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.12s;
}
.track-row:hover .col-index .index-num,
.track-row--ctx-active .col-index .index-num {
  opacity: 0;
}
.track-row:hover .col-index .play-icon,
.track-row--ctx-active .col-index .play-icon {
  opacity: 1;
  pointer-events: auto;
}

/* 歌曲列 */
.col-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  overflow: hidden;
}
.col-title__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
.col-title__name {
  font-size: 15px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-title__artist {
  font-size: 12px;
  line-height: 1.3;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-title__reason {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-cover {
  width: 44px;
  height: 44px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
}
.row-cover--empty {
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}

/* 专辑列 */
.col-album {
  font-size: 14px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 音质列 */
.col-quality {
  width: 52px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

/* 时长列 */
.col-time {
  width: 60px;
  text-align: right;
  font-size: 13px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* 多选列 */
.col-action {
  width: 40px;
  text-align: center;
}
</style>
