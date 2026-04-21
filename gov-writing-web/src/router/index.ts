import { createRouter, createWebHashHistory } from 'vue-router'
import MainLayout from '../layout/MainLayout.vue'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: MainLayout,
      children: [
        {
          path: '',
          redirect: '/chat'
        },
        {
          path: 'chat',
          name: 'chat',
          component: () => import('../views/chat/index.vue')
        },
      ]
    }
  ]
})

export default router
