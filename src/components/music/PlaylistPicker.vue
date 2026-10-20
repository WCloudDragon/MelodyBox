<template>
  <!-- 添加到歌单：歌单多选列表（作为 ModalDialog 自定义 body 渲染） -->
  <div class="pl-picker">
    <div v-for="pl in playlists" :key="pl.id" class="pl-picker__wrap">
      <AppCheckbox
        class="pl-picker__row"
        :model-value="isFull(pl) || checked.has(pl.id)"
        :disabled="isFull(pl)"
        @update:model-value="v => toggle(pl.id, v)"
      >
        <span class="pl-picker__cover">
          <LazyCover v-if="pl.cover_url" :src="pl.cover_url" :thumb-size="72" />
          <span v-else class="pl-picker__cover-empty"><el-icon size="12"><Headset /></el-icon></span>
        </span>
        <span class="pl-picker__name">
          <span class="pl-picker__name-text">{{ pl.name }}</span>
          <el-icon v-if="pl.is_system" class="pl-picker__star" size="12"><StarFilled /></el-icon>
        </span>
        <!-- 状态标签位于数量左侧；歌曲数量常驻显示 -->
        <span v-if="isFull(pl)" class="pl-picker__tag pl-picker__tag--full">{{ total > 1 ? '全部已存在' : '已存在' }}</span>
        <span v-else-if="contained(pl) > 0" class="pl-picker__tag pl-picker__tag--part">已含 {{ contained(pl) }}/{{ total }} 首</span>
        <span class="pl-picker__count">{{ stat(pl).total }} 首</span>
      </AppCheckbox>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Headset, StarFilled } from '@element-plus/icons-vue'
import AppCheckbox from '@/components/AppCheckbox.vue'
import LazyCover from '@/components/LazyCover.vue'

const props = defineProps({
  playlists: { type: Array, default: () => [] },
  // playlist_id → { total: 歌单歌曲总数(含失效条目), contained: 本次选中歌曲已在该歌单的数量 }
  status: { type: Object, default: () => ({}) },
  total: { type: Number, default: 1 }, // 本次待添加的歌曲数
})
const emit = defineEmits(['update:value', 'update:valid'])

const checked = ref(new Set())

function stat(pl) {
  return props.status[pl.id] || { total: pl.track_count ?? 0, contained: 0 }
}
function contained(pl) {
  return stat(pl).contained || 0
}
// 选中歌曲全部已在该歌单 → 勾选并灰显，不可再添加
function isFull(pl) {
  return contained(pl) >= props.total
}

function toggle(id, on) {
  const next = new Set(checked.value)
  if (on) next.add(id)
  else next.delete(id)
  checked.value = next
  emit('update:value', [...next])
  emit('update:valid', next.size > 0)
}
</script>

<style scoped>
.pl-picker {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 264px;
  overflow-y: auto;
  margin-bottom: 14px;
  padding: 2px;
}

/* 双类选择器抬高优先级，覆盖 AppCheckbox 根元素的 flex-start 对齐 */
.pl-picker__wrap .pl-picker__row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 8px;
  border-radius: 8px;
  transition: background 0.15s;
}
.pl-picker__wrap .pl-picker__row:hover {
  background: var(--hover-bg);
}
/* 行内垂直居中时不需要为文本行预留的顶部偏移 */
.pl-picker__row :deep(.app-checkbox__box) {
  margin-top: 0;
}

.pl-picker__cover {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  display: block;
}
.pl-picker__cover-empty {
  width: 100%;
  height: 100%;
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pl-picker__name {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}
.pl-picker__name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pl-picker__row:hover .pl-picker__name {
  color: var(--text-primary);
}

.pl-picker__star {
  color: var(--accent-color);
  flex-shrink: 0;
}
.pl-picker__count {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.pl-picker__tag {
  flex-shrink: 0;
  font-size: 10px;
  line-height: 1;
  padding: 3px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
.pl-picker__tag--full {
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
}
.pl-picker__tag--part {
  color: var(--accent-color);
  background: var(--accent-bg);
}
</style>
