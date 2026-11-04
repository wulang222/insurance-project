import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getUserInfo, logout as apiLogout } from '../api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const userName = computed(() => {
    if (!userInfo.value) return ''
    return userInfo.value.nickname || userInfo.value.username || userInfo.value.phone || '用户'
  })
  const userAvatar = computed(() => {
    if (!userInfo.value) return ''
    return userInfo.value.avatar || ''
  })

  // 保存登录状态
  function setLogin(tokenVal, user) {
    token.value = tokenVal
    userInfo.value = user
    localStorage.setItem('token', tokenVal)
    localStorage.setItem('user', JSON.stringify(user))
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const res = await getUserInfo()
      if (res.data) {
        userInfo.value = res.data
        localStorage.setItem('user', JSON.stringify(res.data))
      }
    } catch (e) {
      console.error('获取用户信息失败', e)
    }
  }

  // 退出登录
  async function doLogout() {
    try {
      await apiLogout()
    } catch (e) {
      // 忽略退出接口错误
    }
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    userName,
    userAvatar,
    setLogin,
    fetchUserInfo,
    doLogout
  }
})
