<template>
  <teleport to="body">
    <Transition :name="menuAnimName">
      <div v-if="visible" class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
        <template v-for="(item, i) in items" :key="i">
          <div v-if="item === '-'" class="ctx-menu-divider" />
          <div
            v-else
            class="ctx-menu-item"
            v-ripple
            :class="{ 'ctx-menu-item--danger': item.danger, 'ctx-menu-item--has-submenu': item.hasSubmenu }"
            @click="$emit('action', item.action)"
            @mouseenter="onItemEnter(item, $event)"
            @mouseleave="onItemLeave"
          >
            <span>{{ item.label }}</span>
            <span v-if="item.hasSubmenu" class="ctx-menu-arrow">›</span>

            <!-- 二级子菜单：嵌套在该项内，悬停展开，移出即收 -->
            <div
              v-if="item.hasSubmenu && submenu && submenuOpen"
              class="ctx-submenu"
              :class="{ 'ctx-submenu--left': submenuSide === 'left' }"
              @click.stop
            >
              <div class="ctx-menu-subtitle">{{ submenu.title }}</div>
              <template v-for="(sub, si) in submenu.items" :key="si">
                <div class="ctx-menu-item" v-ripple @click="$emit('sub-action', sub)">{{ sub.label }}</div>
              </template>
            </div>
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
import { ref, computed, watch } from 'vue'

defineOptions({ name: 'ContextMenu' })
const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  items: { type: Array, default: () => [] },
  animated: { type: Boolean, default: false },
  submenu: { type: Object, default: null }
})
const emit = defineEmits(['close', 'action', 'back', 'sub-action', 'hover-submenu'])

const menuAnimName = computed(() => props.animated ? 'ctx-menu-blur' : 'ctx-menu-none')
const backdropAnimName = computed(() => props.animated ? 'ctx-menu-backdrop' : 'ctx-menu-none')

const submenuOpen = ref(false)
const submenuSide = ref('right')
const SUB_WIDTH = 180

function onItemEnter(item, e) {
  if (item.hasSubmenu) {
    const rect = e.currentTarget.getBoundingClientRect()
    submenuSide.value = (rect.right + SUB_WIDTH > window.innerWidth - 8) ? 'left' : 'right'
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
