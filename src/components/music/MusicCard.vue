<template>
  <div class="music-card" :data-track-path="track.path" v-ripple @dblclick="$emit('play')">
    <div class="music-card__cover" v-ripple @click="$emit('click')">
      <LazyCover v-if="track.cover" :src="track.cover" class="music-card__img" :thumb-size="292" />
      <div v-else class="cover-placeholder">
        <el-icon size="32"><Headset /></el-icon>
      </div>
      <div class="cover-overlay" v-ripple @click.stop="$emit('play')">
        <el-icon size="32"><VideoPlay /></el-icon>
      </div>

      <!-- 来源标签区域（右上角） -->
      <div class="source-tags">
        <!-- 纯本地：硬盘图标 -->
        <span v-if="isLocalOnly" class="source-tag source-tag--local" title="本地歌曲">
          <el-icon size="12"><FolderOpened /></el-icon>
        </span>

        <!-- 云端副本存在（元数据一致）：云朵 -->
        <span v-if="hasCloudCopy && !hasMetaDiff" class="source-tag source-tag--synced" title="该歌曲云端也有">
          <el-icon size="12"><Cloudy /></el-icon>
        </span>

        <!-- 云端副本存在（元数据不一致）：云朵 + 对比 -->
        <span v-if="hasCloudCopy && hasMetaDiff" class="source-tag-group" @click.stop>
          <span class="source-tag source-tag--synced" title="该歌曲云端也有">
            <el-icon size="12"><Cloudy /></el-icon>
          </span>
          <span class="source-tag source-tag--diff" title="云端元数据不一致">
            <el-icon size="12"><WarningFilled /></el-icon>
          </span>
          <!-- tooltip：云端元数据详情 -->
          <div class="cloud-meta-tooltip">
            <div class="cloud-meta-tooltip__title">云端版本元数据</div>
            <div v-for="(v, k) in diffFields" :key="k" class="cloud-meta-tooltip__item">
              <span class="cloud-meta-tooltip__label">{{ metaLabels[k] }}</span>
              <span class="cloud-meta-tooltip__value">{{ v }}</span>
            </div>
          </div>
        </span>

        <!-- 纯云端：蓝色"云端"标签 -->
        <span v-if="track.source === 'cloud'" class="source-tag source-tag--cloud" title="云端歌曲">
          <el-icon size="12"><Cloudy /></el-icon>
          <span>云端</span>
        </span>

        <!-- 本地已有但云端已下架：灰云朵 -->
        <span v-if="hasOfflineCloudCopy" class="source-tag source-tag--offline" title="云端版本已下架">
          <el-icon size="12"><Cloudy /></el-icon>
        </span>
      </div>
    </div>
    <div class="music-card__info">
      <div class="music-card__title truncate" :title="track.title">{{ track.title }}</div>
      <div class="music-card__artist truncate" :title="track.artist">{{ track.artist.split('/').map(s => s.trim()).join(' / ') }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LazyCover from '@/components/LazyCover.vue'
import { Cloudy, FolderOpened, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  track: { type: Object, required: true }
})

defineEmits(['click', 'play'])

const metaLabels = { title: '标题', artist: '艺术家', album: '专辑', genre: '流派' }

// 纯本地（无云端副本，无下架云端）
const isLocalOnly = computed(() =>
  props.track.source === 'local' && !props.track.cloud_meta && !props.track.cloud_offline
)

// 有云端副本（在线）
const hasCloudCopy = computed(() =>
  props.track.source === 'local' && props.track.cloud_meta
)

// 有云端副本但已下架
const hasOfflineCloudCopy = computed(() =>
  props.track.source === 'local' && !props.track.cloud_meta && props.track.cloud_offline
)

// 元数据是否不一致
const hasMetaDiff = computed(() => {
  if (!props.track.cloud_meta) return false
  const local = props.track
  const cloud = props.track.cloud_meta
  const fields = ['title', 'artist', 'album', 'genre']
  return fields.some(k => {
    const a = (local[k] || '').trim()
    const b = (cloud[k] || '').trim()
    return a.toLowerCase() !== b.toLowerCase()
  })
})

// 差异字段（仅返回不一致的）
const diffFields = computed(() => {
  if (!hasMetaDiff.value || !props.track.cloud_meta) return {}
  const local = props.track
  const cloud = props.track.cloud_meta
  const result = {}
  const fields = ['title', 'artist', 'album', 'genre']
  fields.forEach(k => {
    const a = (local[k] || '').trim()
    const b = (cloud[k] || '').trim()
    if (a.toLowerCase() !== b.toLowerCase() && b) {
      result[k] = b
    }
  })
  return result
})
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

/* 来源标签区域 */
.source-tags {
  position: absolute;
  top: 4px;
  right: 4px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  z-index: 2;
  align-items: flex-end;
}

.source-tag-group {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-items: flex-end;
}

.source-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  backdrop-filter: blur(4px);
  white-space: nowrap;
}

.source-tag--local {
  background: rgba(0, 0, 0, 0.45);
  color: #d4d4d8;
}

.source-tag--synced {
  background: rgba(96, 165, 250, 0.3);
  color: #93c5fd;
}

.source-tag--diff {
  background: rgba(251, 191, 36, 0.45);
  color: #fbbf24;
  cursor: pointer;
}

.source-tag--cloud {
  background: rgba(64, 158, 255, 0.85);
  color: #fff;
}

.source-tag--offline {
  background: rgba(113, 113, 122, 0.4);
  color: #a1a1aa;
}

/* 云端元数据 tooltip */
.cloud-meta-tooltip {
  display: none;
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  min-width: 180px;
  max-width: 240px;
  padding: 10px 12px;
  background: #1e1e2e;
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  z-index: 10;
  pointer-events: none;
}

.source-tag--diff:hover + .cloud-meta-tooltip,
.source-tag-group:hover .cloud-meta-tooltip {
  display: block;
}

.cloud-meta-tooltip__title {
  font-size: 11px;
  font-weight: 600;
  color: #a1a1aa;
  margin-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 4px;
}

.cloud-meta-tooltip__item {
  display: flex;
  gap: 8px;
  margin-bottom: 3px;
  font-size: 11px;
  line-height: 1.5;
}

.cloud-meta-tooltip__label {
  color: #71717a;
  flex-shrink: 0;
  min-width: 32px;
}

.cloud-meta-tooltip__value {
  color: #fbbf24;
  word-break: break-all;
}
</style>
