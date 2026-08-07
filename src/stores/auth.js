import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiUrl, authHeaders as makeAuthHeaders } from '@/config/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref('')
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const membershipType = computed(() => user.value?.membership_type || 'free')

  // 从 localStorage 恢复登录态
  function loadFromStorage() {
    try {
      const raw = localStorage.getItem('auth-token')
      if (raw) token.value = raw
      const userRaw = localStorage.getItem('auth-user')
      if (userRaw) user.value = JSON.parse(userRaw)
    } catch {}
  }

  function saveToStorage() {
    if (token.value) {
      localStorage.setItem('auth-token', token.value)
      localStorage.setItem('auth-user', JSON.stringify(user.value))
    } else {
      localStorage.removeItem('auth-token')
      localStorage.removeItem('auth-user')
    }
  }

  async function login(username, password) {
    const res = await fetch(apiUrl('/api/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '登录失败')
    token.value = data.token
    user.value = data.user
    saveToStorage()
    return data
  }

  async function register(username, password, email = '') {
    const res = await fetch(apiUrl('/api/auth/register'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, email })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '注册失败')
    return data
  }

  async function fetchProfile() {
    if (!token.value) return
    try {
      const res = await fetch(apiUrl('/api/auth/profile'), {
        headers: makeAuthHeaders(token.value)
      })
      if (!res.ok) throw new Error('登录已过期')
      user.value = await res.json()
      saveToStorage()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    saveToStorage()
  }

  async function changePassword(oldPassword, newPassword) {
    const res = await fetch(apiUrl('/api/auth/password'), {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...makeAuthHeaders(token.value)
      },
      body: JSON.stringify({ oldPassword, newPassword })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '修改失败')
    return data
  }

  async function deleteAccount(password) {
    const res = await fetch(apiUrl('/api/auth/account'), {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...makeAuthHeaders(token.value)
      },
      body: JSON.stringify({ password })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '注销失败')
    logout()
    return data
  }

  function authHeaders() {
    return makeAuthHeaders(token.value)
  }

  loadFromStorage()

  return {
    user, token, isLoggedIn, isAdmin, membershipType,
    login, register, fetchProfile, logout,
    changePassword, deleteAccount, authHeaders
  }
})
