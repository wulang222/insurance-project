export function readAdminToken() {
  try {
    return localStorage.getItem('admin_token') || ''
  } catch {
    return ''
  }
}

export function writeAdminToken(token) {
  try {
    localStorage.setItem('admin_token', token)
  } catch {
    // 当前页面仍可给出登录结果，路由守卫会在存储不可用时要求重新登录。
  }
}

export function clearAdminToken() {
  try {
    localStorage.removeItem('admin_token')
  } catch {
    // 存储不可用时无需额外清理。
  }
}
