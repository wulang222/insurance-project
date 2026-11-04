<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <aside class="chat-sidebar" :class="{ open: sidebarOpen }">
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
          @click="selectSession(s.sessionId)"
        >
          <div class="session-avatar">AI</div>
          <div class="session-info">
            <div class="session-title">{{ s.title || '新对话' }}</div>
            <div class="session-preview">{{ s.lastMessagePreview || '暂无消息' }}</div>
          </div>
          <span class="session-time">{{ formatTime(s.lastMessageTime) }}</span>
          <button class="btn-delete-session" @click.stop="handleDeleteSession(s.sessionId)" title="删除">×</button>
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
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <!-- Main Area -->
    <main class="chat-main">
      <!-- Mobile hamburger -->
      <button class="mobile-menu-btn" @click="sidebarOpen = !sidebarOpen" v-if="isMobile">
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
          <div class="suggestion-card" @click="sendSuggestion('我想了解重疾险有哪些推荐？')">
            🏥 推荐适合我的重疾险
          </div>
          <div class="suggestion-card" @click="sendSuggestion('医疗险和重疾险有什么区别？')">
            📖 医疗险和重疾险的区别
          </div>
          <div class="suggestion-card" @click="sendSuggestion('我今年30岁，程序员，预算5000元，推荐什么保险？')">
            💰 根据我的情况推荐保险
          </div>
          <div class="suggestion-card" @click="sendSuggestion('请介绍一下养老保险的种类')">
            👴 养老保险有哪些种类
          </div>
        </div>
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
            <textarea
              ref="textareaRef"
              v-model="inputText"
              class="input-textarea"
              placeholder="输入您的问题..."
              :rows="1"
              @keydown.enter.exact="handleSend"
              @input="autoResize"
            ></textarea>
            <button
              class="btn-send"
              :class="{ sending: aiLoading }"
              :disabled="!inputText.trim() || aiLoading"
              @click="handleSend"
            >
              ↑
            </button>
          </div>
          <p class="input-hint">按 Enter 发送，Shift + Enter 换行</p>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { getSessions, deleteSession, sendMessage, queryMessages } from '../api'
import { marked } from 'marked'

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
  currentSessionId.value = ''
  messages.value = []
  // 不使用 router.push，保持在 /chat 页面，只清空右侧
  inputText.value = ''
  sidebarOpen.value = false
  nextTick(() => textareaRef.value?.focus())
}

function selectSession(sessionId) {
  currentSessionId.value = sessionId
  router.replace(`/chat/${sessionId}`)
  loadMessages(sessionId)
  sidebarOpen.value = false
}

async function handleDeleteSession(sessionId) {
  if (!confirm('确定删除这个对话吗？')) return
  try {
    await deleteSession(sessionId)
    sessions.value = sessions.value.filter(s => s.sessionId !== sessionId)
    if (currentSessionId.value === sessionId) {
      startNewChat()
    }
  } catch (e) {
    console.error('删除会话失败', e)
  }
}

// ==================== Messages ====================
async function loadMessages(sessionId) {
  try {
    const res = await queryMessages({ sessionId, pageNum: 1, pageSize: 100 })
    messages.value = res.data || []
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error('加载消息失败', e)
    messages.value = []
  }
}

async function handleSend(e) {
  if (e) {
    // Shift+Enter 换行
    if (e.shiftKey) return
    e.preventDefault()
  }

  const text = inputText.value.trim()
  if (!text || aiLoading.value) return

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

  // 调用 API
  aiLoading.value = true
  try {
    const res = await sendMessage({
      sessionId: currentSessionId.value || undefined,
      content: text,
      agentType: 'simple_agent'
    })

    // 更新 sessionId（新会话时后端创建）
    if (res.data?.sessionId && !currentSessionId.value) {
      currentSessionId.value = res.data.sessionId
      router.replace(`/chat/${res.data.sessionId}`)
    }

    // 添加 AI 回复
    const aiMsg = {
      messageId: res.data?.messageId || (Date.now() + 1).toString(),
      sessionId: res.data?.sessionId || currentSessionId.value,
      role: 'assistant',
      content: res.data?.content || '暂无回复',
      messageType: 'text',
      createTime: new Date().toISOString()
    }
    messages.value.push(aiMsg)

    // 刷新会话列表
    await loadSessions()
  } catch (e) {
    console.error('发送失败', e)
    const errMsg = {
      messageId: (Date.now() + 1).toString(),
      sessionId: currentSessionId.value,
      role: 'assistant',
      content: '抱歉，发送失败了，请稍后重试。\n\n错误信息：' + (e.message || '网络错误'),
      messageType: 'text',
      createTime: new Date().toISOString()
    }
    messages.value.push(errMsg)
  } finally {
    aiLoading.value = false
    await nextTick()
    scrollToBottom()
  }
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
    return marked.parse(text)
  } catch {
    return text.replace(/\n/g, '<br/>')
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
