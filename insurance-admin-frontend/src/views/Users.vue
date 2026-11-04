<script setup>
import { onMounted, ref } from 'vue'
import { kickUser, searchUsers } from '../api'
import AdminNav from '../components/AdminNav.vue'

const phoneNumber = ref('')
const nickName = ref('')
const page = ref({ totals: 0, totalPages: 0, list: [] })
const error = ref('')

async function load() {
  error.value = ''
  try {
    page.value = await searchUsers({
      phoneNumber: phoneNumber.value || null,
      nickName: nickName.value || null,
      pageNo: 1,
      pageSize: 10
    })
  } catch (err) {
    error.value = err.message
  }
}

async function kick(userId) {
  error.value = ''
  try {
    await kickUser(userId)
    await load()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="shell">
    <AdminNav />
    <main>
      <section class="panel">
        <h1>C 端用户</h1>
        <div class="row">
          <input v-model="phoneNumber" placeholder="手机号" />
          <input v-model="nickName" placeholder="昵称" />
          <button @click="load">筛选</button>
        </div>
        <p class="error">{{ error }}</p>
        <p>共 {{ page.totals }} 人，{{ page.totalPages }} 页</p>
        <table>
          <thead>
            <tr><th>用户 id</th><th>昵称</th><th>手机号</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="user in page.list" :key="user.userId">
              <td>{{ user.userId }}</td>
              <td>{{ user.nickName }}</td>
              <td>{{ user.phoneNumber }}</td>
              <td><button @click="kick(user.userId)">踢下线</button></td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</template>
