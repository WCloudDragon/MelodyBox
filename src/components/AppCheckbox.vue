<template>
  <!-- 自研复选框：圆形 + 主题色 + 白色圆角对勾；
       按下缩小（同全屏歌词按压手感），松手经右键菜单同款过冲曲线回弹归位 -->
  <label class="app-checkbox" :class="{ 'is-checked': modelValue, 'is-disabled': disabled }">
    <input
      class="app-checkbox__input"
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="emit('update:modelValue', !modelValue)"
    />
    <span class="app-checkbox__box" aria-hidden="true">
      <svg class="app-checkbox__check" viewBox="0 0 12 10" fill="none">
        <!-- 对勾经光学修正：长臂右上端翘向圆的收窄区，几何居中会显得右挤；
             尖端下压左收 + 0.2px 左移，使两侧实测边距相等（约4.1px） -->
        <path
          d="M1.9 5.6 L4.5 8.2 L10 2.8"
          stroke="#fff"
          stroke-width="2.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </span>
    <span v-if="label" class="app-checkbox__label">{{ label }}</span>
    <slot />
  </label>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
</script>

<style scoped>
.app-checkbox {
  display: inline-flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}

/* 隐藏原生 input，仅保留可聚焦性与键盘语义 */
.app-checkbox__input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.app-checkbox__box {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin-top: 1px;
  border-radius: 50%;
  border: 1.5px solid var(--border-color);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  /* 松手回弹：右键菜单同款过冲曲线（放大后回弹归位） */
  transition: transform 0.32s cubic-bezier(0.34, 1.56, 0.64, 1),
    background-color 0.22s ease,
    border-color 0.22s ease;
}

/* 按下：快速缩小（同歌词行 :active 按压手感）；松手后走上面的回弹曲线 */
.app-checkbox:active .app-checkbox__box {
  transform: scale(0.82);
  transition: transform 0.12s ease-out;
}

.app-checkbox:hover:not(.is-checked) .app-checkbox__box {
  border-color: var(--accent-color);
}

.app-checkbox.is-checked .app-checkbox__box {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

/* 对勾：白色圆头描边，随选中弹性放大；-0.2px 为光学居中补偿 */
.app-checkbox__check {
  width: 11px;
  height: 9px;
  transform: translate(-0.2px, 0) scale(0);
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.app-checkbox.is-checked .app-checkbox__check {
  transform: translate(-0.2px, 0) scale(1);
}

/* 键盘聚焦可见环 */
.app-checkbox__input:focus-visible + .app-checkbox__box {
  box-shadow: 0 0 0 3px var(--accent-bg);
}

.app-checkbox__label {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}
.app-checkbox:hover .app-checkbox__label {
  color: var(--text-primary);
}

.app-checkbox.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.app-checkbox.is-disabled:active .app-checkbox__box {
  transform: none;
}
</style>
