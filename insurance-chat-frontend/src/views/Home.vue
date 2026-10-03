<template>
  <div class="home-page">
    <!-- Nav -->
    <nav class="home-nav">
      <div class="logo">
        <span class="logo-icon">B</span>
        Insurance Chat
      </div>
      <div class="nav-links">
        <a href="#capabilities" class="nav-link">核心能力</a>
        <a
          href="https://github.com/wulang222/insurance-project#readme"
          class="nav-link"
          target="_blank"
          rel="noreferrer"
        >项目文档</a>
        <button v-if="!userStore.isLoggedIn" class="btn-login-sm" @click="$router.push('/login')">
          登录
        </button>
        <button v-else class="btn-login-sm" @click="$router.push('/chat')">
          进入对话
        </button>
      </div>
    </nav>

    <!-- Hero -->
    <section class="hero-section">
      <div class="hero-badge">
        <span class="dot"></span>
        AI 智能对话已就绪
      </div>

      <h1 class="hero-title">
        探索 AI 的<br />
        <span class="gradient">无限可能</span>
      </h1>

      <p class="hero-subtitle">
        Insurance Chat 是一个基于大语言模型的智能对话平台，
        支持多维度的知识问答、保险推荐和个性化服务，
        让 AI 真正成为您的高效助手。
      </p>

      <button class="btn-start-chat" @click="startChat">
        <span>✨</span>
        立即对话
      </button>

      <!-- Features -->
      <div id="capabilities" class="features">
        <div class="feature-card">
          <div class="icon">🧠</div>
          <div class="title">智能问答</div>
          <div class="desc">基于大语言模型，理解复杂语义，提供精准答案</div>
        </div>
        <div class="feature-card">
          <div class="icon">🛡️</div>
          <div class="title">保险推荐</div>
          <div class="desc">分析用户画像，智能匹配最合适的保险产品方案</div>
        </div>
        <div class="feature-card">
          <div class="icon">💬</div>
          <div class="title">多轮对话</div>
          <div class="desc">支持上下文记忆的连续对话，体验流畅自然的交互</div>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="home-footer">
      © 2026 Insurance Chat. All rights reserved.
    </footer>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

function startChat() {
  if (userStore.isLoggedIn) {
    router.push('/chat')
  } else {
    router.push('/login')
  }
}
</script>
