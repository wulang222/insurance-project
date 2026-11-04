import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Users from './views/Users.vue'
import Products from './views/Products.vue'
import Policies from './views/Policies.vue'
import Documents from './views/Documents.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', redirect: '/users' },
    { path: '/users', component: Users },
    { path: '/products', component: Products },
    { path: '/policies', component: Policies },
    { path: '/documents', component: Documents }
  ]
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !localStorage.getItem('admin_token')) {
    return '/login'
  }
  return true
})

export default router
