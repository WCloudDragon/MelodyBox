<template>
  <teleport to="body">
    <template v-if="animated">
      <Transition name="ctx-menu-blur">
        <div v-if="visible" class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
          <template v-for="(item, i) in items" :key="i">
            <div v-if="item === '-'" class="ctx-menu-divider" />
            <div v-else class="ctx-menu-item" v-ripple :class="{ 'ctx-menu-item--danger': item.danger }" @click="$emit('action', item.action)">{{ item.label }}</div>
          </template>
        </div>
      </Transition>
      <Transition name="ctx-menu-backdrop">
        <div v-if="visible" class="ctx-menu-backdrop" @click="$emit('close')" />
      </Transition>
    </template>
    <template v-else>
      <div v-if="visible" class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
        <template v-for="(item, i) in items" :key="i">
          <div v-if="item === '-'" class="ctx-menu-divider" />
          <div v-else class="ctx-menu-item" v-ripple :class="{ 'ctx-menu-item--danger': item.danger }" @click="$emit('action', item.action)">{{ item.label }}</div>
        </template>
      </div>
      <div v-if="visible" class="ctx-menu-backdrop" @click="$emit('close')" />
    </template>
  </teleport>
</template>

<script setup>
defineOptions({ name: 'ContextMenu' })
defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  items: { type: Array, default: () => [] },
  animated: { type: Boolean, default: false }
})
defineEmits(['close', 'action'])
</script>
