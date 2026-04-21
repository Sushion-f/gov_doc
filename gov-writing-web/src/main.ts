import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
/** TinyMCE 自托管：注册 window.tinymce，避免 tinymce-vue 回退到 CDN */
import '@/views/chat/tinymce/boot'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/index.scss'

// 导入mock数据
import '@/mock'
import '@/permission'

const app = createApp(App)

app.use(ElementPlus)
app.use(router)

app.mount('#app')
