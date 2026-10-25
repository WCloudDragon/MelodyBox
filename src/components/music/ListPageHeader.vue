<template>
  <div class="list-page-header" ref="headerEl" :class="{ 'fog-on': fogOn, 'title-follows-fog': fogTitle }">
    <!-- 返回按钮（下钻页）：置于标题左侧，标题随 flex 自然右移；顶层页不渲染保持现状 -->
    <button v-if="showBack" class="lph-btn lph-btn--back" title="返回" @click="onBack">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <line x1="20" y1="12" x2="4" y2="12"/>
        <polyline points="8.5 16.5 4 12 8.5 7.5"/>
      </svg>
    </button>
    <h1 class="list-page-header__title">{{ title }}</h1>
    <span v-if="count != null" class="list-page-header__count">{{ count }}</span>
    <div class="list-page-header__spacer"></div>

    <!-- 页面自定义右侧操作（导入/刷新/播放全部等） -->
    <slot />

    <!-- 播放模式：左键以当前模式一键起播本列表，右键菜单切换模式（复用全局右键菜单样式/动效/防出屏） -->
    <button
      v-if="showPlayMode && listTracks && listTracks.length"
      class="lph-btn lph-btn--playmode"
      :title="`以${playModeLabel}模式播放本列表（右键切换模式）`"
      @click="player.playListByMode(listTracks)"
      @contextmenu.prevent.stop="openModeMenu($event)"
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M2 3h2v10H2V3zm4 0h8v2H6V3zm0 4h6v2H6V7zm0 4h8v2H6v-2z"/></svg>
      <span>{{ playModeLabel }}</span>
    </button>

    <!-- 排序 -->
    <button v-if="showSort" class="lph-btn" :class="{ active: sortOpen }" title="排序" @click.stop="toggleSort($event)">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2v9H2l3 3 3-3H6V2H4zm8 0h-2v12h-2l3 3 3-3h-2V2z"/></svg>
    </button>

    <!-- 筛选 -->
    <button v-if="showFilter" class="lph-btn" :class="{ active: filterOpen }" title="筛选" @click.stop="toggleFilter($event)">
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

    <!-- 浮层透明遮罩：打开排序/筛选时拦截外部点击——仅关闭浮层，不穿透到背景元素 -->
    <div
      v-if="sortOpen || filterOpen"
      class="lph-backdrop"
      @click="sortOpen = filterOpen = false"
    />

    <!-- 排序面板 -->
    <Transition name="lph-panel">
      <div v-if="sortOpen" class="lph-panel" :style="{ right: panelRight + 'px' }" @click.stop>
      <div class="lph-panel__title">排序</div>
      <button v-for="opt in sortOptions" :key="opt.value" class="lph-panel__item" v-ripple :class="{ active: sortKey === opt.value }" @click="chooseSort(opt.value)">
        <span>{{ opt.label }}</span>
        <span v-if="sortKey === opt.value" class="lph-panel__arrow">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
      </button>
      <div class="lph-panel__divider"></div>
      <button class="lph-panel__item" v-ripple :class="{ active: sortOrder === 'asc' }" @click="setSortOrder('asc')">
        <span>升序</span>
        <span v-if="sortOrder === 'asc'" class="lph-panel__arrow">↑</span>
      </button>
      <button class="lph-panel__item" v-ripple :class="{ active: sortOrder === 'desc' }" @click="setSortOrder('desc')">
        <span>降序</span>
        <span v-if="sortOrder === 'desc'" class="lph-panel__arrow">↓</span>
      </button>
    </div>
      </Transition>

    <!-- 筛选面板 -->
    <Transition name="lph-panel">
      <div v-if="filterOpen" class="lph-panel lph-panel--filter" :style="{ right: panelRight + 'px' }" @click.stop>
        <div v-for="group in filterGroups" :key="group.key" class="lph-panel__group">
          <div class="lph-panel__title">{{ group.label }}</div>
          <div class="lph-panel__options">
            <button
              v-for="opt in group.options"
              :key="opt.value"
              class="lph-panel__item lph-panel__opt"
              v-ripple
              :class="{ active: filterValues[group.key] === opt.value }"
              @click="chooseFilter(group.key, opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 播放模式右键菜单：复用全局右键菜单（样式/动效/防出屏与列表项一致） -->
    <ContextMenu
      :visible="modeMenu.visible"
      :x="modeMenu.x"
      :y="modeMenu.y"
      :items="modeMenuItems"
      :animated="true"
      @close="modeMenu.visible = false"
      @action="setPlayMode"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePlayerStore, PLAY_MODES } from '@/stores/player'
