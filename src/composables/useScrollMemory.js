import { onActivated, nextTick } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

const scrollMap = {}

/**
 * 页面滚动位置记忆
 * 使用 onBeforeRouteLeave 在 DOM 被移除之前保存位置
 * @param {string} key - 唯一标识
 * @param {() => Element | null} getContainer - 返回滚动容器元素的函数
 */
export function useScrollMemory(key, getContainer) {
  onBeforeRouteLeave(() => {
    const el = getContainer()
    if (el) {
      scrollMap[key] = el.scrollTop
    }
  })

  onActivated(() => {
    if (scrollMap[key] !== undefined) {
      nextTick(() => {
        nextTick(() => {
          const el = getContainer()
          if (el && el.scrollHeight > 0) {
            el.scrollTop = scrollMap[key]
          }
        })
      })
    }
  })
}
