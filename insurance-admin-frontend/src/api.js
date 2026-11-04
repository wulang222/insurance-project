import axios from 'axios'
import { clearAdminToken, readAdminToken } from './storage'

const http = axios.create({ baseURL: '/admin', timeout: 30000 })

http.interceptors.request.use((config) => {
  const token = readAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body.code !== 200000) {
      return Promise.reject(new Error(body.msg || '请求失败'))
    }
    return body.data
  },
  (error) => {
    if (error.response?.status === 401) {
      clearAdminToken()
      if (location.pathname !== '/login') {
        location.href = '/login'
      }
    }
    const message = error.response?.data?.msg || error.message
    return Promise.reject(new Error(message))
  }
)

export function login(phone, password) {
  return http.post('/sys_user/login/password', { phone, password })
}

export function searchUsers(payload) {
  return http.post('/app_user/list/search', payload)
}

export function kickUser(userId) {
  return http.post('/app_user/kick', { userId })
}

export function listProducts(payload) {
  return http.post('/product/list', payload)
}

export function saveProduct(payload) {
  return http.post('/product/save', payload)
}

export function listPolicies(payload) {
  return http.post('/policy/list', payload)
}

export function savePolicy(payload) {
  return http.post('/policy/save', payload)
}

export function listDocuments(payload) {
  return http.post('/knowledge/list', payload)
}

export function uploadDocument(formData) {
  return http.post('/knowledge/upload', formData)
}

export function replaceDocument(id, formData) {
  return http.post(`/knowledge/${id}/replace`, formData)
}

export function listChunks(id) {
  return http.get(`/knowledge/${id}/chunks`)
}
