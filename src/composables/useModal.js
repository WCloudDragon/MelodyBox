import { reactive, inject, provide } from 'vue'

const MODAL_KEY = Symbol('modal')

export function createModalProvider() {
  let resolvePromise = null
  let rejectPromise = null

  const state = reactive({
    visible: false,
    title: '',
    message: '',
    mode: 'confirm', // 'confirm' | 'prompt' | 'alert'
    confirmText: '确认',
    cancelText: '取消',
    danger: false,
    inputType: 'text',
    inputPlaceholder: '',
    inputDefault: '',
    inputValidator: null,
  })

  function open(options) {
    Object.assign(state, {
      visible: false,
      title: '',
      message: '',
      mode: 'confirm',
      confirmText: '确认',
      cancelText: '取消',
      danger: false,
      inputType: 'text',
      inputPlaceholder: '',
      inputDefault: '',
      inputValidator: null,
    })
    Object.assign(state, options, { visible: true })

    return new Promise((resolve, reject) => {
      resolvePromise = resolve
      rejectPromise = reject
    })
  }

  function confirm(options) {
    const opts = typeof options === 'string'
      ? { message: options }
      : options
    return open({ mode: 'confirm', ...opts })
  }

  function prompt(options) {
    const opts = typeof options === 'string'
      ? { message: options }
      : options
    return open({ mode: 'prompt', ...opts })
  }

  function alert(options) {
    const opts = typeof options === 'string'
      ? { message: options }
      : options
    return open({ mode: 'alert', ...opts })
  }

  function handleConfirm(value) {
    state.visible = false
    if (resolvePromise) {
      resolvePromise(value)
      resolvePromise = null
    }
  }

  function handleCancel() {
    state.visible = false
    if (rejectPromise) {
      rejectPromise('cancel')
      rejectPromise = null
    }
  }

  const ctx = { state, confirm, prompt, alert, handleConfirm, handleCancel }
  provide(MODAL_KEY, ctx)
  return ctx
}

export function useModal() {
  const ctx = inject(MODAL_KEY)
  if (!ctx) {
    throw new Error('useModal() must be used within a component that has createModalProvider()')
  }
  return ctx
}