import ContextMenu from '@/components/music/ContextMenu.vue'

const props = defineProps({
  title: { type: String, required: true },
  count: { type: [String, Number], default: null },
  // 当前页面显示的歌曲列表：播放模式按钮以它为起播对象（专辑/艺术家等无歌曲列表的页面不传 → 按钮隐藏）
  listTracks: { type: Array, default: null },
  showPlayMode: { type: Boolean, default: true },
  showSort: { type: Boolean, default: false },
  showFilter: { type: Boolean, default: false },
  showMultiSelect: { type: Boolean, default: false },
  multiSelectActive: { type: Boolean, default: false },
  showViewSwitch: { type: Boolean, default: false },
  viewMode: { type: String, default: 'list' },
  // 返回按钮（下钻页）：显示于标题左侧
  showBack: { type: Boolean, default: false },
  // 无浏览历史（刷新/直达 URL）时的返回兜底目标，建议传语义父级（如专辑列表页传 /albums）
  backFallback: { type: String, default: '' },
  // 自定义返回动作：传入后替代默认路由返回（设置页二级页用其回到设置菜单）
  backHandler: { type: Function, default: null },
  // 标题随雾显隐：页面已在内容区常驻同名标题（page-content-title）时开启，
  // 顶部时页头标题/计数隐藏，下滚后随雾同步淡入
  fogTitle: { type: Boolean, default: false },
  sortOptions: { type: Array, default: () => [] },
  sortKey: { type: String, default: '' },
  sortOrder: { type: String, default: 'asc' },
  filterGroups: { type: Array, default: () => [] },
  filterValues: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['sort', 'filter', 'viewChange', 'toggleMultiSelect'])

const router = useRouter()

// 返回：优先自定义动作；有浏览历史则 back；否则跳语义父级（兜底到首页）
function onBack() {
  if (props.backHandler) {
    props.backHandler()
    return
  }
  if (window.history.state?.back) {
    router.back()
  } else if (props.backFallback) {
    router.replace(props.backFallback)
  } else {
    router.replace('/')
  }
}

const player = usePlayerStore()
const { playMode } = storeToRefs(player)

// ==================== 顶部雾区滚动显隐 ====================
// 顶部（scrollTop ≤ 阈值）时雾区（frost/fade）与标题隐藏，下滚一点后同步淡入。
// 滚动容器因页面而异：详情页滚 main-content，列表页（穿透式布局）滚视图内部
// 容器——scroll 事件用捕获模式接住任意容器，按事件来源过滤相关容器后再取 scrollTop
const FOG_THRESHOLD = 24
const fogOn = ref(false)

function _syncFogFromTarget(target) {
  if (!(target instanceof Element)) return
  const view = headerEl.value?.parentElement
  if (target.classList.contains('main-content') || (view && view.contains(target))) {
    fogOn.value = target.scrollTop > FOG_THRESHOLD
  }
}

function _onDocScrollCapture(e) { _syncFogFromTarget(e.target) }

// 初始/激活时全量探测：取 main-content 与视图内部滚动容器的最大 scrollTop
// （列表页滚内层、详情页滚 main，二者取大者即为「页面滚过多少」）
function _syncFogOn() {
  let st = 0
  const main = document.querySelector('.main-content')
  if (main) st = main.scrollTop
  const view = headerEl.value?.parentElement
  if (view) {
    for (const el of view.querySelectorAll('*')) {
      const s = getComputedStyle(el)
      if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollTop > st) st = el.scrollTop
    }
  }
  fogOn.value = st > FOG_THRESHOLD
}

watch(fogOn, (v) => {
  for (const el of [_frostEl, _fadeEl]) if (el) el.style.opacity = v ? '1' : '0'
})

const sortOpen = ref(false)
const filterOpen = ref(false)
const modeMenu = ref({ visible: false, x: 0, y: 0 })

