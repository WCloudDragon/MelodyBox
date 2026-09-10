<template>
  <div class="list-page-header" ref="headerEl">
    <h1 class="list-page-header__title">{{ title }}</h1>
    <span v-if="count != null" class="list-page-header__count">{{ count }}</span>
    <div class="list-page-header__spacer"></div>

    <!-- 页面自定义右侧操作（导入/刷新/播放全部等） -->
    <slot />

    <!-- 播放模式：左键循环切换，右键弹菜单 -->
    <button
      v-if="showPlayMode"
      class="lph-btn lph-btn--playmode"
      :title="playModeLabel"
      @click="player.togglePlayMode()"
      @contextmenu.prevent.stop="openModeMenu($event)"
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M2 3h2v10H2V3zm4 0h8v2H6V3zm0 4h6v2H6V7zm0 4h8v2H6v-2z"/></svg>
      <span>{{ playModeLabel }}</span>
    </button>

    <!-- 排序 -->
    <button v-if="showSort" class="lph-btn" :class="{ active: sortOpen }" title="排序" @click.stop="sortOpen = !sortOpen">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2v9H2l3 3 3-3H6V2H4zm8 0h-2v12h-2l3 3 3-3h-2V2z"/></svg>
    </button>

    <!-- 筛选 -->
    <button v-if="showFilter" class="lph-btn" :class="{ active: filterOpen }" title="筛选" @click.stop="filterOpen = !filterOpen">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M1 2h14l-5.5 7v4.5L6.5 14V9L1 2z"/></svg>
    </button>

    <!-- 多选 -->
    <button v-if="showMultiSelect" class="lph-btn" :class="{ active: multiSelectActive }" :title="multiSelectActive ? '退出多选' : '多选'" @click="$emit('toggleMultiSelect')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3l1.5 1.5L7 1.5"/><rect x="2" y="5" width="11" height="11" rx="2"/></svg>
    </button>

    <!-- 视图切换 -->
    <button v-if="showViewSwitch" class="lph-btn" :title="viewMode === 'grid' ? '列表视图' : '网格视图'" @click="$emit('viewChange', viewMode === 'grid' ? 'list' : 'grid')">
      <svg v-if="viewMode === 'grid'" width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M2 2h5v5H2V2zm7 0h5v5H9V2zM2 9h5v5H2V9zm7 0h5v5H9V9z"/></svg>
      <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M2 3h12v1H2V3zm0 5h12v1H2V8zm0 5h12v1H2v-1z"/></svg>
    </button>

    <!-- 搜索（点击展开输入框） -->
    <button v-if="showSearch && !searchOpen" class="lph-btn" title="搜索" @click="searchOpen = true">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
    </button>
    <div v-else-if="showSearch && searchOpen" class="lph-search">
      <input
        ref="searchInput"
        v-model="searchValueLocal"
        type="text"
        placeholder="搜索..."
        @keydown.esc="closeSearch"
      />
      <button class="lph-search__close" title="关闭" @click="closeSearch">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><path d="M9.5 2.5L2.5 9.5M2.5 2.5l7 7" stroke="currentColor" stroke-width="1.4"/></svg>
      </button>
    </div>

    <!-- 排序面板 -->
    <div v-if="sortOpen" class="lph-panel" @click.stop>
      <div class="lph-panel__title">排序</div>
      <button v-for="opt in sortOptions" :key="opt.value" class="lph-panel__item" :class="{ active: sortKey === opt.value }" @click="chooseSort(opt.value)">
        <span>{{ opt.label }}</span>
        <span v-if="sortKey === opt.value" class="lph-panel__arrow">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
      </button>
      <div class="lph-panel__divider"></div>
      <div class="lph-panel__row">
        <button class="lph-panel__item lph-panel__dir" :class="{ active: sortOrder === 'asc' }" @click="setSortOrder('asc')">升序</button>
        <button class="lph-panel__item lph-panel__dir" :class="{ active: sortOrder === 'desc' }" @click="setSortOrder('desc')">降序</button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <div v-if="filterOpen" class="lph-panel lph-panel--filter" @click.stop>
      <div v-for="group in filterGroups" :key="group.key" class="lph-panel__group">
        <div class="lph-panel__title">{{ group.label }}</div>
        <div class="lph-panel__options">
          <button
            v-for="opt in group.options"
            :key="opt.value"
            class="lph-panel__item lph-panel__opt"
            :class="{ active: filterValues[group.key] === opt.value }"
            @click="chooseFilter(group.key, opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- 播放模式二级菜单 -->
    <Teleport to="body">
      <Transition name="lph-menu">
        <div v-if="modeMenu.visible" class="lph-mode-menu" :style="{ left: modeMenu.x + 'px', top: modeMenu.y + 'px' }" @click.stop>
          <div class="lph-panel__title">播放模式</div>
          <button v-for="m in modeOptions" :key="m.value" class="lph-panel__item" :class="{ active: playMode === m.value }" @click="setPlayMode(m.value)">{{ m.label }}</button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { usePlayerStore } from '@/stores/player'

