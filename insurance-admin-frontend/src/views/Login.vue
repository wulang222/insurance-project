<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import CryptoJS from 'crypto-js'
import { login } from '../api'
import { writeAdminToken } from '../storage'

const router = useRouter()
const phone = ref('')
const password = ref('')
const error = ref('')
const showPassword = ref(false)
const submitting = ref(false)

function encryptPassword(value) {
  const key = CryptoJS.enc.Utf8.parse('12345678abcdefgh')
  const encrypted = CryptoJS.AES.encrypt(CryptoJS.enc.Utf8.parse(value), key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7
  })
  return encrypted.ciphertext.toString(CryptoJS.enc.Hex)
}

async function submit() {
  if (submitting.value) return
  error.value = ''
  submitting.value = true
  try {
    const token = await login(phone.value, encryptPassword(password.value))
    writeAdminToken(token.accessToken)
    router.push('/users')
  } catch (err) {
    error.value = err.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main>
    <form class="panel login-panel" novalidate @submit.prevent="submit">
      <h1>超管登录</h1>
      <div class="login-fields">
        <label for="admin-phone">手机号</label>
        <input id="admin-phone" v-model="phone" inputmode="tel" autocomplete="username" />
        <label for="admin-password">密码</label>
        <div class="password-field">
          <input
            id="admin-password"
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
          />
          <button
            class="secondary-button"
            type="button"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            :aria-pressed="showPassword"
            @click="showPassword = !showPassword"
          >
            {{ showPassword ? '隐藏' : '显示' }}
          </button>
        </div>
        <button type="submit" :disabled="submitting">
          {{ submitting ? '登录中…' : '登录' }}
        </button>
      </div>
      <p class="error" role="alert" aria-live="polite">{{ error }}</p>
    </form>
  </main>
</template>