// 排序/筛选浮层锚定到触发按钮右缘（absolute 相对页头 padding box），
// 不再按「距右侧第几个按钮」写死偏移，按钮数量变化时也不会错位
const panelRight = ref(58)

function _anchorPanel(e) {
  const header = headerEl.value
  if (!header) return
  const headerRect = header.getBoundingClientRect()
  const btnRect = e.currentTarget.getBoundingClientRect()
  panelRight.value = Math.max(8, Math.round(headerRect.right - btnRect.right))
}

function toggleSort(e) {
  _anchorPanel(e)
  filterOpen.value = false
  sortOpen.value = !sortOpen.value
}

function toggleFilter(e) {
  _anchorPanel(e)
  sortOpen.value = false
  filterOpen.value = !filterOpen.value
}

// 按钮短标签：注册表 label 去掉「播放」尾字（顺序播放→顺序）
const playModeLabel = computed(() => {
  const m = PLAY_MODES.find(m => m.key === playMode.value)
  return (m?.label || '顺序播放').replace(/播放$/, '')
})

// 列表页模式菜单：仅含 inList 模式（单曲循环属于播放器，不在列表菜单提供）
const modeMenuItems = computed(() =>
  PLAY_MODES.filter(m => m.inList).map(m => ({
    label: m.label + (playMode.value === m.key ? ' ✓' : ''),
    action: m.key
  }))
)

