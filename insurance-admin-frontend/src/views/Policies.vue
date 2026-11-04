<script setup>
import { onMounted, reactive, ref } from 'vue'
import { listPolicies, savePolicy } from '../api'
import AdminNav from '../components/AdminNav.vue'

const form = reactive({
  userId: '',
  policyNo: '',
  productName: '',
  premium: 100,
  sumInsured: 100000,
  policyStatus: 1,
  startDate: '2026-01-01',
  endDate: '2027-01-01'
})
const userId = ref('')
const page = ref({ totals: 0, totalPages: 0, list: [] })
const error = ref('')

async function load() {
  error.value = ''
  try {
    page.value = await listPolicies({
      pageNo: 1,
      pageSize: 20,
      userId: userId.value ? Number(userId.value) : null
    })
  } catch (err) {
    error.value = err.message
  }
}

async function submit() {
  error.value = ''
  try {
    await savePolicy({ ...form, userId: Number(form.userId) })
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
        <h1>历史保单</h1>
        <div class="row">
          <input v-model="form.userId" placeholder="用户 id" />
          <input v-model="form.policyNo" placeholder="保单号" />
          <input v-model="form.productName" placeholder="产品名" />
          <input v-model.number="form.premium" type="number" placeholder="保费" />
          <input v-model.number="form.sumInsured" type="number" placeholder="保额" />
          <input v-model.number="form.policyStatus" type="number" placeholder="状态 1-4" />
          <input v-model="form.startDate" type="date" />
          <input v-model="form.endDate" type="date" />
          <button @click="submit">保存</button>
        </div>
      </section>
      <section class="panel">
        <div class="row">
          <input v-model="userId" placeholder="按用户 id 查看" />
          <button @click="load">查看</button>
        </div>
        <p class="error">{{ error }}</p>
        <table>
          <thead>
            <tr><th>保单号</th><th>用户</th><th>产品</th><th>保费</th><th>保额</th><th>状态</th><th>起止</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in page.list" :key="item.id">
              <td>{{ item.policyNo }}</td>
              <td>{{ item.userId }}</td>
              <td>{{ item.productName }}</td>
              <td>{{ item.premium }}</td>
              <td>{{ item.sumInsured }}</td>
              <td>{{ item.policyStatus }}</td>
              <td>{{ item.startDate }} ~ {{ item.endDate }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</template>
