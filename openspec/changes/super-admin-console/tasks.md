# Tasks

## 1. 知识文档表

- [x] 1.1 在 `deploy/dev/app/res/sql/` 增加 `knowledge_document` 建表脚本，列包含文档 id、标题、可选产品编号、文件类型、对象存储键、校验和、`processing`/`available`/`failed` 状态、分块数、错误信息、操作者和时间，并核对脚本可在空库执行

## 2. 超管登录与接口鉴权

- [x] 2.1 修改 `SysUserServiceImpl.login`：密码和启用状态通过后，身份不是 `super_admin` 不签发令牌；补测试覆盖超管成功、密码错误、`platform_admin` 拒绝、停用超管拒绝，并用 `SysUserControllerTest` 验证
- [x] 2.2 在 `insurance-admin` 增加登录白名单之外的拦截器，按当前 `sys` 令牌复查启用中的 `super_admin`，拒绝缺失、过期和非超管令牌；用控制器测试验证旧 `platform_admin` 令牌访问管理接口被拒绝、超管令牌通过
- [x] 2.3 确认门户登录仍给 C 端用户发 `userFrom=app` 的会话，并用现有门户登录测试或新增用例验证它不要求 `super_admin`
- [x] 2.4 在 README 的已知限制中写明管理端只允许 `super_admin` 登录，核对这句话和登录拒绝行为一致

## 3. C 端用户查看与踢人

- [x] 3.1 让 `/app_user/list/search` 支持按手机号和昵称过滤，并返回用户 id、昵称、手机号和分页边界；用服务测试验证过滤结果
- [x] 3.2 新增踢人接口：目标必须是已存在的 `app_user`，调用 `TokenService.delLoginUser(userId, "app")`，不删除用户、保单和聊天记录，也不删除 `sys` 会话；用不存在的用户 id 验证请求被拒绝且没有会话被删
- [x] 3.3 用测试验证踢人后该 `app` 令牌不再被视为登录，而同一用户 id 的 `sys` 会话仍在

## 4. 产品与保单管理接口

- [x] 4.1 在 `insurance-admin` 实现 `insurance_products` 的新增、按 `product_id` 更新、上下架和分页查询，查询支持险种、产品编号和上架状态，默认包含下架产品；用测试验证重复 `product_id` 被拒绝且原行不变
- [x] 4.2 实现 `user_policy_history` 的新增、按保单号更新和分页查询，查询支持用户 id 和保单状态；用户必须存在于 `app_user`，重复保单号被拒绝；用测试验证未知用户和重复保单号
- [x] 4.3 用 `MySQLProductRepository` 的测试验证新写入的上架产品能被匹配查询返回，下架产品不出现在 Agent 查询结果中

## 5. CRM 读取真实保单

- [x] 5.1 新增 MySQL 客户仓库，按用户 id 读取 `user_policy_history`，映射保单号、产品名、保费、保额、状态和生效日期；无记录时返回空列表，查询失败时抛出依赖不可用，不回退假数据
- [x] 5.2 把 `build_lifespan` 的生产 `customer_repository` 换成该 MySQL 实现，测试里继续显式注入 `FakeCustomerRepository`；用单元测试验证有保单和空保单两个场景

## 6. 单文档向量化

- [x] 6.1 为单个 pdf、docx、md、txt 文件增加失败即中止的写入路径：插入带 `document_id` 和新 `generation` 的分块，全部成功后再删除该文档的其他 generation；任一批次失败则删除本次 generation 并保留旧分块；用假 Milvus 或测试替身验证成功、失败和其他文档不受影响
- [x] 6.2 增加不进入网关的 Python 内网接口，用共享密钥保护单文档入库和按 `document_id` 读取分块；密钥错误时拒绝，且接口不调用 `recreate_collection`
- [x] 6.3 确认可用文档的分块元数据包含标题、来源、校验和，以及上传时提供的产品编号；用检索测试验证新分块可被命中，替换成功后旧分块不再返回

## 7. 管理服务编排知识入库

- [x] 7.1 管理服务接收超管上传，拒绝空文件、超过 20MB 和非 pdf/docx/md/txt 文件，经 `insurance-file` 保存原文并写入 `knowledge_document`，初始状态为 `processing`；用测试验证非法类型不产生向量
- [x] 7.2 异步调用 Python 内网接口，按返回结果把登记行更新为 `available` 加分块数，或 `failed` 加错误信息；密钥缺失或入库失败时保持失败状态，不把文档标成可用
- [x] 7.3 提供同一文档 id 的替换上传、文档分页列表和分块查询；列表包含状态、标题、可选产品编号、校验和与分块数，分块查询返回文本和引用元数据；用测试验证非超管上传被拒绝

## 8. 超管控制台

- [x] 8.1 新增独立的 `insurance-admin-frontend`，包含登录、C 端用户、产品、保单、知识文档页面，只请求网关 `/admin/**`；运行生产构建，确认构建成功且客户聊天前端没有这些路由
- [x] 8.2 用户页可以筛选并踢人，产品页和保单页可以提交与查看列表，文档页可以上传、看到 `processing`/`available`/`failed` 并查看分块；用页面测试或构建后的路由检查确认这些操作都调用对应管理接口

## 9. 跨模块验收

- [x] 9.1 运行管理服务新增测试、Python 保单仓库与入库测试，以及超管前端构建；全部通过后，对照四份 delta spec 的场景核对没有未覆盖的拒绝路径