function openModeMenu(e) {
  // 坐标原样传入；防出屏由 ContextMenu 渲染后实测尺寸自行修正
  modeMenu.value = { visible: true, x: e.clientX, y: e.clientY }
}
function closeModeMenu() { modeMenu.value.visible = false }
function setPlayMode(m) {
  // 右键菜单选中：设定模式偏好，并立即按该模式起播本列表
  player.setPlayMode(m)
  player.playListByMode(props.listTracks)
  closeModeMenu()
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

watch(() => [sortOpen.value, filterOpen.value], () => closeModeMenu())

// ===== 顶栏背景模糊（headerEl 内 absolute + 下延采样区） =====
// 三要素齐备：
//  1) 挂 headerEl 内 + z-index:-1 → 与文字同 stacking context，垫底不罩文字
//  2) absolute 相对页头自身定位（页头恒为视口固定位置：列表页页头 absolute 悬浮、
//     详情页页头 sticky 贴顶）→ frost 跟随页头，无 containing block 切换问题；
//     页面过渡 scale 动画中与页头同帧变换，模糊不再错位/消失
//  3) 高度 = 页头高 + 60px 下延 → 下段伸出页头矩形、悬到滚动内容上，
//     保证 backdrop 采样生效（sticky 矩形内是采样死区；用主动下延替代偶然错位）
const headerEl = ref(null)
let _frostEl = null
let _fadeEl = null
const FROST_EXTEND = 60        // 页头下方伸出段：保证采样可见

function _syncFrost() {
  if (!_frostEl || !headerEl.value) return
  const h = headerEl.value.offsetHeight
  if (h <= 0) return
  // frost 上伸至窗口顶（--content-top = TitleBar 高 + 页头上方背景带），下延采样区照旧
  _frostEl.style.height = `calc(var(--content-top, 60px) + ${h + FROST_EXTEND}px)`
  // 遮罩层从窗口顶铺到页头底（TitleBar 高度内全浓度，页头区渐透明）
  if (_fadeEl) _fadeEl.style.height = `calc(var(--content-top, 60px) + ${h}px)`
}

function _buildFrost() {
  if (_frostEl || !headerEl.value) return
  _frostEl = document.createElement('div')
  _frostEl.className = 'lph-frost'
  Object.assign(_frostEl.style, {
    position: 'absolute',
    top: 'calc(-1 * var(--content-top, 60px))',  // 上伸至窗口顶：雾从标题栏背后开始
    // 左右外扩一个 main padding：雾铺满「侧边栏右缘 → 窗口右缘」（右侧额外盖过滚动条 gutter）
    left: 'calc(-1 * var(--content-pad, 32px))',
    right: 'calc(-1 * var(--content-pad, 32px) - 6px)',
    zIndex: '-1',               // 页头 context 内垫底，文字永不罩
    pointerEvents: 'none',
    // 雾随滚动显隐：顶部隐藏，下滚淡入（fogOn watch 切换 opacity）
    opacity: fogOn.value ? '1' : '0',
    transition: 'opacity 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0), background 0.25s ease',
    // 模糊半径对齐侧边栏/播放队列的 --glass-blur（24px saturate）；
    // 无底色：加 background 会产生色差（浅色主题尤其明显），保持纯模糊
    backdropFilter: 'var(--glass-blur)',
    webkitBackdropFilter: 'var(--glass-blur)',
    // mask 梯度（frost 总高 = content-top 60 + 页头高 + 60 下延，% 从底部起算；
    // 页头底位于 (60+页头高)/总高 ≈ 66% 处，随页头实际高度浮动）：
    //   下延尾(0-8%)透明缓冲 → 下延中段渐浓(30% 0.65) → 页头底(66%)起整条实心到顶
    //   TitleBar 悬浮半透背景罩住窗口顶段，雾在其背后若隐若现
    maskImage: 'linear-gradient(to top, transparent 0%, transparent 8%, rgba(0,0,0,0.65) 30%, #000 66%, #000 100%)',
    WebkitMaskImage: 'linear-gradient(to top, transparent 0%, transparent 8%, rgba(0,0,0,0.65) 30%, #000 66%, #000 100%)'
  })
  headerEl.value.appendChild(_frostEl)
  // 透明度遮罩层：窗口顶全浓度、页头区线性渐透明（渐变见 App.vue .lph-fade）。
  // 与 frost 同为 z:-1 但 DOM 靠后 → 绘制在模糊之上、页头文字/按钮之下
  _fadeEl = document.createElement('div')
  _fadeEl.className = 'lph-fade'
  Object.assign(_fadeEl.style, {
    position: 'absolute',
    top: 'calc(-1 * var(--content-top, 60px))',  // 顶至窗口顶，与 frost 同域
    left: 'calc(-1 * var(--content-pad, 32px))',
    right: 'calc(-1 * var(--content-pad, 32px) - 6px)',
    zIndex: '-1',
    pointerEvents: 'none',
    opacity: fogOn.value ? '1' : '0',
    transition: 'opacity 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0)'
  })
  headerEl.value.appendChild(_fadeEl)
  _syncFrost()
}

function _removeFrost() {
  if (_frostEl) { _frostEl.remove(); _frostEl = null }
  if (_fadeEl) { _fadeEl.remove(); _fadeEl = null }
}

onMounted(() => {
  const m = async () => {
    if (document.fonts?.ready) { try { await document.fonts.ready } catch {} }
    await nextTick()
    _buildFrost()
    _syncFogOn()
  }
  m()
  // 雾/标题随滚动显隐：捕获模式接住任意滚动容器（main 或视图内部容器）
  document.addEventListener('scroll', _onDocScrollCapture, true)
  // 页头高度 -> 全局 CSS 变量：穿透式布局（列表滚动容器全高 + spacer 顶部偏移）
  // 依赖此值，页头几何变化（字体加载/换行）时自动同步；frost 高度同步复用同一回调
  // 守卫：keep-alive 离场时 DOM 移出文档，RO 会报 0 尺寸——跳过，
  // 否则离场实例会把全局 --lph-h 清零，导致目标页 spacer 失效、内容顶穿页头
  _lphRO = new ResizeObserver(() => {
    const el = headerEl.value
    if (!el || !el.isConnected) return
    const h = el.offsetHeight
    if (h <= 0) return
    document.documentElement.style.setProperty('--lph-h', h + 'px')
    _syncFrost()
  })
  _lphRO.observe(headerEl.value)
  document.documentElement.style.setProperty('--lph-h', headerEl.value.offsetHeight + 'px')
})

// keep-alive 复用切回时立即矫正 --lph-h 与 frost（不依赖 RO 的触发时机）
onActivated(() => {
  const el = headerEl.value
  if (!el || !el.isConnected) return
  const h = el.offsetHeight
  if (h <= 0) return
  document.documentElement.style.setProperty('--lph-h', h + 'px')
  _syncFrost()
  _syncFogOn()
})

let _lphRO = null

onBeforeUnmount(() => {
  _removeFrost()
  _lphRO?.disconnect()
  document.removeEventListener('scroll', _onDocScrollCapture, true)
})
</script>

<style scoped>
/* 页头本体完全透明。注：此环境的 Chromium 中 sticky 容器矩形内的
   backdrop-filter 采样不可靠（多轮实测），未使用毛玻璃背景方案。 */
.list-page-header {
  position: sticky;
  /* 沉浸式布局下 main 滚动视口顶 = 窗口顶，sticky 贴定点 = TitleBar 底下方 */
  top: var(--content-top, 0px);
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 10px;
  /* 顶/底收紧：标题与控件贴近标题栏（对齐文件夹页的贴顶比例） */
  padding: 6px var(--page-pad-x, 12px) 8px;
  margin-bottom: 10px;
  background: transparent;
}
.list-page-header__title {
  /* 字号对齐文件夹页标题（28px），各页面标题栏视觉统一 */
  font-size: 28px; font-weight: 700; margin: 0; white-space: nowrap;
  letter-spacing: -0.3px; line-height: 1.2;
}
.list-page-header__count { font-size: 13px; color: var(--text-tertiary); }
/* 标题/计数随雾显隐（fog-title 页面）：顶部隐藏（标题由内容区 page-content-title 承载），
   下滚后随雾同步淡入；未开启 fog-title 的页面标题常显不受影响 */
.list-page-header.title-follows-fog .list-page-header__title,
.list-page-header.title-follows-fog .list-page-header__count {
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0), transform 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.list-page-header.title-follows-fog.fog-on .list-page-header__title,
.list-page-header.title-follows-fog.fog-on .list-page-header__count {
  opacity: 1;
  transform: none;
}
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
/* 返回按钮：纯箭头，无背景块；hover 仅让箭头提亮/变淡，不出现底色 */
.lph-btn--back {
  width: 24px;
  height: 24px;
  margin-left: -2px;
  padding: 0;
  justify-content: center;
  color: var(--text-primary);
  transition: color 0.2s;
}
.lph-btn--back:hover {
  background: transparent;
  color: var(--text-tertiary);
}

.lph-backdrop {
  position: fixed; inset: 0; z-index: 25;
}
/* 浮层：与全局右键菜单（.ctx-menu）同一规格——圆角 8、通栏条目、玻璃材质 */
.lph-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 58px;
  min-width: 160px;
  padding: 4px 0;
  border-radius: 8px;
  background: var(--glass-bg-strong, rgba(30, 30, 38, 0.92));
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  box-shadow: inset 0 1px 0 var(--glass-highlight), var(--glass-shadow);
  z-index: 30;
}
/* 开闭动画：与右键菜单 ctx-menu-blur 同配方（弹性回弹入场 + 模糊缩小离场） */
.lph-panel-enter-active {
  animation: lph-panel-pop 0.38s cubic-bezier(0.34, 1.56, 0.64, 1);
  transition: opacity 0.28s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.28s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lph-panel-enter-from {
  opacity: 0;
  filter: blur(6px);
  transform: scale(0.85);
}
@keyframes lph-panel-pop {
  0%   { transform: scale(0.85); }
  100% { transform: scale(1); }
}
.lph-panel-leave-active {
  transition: opacity 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.lph-panel-leave-to {
  opacity: 0;
  filter: blur(6px);
  transform: scale(0.85);
}
.lph-panel--filter { min-width: 220px; right: 96px; }
.lph-panel__group { padding: 2px 0 4px; }
.lph-panel__group + .lph-panel__group { border-top: 1px solid var(--border-color); }
.lph-panel__options { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 6px; }
.lph-panel__title { font-size: 11px; color: var(--text-tertiary); padding: 6px 16px 2px; letter-spacing: 1px; }
.lph-panel__item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}
.lph-panel__item:hover { background: var(--hover-bg-strong); }
.lph-panel__item.active { color: var(--accent-color); }
.lph-panel__arrow { color: var(--accent-color); }
.lph-panel__divider { height: 1px; background: var(--border-color); margin: 4px 0; }
.lph-panel__opt {
  width: auto; padding: 5px 10px; border-radius: 8px;
  color: var(--text-secondary);
}
.lph-panel__opt:hover { background: var(--hover-bg-strong); }
.lph-panel__opt.active { background: var(--accent-bg); color: var(--accent-color); }
</style>
