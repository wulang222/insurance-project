import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getUserInfo, logout as apiLogout } from '../api'

function readStorage(key, fallback = '') {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // 隐私模式或存储空间不足时仍允许当前会话继续使用。
  }
}

function removeStorage(key) {
  try {
    localStorage.removeItem(key)
  } catch {
    // 存储不可用时，内存状态仍会被清理。
  }
}

function readStoredUser() {
  try {
    return JSON.parse(readStorage('user', 'null'))
  } catch {
    removeStorage('user')
    return null
  }
}

export const useUserStore = defineStore('user', () => {
  const token = ref(readStorage('token'))
  const userInfo = ref(readStoredUser())

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
    writeStorage('token', tokenVal)
    writeStorage('user', JSON.stringify(user))
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const res = await getUserInfo()
      if (res.data) {
        userInfo.value = res.data
        writeStorage('user', JSON.stringify(res.data))
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
    removeStorage('token')
    removeStorage('user')
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
