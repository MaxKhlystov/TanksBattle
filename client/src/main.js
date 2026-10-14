import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
import App from './App.vue'
import router from './router'
import "bootstrap/dist/css/bootstrap.css"
import "./styles/style.css"

// --- Конфиг axios (правка H3: единая точка для CSRF и cookies) ---
axios.defaults.withCredentials = true
axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'
// ------------------------------------------------------------------

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')