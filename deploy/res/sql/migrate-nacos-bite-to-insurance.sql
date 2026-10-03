-- =============================================================================
-- Nacos 配置迁移脚本：bite -> insurance
-- 适用场景：已有 Nacos 运行环境，从 bite 命名迁移到 insurance 命名
--
-- 使用前请修改下方数据库名（test / prd 对应各自的 nacos 库）
-- 执行前建议备份 config_info 表
-- =============================================================================

-- USE `insurance_nacos_test`;   -- 生产环境
-- USE `insurance_nacos_prd`;    -- 生产环境

-- -----------------------------------------------------------------------------
-- 1. 重命名服务专属配置文件 data_id
-- -----------------------------------------------------------------------------
UPDATE config_info SET data_id = 'insurance-gateway-dev.yaml'  WHERE data_id = 'bite-gateway-dev.yaml';
UPDATE config_info SET data_id = 'insurance-admin-dev.yaml'    WHERE data_id = 'bite-admin-dev.yaml';
UPDATE config_info SET data_id = 'insurance-file-dev.yaml'     WHERE data_id = 'bite-file-dev.yaml';
UPDATE config_info SET data_id = 'insurance-portal-dev.yaml'  WHERE data_id = 'bite-portal-dev.yaml';

UPDATE config_info SET data_id = 'insurance-gateway-prd.yaml'   WHERE data_id = 'bite-gateway-prd.yaml';
UPDATE config_info SET data_id = 'insurance-admin-prd.yaml'     WHERE data_id = 'bite-admin-prd.yaml';
UPDATE config_info SET data_id = 'insurance-file-prd.yaml'      WHERE data_id = 'bite-file-prd.yaml';
UPDATE config_info SET data_id = 'insurance-portal-prd.yaml'   WHERE data_id = 'bite-portal-prd.yaml';

-- dev 环境（如有）
UPDATE config_info SET data_id = 'insurance-gateway-dev.yaml'  WHERE data_id = 'bite-gateway-dev.yaml';
UPDATE config_info SET data_id = 'insurance-admin-dev.yaml'    WHERE data_id = 'bite-admin-dev.yaml';
UPDATE config_info SET data_id = 'insurance-file-dev.yaml'     WHERE data_id = 'bite-file-dev.yaml';
UPDATE config_info SET data_id = 'insurance-portal-dev.yaml'  WHERE data_id = 'bite-portal-dev.yaml';

-- -----------------------------------------------------------------------------
-- 2. 批量替换配置内容（包名、服务名、密码等）
--    注意顺序：先替换 bitejiuyeke，再替换 Bite，最后替换 bite
-- -----------------------------------------------------------------------------
UPDATE config_info SET content = REPLACE(content, 'com.bitejiuyeke', 'com.insurance') WHERE content LIKE '%bitejiuyeke%';
UPDATE config_info SET content = REPLACE(content, 'Bite', 'Insurance')                  WHERE content LIKE '%Bite%';
-- 密码迁移由部署环境的 Secret 管理器执行，禁止在迁移脚本中保存明文凭据。
UPDATE config_info SET content = REPLACE(content, '__OLD_PASSWORD__', '__NEW_PASSWORD__') WHERE content LIKE '%__OLD_PASSWORD__%';
UPDATE config_info SET content = REPLACE(content, 'bitejiuyeke', 'insurance')         WHERE content LIKE '%bitejiuyeke%';
UPDATE config_info SET content = REPLACE(content, 'bite-', 'insurance-')              WHERE content LIKE '%bite-%';
UPDATE config_info SET content = REPLACE(content, 'lb://bite-', 'lb://insurance-')    WHERE content LIKE '%lb://bite-%';

-- 网关 mstemplate 路由修正（服务注册名已改为 insurance-mstemplate）
UPDATE config_info SET content = REPLACE(content, 'uri: lb://mstemplate', 'uri: lb://insurance-mstemplate')
WHERE data_id LIKE 'insurance-gateway-%' AND content LIKE '%lb://mstemplate%';

-- MyBatis 包扫描路径
UPDATE config_info SET content = REPLACE(content, 'com.bite.', 'com.insurance.')
WHERE content LIKE '%com.bite.%';

-- 数据库用户名（如使用了 bite 前缀账号）
UPDATE config_info SET content = REPLACE(content, 'username: bitedev', 'username: insurancedev')
WHERE content LIKE '%username: bitedev%';
UPDATE config_info SET content = REPLACE(content, 'username: bite', 'username: insurance')
WHERE content LIKE '%username: bite%';

-- -----------------------------------------------------------------------------
-- 3. 刷新 MD5（Nacos 2.x 部分版本依赖 md5 校验，修改 content 后需同步）
-- -----------------------------------------------------------------------------
UPDATE config_info SET md5 = MD5(content), gmt_modified = NOW()
WHERE data_id LIKE 'insurance-%' OR data_id LIKE 'share-%';

-- -----------------------------------------------------------------------------
-- 4. 验证：检查是否还有 bite 残留
-- -----------------------------------------------------------------------------
-- SELECT data_id, content FROM config_info WHERE content LIKE '%bite%' OR data_id LIKE '%bite%';
