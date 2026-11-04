<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import CryptoJS from 'crypto-js'
import { login } from '../api'

const router = useRouter()
const phone = ref('')
const password = ref('')
const error = ref('')

function encryptPassword(value) {
  const key = CryptoJS.enc.Utf8.parse('12345678abcdefgh')
  const encrypted = CryptoJS.AES.encrypt(CryptoJS.enc.Utf8.parse(value), key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7
  })
  return encrypted.ciphertext.toString(CryptoJS.enc.Hex)
}

async function submit() {
  error.value = ''
  try {
    const token = await login(phone.value, encryptPassword(password.value))
    localStorage.setItem('admin_token', token.accessToken)
    router.push('/users')
  } catch (err) {
    error.value = err.message
  }
}
</script>

<template>
  <main>
    <form class="panel" @submit.prevent="submit">
      <h1>超管登录</h1>
      <div class="row">
        <input v-model="phone" placeholder="手机号" />
        <input v-model="password" type="password" placeholder="密码" />
        <button type="submit">登录</button>
      </div>
      <p class="error">{{ error }}</p>
    </form>
  </main>
</template>
