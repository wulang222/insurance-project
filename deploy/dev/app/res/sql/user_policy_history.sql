CREATE TABLE `user_policy_history` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` bigint unsigned NOT NULL COMMENT '用户ID（关联用户表）',
  `policy_no` varchar(64) NOT NULL COMMENT '保单号',
  `product_name` varchar(128) NOT NULL COMMENT '保险产品名称',
  `premium` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '保费（元）',
  `sum_insured` decimal(15,2) NOT NULL DEFAULT '0.00' COMMENT '保额（元）',
  `policy_status` tinyint NOT NULL DEFAULT '1' COMMENT '保单状态：1-生效中，2-已失效，3-理赔中，4-已终止',
  `start_date` date NOT NULL COMMENT '保单生效起始日',
  `end_date` date NOT NULL COMMENT '保单生效结束日',
  `purchase_time` datetime NOT NULL COMMENT '购买时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_policy_no` (`policy_no`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_purchase_time` (`purchase_time`),
  KEY `idx_user_status` (`user_id`, `policy_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户历史保单表';
