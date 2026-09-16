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

            <!-- 二级子菜单：嵌套在该项内，悬停展开，移出即收 -->
            <Transition name="ctx-menu-blur">
              <div
                v-if="submenu && submenuOpen"
                class="ctx-submenu"
                :class="{ 'ctx-submenu--left': submenuSide === 'left', 'ctx-submenu--bottom': submenuAlign === 'bottom' }"
                @click.stop
              >
                <div class="ctx-menu-subtitle">{{ submenu.title }}</div>
                <template v-for="(sub, si) in submenu.items" :key="si">
                  <div class="ctx-menu-item" v-ripple @click="$emit('sub-action', sub)">{{ sub.label }}</div>
                </template>
              </div>
            </Transition>
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

function onItemEnter(item, e) {
  if (item.hasSubmenu) {
    const rect = e.currentTarget.getBoundingClientRect()
    submenuSide.value = (rect.right + SUB_WIDTH > window.innerWidth - 8) ? 'left' : 'right'
    submenuAlign.value = (rect.top + SUB_HEIGHT > window.innerHeight - 8) ? 'bottom' : 'top'
    submenuOpen.value = true
    emit('hover-submenu')
  } else {
    submenuOpen.value = false
  }
}
function onItemLeave() {
  submenuOpen.value = false
}

watch(() => props.visible, (v) => {
  if (!v) submenuOpen.value = false
})
</script>
