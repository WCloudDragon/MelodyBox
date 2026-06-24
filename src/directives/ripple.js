/**
 * v-ripple 指令 —— Material Design 涟漪效果
 * 鼠标按下时展开波纹，松开后渐隐消失，长按期间持续可见。
 * 用法: <div v-ripple /> 或 <div v-ripple="{ color: 'rgba(255,255,255,0.15)' }" />
 */
function createRipple(e, el, opts = {}) {
  const color = opts.color || getComputedStyle(document.documentElement).getPropertyValue('--ripple-color').trim() || 'rgba(255, 255, 255, 0.12)'
  const size = Math.max(el.clientWidth, el.clientHeight)

  const rect = el.getBoundingClientRect()
  const x = e.clientX - rect.left - size / 2
  const y = e.clientY - rect.top - size / 2

  const ripple = document.createElement('span')
  ripple.className = 'v-ripple__wave'
  ripple.style.cssText = `
    position: absolute;
    left: ${x}px;
    top: ${y}px;
    width: ${size}px;
    height: ${size}px;
    border-radius: 50%;
    background: ${color};
    pointer-events: none;
    transform: scale(0);
    transition: transform 500ms ease-out, opacity 500ms ease-out;
    opacity: 1;
  `
  el.appendChild(ripple)

  // 下一帧展开波纹
  requestAnimationFrame(() => {
    ripple.style.transform = 'scale(2.5)'
  })

  return ripple
}

function fadeOutRipple(ripple) {
  ripple.style.opacity = '0'
  ripple.addEventListener('transitionend', () => {
    ripple.remove()
  }, { once: true })
}

const rippleDirective = {
  mounted(el, binding) {
    const style = getComputedStyle(el)
    if (style.position === 'static') {
      el.style.position = 'relative'
    }
    if (style.overflow !== 'hidden' && style.overflow !== 'clip') {
      el.style.overflow = 'hidden'
    }

    let activeRipple = null

    function onMouseDown(e) {
      if (e.button !== 0) return
      activeRipple = createRipple(e, el, binding.value)
    }

    function onMouseUp() {
      if (activeRipple) {
        fadeOutRipple(activeRipple)
        activeRipple = null
      }
    }

    function onMouseLeave() {
      if (activeRipple) {
        fadeOutRipple(activeRipple)
        activeRipple = null
      }
    }

    el.addEventListener('mousedown', onMouseDown)
    el.addEventListener('mouseup', onMouseUp)
    el.addEventListener('mouseleave', onMouseLeave)

    // 全局 mouseup：鼠标拖到元素外松开
    function onGlobalMouseUp(e) {
      if (activeRipple && e.target !== el && !el.contains(e.target)) {
        fadeOutRipple(activeRipple)
        activeRipple = null
      }
    }
    document.addEventListener('mouseup', onGlobalMouseUp)

    el.__rippleCleanup = () => {
      el.removeEventListener('mousedown', onMouseDown)
      el.removeEventListener('mouseup', onMouseUp)
      el.removeEventListener('mouseleave', onMouseLeave)
      document.removeEventListener('mouseup', onGlobalMouseUp)
    }
  },

  unmounted(el) {
    if (el.__rippleCleanup) {
      el.__rippleCleanup()
      delete el.__rippleCleanup
    }
  }
}

export default rippleDirective
