<template>
  <div class="track-table">
    <!-- 列表体（embedded 模式不自建滚动容器，交由外层整页滚动）；无表头，与列表页一致 -->
    <div class="track-table__body" :class="{ 'track-table__body--embedded': embedded }" ref="bodyRef">
      <div v-if="!tracks.length" class="track-table__empty">暂无歌曲</div>
      <div
        v-for="(track, index) in tracks"
        :key="track.path || index"
        class="track-row"
        v-ripple
        :style="{ gridTemplateColumns: gridTemplate }"
        :class="{
          playing: currentPath === track.path,
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
            <!-- 结构与音乐库页一致：row 负责单行截断，artist 只负责字号/行高 -->
            <span v-if="showArtist" class="col-title__artist-row">
              <template v-for="(name, ai) in (track.artist || '').split('/').map(s => s.trim()).filter(Boolean)" :key="ai">
                <router-link :to="`/artist/${encodeURIComponent(name)}`" class="link col-title__artist">{{ name }}</router-link>
                <span v-if="ai < (track.artist || '').split('/').map(s => s.trim()).filter(Boolean).length - 1" class="col-title__sep"> / </span>
              </template>
            </span>
          </div>
        </span>
        <span v-if="showAlbum" class="col-album">
          <router-link v-if="track.album" :to="`/album/${encodeURIComponent(track.album)}`" class="link">{{ track.album }}</router-link>
        </span>
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
import { ref, computed } from 'vue'
import { formatDuration, qualityClass } from '@/utils/format'
import LazyCover from '@/components/LazyCover.vue'

defineOptions({ name: 'TrackTable' })

const props = defineProps({
  tracks: { type: Array, required: true },
  currentPath: { type: String, default: null },
  contextTarget: { type: String, default: null },
  showAlbum: { type: Boolean, default: true },
  showArtist: { type: Boolean, default: true },
  multiSelectMode: { type: Boolean, default: false },
  // 嵌入模式：列表体不自建滚动容器（外层整页滚动），并用标题渐显时保持自然高度
  embedded: { type: Boolean, default: false },
  selectedPaths: { type: Set, default: null },
})

defineEmits(['play', 'contextmenu', 'toggleSelect'])

const bodyRef = ref(null)

// 列模板与列表页 track-row 同一套规格：序号/歌曲/（专辑）/音质/时长/（多选）
const gridTemplate = computed(() => {
  const cols = ['40px', '1fr']
  if (props.showAlbum) cols.push('1fr')
  cols.push('52px', '60px')
  if (props.multiSelectMode) cols.push('40px')
  return cols.join(' ')
})

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

.track-table__body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.track-table__body--embedded {
  flex: none;
  overflow: visible;
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
  align-items: center;
  /* 与音乐库页同规格：内容落 --page-pad-x 基准线 */
  padding: 0 var(--page-pad-x, 12px);
  height: 64px;
  border-radius: 6px;
  transition: background 0.15s;
  cursor: default;
  content-visibility: auto;
  contain-intrinsic-size: 64px;
}

.track-row:hover,
.track-row--ctx-active {
  background: var(--hover-bg);
}
.track-row.playing {
  background: var(--accent-bg);
}
.track-row.playing .col-title__name {
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

/* 歌曲列：样式与音乐库页逐字一致 */
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
.col-title__artist-row {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.col-title__artist {
  font-size: 12px;
  line-height: 1.3;
}
.col-title__sep { font-size: 12px; color: var(--text-tertiary); }
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
.link { color: var(--text-secondary); text-decoration: none; }
.link:hover { color: var(--accent-color); text-decoration: underline; }

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
