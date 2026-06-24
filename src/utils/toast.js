/**
 * Toast 通知工具
 * 基于全局 ProgressPanel，无侵入式右下角提示
 */
import { addToast } from '@/stores/progress'

export function toastSuccess(msg) {
  addToast(msg, 'success')
}

export function toastWarning(msg) {
  addToast(msg, 'warning')
}

export function toastError(msg) {
  addToast(msg, 'error')
}

export function toastInfo(msg) {
  addToast(msg, 'info')
}

// 保持与 element-plus ElMessage 兼容的 API
export const ElMessage = {
  success: toastSuccess,
  warning: toastWarning,
  error: toastError,
  info: toastInfo
}
