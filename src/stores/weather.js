import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const WEATHER_BASE = 'http://127.0.0.1:5000/api/weather'
const CACHE_KEY = 'melodybox_weather_cache'
const CACHE_TTL = 30 * 60 * 1000 // 30 分钟

export const useWeatherStore = defineStore('weather', () => {
  const weatherData = ref(null)
  const isLoading = ref(false)
  const isConfigured = ref(false)
  const error = ref(null)

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

  /** 加载天气数据 */
  async function loadWeather() {
    if (_loadFromCache()) return

    isLoading.value = true
    error.value = null

    try {
      const geo = await _getGeoPosition()
      let url = `${WEATHER_BASE}/current`
      if (geo) {
        url += `?lat=${geo.lat}&lon=${geo.lon}`
      }

      const res = await fetch(url)
      const data = await res.json()

      if (!res.ok) {
        if (data.configured === false) {
          isConfigured.value = false
          error.value = '未配置天气 API Key'
        } else {
          error.value = data.error || '天气获取失败'
        }
        return
      }

      weatherData.value = data
      isConfigured.value = true
      _saveToCache(data)
    } catch (e) {
      error.value = '网络请求失败'
    } finally {
      isLoading.value = false
    }
  }

  /** 清除缓存并重新加载 */
  function refreshWeather() {
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
