# Proposal

## Why

产品目录、历史保单和条款知识目前没有超管入口：产品靠 SQL 脚本写入，保单表没有管理接口且 CRM 仍读假数据，条款只能用本地目录扫描进 Milvus。运营无法在一个只允许超级管理员进入的后台里维护这些数据，也不能查看 C 端用户并立即结束其登录。

## What Changes

- **BREAKING**：`/admin/sys_user/login/password` 只给身份为 `super_admin` 且状态为启用的 `sys_user` 签发令牌。`platform_admin` 等其他身份不能登录；已签发的非超管令牌访问管理接口时也会被拒绝。
- 超管可以分页查看 C 端 `app_user`，并按用户踢下线。踢人只删除 `userFrom=app` 的 Redis 登录态，不删除账号、保单或聊天记录。
- 超管可以新增、更新、上下架并分页查看 `insurance_products`。这是产品 Agent 与知识 Agent 实际查询的在售产品表。
- 超管可以新增、更新并分页查看 `user_policy_history`。CRM 改为从该表读取客户保单，不再使用假的客户仓库。
- 超管可以上传条款文档（pdf、docx、md、txt），系统保存原文并复用现有分块与嵌入流水线写入 Milvus 集合 `file_documents`。上传不重建集合。同一文档再次上传时替换该文档已有向量。超管可以查看文档目录和对应分块。
- 增加独立的超管控制台，只调用上述 `/admin/**` 接口。客户聊天前端保持不变。

不纳入本次：聊天会话与消息、字典与参数、地区数据、JSON 保障缺口规则、源码或表格类文件的向量化、删除 C 端账号。

## Capabilities

### New Capabilities

- `super-admin-auth`: 仅超级管理员可以登录管理端，并且管理接口拒绝其他身份。
- `app-user-administration`: 超管查看 C 端用户并撤销其登录会话。
- `insurance-business-data`: 超管维护并查看产品目录和用户历史保单，且 Agent 读取这些 MySQL 数据。
- `knowledge-document-ingest`: 超管上传条款文档、完成向量化，并查看知识库文档与分块。

### Modified Capabilities

- 无。主规格目录目前没有已发布能力。

## Impact

- `insurance-admin`：登录校验、超管鉴权、用户踢人、产品与保单接口、知识文档编排。
- `insurance-common-security` 的 `TokenService.delLoginUser`：按 `app` 来源删除登录态。
- Python：单文件向量化入口，以及 CRM 对 `user_policy_history` 的真实读取。
- MySQL：产品与保单沿用现表；新增知识文档登记表。Milvus 沿用 `file_documents`，禁止由管理接口重建集合。
- 新增超管前端，经网关 `/admin/**` 访问。客户门户登录与 `/chat` 契约不变。
- 依赖现有 Redis 会话、DashScope 嵌入和 Milvus。嵌入或向量库失败时，文档保持失败状态，不把未写入的内容标成可用。
