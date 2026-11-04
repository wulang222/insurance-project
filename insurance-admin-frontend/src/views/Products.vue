<script setup>
import { onMounted, reactive, ref } from 'vue'
import { listProducts, saveProduct } from '../api'
import AdminNav from '../components/AdminNav.vue'

const form = reactive({
  productId: '',
  productName: '',
  insuranceType: '医疗险',
  minAge: 0,
  maxAge: 65,
  minPrice: 100,
  maxPrice: 2000,
  targetOccupations: '全部职业',
  description: '',
  active: true
})
const filter = reactive({ insuranceType: '', productId: '', active: '' })
const page = ref({ totals: 0, totalPages: 0, list: [] })
const error = ref('')

async function load() {
  error.value = ''
  try {
    page.value = await listProducts({
      pageNo: 1,
      pageSize: 20,
      insuranceType: filter.insuranceType || null,
      productId: filter.productId || null,
      active: filter.active === '' ? null : filter.active === 'true'
    })
  } catch (err) {
    error.value = err.message
  }
}

async function submit() {
  error.value = ''
  try {
    await saveProduct({ ...form })
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
        <h1>保险产品</h1>
        <div class="row">
          <input v-model="form.productId" placeholder="产品编号" />
          <input v-model="form.productName" placeholder="名称" />
          <input v-model="form.insuranceType" placeholder="险种" />
          <input v-model.number="form.minAge" type="number" placeholder="最小年龄" />
          <input v-model.number="form.maxAge" type="number" placeholder="最大年龄" />
          <input v-model.number="form.minPrice" type="number" placeholder="最低保费" />
          <input v-model.number="form.maxPrice" type="number" placeholder="最高保费" />
          <input v-model="form.targetOccupations" placeholder="职业" />
          <input v-model="form.description" placeholder="描述" />
          <label><input v-model="form.active" type="checkbox" /> 上架</label>
          <button @click="submit">保存</button>
        </div>
      </section>
      <section class="panel">
        <div class="row">
          <input v-model="filter.insuranceType" placeholder="按险种" />
          <input v-model="filter.productId" placeholder="按产品编号" />
          <select v-model="filter.active">
            <option value="">全部，含下架</option>
            <option value="true">只看上架</option>
            <option value="false">只看下架</option>
          </select>
          <button @click="load">查看</button>
        </div>
        <p class="error">{{ error }}</p>
        <table>
          <thead>
            <tr><th>编号</th><th>名称</th><th>险种</th><th>年龄</th><th>保费</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in page.list" :key="item.id">
              <td>{{ item.productId }}</td>
              <td>{{ item.productName }}</td>
              <td>{{ item.insuranceType }}</td>
              <td>{{ item.minAge }}-{{ item.maxAge }}</td>
              <td>{{ item.minPrice }}-{{ item.maxPrice }}</td>
              <td>{{ item.isActive === 1 ? '上架' : '下架' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</template>