const props = defineProps({
  title: { type: String, required: true },
  count: { type: [String, Number], default: null },
  showPlayMode: { type: Boolean, default: true },
  showSearch: { type: Boolean, default: false },
  showSort: { type: Boolean, default: false },
  showFilter: { type: Boolean, default: false },
  showMultiSelect: { type: Boolean, default: false },
  multiSelectActive: { type: Boolean, default: false },
  showViewSwitch: { type: Boolean, default: false },
  viewMode: { type: String, default: 'list' },
  sortOptions: { type: Array, default: () => [] },
  sortKey: { type: String, default: '' },
  sortOrder: { type: String, default: 'asc' },
  filterGroups: { type: Array, default: () => [] },
  filterValues: { type: Object, default: () => ({}) },
  searchValue: { type: String, default: '' }
})
const emit = defineEmits(['sort', 'filter', 'viewChange', 'toggleMultiSelect', 'update:searchValue'])

const player = usePlayerStore()
const { playMode } = storeToRefs(player)

const searchOpen = ref(false)
const sortOpen = ref(false)
const filterOpen = ref(false)
const modeMenu = ref({ visible: false, x: 0, y: 0 })
const searchInput = ref(null)
const searchValueLocal = ref(props.searchValue)

const playModeLabel = computed(() => ({
  sequential: '顺序',
  'repeat-one': '单曲循环',
  shuffle: '随机',
  repeat: '列表循环'
})[playMode.value] || '顺序')

const modeOptions = [
  { value: 'sequential', label: '顺序播放' },
  { value: 'repeat', label: '列表循环' },
  { value: 'repeat-one', label: '单曲循环' },
  { value: 'shuffle', label: '随机播放' }
]

function openModeMenu(e) {
  const x = Math.min(e.clientX, window.innerWidth - 180)
  const y = Math.min(e.clientY, window.innerHeight - 220)
  modeMenu.value = { visible: true, x, y }
}
function closeModeMenu() { modeMenu.value.visible = false }
function setPlayMode(m) {
  player.playMode = m
  closeModeMenu()
}

function closeSearch() {
  searchOpen.value = false
  searchValueLocal.value = ''
  if (props.searchValue) emit('update:searchValue', '')
}

function chooseSort(key) {
  emit('sort', { key, order: props.sortOrder })
  sortOpen.value = false
}
function setSortOrder(order) {
  emit('sort', { key: props.sortKey, order })
  sortOpen.value = false
}
function chooseFilter(key, value) {
  emit('filter', { key, value })
  filterOpen.value = false
}

watch(searchOpen, async (v) => {
  if (v) { await nextTick(); searchInput.value?.focus() }
})
watch(() => props.searchValue, (v) => {
  if (v !== searchValueLocal.value) searchValueLocal.value = v
})
watch(() => [sortOpen.value, filterOpen.value], () => closeModeMenu())

// ===== 顶栏背景模糊（页头内 fixed z-1 + cb 补偿 + 下延采样区） =====
// 三要素齐备：
//  1) 挂 headerEl 内 + z-index:-1 → 与文字同 stacking context，垫底不罩文字
//  2) containing block 坐标补偿 → 精确对齐页头（fixed 基准非视口）
//  3) 高度 = 页头高 + 60px 下延 → 下段伸出页头矩形、悬到滚动内容上，
//     保证 backdrop 采样生效（sticky 矩形内是采样死区；这是⑤"错位才有模糊"
//     的机制，现在用主动下延替代偶然错位）
const headerEl = ref(null)
let _frostEl = null
let _onScroll = null
let _cb = null
const FROST_EXTEND = 60        // 页头下方伸出段：保证采样可见

/** 找到 fixed 定位的 containing block（最近 transform/filter/will-change 祖先） */
function _findCb(el) {
  let node = el.parentElement
  while (node && node !== document.documentElement) {
    const cs = getComputedStyle(node)
    const isCb =
      (cs.transform && cs.transform !== 'none') ||
      (cs.filter && cs.filter !== 'none') ||
      (cs.perspective && cs.perspective !== 'none') ||
      (cs.willChange && /transform|filter/.test(cs.willChange))
    if (isCb) return node
    node = node.parentElement
  }
  return null
}

