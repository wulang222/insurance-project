---
version: alpha
name: "Insurance Chat"
description: "面向中文保险咨询的可信 AI 工作台，以可追踪分析过程和证据来源建立信任。"
colors:
  primary: "#4F46E5"
  primary-hover: "#4338CA"
  primary-light: "#EEF2FF"
  page: "#F3F4F6"
  surface: "#FFFFFF"
  text: "#111827"
  text-secondary: "#6B7280"
  border: "#E5E7EB"
  success: "#047857"
  warning: "#B45309"
  danger: "#DC2626"
  focus: "#818CF8"
typography:
  sans:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    lineHeight: "1.6"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
rounded:
  DEFAULT: "12px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
spacing:
  control-gap: "10px"
  message-gap: "24px"
  content-max: "800px"
components:
  chat-message:
    radius: "12px"
  run-progress:
    radius: "12px"
  button:
    focusRing: "#818CF8"
  dialog:
    maxWidth: "420px"
---

# Insurance Chat Design System

## Overview

### Creative North Star

界面参考保险顾问桌面的“保障分析档案”：主体保持安静、易读，关键结论必须能展开查看处理轨迹和原始证据。它不是娱乐型聊天机器人，也不是只展示模型气泡的通用 AI 模板。

### Product context and register

- **Audience and primary job:** 中文用户在桌面端或手机端描述家庭情况，获得可验证的保险保障分析，并在缺少信息时继续补充。
- **Target market and evidence:** 当前仓库业务、接口与演示内容均面向中文保险咨询；不据此推断具体司法辖区或代替正式保险建议。
- **Locale and language policy:** 产品界面使用简体中文，技术标识和产品固有名称可保留英文；面向用户的错误不得暴露后端原文。
- **Usage scene:** 中等频率、较高信任要求的连续对话；信息密度适中，移动端保持完整引用和操作能力。
- **Register:** 产品界面优先，首页可承担有限品牌表达。
- **Memorable signature:** 对话顶部的“分析轨迹”像一条承保档案时间线，明确展示路由、专业模块和最终状态。
- **Restraint:** 消息、表单、确认框和引用保持熟悉的产品交互，不以装饰性动画干扰阅读。
- **Anti-references:** 避免霓虹控制台、游戏化 Agent 头像群和无法解释的彩色数据卡；这些会削弱保险场景的可信度。
- **Token ownership/runtime mapping:** 采用 Model B。`insurance-chat-frontend/src/assets/main.css` 是运行时 token 的唯一所有者，本文件镜像已接受值并解释用途；组件只消费 CSS 变量，不复制独立色值系统。

## Colors

靛蓝 `primary` 表示主要操作和当前处理路径；绿色只表示已完成，琥珀色只表示证据或信息警告，红色保留给失败和不可恢复的删除。页面、侧栏和消息通过浅灰色调分层，键盘焦点统一使用 `focus`，不能只靠颜色表达状态。

## Typography

正文使用系统中文无衬线栈，保证 Windows、macOS 和移动设备均可读；14px 为工作台基准字号，长回答保持约 1.6 行高。Trace ID、Citation ID 和代码使用等宽字体。标题依靠字号和字重建立层级，不使用全大写或斜体装饰。

## Layout

桌面端采用 280px 会话导航加弹性对话区，正文最大宽度 800px。移动端导航变为覆盖层，消息体、分析轨迹和引用均保持同等信息完整度。对话滚动由消息区域负责，输入区保持稳定；加载、错误与完成状态不得推动主要输入控件产生跳动。

## Elevation & Depth

默认以边框和色调区分层级；静态卡片不增加重阴影。浮层确认框使用 `shadow-lg`，移动导航使用半透明遮罩。分析轨迹用浅色渐变表达当前工作，但不作为装饰背景扩散到普通内容。

## Shapes

控件和消息以 8–12px 圆角为主；主要发送/停止动作可以使用圆形。消息靠近头像一角收紧至 4px，形成明确的发言方向。24px 胶囊只用于已有品牌入口，不扩散到工作台控件。

## Components

### Foundational visual states

所有按钮包含默认、hover、focus-visible、active、disabled 和 busy 状态。异步分析使用命名阶段与稳定的状态区域；错误保留问题并提供“重新发送”。动画必须响应 `prefers-reduced-motion`。

### Buttons and actions

每个区域只有一个高强调主操作。发送为 `primary`，停止为低强调 `danger`，删除仅在应用自有确认框中使用高强调红色；取消删除首先获得焦点。图标按钮必须有中文可访问名称。

### Navigation and data display

会话条目使用真实按钮并通过 `aria-current` 标记当前项。分析轨迹按服务端 SSE 事件顺序展示；引用使用原生 `details/summary`，点击后显示标题、章节、页码、摘录和 Citation ID。

### Forms and overlays

聊天输入框禁止手工缩放但支持自动增高，Enter 发送、Shift+Enter 换行，并保护中文 IME 组合输入。删除确认框负责焦点进入、循环、Escape 关闭和触发点恢复。错误信息使用持久的行内区域，不用浏览器 `alert` 或 `confirm`。

### Iconography

当前项目不引入新图标库；采用简单文字符号时必须配合可访问名称。Emoji 只用于欢迎建议的语义提示，不作为唯一信息载体。

### Motion

交互反馈以 150–250ms 为主；分析中的脉冲是唯一持续动画。减少动态模式下取消位移、缩放和循环动画，仅保留状态本身。

### Content and data visualization

文案直接说明当前发生了什么和下一步能做什么。保险结论必须区分建议、警告和来源；不使用“保证赔付”等承诺性措辞。Trace 和 Citation 标识用于核查，不替代可读的来源说明。

## Do's and Don'ts

- **Do:** 让每个保险事实可以回到产品字段、规则版本或 Citation。
- **Do:** 同一异步状态在 SSE、消息历史和恢复流程中使用同一名称。
- **Don't:** 用模型思考原文、后端异常或敏感数据填充进度区。
- **Don't:** 为追求“AI 感”增加与保险决策无关的动画、光效或仪表盘装饰。
