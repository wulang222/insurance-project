# UX Contract

## Product context

- Audience: 保险平台超级管理员与运营人员。
- Primary jobs: 管理 C 端用户、保险产品、历史保单和知识文档。
- Active locale: `zh-CN`。
- Accessibility target: WCAG 2.2 AA。

## Business-context sources

| Domain / scope | Authoritative source | Source type | Reviewed date |
|---|---|---|---|
| 超管权限与认证 | `openspec/changes/super-admin-console/specs/super-admin-auth/spec.md` | Product spec | 2026-11-04 |
| 用户管理 | `openspec/changes/super-admin-console/specs/app-user-administration/spec.md` | Product spec | 2026-11-04 |
| 产品与保单数据 | `openspec/changes/super-admin-console/specs/insurance-business-data/spec.md` | Product spec | 2026-11-04 |
| 知识文档生命周期 | `openspec/changes/super-admin-console/specs/knowledge-document-ingest/spec.md` | Product spec | 2026-11-04 |

## Visual contract

- Project `DESIGN.md`: `DESIGN.md`。
- Token ownership: Model B；`src/styles.css` 是运行时唯一所有者，DESIGN.md 镜像并解释已接受值。
- Supported themes: 浅色；强制高对比模式使用系统颜色。

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | 原生 `select` | `premium-ui.json` | native | keyboard + popup |
| Date | 原生 `input[type=date]` | `premium-ui.json` | native | locale + keyboard + E2E |
| Form | Vue 页面表单与字段标签 | 本文件 Validation | create / filter | validation E2E |
| Scrollbar | `src/styles.css` 全局样式 | `DESIGN.md` | geometry exceptions | computed style |
| CRUD | 页面 API 操作函数 | OpenSpec 业务规格 | stay + refresh | page tests + browser flow |

## Component behavior

- Button: 默认、hover、focus-visible、disabled 和 busy 状态保持同一尺寸；重复提交由页面状态阻止。
- Input: 使用真实标签或可访问名称；错误显示在持久的行内区域。
- Secret input: 默认遮罩，提供带动态可访问名称的显示/隐藏按钮。
- Table: 使用语义化 `table`，窄屏由面板承担水平滚动。

## Dataset navigation

- 当前后端接口按页面固定请求 10 或 20 条；页面显示服务端总数。
- 筛选仅在用户明确点击“筛选”或“查看”时请求，不按每次键入自动请求。
- 空结果保留表头；请求失败保留筛选条件并显示行内错误。

## Flow ledger

| Operation | Trigger | Pending | Success destination | Success feedback | Failure recovery | Focus outcome | Source ref |
|---|---|---|---|---|---|---|---|
| 登录 | 登录按钮 | 禁用按钮并显示“登录中” | 用户管理 | 路由切换 | 保留手机号，显示通用错误 | 保持表单上下文 | super-admin-auth |
| 保存产品/保单 | 保存按钮 | 原位等待 | 当前页面 | 刷新列表 | 保留输入并显示错误 | 保持触发区域 | insurance-business-data |
| 筛选 | 筛选/查看按钮 | 原位等待 | 当前页面 | 更新表格 | 保留条件并显示错误 | 保持触发按钮 | app-user-administration |
| 上传/替换文档 | 上传/替换按钮 | 服务端处理状态 | 当前页面 | 刷新文档状态 | 保留文件选择并显示错误 | 保持触发区域 | knowledge-document-ingest |

## Navigation and responsive behavior

- 每个路由设置唯一中文文档标题。
- 桌面端使用侧栏；720px 以下转换为可水平滚动的顶部导航。
- 导航使用 `RouterLink`，保持 SPA 路由和当前项状态。
- 表格在面板内横向滚动，不裁切操作列。

## Async and resilience

- 默认采用 pessimistic mutation；服务端成功后刷新列表。
- API 超时为 30 秒；失败不清空当前输入。
- 401 清理本地令牌并返回登录页；存储访问必须捕获浏览器异常。
- 当前版本不做离线写入、自动保存或乐观更新。

## Validation

- 登录表单声明 `novalidate`，应用自行显示错误。
- 服务端错误映射到页面行内错误区，不使用浏览器弹窗。
- 密码只在内存中处理，不写入持久存储、URL 或日志。

## Verification

- Static audit: `audit_project.py . --mode strict --config premium-ui.json --no-write`。
- Frontend: `npm run test:pages`、`npm run build`。
- Browser: 登录页键盘操作、窄屏导航、用户/产品/保单/知识库页面加载与错误状态。
