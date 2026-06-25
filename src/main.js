import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import ripple from './directives/ripple'
import './assets/styles/global.css'

const app = createApp(App)

app.directive('ripple', ripple)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: undefined })
app.mount('#app')

// 修复 Electron 下鼠标快速移出窗口时 :hover 状态残留的 Chromium bug
window.addEventListener('mouseout', (e) => {
  if (!e.relatedTarget || e.relatedTarget.nodeName === 'HTML') {
    document.body.style.pointerEvents = 'none'
    document.body.offsetHeight // 强制重排清空 hover
    document.body.style.pointerEvents = ''
  }
})
