<template>
  <teleport to="body">
    <Transition :name="menuAnimName">
      <div v-if="visible" ref="menuEl" class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
        <template v-for="(item, i) in items" :key="i">
          <div v-if="item === '-'" class="ctx-menu-divider" />
          <div
            v-else-if="item.hasSubmenu"
            class="ctx-menu-item ctx-menu-item--has-submenu"
            @mouseenter="onItemEnter(item, $event)"
            @mouseleave="onItemLeave"
          >
            <div class="ctx-menu-item__body" v-ripple>
              <span>{{ item.label }}</span>
              <span class="ctx-menu-arrow">›</span>
            </div>
          </div>
          <div
            v-else
            class="ctx-menu-item"
            v-ripple
            :class="{ 'ctx-menu-item--danger': item.danger }"
            @click="$emit('action', item.action)"
            @mouseenter="onItemEnter(item, $event)"
            @mouseleave="onItemLeave"
          >
            <span>{{ item.label }}</span>
          </div>
        </template>
      </div>
    </Transition>

    <Transition :name="backdropAnimName">
      <div v-if="visible" class="ctx-menu-backdrop" @click="$emit('close')" />
    </Transition>

    <!-- 二级子菜单：Teleport 至 body 与主菜单平级。不可嵌套在主菜单内——
         主菜单自身是 backdrop-filter 元素，Chromium 中嵌套其内的子元素
         backdrop 采样失效，模糊退化为近实心底（与主菜单材质不一致）。
         平级渲染后与主菜单使用同一玻璃配方，视觉统一 -->
    <Transition :name="menuAnimName">
      <div
        v-if="visible && submenu && submenuOpen"
        ref="submenuEl"
        class="ctx-submenu"
        :style="{ left: submenuPos.left + 'px', top: submenuPos.top + 'px' }"
        @click.stop
        @mouseenter="onSubmenuEnter"
        @mouseleave="onSubmenuLeave"
      >
        <div class="ctx-menu-subtitle">{{ submenu.title }}</div>
        <template v-for="(sub, si) in submenu.items" :key="si">
          <div class="ctx-menu-item" v-ripple @click="$emit('sub-action', sub)">{{ sub.label }}</div>
        </template>
      </div>
    </Transition>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

defineOptions({ name: 'ContextMenu' })
const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  items: { type: Array, default: () => [] },
  animated: { type: Boolean, default: false },
  submenu: { type: Object, default: null }
})
const emit = defineEmits(['close', 'action', 'sub-action', 'hover-submenu'])

const menuAnimName = computed(() => props.animated ? 'ctx-menu-blur' : 'ctx-menu-none')
const backdropAnimName = computed(() => props.animated ? 'ctx-menu-backdrop' : 'ctx-menu-none')

const menuEl = ref(null)
// 防出屏修正后的实际坐标（初始等于传入坐标，渲染后按实测尺寸修正）
const pos = ref({ x: props.x, y: props.y })
const x = computed(() => pos.value.x)
const y = computed(() => pos.value.y)

// 菜单渲染后按实测尺寸防出屏：不再依赖调用方估算宽高（内容条数可变，估算必失准）
watch(() => props.visible, async (v) => {
  if (v) {
    pos.value = { x: props.x, y: props.y }
    await nextTick()
    const el = menuEl.value
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    let nx = props.x
    let ny = props.y
    if (nx + w > window.innerWidth - 8) nx = Math.max(8, window.innerWidth - w - 8)
    if (ny + h > window.innerHeight - 8) ny = Math.max(8, window.innerHeight - h - 8)
    pos.value = { x: nx, y: ny }
  }
})

const submenuOpen = ref(false)
const submenuSide = ref('right')
const submenuAlign = ref('top')
const SUB_WIDTH = 180
const SUB_HEIGHT = 160
// 子菜单 Teleport 至 body 后需自行计算 fixed 定位（实测尺寸 + 防出屏）
const submenuEl = ref(null)
const submenuPos = ref({ left: 0, top: 0 })
const submenuHover = ref(false)
let submenuRect = null
let leaveTimer = null

function onItemEnter(item, e) {
  clearTimeout(leaveTimer)
  if (item.hasSubmenu) {
    submenuRect = e.currentTarget.getBoundingClientRect()
    submenuSide.value = (submenuRect.right + SUB_WIDTH > window.innerWidth - 8) ? 'left' : 'right'
    submenuAlign.value = (submenuRect.top + SUB_HEIGHT > window.innerHeight - 8) ? 'bottom' : 'top'
    submenuOpen.value = true
    positionSubmenu()
    emit('hover-submenu')
  } else {
    submenuOpen.value = false
  }
}
function onItemLeave() {
  // 延迟关闭：为"从父项移入子菜单"留出过桥时间（Teleport 后子菜单不再是父项的 DOM 后代，
  // 移动指针会先触发父项 mouseleave）；进入子菜单时 onSubmenuEnter 会撤销本次关闭
  clearTimeout(leaveTimer)
  leaveTimer = setTimeout(() => {
    if (!submenuHover.value) submenuOpen.value = false
  }, 60)
}
function onSubmenuEnter() {
  clearTimeout(leaveTimer)
  submenuHover.value = true
}
function onSubmenuLeave() {
  submenuHover.value = false
  submenuOpen.value = false
}

async function positionSubmenu() {
  await nextTick()
  const rect = submenuRect
  if (!rect) return
  const el = submenuEl.value
  const w = el ? el.offsetWidth : SUB_WIDTH
  const h = el ? el.offsetHeight : SUB_HEIGHT
  let left = submenuSide.value === 'right' ? rect.right : rect.left - w
  let top = submenuAlign.value === 'top' ? rect.top : rect.bottom - h
  // 防出屏兜底（与主菜单同策略）
  left = Math.min(Math.max(8, left), window.innerWidth - w - 8)
  top = Math.min(Math.max(8, top), window.innerHeight - h - 8)
  submenuPos.value = { left, top }
}

watch(() => props.visible, (v) => {
  if (!v) {
    submenuOpen.value = false
    submenuHover.value = false
  }
})
</script>
