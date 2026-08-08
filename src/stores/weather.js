import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiUrl } from '@/config/api'
const CACHE_KEY = 'melodybox_weather_cache'
const CACHE_TTL = 30 * 60 * 1000 // 30 分钟

// 失败自动重试：退避间隔（毫秒），共 5 次，总时长约 8.5 分钟
const RETRY_SCHEDULE = [10_000, 30_000, 60_000, 120_000, 300_000]

export const useWeatherStore = defineStore('weather', () => {
  const weatherData = ref(null)
  const isLoading = ref(false)
  const isConfigured = ref(false)
  const error = ref(null)
  // 静默自动重试状态（仅显示"自动重试中 n/5"小字，不打扰用户）
  const retrying = ref(false)
  const retryCount = ref(0)
  const retryTotal = ref(RETRY_SCHEDULE.length)
  let retryTimer = null

  const city = computed(() => weatherData.value?.location?.name || '')
  const temp = computed(() => weatherData.value?.weather?.temp || '')
  const weatherText = computed(() => weatherData.value?.weather?.text || '')
  const suggestion = computed(() => weatherData.value?.recommendation?.suggestion || '')
  const mood = computed(() => weatherData.value?.recommendation?.mood || 'calm')
  const moodLabel = computed(() => weatherData.value?.recommendation?.moodLabel || '舒缓')

  /** 尝试从 localStorage 恢复缓存 */
  function _loadFromCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY)
      if (!raw) return false
      const cached = JSON.parse(raw)
      if (cached.expireAt > Date.now()) {
        weatherData.value = cached.data
        isConfigured.value = true
        return true
      }
    } catch {}
    return false
  }

  /** 缓存到 localStorage */
  function _saveToCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        data,
        expireAt: Date.now() + CACHE_TTL,
      }))
    } catch {}
  }

  /** 请求浏览器 Geolocation 定位（返回 Promise） */
  function _getGeoPosition() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        resolve(null)
        return
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => resolve(null),
        { timeout: 5000, maximumAge: 600000 }
      )
    })
  }

  /** 清理重试状态（成功/配置缺失/手动刷新时调用） */
  function _clearRetry() {
    if (retryTimer) { clearTimeout(retryTimer); retryTimer = null }
    retrying.value = false
    retryCount.value = 0
  }

  /** 安排下一次静默重试；全部用尽时不安排（error 由调用方置位） */
  function _scheduleRetry() {
    if (retryCount.value >= RETRY_SCHEDULE.length) {
      retrying.value = false
      return
    }
    retrying.value = true
    const delay = RETRY_SCHEDULE[retryCount.value]
    retryCount.value += 1
    retryTimer = setTimeout(() => {
      retryTimer = null
      loadWeather({ silentRetry: true })
    }, delay)
  }

  /** 加载天气数据；瞬时失败自动静默重试，全部结束才进入可手动重试状态 */
  async function loadWeather(opts = {}) {
    const silentRetry = !!opts.silentRetry
    // 已有重试在途：其他触发源（30 分钟定时器）不叠加
    if (!silentRetry && retryTimer) return

    if (_loadFromCache()) {
      _clearRetry()
      return
    }

    if (!silentRetry) {
      isLoading.value = true
      error.value = null
    }

    try {
      const geo = await _getGeoPosition()
      let url = `${apiUrl('/api/weather/current')}`
      if (geo) {
        url += `?lat=${geo.lat}&lon=${geo.lon}`
      }

      const res = await fetch(url)
      const data = await res.json()

      if (!res.ok) {
        if (data.configured === false) {
          // 配置缺失：不是瞬时故障，不重试
          _clearRetry()
          isConfigured.value = false
          error.value = '未配置天气 API Key'
        } else {
          // 瞬时故障：先静默重试，用尽后才提示
          const msg = data.error || '天气获取失败'
          if (retryCount.value < RETRY_SCHEDULE.length) {
            _scheduleRetry()
          } else {
            retrying.value = false
            error.value = msg
          }
        }
        return
      }

      weatherData.value = data
      isConfigured.value = true
      error.value = null
      _saveToCache(data)
      _clearRetry()
    } catch (e) {
      // 网络异常同样按瞬时故障处理
      if (retryCount.value < RETRY_SCHEDULE.length) {
        _scheduleRetry()
      } else {
        retrying.value = false
        error.value = '网络请求失败'
      }
    } finally {
      if (!silentRetry) isLoading.value = false
    }
  }

  /** 手动刷新（清除缓存 + 取消在途重试 + 立即加载） */
  function refreshWeather() {
    _clearRetry()
    localStorage.removeItem(CACHE_KEY)
    loadWeather()
  }

  // 初始化时尝试加载
  loadWeather()

  // 每 30 分钟自动刷新天气数据
  const _refreshTimer = setInterval(() => {
    localStorage.removeItem(CACHE_KEY)
    loadWeather()
  }, CACHE_TTL)

  return {
    weatherData,
    isLoading,
    isConfigured,
    error,
    retrying,
    retryCount,
    retryTotal,
    city,
    temp,
    weatherText,
    suggestion,
    mood,
    moodLabel,
    loadWeather,
    refreshWeather,
  }
})
