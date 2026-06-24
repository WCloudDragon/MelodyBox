<template>
  <img
    ref="elRef"
    v-bind="$attrs"
    class="lazy-cover"
    :class="{ loaded }"
    decoding="async"
    loading="lazy"
    :src="finalSrc"
    @load="onLoad"
    @error="onError"
  />
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  thumbSize: { type: Number, default: 0 }
})
const emit = defineEmits(['error'])
const elRef = ref(null)
const loaded = ref(false)

const finalSrc = computed(() => {
  if (!props.src || !props.thumbSize || props.thumbSize <= 0) return props.src
  const sep = props.src.includes('?') ? '&' : '?'
  return `${props.src}${sep}thumb=${props.thumbSize}`
})

function onLoad() {
  loaded.value = true
}

function onError() {
  emit('error')
}
</script>

<style scoped>
.lazy-cover { opacity: 0; transition: opacity 0.15s; }
.lazy-cover.loaded { opacity: 1; }
</style>
