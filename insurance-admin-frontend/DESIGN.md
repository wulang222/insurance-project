---
version: alpha
name: "Insurance Admin Console"
description: "面向保险运营人员的紧凑管理台，以深松绿色导航和安静的数据面板强调可信、可核查的日常操作。"
colors:
  primary: "#0F6B5C"
  navigation: "#12352F"
  page: "#F4F6F8"
  surface: "#FFFFFF"
  text: "#1F2933"
  border: "#C5CED6"
  divider: "#E6EBF0"
  danger: "#9B1C1C"
  warning: "#FDE68A"
  success: "#BBF7D0"
  focus: "#2A8C7B"
typography:
  sans:
    fontFamily: "'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    lineHeight: "1.5"
rounded:
  DEFAULT: "6px"
  sm: "6px"
  md: "10px"
spacing:
  control-padding: "8px"
  panel-padding: "16px"
  page-padding: "24px"
components:
  button:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "{spacing.control-padding}"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "{spacing.panel-padding}"
---

# Insurance Admin Console Design System

## Overview

管理台以“保险运营台账”为视觉参照：页面像一套清晰的业务档案，导航稳定、表格易扫读、状态颜色只承担语义。目标用户是处理用户、产品、保单和知识文档的中文运营人员，界面属于高频产品工具，不承担营销表达。

运行时采用 Model B：`src/styles.css` 是 CSS token 与组件样式的唯一所有者，本文件镜像已经接受的值并解释使用边界。深松绿导航是唯一识别性表达；内容区保持克制，避免渐变大屏、玻璃拟态和装饰性 Agent 元素。

## Colors

`primary` 用于主要操作和当前导航，`navigation` 只用于侧栏。`danger` 仅表示错误或安全相关操作；`warning`、`success` 只表示文档处理状态。`focus` 为所有键盘操作提供可见焦点，不能只靠颜色表达状态。

## Typography

正文使用支持简体中文的系统无衬线字体栈。表格、表单和状态信息保持紧凑但可读；标题依靠字号和字重建立层级，不使用装饰性斜体或全大写。

## Layout

桌面端使用 180px 固定导航列和弹性内容区。窄屏改为顶部横向导航，表格由内容区域承担水平滚动，不能裁掉操作列。面板间距保持 16px，页面边距在窄屏缩小。

## Elevation & Depth

面板依靠背景和边框层级，不使用重阴影。状态、错误和焦点通过稳定的行内区域呈现，异步变化不得移动主要操作。

## Shapes

输入框、按钮和导航项使用 6px 圆角；面板使用 10px。胶囊形只用于短状态徽标。

## Components

按钮、输入框、导航和表格的默认、hover、focus-visible、disabled 状态由全局样式统一负责。原生日期和下拉控件是明确选择：当前工具接受操作系统弹层，以降低维护成本；其标签、键盘语义和焦点样式仍由应用保证。

## Do's and Don'ts

- **Do:** 保持用户、产品、保单和知识库页面的导航、筛选、错误反馈一致。
- **Do:** 用文字同时说明处理状态和失败原因。
- **Don't:** 用浏览器弹窗或只靠颜色表达关键状态。
- **Don't:** 在单个页面复制独立色值或另建局部滚动条主题。
