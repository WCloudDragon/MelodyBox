<template>
  <img
    ref="elRef"
    v-bind="$attrs"
    class="lazy-cover"
    :class="{ loaded }"
    decoding="async"
    :src="activeSrc"
    @load="onLoad"
    @error="onError"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  thumbSize: { type: Number, default: 0 }
})
const emit = defineEmits(['error'])
const elRef = ref(null)
const loaded = ref(false)

const targetSrc = computed(() => {
  if (!props.src) return ''
  // 无缩略图需求 → 原样返回
  if (!props.thumbSize || props.thumbSize <= 0) return props.src

  // 从 HTTP 封面 URL 提取 path 参数 → 构建 thumb:// 直读本地缩略图
  try {
    const u = new URL(props.src)
    const coverPath = u.searchParams.get('path')
    if (coverPath) {
      const basename = decodeURIComponent(coverPath).split(/[/\\]/).pop()
      if (basename) return `thumb://${props.thumbSize}/${basename}`
    }
  } catch {}

  // 回退：非 HTTP URL 或解析失败，走原 Flask HTTP
  const sep = props.src.includes('?') ? '&' : '?'
  return `${props.src}${sep}thumb=${props.thumbSize}`
})

// ======== 模块级：已加载缓存 + 共享 IO（按视口距离排序） ========
const _loadedSrcCache = new Map()
const ROOT_MARGIN = '800px'

let _sharedIO = null
function _getSharedIO() {
  if (!_sharedIO) {
    _sharedIO = new IntersectionObserver(
      entries => {
        const vc = window.innerHeight / 2
        // 按到视口中心的垂直距离排序，越近越先加载
        const candidates = []
        for (const entry of entries) {
          if (entry.isIntersecting && typeof entry.target._lc_cb === 'function') {
            const rect = entry.boundingClientRect
            candidates.push({ cb: entry.target._lc_cb, y: rect.top + rect.height / 2 })
          }
        }
        candidates.sort((a, b) => Math.abs(a.y - vc) - Math.abs(b.y - vc))
        for (const c of candidates) c.cb(true)
      },
      { rootMargin: ROOT_MARGIN }
    )
  }
  return _sharedIO
}
// ============================================================

const activeSrc = ref('')
const _resolvedFor = ref('')
let _unmounted = false

function _tryStartLoad(src) {
  if (!src || _unmounted || _resolvedFor.value !== src) return
  activeSrc.value = src
}

function _reset() {
  activeSrc.value = ''
  loaded.value = false
}

function _observe() {
  if (!elRef.value || !targetSrc.value) return
  // 命中缓存：0ms 直出
  if (_loadedSrcCache.has(targetSrc.value)) {
    activeSrc.value = targetSrc.value
    loaded.value = true
    return
  }
  const io = _getSharedIO()
  io.unobserve(elRef.value)
  elRef.value._lc_cb = (isIntersecting) => {
    if (!isIntersecting || _unmounted) return
    io.unobserve(elRef.value)
    delete elRef.value._lc_cb
    _tryStartLoad(targetSrc.value)
  }
  io.observe(elRef.value)
}

function _unobserve() {
  if (elRef.value) {
    _getSharedIO().unobserve(elRef.value)
    delete elRef.value._lc_cb
  }
}

onMounted(() => {
  _resolvedFor.value = targetSrc.value
  if (targetSrc.value) _observe()
})

onUnmounted(() => {
  _unmounted = true
  _unobserve()
  _reset()
})

watch(targetSrc, (newSrc) => {
  _reset()
  _resolvedFor.value = newSrc
  if (newSrc) _observe()
})

function onLoad() {
  loaded.value = true
  _loadedSrcCache.set(_resolvedFor.value, true)
}

function onError() {
  emit('error')
}
</script>

<style scoped>
.lazy-cover { opacity: 0; transition: opacity 0.15s; }
.lazy-cover.loaded { opacity: 1; }
</style>
