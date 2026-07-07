import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const WEATHER_BASE = 'http://127.0.0.1:5000/api/weather'
const CACHE_KEY = 'melodybox_weather_cache'
const CACHE_TTL = 30 * 60 * 1000 // 30 分钟

// 天气代码 → 天气图标（使用 emoji）
const WEATHER_ICONS = {
  '100': '☀️', '150': '☀️', '153': '☀️',           // 晴
  '101': '⛅', '102': '⛅', '103': '⛅',              // 多云/少云
  '104': '☁️',                                        // 阴
  '300': '🌦️', '301': '🌧️', '305': '🌧️', '309': '🌧️', // 小雨
  '302': '⛈️', '303': '⛈️', '304': '⛈️',             // 暴雨/雷阵雨
  '306': '🌧️', '307': '🌧️', '308': '🌧️',             // 中大雨
  '310': '🌧️', '311': '🌧️', '312': '🌧️', '313': '🌧️',
  '350': '🌧️', '351': '🌧️',
  '400': '🌨️', '401': '❄️', '402': '❄️', '403': '❄️', // 雪
  '404': '🌨️', '405': '🌨️', '406': '🌨️', '407': '🌨️',
  '408': '❄️', '409': '❄️', '410': '❄️',
  '456': '🌨️', '457': '🌨️',
  '500': '🌫️', '501': '🌫️', '502': '🌫️',           // 雾/霾
  '503': '🌪️', '504': '🌪️',                          // 沙尘
  '507': '🌪️', '508': '🌪️',
  '509': '🌫️', '510': '🌫️', '514': '🌫️', '515': '🌫️',
  '900': '🔥',                                        // 炎热
  '901': '🥶',                                        // 寒冷
}

export const useWeatherStore = defineStore('weather', () => {
  const weatherData = ref(null)
  const isLoading = ref(false)
  const isConfigured = ref(false)
  const error = ref(null)

  const city = computed(() => weatherData.value?.location?.name || '')
  const temp = computed(() => weatherData.value?.weather?.temp || '')
  const weatherText = computed(() => weatherData.value?.weather?.text || '')
  const weatherIcon = computed(() => {
    const code = weatherData.value?.weather?.code || ''
    return WEATHER_ICONS[code] || '🌤️'
  })
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

  return {
    weatherData,
    isLoading,
    isConfigured,
    error,
    city,
    temp,
    weatherText,
    weatherIcon,
    suggestion,
    mood,
    moodLabel,
    loadWeather,
    refreshWeather,
  }
})
