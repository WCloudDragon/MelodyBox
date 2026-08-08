import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiUrl, authHeaders as makeAuthHeaders } from '@/config/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref('')
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const membershipType = computed(() => user.value?.membership_type || 'free')

  // 会员体系（1.1：客户端模拟购买 + 管理端调价上下架）
  const membershipStatus = ref({
    membership_type: 'free', membership_expire: null, is_vip: false, is_svip: false,
  })
  const membershipPlans = ref([])
  const isVip = computed(() => user.value?.role === 'admin' || membershipStatus.value.is_vip)
  const membershipExpire = computed(() => membershipStatus.value.membership_expire)

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
    fetchMembership()
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
      fetchMembership()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    membershipStatus.value = { membership_type: 'free', membership_expire: null, is_vip: false, is_svip: false }
    membershipPlans.value = []
    saveToStorage()
  }

  /** 拉取当前会员状态（过期自动降级由后端处理） */
  async function fetchMembership() {
    if (!token.value) return
    try {
      const res = await fetch(apiUrl('/api/auth/membership/status'), {
        headers: makeAuthHeaders(token.value),
      })
      if (res.ok) {
        membershipStatus.value = await res.json()
        if (user.value && !user.value.membership_type) {
          user.value = { ...user.value, membership_type: membershipStatus.value.membership_type }
        }
      }
    } catch {}
  }

  /** 拉取在售会员方案 */
  async function loadPlans() {
    try {
      const res = await fetch(apiUrl('/api/auth/membership/plans'))
      if (res.ok) {
        const data = await res.json()
        membershipPlans.value = data.plans || []
      }
    } catch {}
  }

  /** 模拟购买会员（后端模拟支付成功） */
  async function purchasePlan(planId) {
    const res = await fetch(apiUrl('/api/auth/membership/purchase'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...makeAuthHeaders(token.value) },
      body: JSON.stringify({ plan_id: planId }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '购买失败')
    await fetchMembership()
    await fetchProfile()
    return data
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
  loadPlans()
  fetchMembership()

  return {
    user, token, isLoggedIn, isAdmin, membershipType,
    membershipStatus, membershipPlans, isVip, membershipExpire,
    login, register, fetchProfile, logout,
    changePassword, deleteAccount, authHeaders,
    fetchMembership, loadPlans, purchasePlan,
  }
})
