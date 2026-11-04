# Design

## Context

管理端已经是 `insurance-admin`，网关把 `/admin/**` 转到该服务并去掉前缀。`/sys_user/login/password` 今天只校验手机号、密码和启用状态，不区分 `super_admin` 与 `platform_admin`。网关只检查 Redis 里是否还有令牌，不检查身份。C 端登录在门户里把 `userFrom` 设为 `app`，`TokenService.delLoginUser(userId, userFrom)` 已能按来源删除会话。

Agent 从 MySQL `insurance_products` 读在售产品。`user_policy_history` 已有表结构，但 `build_lifespan` 仍把 CRM 接到 `FakeCustomerRepository`。条款向量由 `vectorizer` 扫描本地目录写入 Milvus 集合 `file_documents`；管理接口不能调用会重建集合的路径。原文上传可以复用 `insurance-file` 的对象存储。

## Goals / Non-Goals

**Goals:**

- 超管身份在登录和管理接口两处都生效，包括已经发出的非超管令牌。
- 产品、保单由管理服务写入 Agent 正在读取的同一 MySQL 库。
- 文档入库复用现有加载、分块和嵌入，并满足“新向量写成功后才删旧向量”。
- 控制台只是这些接口的操作界面。

**Non-Goals:**

- 不改客户聊天前端，也不把超管页面放进门户。
- 不把保障缺口规则从 JSON 迁到 MySQL。
- 不重做 Redis 令牌索引；踢人继续使用现有按来源删除。
- 不开放目录扫描或 `recreate_collection` 给管理接口。

## Decisions

### 1. 能力落在现有管理服务，向量化留在 Python

管理接口、超管校验、产品与保单写入放在 `insurance-admin`。Python 增加仅内网可调用的单文档入库接口，供管理服务在保存原文后调用。产品查询继续走现有 `MySQLProductRepository`，不在 Python 再做一套写入。

备选是把产品 CRUD 也放到 FastAPI。否决原因：网关和登录已经在 Java 管理服务，两套写入会分裂校验。

### 2. 超管校验放在管理服务，而不是只放在页面

登录在密码和启用状态通过后，身份必须等于 `super_admin`，否则不发令牌。除登录白名单外，管理服务拦截器读取当前 `sys` 令牌，再查 `sys_user`：身份不是启用中的 `super_admin` 就拒绝。这样字典、参数、用户和本次新接口使用同一规则。

备选是只改登录。否决原因：旧的 `platform_admin` 令牌在过期前仍可用。

### 3. 踢人只撤销 C 端会话

新增按 `app_user` id 踢人的接口。用户必须存在；然后调用 `delLoginUser(userId, "app")`。不修改用户行，不触碰 `sys` 会话。

### 4. 业务表只覆盖 Agent 真正依赖的两张表

- `insurance_products`：新增、按 `product_id` 更新、上下架、分页查询。下架写 `is_active=0`。Agent 现有查询已经排除未上架产品。
- `user_policy_history`：新增、按保单号更新、分页查询。用户 id 必须存在于 `app_user`。生产生命周期把 `customer_repository` 换成读取该表的 MySQL 实现；测试仍显式注入 `FakeCustomerRepository`。没有保单时返回空列表。

`chat_session`、`chat_message`、字典、参数和 `coverage_rules.json` 不提供上传接口。

### 5. 知识文档用 MySQL 登记，Milvus 只存分块

新增 `knowledge_document`：文档 id、标题、可选 `product_id`、文件类型、对象存储键、校验和、状态（`processing`、`available`、`failed`）、分块数、错误信息、操作者、时间。文档 id 是替换和检索元数据里的稳定身份，校验和只用于审计。

上传流程：

1. 校验扩展名是 pdf、docx、md、txt，且文件非空、不超过 20MB。
2. 经文件服务保存原文，插入或更新登记行，状态为 `processing`。
3. 管理服务异步调用 Python。Python 用现有 loader、chunker 和嵌入处理这一个文件，向 `file_documents` 插入带 `document_id` 和新 `generation` 的分块。
4. 全部批次成功后，按 `document_id` 删除其他 generation，再把登记行更新为 `available` 和实际分块数。
5. 任一批次失败时，删除本次 generation，登记行改为 `failed`，旧 generation 保留。

首次入库没有旧 generation。管理接口不调用 `create_collection(recreate=True)`。Python 路径使用独立的失败即中止写入，不沿用目录扫描里“单批失败后继续”的行为。

内网接口使用共享密钥请求头，不加入网关路由。密钥缺失时管理服务把文档标为失败。

### 6. 控制台是独立 Vue 应用

新增 `insurance-admin-frontend`，页面为登录、C 端用户、产品、保单、知识文档。它只请求网关 `/admin/**`，令牌存在浏览器本地存储。客户聊天应用不增加这些路由。

备选是把页面放进 `insurance-chat-frontend`。否决原因：客户令牌和超管令牌会混在同一个前端里。

## Risks / Trade-offs

- [非超管账号无法再进管理端] → 这是预期的不兼容变更。部署说明写明只有 `super_admin` 可以登录，现有种子账号身份已是 `super_admin`。
- [踢人使用 Redis `KEYS` 扫描] → 沿用现有实现，本次不改令牌键结构。用户量上来后再单独做索引。
- [嵌入或 Milvus 失败] → 文档保持 `failed`，旧分块仍可检索；控制台展示错误信息并允许重试。
- [CRM 从假数据切到真实保单] → 生产不再隐式返回假保单。MySQL 不可用时按现有依赖失败处理，不回退到假数据。
- [管理列表会显示手机号] → 仅超管接口返回，沿用现有解密方式，不写进 Agent 日志。

## Migration Plan

1. 在开发库执行 `knowledge_document` 建表脚本。产品和保单表已存在，不改列。
2. 先发布 Python：内网入库接口，以及 CRM 读取 `user_policy_history`。
3. 再发布 `insurance-admin` 和文件服务配置，最后发布控制台。
4. 回滚时先停控制台和新管理路由。已写入的产品和保单保留。CRM 回滚到假仓库只用于紧急恢复，恢复后保单查询会暂时看不到 MySQL 数据。失败文档不会被标成可用。

## Open Questions

无。文件上限 20MB、异步入库和“文档 id 即替换身份”已在上面确定，不改变规格中的可见行为。
