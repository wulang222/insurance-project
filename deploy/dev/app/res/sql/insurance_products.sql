-- =====================================================
-- 保险产品表 (保险推荐Agent核心数据表)
-- 数据库: insurance_dev
-- =====================================================

CREATE TABLE IF NOT EXISTS `insurance_products` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `product_id` VARCHAR(32) NOT NULL COMMENT '产品编号（如CI001）',
    `product_name` VARCHAR(128) NOT NULL COMMENT '产品名称',
    `insurance_type` VARCHAR(32) NOT NULL COMMENT '险种类型：重疾险/医疗险/意外险/寿险/年金险',
    `min_age` INT NOT NULL DEFAULT 0 COMMENT '最小投保年龄',
    `max_age` INT NOT NULL DEFAULT 100 COMMENT '最大投保年龄',
    `min_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '最低保费（元/年）',
    `max_price` DECIMAL(10,2) NOT NULL DEFAULT 999999.00 COMMENT '最高保费（元/年）',
    `target_occupations` VARCHAR(512) NOT NULL DEFAULT '全部职业' COMMENT '目标职业（逗号分隔，用于LIKE匹配）',
    `description` TEXT COMMENT '产品描述/特色',
    `is_active` TINYINT NOT NULL DEFAULT 1 COMMENT '是否上架：1上架 0下架',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_product_id` (`product_id`),
    KEY `idx_insurance_type` (`insurance_type`),
    KEY `idx_age_range` (`min_age`, `max_age`),
    KEY `idx_price` (`min_price`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='保险产品表';


-- =====================================================
-- 初始化示例数据（与agent mock数据一致）
-- =====================================================

INSERT INTO `insurance_products` (`product_id`, `product_name`, `insurance_type`, `min_age`, `max_age`, `min_price`, `max_price`, `target_occupations`, `description`) VALUES
('CI001', '安心保·重疾险（标准版）', '重疾险', 18, 55, 3000.00, 8000.00, '程序员,IT从业者,工程师,白领', '覆盖120种重疾，含轻症豁免，适合IT从业者的高性价比重疾保障。'),
('CI002', '健康守护·终身重疾险', '重疾险', 0, 50, 5000.00, 15000.00, '程序员,教师,医生,公务员,白领', '终身保障，150种重疾+50种轻症，含身故返保费。'),
('CI003', '年轻保·重疾险（基础版）', '重疾险', 18, 35, 1500.00, 4000.00, '程序员,设计师,运营,应届生', '专为年轻人定制的入门级重疾险，低保费高杠杆。'),
('MI001', '全民e保·百万医疗险', '医疗险', 0, 65, 200.00, 2000.00, '全部职业', '400万医疗保障，不限社保用药，含质子重离子治疗。'),
('AC001', '平安行·综合意外险', '意外险', 18, 60, 100.00, 1000.00, '全部职业', '高额意外保障，含猝死责任，适合经常出差的职场人士。'),
('LI001', '鑫裕金生·定期寿险', '寿险', 18, 55, 800.00, 5000.00, '程序员,工程师,高管,白领', '高保额定寿，最高300万保额，家庭支柱首选。'),
('LI002', '传世无忧·终身寿险', '寿险', 0, 65, 3000.00, 50000.00, '企业家,高管,高净值人群', '终身保障+财富传承，含分红机制。'),
('PI001', '福满堂·年金险', '年金险', 0, 60, 10000.00, 100000.00, '白领,公务员,教师,企业主', '稳健理财型年金，退休后按月领取，含身故保障。');
