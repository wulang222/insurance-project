<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <aside class="chat-sidebar" :class="{ open: sidebarOpen }" aria-label="对话导航">
      <div class="sidebar-header">
        <div class="brand">
          <span class="brand-icon">B</span>
          Insurance Chat
        </div>
        <button class="btn-new-chat" @click="startNewChat">
          <span>＋</span> 新对话
        </button>
      </div>

      <!-- Session List -->
      <div class="session-list" v-if="sessions.length > 0">
        <div
          v-for="s in sessions"
          :key="s.sessionId"
          class="session-item"
          :class="{ active: currentSessionId === s.sessionId }"
        >
          <button
            class="session-select"
            :aria-current="currentSessionId === s.sessionId ? 'page' : undefined"
            @click="selectSession(s.sessionId)"
          >
            <span class="session-avatar">AI</span>
            <span class="session-info">
              <span class="session-title">{{ s.title || '新对话' }}</span>
              <span class="session-preview">{{ s.lastMessagePreview || '暂无消息' }}</span>
            </span>
            <span class="session-time">{{ formatTime(s.lastMessageTime) }}</span>
          </button>
          <button
            class="btn-delete-session"
            :aria-label="`删除对话：${s.title || '新对话'}`"
            @click="openDeleteDialog(s, $event)"
          >×</button>
        </div>
      </div>

      <div class="empty-sessions" v-else>
        <span class="icon">💬</span>
        <span>暂无对话记录</span>
        <span style="font-size:12px;margin-top:4px;">点击上方按钮开始新对话</span>
      </div>

      <!-- Footer -->
      <div class="sidebar-footer">
        <div class="user-avatar">{{ userStore.userName?.charAt(0) || 'U' }}</div>
        <span class="user-name">{{ userStore.userName }}</span>
        <button class="btn-logout" @click="handleLogout">退出</button>
      </div>
    </aside>

    <!-- Mobile sidebar overlay -->
    <button
      v-if="sidebarOpen"
      class="sidebar-overlay"
      aria-label="关闭对话导航"
      @click="sidebarOpen = false"
    ></button>

    <!-- Main Area -->
    <main class="chat-main">
      <!-- Mobile hamburger -->
      <button
        class="mobile-menu-btn"
        aria-label="打开对话导航"
        @click="sidebarOpen = !sidebarOpen"
        v-if="isMobile"
      >
        ☰
      </button>

      <!-- Welcome / Empty State -->
      <div class="chat-welcome" v-if="!currentSessionId && messages.length === 0">
        <div class="welcome-icon">✨</div>
        <h2>Hi，{{ userStore.userName }}</h2>
        <p>
          我是您的专属 AI 助手，可以帮您解答问题、推荐保险产品、查询知识等。
          请在下方输入您的问题开始对话。
        </p>
        <div class="suggestions">
          <button class="suggestion-card" @click="sendSuggestion('我想了解重疾险有哪些推荐？')">
            🏥 推荐适合我的重疾险
          </button>
          <button class="suggestion-card" @click="sendSuggestion('医疗险和重疾险有什么区别？')">
            📖 医疗险和重疾险的区别
          </button>
          <button class="suggestion-card" @click="sendSuggestion('我今年30岁，程序员，预算5000元，推荐什么保险？')">
            💰 根据我的情况推荐保险
          </button>
          <button class="suggestion-card" @click="sendSuggestion('请介绍一下养老保险的种类')">
            👴 养老保险有哪些种类
          </button>
        </div>
      </div>

      <section
        v-if="streamStages.length > 0"
        class="run-progress"
        :class="{ complete: !aiLoading && !streamError }"
        aria-label="分析进度"
      >
        <div class="run-progress-heading">
          <span class="run-pulse" aria-hidden="true"></span>
          <strong>{{ aiLoading ? '正在组织保障分析' : '本次分析轨迹' }}</strong>
          <span>{{ currentStage }}</span>
        </div>
        <ol>
          <li v-for="stage in streamStages" :key="stage.id">
            <span>{{ stage.label }}</span>
            <small v-if="stage.detail">{{ stage.detail }}</small>
          </li>
        </ol>
      </section>

      <div v-if="streamError" class="stream-error" role="alert">
        <span>{{ streamError }}</span>
        <button type="button" @click="retryLastMessage">重新发送</button>
      </div>

      <!-- Messages Area -->
      <div class="messages-area" ref="messagesArea" v-if="messages.length > 0 || aiLoading">
        <div class="messages-container">
          <div
            v-for="msg in messages"
            :key="msg.messageId"
            class="message-row"
            :class="msg.role"
          >
            <div class="message-avatar">
              {{ msg.role === 'assistant' ? 'AI' : (userStore.userName?.charAt(0) || 'U') }}
            </div>
            <div class="message-body">
              <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
              <div v-if="msg.metadata?.warnings?.length" class="message-warnings" role="status">
                <strong>信息提示</strong>
                <ul>
                  <li v-for="warning in msg.metadata.warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>
              <div v-if="msg.metadata?.requiredInput" class="required-input-card">
                <strong>需要您补充</strong>
                <p>{{ msg.metadata.requiredInput.question }}</p>
              </div>
              <details v-if="msg.metadata?.citations?.length" class="citation-panel">
                <summary>查看来源（{{ msg.metadata.citations.length }}）</summary>
                <article
                  v-for="citation in msg.metadata.citations"
                  :key="citation.citation_id"
                  class="citation-item"
                >
                  <strong>{{ citation.title }}</strong>
                  <span>
                    {{ citation.section || '原始条款' }}<template v-if="citation.page"> · 第 {{ citation.page }} 页</template>
                  </span>
                  <p>{{ citation.excerpt }}</p>
                  <code>{{ citation.citation_id }}</code>
                </article>
              </details>
              <div class="message-time">{{ formatTime(msg.createTime) }}</div>
            </div>
          </div>

          <!-- AI typing indicator -->
          <div v-if="aiLoading" class="message-row assistant">
            <div class="message-avatar">AI</div>
            <div class="message-body">
              <div class="message-content">
                <div class="loading-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <div class="input-container">
          <div class="input-box">
            <label class="sr-only" for="chat-input">输入保险问题</label>
            <textarea
              id="chat-input"
              ref="textareaRef"
              v-model="inputText"
              class="input-textarea resize-none"
              placeholder="输入您的问题..."
              :rows="1"
              :disabled="aiLoading"
              @keydown="handleTextareaKeydown"
              @input="autoResize"
            ></textarea>
            <button
              v-if="!aiLoading"
              class="btn-send"
              :disabled="!inputText.trim()"
              aria-label="发送消息"
              @click="handleSend"
            >
              ↑
            </button>
            <button
              v-else
              class="btn-stop"
              aria-label="停止接收回复"
              @click="stopStreaming"
            >
              ■
            </button>
          </div>
          <p class="input-hint">按 Enter 发送，Shift + Enter 换行；生成中可停止接收</p>
        </div>
      </div>
    </main>

    <div
      v-if="deleteDialog.open"
      class="dialog-backdrop"
      @keydown="handleDialogKeydown"
    >
      <section
        class="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
      >
        <h2 id="delete-dialog-title">删除这段对话？</h2>
        <p id="delete-dialog-description">
          “{{ deleteDialog.title }}”将从对话列表移除，当前版本暂不支持恢复。
        </p>
        <p v-if="deleteDialog.error" class="dialog-error" role="alert">{{ deleteDialog.error }}</p>
        <div class="dialog-actions">
          <button ref="deleteCancelRef" class="btn-dialog-neutral" :disabled="deleteDialog.busy" @click="closeDeleteDialog">
            保留对话
          </button>
          <button ref="deleteConfirmRef" class="btn-dialog-danger" :disabled="deleteDialog.busy" @click="confirmDeleteSession">
            {{ deleteDialog.busy ? '正在删除…' : '删除对话' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { getSessions, deleteSession, queryMessages, streamMessage } from '../api'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ==================== State ====================
const sessions = ref([])
const currentSessionId = ref('')
const messages = ref([])
const inputText = ref('')
const aiLoading = ref(false)
const sidebarOpen = ref(false)
const textareaRef = ref(null)
const messagesArea = ref(null)
const deleteCancelRef = ref(null)
const deleteConfirmRef = ref(null)
const streamStages = ref([])
const currentStage = ref('')
const streamError = ref('')
const lastSentText = ref('')
const deleteDialog = reactive({
  open: false,
  sessionId: '',
  title: '',
  busy: false,
  error: '',
  trigger: null
})
let streamController = null

const isMobile = computed(() => window.innerWidth <= 768)

// ==================== Lifecycle ====================
onMounted(async () => {
  await userStore.fetchUserInfo()
  await loadSessions()

  // 如果 URL 带有 sessionId，自动选中
  if (route.params.sessionId) {
    selectSession(route.params.sessionId)
  }
})

onBeforeUnmount(() => {
  streamController?.abort()
})

// ==================== Session Management ====================
async function loadSessions() {
  try {
    const res = await getSessions()
    sessions.value = res.data || []
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

function startNewChat() {
  streamController?.abort()
  currentSessionId.value = ''
  messages.value = []
  // 不使用 router.push，保持在 /chat 页面，只清空右侧
  inputText.value = ''
  streamStages.value = []
  currentStage.value = ''
  streamError.value = ''
  sidebarOpen.value = false
  nextTick(() => textareaRef.value?.focus())
}

function selectSession(sessionId) {
  currentSessionId.value = sessionId
  router.replace(`/chat/${sessionId}`)
  loadMessages(sessionId)
  sidebarOpen.value = false
}

function openDeleteDialog(session, event) {
  deleteDialog.open = true
  deleteDialog.sessionId = session.sessionId
  deleteDialog.title = session.title || '新对话'
  deleteDialog.error = ''
  deleteDialog.trigger = event.currentTarget
  nextTick(() => deleteCancelRef.value?.focus())
}

function closeDeleteDialog() {
  if (deleteDialog.busy) return
  deleteDialog.open = false
  nextTick(() => deleteDialog.trigger?.focus())
}

function handleDialogKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeDeleteDialog()
    return
  }
  if (event.key !== 'Tab') return
  const first = deleteCancelRef.value
  const last = deleteConfirmRef.value
  if (!first || !last) return
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

async function confirmDeleteSession() {
  if (deleteDialog.busy) return
  deleteDialog.busy = true
  deleteDialog.error = ''
  try {
    await deleteSession(deleteDialog.sessionId)
    sessions.value = sessions.value.filter(s => s.sessionId !== deleteDialog.sessionId)
    if (currentSessionId.value === deleteDialog.sessionId) {
      startNewChat()
    }
    deleteDialog.open = false
  } catch (e) {
    deleteDialog.error = '暂时无法删除，请检查网络后重试。'
  } finally {
    deleteDialog.busy = false
  }
}

// ==================== Messages ====================
async function loadMessages(sessionId) {
  try {
    const res = await queryMessages({ sessionId, pageNum: 1, pageSize: 100 })
    messages.value = (res.data || []).map(message => ({
      ...message,
      metadata: parseMetadata(message.metadataJson)
    }))
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error('加载消息失败', e)
    messages.value = []
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || aiLoading.value) return
  lastSentText.value = text
  streamError.value = ''
  streamStages.value = []
  currentStage.value = '正在连接分析服务'

  // 添加用户消息到界面
  const userMsg = {
    messageId: Date.now().toString(),
    sessionId: currentSessionId.value,
    role: 'user',
    content: text,
    messageType: 'text',
    createTime: new Date().toISOString()
  }
  messages.value.push(userMsg)
  inputText.value = ''
  autoResize()
  await nextTick()
  scrollToBottom()

  // 调用标准 SSE API；每个事件在 Java 层保持原始事件名和数据结构。
  aiLoading.value = true
  streamController = new AbortController()
  try {
    await streamMessage(
      {
        sessionId: currentSessionId.value || undefined,
        content: text
      },
      {
        signal: streamController.signal,
        onEvent: handleStreamEvent
      }
    )
    await loadSessions()
  } catch (e) {
    streamError.value = e.name === 'AbortError'
      ? '已停止接收本次回复。服务端可能仍在完成并保存分析。'
      : '分析服务暂时不可用，您的问题已保留，可以重新发送。'
  } finally {
    aiLoading.value = false
    streamController = null
    await nextTick()
    scrollToBottom()
    textareaRef.value?.focus()
  }
}

function handleStreamEvent(event) {
  const payload = event.data && typeof event.data === 'object' ? event.data : {}
  const label = payload.stage || stageLabel(event.type)
  if (label && event.type !== 'run.result' && event.type !== 'done') {
    currentStage.value = label
    streamStages.value.push({
      id: `${event.id || streamStages.value.length}-${event.type}`,
      label,
      detail: payload.agent || payload.route || ''
    })
  }
  if (payload.thread_id && !currentSessionId.value) {
    currentSessionId.value = payload.thread_id
    router.replace(`/chat/${payload.thread_id}`)
  }
  if (event.type === 'run.result') {
    const metadata = {
      runId: payload.run_id,
      status: payload.status,
      handledBy: payload.handled_by || [],
      citations: payload.citations || [],
      warnings: payload.warnings || [],
      requiredInput: payload.required_input || null,
      traceId: findRootTraceId(payload.trace, payload.run_id)
    }
    messages.value.push({
      messageId: payload.run_id || (Date.now() + 1).toString(),
      sessionId: payload.thread_id || currentSessionId.value,
      role: 'assistant',
      content: payload.answer || payload.required_input?.question || '本次分析没有生成可展示内容。',
      messageType: 'text',
      metadata,
      createTime: new Date().toISOString()
    })
    if (payload.status === 'failed') {
      streamError.value = '本次分析未完成，请稍后重新发送。'
    }
    nextTick(scrollToBottom)
  }
}

function stageLabel(type) {
  return {
    'run.started': '正在分析您的需求',
    'route.selected': '已确定处理路径',
    'agent.completed': '专业模块已完成',
    'run.interrupted': '需要补充信息',
    'run.completed': '分析完成',
    'run.failed': '分析未完成'
  }[type] || ''
}

function findRootTraceId(trace, fallback) {
  const root = trace?.spans?.find(span => String(span.name || '').startsWith('run '))
  return root?.span_id || fallback || ''
}

function handleTextareaKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  handleSend()
}

function stopStreaming() {
  streamController?.abort()
}

function retryLastMessage() {
  if (!lastSentText.value || aiLoading.value) return
  inputText.value = lastSentText.value
  handleSend()
}

function sendSuggestion(text) {
  inputText.value = text
  handleSend()
}

// ==================== Helpers ====================
const scrollToBottom = () => {
  nextTick(() => {
    const el = messagesArea.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

const autoResize = () => {
  nextTick(() => {
    const el = textareaRef.value
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    }
  })
}

const formatTime = (t) => {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const pad = n => String(n).padStart(2, '0')
  if (isToday) {
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const renderMarkdown = (text) => {
  if (!text) return ''
  try {
    return DOMPurify.sanitize(marked.parse(text))
  } catch {
    return DOMPurify.sanitize(text).replace(/\n/g, '<br/>')
  }
}

const parseMetadata = (raw) => {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

async function handleLogout() {
  await userStore.doLogout()
  router.push('/')
}
</script>

<style scoped>
.sidebar-overlay {
  display: none;
}
.mobile-menu-btn {
  display: none;
}

@media (max-width: 768px) {
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    z-index: 199;
  }
  .mobile-menu-btn {
    display: block;
    position: fixed;
    top: 12px;
    left: 12px;
    z-index: 50;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: white;
    border: 1px solid var(--border);
    font-size: 18px;
  }
}
</style>
