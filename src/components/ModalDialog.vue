<template>
  <teleport to="body">
    <!-- 背景遮罩 -->
    <Transition name="modal-backdrop">
      <div v-if="visible" class="modal-backdrop" @click="handleBackdrop" />
    </Transition>
    <!-- 弹窗主体 -->
    <Transition name="modal-dialog" @after-leave="emitClosed">
      <div v-if="visible" class="modal-dialog" @click.stop>
        <div class="modal-header">
          <h3>{{ title }}</h3>
        </div>

        <template v-if="mode === 'prompt'">
          <p class="modal-message" v-if="message">{{ message }}</p>
          <input
            ref="inputRef"
            v-model="inputValue"
            class="modal-input"
            :type="inputType"
            :placeholder="inputPlaceholder"
            @keyup.enter="handleConfirm"
            @keyup.escape="handleCancel"
          />
          <p v-if="inputError" class="modal-input-error">{{ inputError }}</p>
        </template>

        <template v-else>
          <p class="modal-message" v-if="message">{{ message }}</p>
          <slot />
        </template>

        <div class="modal-footer">
          <button
            v-if="showCancel"
            class="modal-btn modal-btn--cancel"
            @click="handleCancel"
          >{{ cancelText }}</button>
          <button
            class="modal-btn modal-btn--confirm"
            :class="{ 'modal-btn--danger': danger }"
            @click="handleConfirm"
          >{{ confirmText }}</button>
        </div>
      </div>
    </Transition>
  </teleport>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'

const props = defineProps({
  visible: Boolean,
  title: { type: String, default: '' },
  message: { type: String, default: '' },
  mode: { type: String, default: 'confirm' }, // 'confirm' | 'prompt' | 'alert'
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  danger: { type: Boolean, default: false },
  inputType: { type: String, default: 'text' },
  inputPlaceholder: { type: String, default: '' },
  inputDefault: { type: String, default: '' },
  inputValidator: { type: Function, default: null },
})
const emit = defineEmits(['confirm', 'cancel', 'closed'])

const inputRef = ref(null)
const inputValue = ref('')
const inputError = ref('')

const showCancel = computed(() => props.mode !== 'alert')

watch(() => props.visible, async (v) => {
  if (v) {
    inputValue.value = props.inputDefault || ''
    inputError.value = ''
    await nextTick()
    inputRef.value?.focus()
  }
})

function handleConfirm() {
  if (props.mode === 'prompt' && props.inputValidator) {
    const result = props.inputValidator(inputValue.value)
    if (result !== true) {
      inputError.value = result
      return
    }
  }
  emit('confirm', props.mode === 'prompt' ? inputValue.value : undefined)
}

function handleCancel() {
  emit('cancel')
}

function handleBackdrop() {
  if (props.mode !== 'alert') {
    emit('cancel')
  }
}

function emitClosed() {
  emit('closed')
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(0, 0, 0, 0.45);
}

.modal-dialog {
  position: fixed;
  z-index: 10001;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 400px;
  max-width: 90vw;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
  padding: 24px;
}

.modal-header {
  margin-bottom: 12px;
}

.modal-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.modal-message {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0 0 16px;
  white-space: pre-line;
}

.modal-input {
  width: 100%;
  padding: 10px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
  margin-bottom: 4px;
}

.modal-input:focus {
  border-color: var(--accent-color);
}

.modal-input::placeholder {
  color: var(--text-tertiary);
}

.modal-input-error {
  font-size: 12px;
  color: #f56c6c;
  margin: 4px 0 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.modal-btn {
  padding: 8px 20px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: opacity 0.2s;
}

.modal-btn:active {
  opacity: 0.8;
}

.modal-btn--cancel {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.modal-btn--cancel:hover {
  background: var(--hover-bg-strong);
  color: var(--text-primary);
}

.modal-btn--confirm {
  background: var(--accent-color);
  color: #fff;
}

.modal-btn--confirm:hover {
  background: #5558e6;
}

.modal-btn--danger {
  background: #ef4444;
}

.modal-btn--danger:hover {
  background: #dc2626;
}

/* ===== 进场：弹性缩放 + 模糊收拢 + 渐显（照搬右键菜单 ctx-menu-blur） ===== */
.modal-dialog-enter-active {
  animation: modal-pop 0.38s cubic-bezier(0.34, 1.56, 0.64, 1);
  transition: opacity 0.28s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.28s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

.modal-dialog-enter-from {
  opacity: 0;
  filter: blur(6px);
}

@keyframes modal-pop {
  0%   { transform: translate(-50%, -50%) scale(0.85); }
  100% { transform: translate(-50%, -50%) scale(1); }
}

/* ===== 离场：缩小 + 渐隐 + 模糊扩散 ===== */
.modal-dialog-leave-active {
  transition: opacity 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              filter 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              transform 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}

.modal-dialog-leave-to {
  opacity: 0;
  filter: blur(6px);
  transform: translate(-50%, -50%) scale(0.85);
}

/* ===== 背景遮罩淡入淡出 ===== */
.modal-backdrop-enter-active { transition: opacity 0.2s ease; }
.modal-backdrop-leave-active { transition: opacity 0.2s ease; }
.modal-backdrop-enter-from,
.modal-backdrop-leave-to { opacity: 0; }
</style>
