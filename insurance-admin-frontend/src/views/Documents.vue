<script setup>
import { onMounted, ref } from 'vue'
import { listChunks, listDocuments, replaceDocument, uploadDocument } from '../api'
import AdminNav from '../components/AdminNav.vue'

const title = ref('')
const productId = ref('')
const file = ref(null)
const page = ref({ totals: 0, totalPages: 0, list: [] })
const chunks = ref([])
const error = ref('')

function choose(event) {
  file.value = event.target.files[0] || null
}

async function load() {
  error.value = ''
  try {
    page.value = await listDocuments({ pageNo: 1, pageSize: 20 })
  } catch (err) {
    error.value = err.message
  }
}

async function upload(documentId) {
  error.value = ''
  if (!file.value) {
    error.value = '请选择 pdf、docx、md 或 txt'
    return
  }
  const form = new FormData()
  form.append('file', file.value)
  form.append('title', title.value)
  form.append('productId', productId.value)
  try {
    if (documentId) {
      await replaceDocument(documentId, form)
    } else {
      await uploadDocument(form)
    }
    await load()
  } catch (err) {
    error.value = err.message
  }
}

async function openChunks(id) {
  error.value = ''
  try {
    chunks.value = await listChunks(id)
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
        <h1>知识文档</h1>
        <div class="row">
          <input v-model="title" placeholder="标题" />
          <input v-model="productId" placeholder="产品编号，可选" />
          <input type="file" accept=".pdf,.docx,.md,.txt" @change="choose" />
          <button @click="upload()">上传</button>
        </div>
        <p class="error">{{ error }}</p>
      </section>
      <section class="panel">
        <table>
          <thead>
            <tr><th>标题</th><th>产品</th><th>状态</th><th>分块</th><th>校验和</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in page.list" :key="item.id">
              <td>{{ item.title }}</td>
              <td>{{ item.productId }}</td>
              <td><span class="badge" :class="item.status">{{ item.status }}</span></td>
              <td>{{ item.chunkCount }}</td>
              <td>{{ item.checksum }}</td>
              <td>
                <button @click="openChunks(item.id)">查看分块</button>
                <button @click="upload(item.id)">替换</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="page.list.some((item) => ['processing', 'available', 'failed'].includes(item.status))">
          状态包含 processing、available、failed
        </p>
        <article v-for="(chunk, index) in chunks" :key="index">
          <p>{{ chunk.text }}</p>
          <pre>{{ chunk.metadata }}</pre>
        </article>
      </section>
    </main>
  </div>
</template>
