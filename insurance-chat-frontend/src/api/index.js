/**
 * API 请求层 — 统一封装所有后端接口调用
 *
 * 请求链路: 前端 → 网关(127.0.0.1:18080) → bite-portal服务
 * 所有接口统一加 /portal 前缀，由网关路由到对应微服务
 */
import axios from 'axios'

const API_BASE_URL = import.meta.env.DEV ? '' : 'http://127.0.0.1:18080'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器：自动携带 token
api.interceptors.request.use(config => {
  const token = getStoredToken()
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
api.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code === 200000) {
      return res
    }
    return Promise.reject(new Error(res.msg || '请求失败'))
  },
  error => {
    if (error.response?.status === 401) {
      clearStoredSession()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ==================== 用户接口 ====================

/** 微信登录 */
export function loginByWechat(openId) {
  return api.post('/portal/user/login/wechat', { openId })
}

/** 发送手机验证码 */
export function sendPhoneCode(phone) {
  return api.get('/portal/user/send_code', { params: { phone } })
}

/** 手机验证码登录 */
export function loginByPhone(phone, code) {
  return api.post('/portal/user/login/code', { phone, code })
}

/** 发送邮箱验证码 */
export function sendEmailCode(email) {
  return api.get('/portal/user/email/send_code', { params: { email } })
}

/** 邮箱验证码登录 */
export function loginByEmail(email, code) {
  return api.post('/portal/user/login/email/code', { email, code })
}

/** 获取登录用户信息 */
export function getUserInfo() {
  return api.get('/portal/user/login_info/get')
}

/** 退出登录 */
export function logout() {
  return api.delete('/portal/user/logout')
}

// ==================== 聊天接口 ====================

/** 获取会话列表 */
export function getSessions() {
  return api.get('/portal/chat/sessions')
}

/** 删除会话 */
export function deleteSession(sessionId) {
  return api.delete(`/portal/chat/session/${sessionId}`)
}

/** 更新会话标题 */
export function updateSessionTitle(sessionId, title) {
  return api.put(`/portal/chat/session/${sessionId}/title`, null, { params: { title } })
}

/** 发送消息（非流式） */
export function sendMessage(data) {
  return api.post('/portal/chat/send', data)
}

/** 查询会话历史消息 */
export function queryMessages(data) {
  return api.post('/portal/chat/messages', data)
}

/** 流式发送消息 — 返回 EventSource URL */
export function getStreamUrl(data) {
  const token = getStoredToken()
  return {
    url: '/portal/chat/send/stream',
    token,
    body: data
  }
}

/**
 * 使用 fetch + ReadableStream 消费 POST SSE，保留后端标准事件名和数据结构。
 */
export async function streamMessage(data, { signal, onEvent }) {
  const token = getStoredToken()
  const response = await fetch(`${API_BASE_URL}/portal/chat/send/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(data),
    signal
  })

  if (response.status === 401) {
    clearStoredSession()
    window.location.assign('/login')
    throw new Error('登录状态已失效')
  }
  if (!response.ok || !response.body) {
    throw new Error('AI 服务暂时不可用')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const event = parseSseBlock(block)
      if (event) onEvent(event)
    }
    if (done) break
  }

  const trailing = parseSseBlock(buffer)
  if (trailing) onEvent(trailing)
}

function parseSseBlock(block) {
  if (!block.trim()) return null
  let type = 'message'
  let id = ''
  const dataLines = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) type = line.slice(6).trim()
    else if (line.startsWith('id:')) id = line.slice(3).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (dataLines.length === 0) return null
  const raw = dataLines.join('\n')
  let payload = raw
  try {
    payload = JSON.parse(raw)
  } catch {
    // SSE permits text payloads; callers receive them unchanged.
  }
  return { type, id, data: payload }
}

function getStoredToken() {
  try {
    return localStorage.getItem('token')
  } catch {
    return null
  }
}

function clearStoredSession() {
  try {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  } catch {
    // Private browsing/storage denial should not block re-authentication.
  }
}

export default api
