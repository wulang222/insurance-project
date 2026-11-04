import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Users from './views/Users.vue'
import Products from './views/Products.vue'
import Policies from './views/Policies.vue'
import Documents from './views/Documents.vue'
import { readAdminToken } from './storage'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { title: '登录' } },
    { path: '/', redirect: '/users' },
    { path: '/users', component: Users, meta: { title: '用户管理' } },
    { path: '/products', component: Products, meta: { title: '产品管理' } },
    { path: '/policies', component: Policies, meta: { title: '保单管理' } },
    { path: '/documents', component: Documents, meta: { title: '知识库管理' } }
  ]
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !readAdminToken()) {
    return '/login'
  }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '后台管理'} | 保险运营台`
})

export default router
