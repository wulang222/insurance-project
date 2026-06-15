<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Header -->
      <div class="login-header">
        <div class="logo-icon">B</div>
        <h2>欢迎回来</h2>
        <p>登录后开始智能对话</p>
      </div>

      <!-- Tabs -->
      <div class="login-tabs">
        <button class="login-tab" :class="{ active: tab === 'phone' }" @click="tab = 'phone'">
          📱 手机登录
        </button>
        <button class="login-tab" :class="{ active: tab === 'email' }" @click="tab = 'email'">
          📧 邮箱登录
        </button>
        <button class="login-tab" :class="{ active: tab === 'wechat' }" @click="tab = 'wechat'">
          💬 微信登录
        </button>
      </div>

      <!-- Phone Login -->
      <form v-if="tab === 'phone'" @submit.prevent="handlePhoneLogin">
        <div class="form-group">
          <label class="form-label">手机号</label>
          <input v-model="phone" class="form-input" type="tel" placeholder="请输入手机号" maxlength="11" />
        </div>
        <div class="form-group">
          <label class="form-label">验证码</label>
          <div class="input-row">
            <input v-model="phoneCode" class="form-input" type="text" placeholder="请输入验证码" maxlength="6" />
            <button type="button" class="btn-code" :disabled="phoneCountdown > 0" @click="sendPhoneSms">
              {{ phoneCountdown > 0 ? `${phoneCountdown}s` : '获取验证码' }}
            </button>
          </div>
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button type="submit" class="btn-submit" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <!-- Email Login -->
      <form v-if="tab === 'email'" @submit.prevent="handleEmailLogin">
        <div class="form-group">
          <label class="form-label">邮箱地址</label>
          <input v-model="email" class="form-input" type="email" placeholder="请输入邮箱地址" />
        </div>
        <div class="form-group">
          <label class="form-label">验证码</label>
          <div class="input-row">
            <input v-model="emailCode" class="form-input" type="text" placeholder="请输入验证码" maxlength="6" />
            <button type="button" class="btn-code" :disabled="emailCountdown > 0" @click="sendEmailVerificationCode">
              {{ emailCountdown > 0 ? `${emailCountdown}s` : '获取验证码' }}
            </button>
          </div>
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button type="submit" class="btn-submit" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <!-- WeChat Login -->
      <div v-if="tab === 'wechat'" style="text-align:center;">
        <p style="color:var(--text-secondary);margin-bottom:16px;font-size:14px;">
          请使用微信扫描下方二维码登录
        </p>
        <div style="
          width:180px;height:180px;margin:0 auto 16px;
          background:var(--bg-page);border-radius:12px;
          display:flex;align-items:center;justify-content:center;
          font-size:48px;color:var(--text-muted);
        ">
          📱
        </div>
        <p style="color:var(--text-muted);font-size:12px;margin-bottom:16px;">
          微信登录需在微信客户端内打开或扫描小程序码
        </p>
        <div class="form-group">
          <label class="form-label">或输入微信OpenID（开发模式）</label>
          <input v-model="wechatOpenId" class="form-input" type="text" placeholder="请输入微信OpenID" />
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button class="btn-submit" :disabled="loading" @click="handleWechatLogin">
          {{ loading ? '登录中...' : '微信登录' }}
        </button>
      </div>

      <!-- Back -->
      <router-link to="/" class="login-back">← 返回首页</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'
import {
  sendPhoneCode,
  loginByPhone,
  sendEmailCode,
  loginByEmail,
  loginByWechat
} from '../api'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const tab = ref('phone')
const errorMsg = ref('')
const loading = ref(false)

// Phone
const phone = ref('')
const phoneCode = ref('')
const phoneCountdown = ref(0)

// Email
const email = ref('')
const emailCode = ref('')
const emailCountdown = ref(0)

// WeChat
const wechatOpenId = ref('')

// Send phone SMS
async function sendPhoneSms() {
  if (!phone.value || phone.value.length !== 11) {
    errorMsg.value = '请输入正确的手机号'
    return
  }
  errorMsg.value = ''
  try {
    await sendPhoneCode(phone.value)
    phoneCountdown.value = 60
    const timer = setInterval(() => {
      phoneCountdown.value--
      if (phoneCountdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) {
    errorMsg.value = e.message || '发送验证码失败'
  }
}

// Send email code
async function sendEmailVerificationCode() {
  if (!email.value || !email.value.includes('@')) {
    errorMsg.value = '请输入正确的邮箱地址'
    return
  }
  errorMsg.value = ''
  try {
    await sendEmailCode(email.value)
    emailCountdown.value = 60
    const timer = setInterval(() => {
      emailCountdown.value--
      if (emailCountdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) {
    errorMsg.value = e.message || '发送验证码失败'
  }
}

// Phone login
async function handlePhoneLogin() {
  if (!phone.value || !phoneCode.value) {
    errorMsg.value = '请输入手机号和验证码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await loginByPhone(phone.value, phoneCode.value)
    onLoginSuccess(res)
  } catch (e) {
    errorMsg.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

// Email login
async function handleEmailLogin() {
  if (!email.value || !emailCode.value) {
    errorMsg.value = '请输入邮箱和验证码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await loginByEmail(email.value, emailCode.value)
    onLoginSuccess(res)
  } catch (e) {
    errorMsg.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

// WeChat login
async function handleWechatLogin() {
  if (!wechatOpenId.value) {
    errorMsg.value = '请输入微信OpenID'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await loginByWechat(wechatOpenId.value)
    onLoginSuccess(res)
  } catch (e) {
    errorMsg.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

// Login success — API 返回 R<TokenVO>，其中 data.accessToken 为令牌
function onLoginSuccess(res) {
  // TokenVO: { accessToken, expires }
  const token = res.data?.accessToken || ''
  if (!token) {
    errorMsg.value = '登录失败：未获取到令牌'
    return
  }
  // 先保存 token（用户信息在 Chat 页面加载时通过 /login_info/get 获取）
  userStore.setLogin(token, null)
  const redirect = route.query.redirect || '/chat'
  router.push(redirect)
}
</script>
