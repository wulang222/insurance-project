import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { title: 'Insurance Chat - AI智能对话平台' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录 - Insurance Chat' }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('../views/Chat.vue'),
    meta: { title: '对话 - Insurance Chat', requiresAuth: true }
  },
  {
    path: '/chat/:sessionId',
    name: 'ChatSession',
    component: () => import('../views/Chat.vue'),
    meta: { title: '对话 - Insurance Chat', requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录重定向到登录页
router.beforeEach((to, from, next) => {
  document.title = to.meta.title || 'Insurance Chat'

  if (to.meta.requiresAuth) {
    const userStore = useUserStore()
    if (!userStore.isLoggedIn) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
  }
  next()
})

export default router