function _syncFrost() {
  if (!_frostEl || !headerEl.value) return
  const r = headerEl.value.getBoundingClientRect()   // 视口坐标
  if (r.height <= 0) return
  const cbR = _cb ? _cb.getBoundingClientRect() : { top: 0, left: 0 }
  _frostEl.style.top = `${r.top - cbR.top}px`
  _frostEl.style.left = `${r.left - cbR.left}px`
  _frostEl.style.width = `${r.width}px`
  _frostEl.style.height = `${r.height + FROST_EXTEND}px`   // 下延->采样区
}

function _buildFrost() {
  if (_frostEl || !headerEl.value) return
  _cb = _findCb(headerEl.value)
  _frostEl = document.createElement('div')
  Object.assign(_frostEl.style, {
    position: 'fixed',
    zIndex: '-1',               // 页头 context 内垫底，文字永不罩
    pointerEvents: 'none',
    backdropFilter: 'blur(20px) saturate(150%)',
    webkitBackdropFilter: 'blur(20px) saturate(150%)',
    // mask: to top => 0%(底)=transparent、100%(顶)=#000 → 底部渐隐、顶部实心
    maskImage: 'linear-gradient(to top, transparent 0%, #000 100%)',
    WebkitMaskImage: 'linear-gradient(to top, transparent 0%, #000 100%)'
  })
  headerEl.value.appendChild(_frostEl)
  _syncFrost()
  _onScroll = _syncFrost
  document.addEventListener('scroll', _onScroll, true)
  window.addEventListener('resize', _onScroll)
}

function _removeFrost() {
  if (_onScroll) {
    document.removeEventListener('scroll', _onScroll, true)
    window.removeEventListener('resize', _onScroll)
    _onScroll = null
  }
  if (_frostEl) { _frostEl.remove(); _frostEl = null }
  _cb = null
}

onMounted(() => {
  const m = async () => {
    if (document.fonts?.ready) { try { await document.fonts.ready } catch {} }
    await nextTick()
    _buildFrost()
  }
  m()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  _removeFrost()
})
</script>

<style scoped>
/* 页头本体完全透明。注：此环境的 Chromium 中 sticky 容器矩形内的
   backdrop-filter 采样不可靠（多轮实测），未使用毛玻璃背景方案。 */
.list-page-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px 10px;
  margin-bottom: 10px;
  background: transparent;
}
.list-page-header__title { font-size: 20px; font-weight: 700; margin: 0; white-space: nowrap; }
.list-page-header__count { font-size: 13px; color: var(--text-tertiary); }
.list-page-header__spacer { flex: 1; }

.lph-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.lph-btn:hover { background: var(--hover-bg-strong); color: var(--text-primary); }
.lph-btn.active { background: var(--accent-bg); color: var(--accent-color); }
.lph-btn--playmode {
  border: 1px solid var(--border-color);
  font-size: 13px;
}

.lph-search {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 34px;
  padding: 0 6px 0 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.25);
}
.lph-search input {
  width: 180px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
}
.lph-search__close {
  border: none;
  background: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
}
.lph-search__close:hover { color: var(--text-primary); }

.lph-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 58px;
  min-width: 170px;
  padding: 8px;
  border-radius: 12px;
  background: var(--glass-bg-strong, rgba(30, 30, 38, 0.92));
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  border: 1px solid var(--border-color);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  z-index: 30;
}
.lph-panel--filter { min-width: 220px; right: 96px; }
.lph-panel--filter .lph-panel__options { display: flex; flex-wrap: wrap; gap: 4px; }
.lph-panel__title { font-size: 11px; color: var(--text-tertiary); padding: 4px 8px; }
.lph-panel__item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  padding: 7px 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}
.lph-panel__item:hover { background: var(--hover-bg-strong); color: var(--text-primary); }
.lph-panel__item.active { color: var(--accent-color); }
.lph-panel__arrow { color: var(--accent-color); }
.lph-panel__divider { height: 1px; background: var(--border-color); margin: 6px 4px; }
.lph-panel__row { display: flex; gap: 6px; }
.lph-panel__dir { justify-content: center; }
.lph-panel__opt { width: auto; }

.lph-mode-menu {
  position: fixed;
  min-width: 170px;
  padding: 8px;
  border-radius: 12px;
  background: var(--glass-bg-strong, rgba(30, 30, 38, 0.92));
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  border: 1px solid var(--border-color);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  z-index: 200;
}
.lph-mode-menu .lph-panel__item { width: 100%; }
.lph-menu-enter-active, .lph-menu-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.lph-menu-enter-from, .lph-menu-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
