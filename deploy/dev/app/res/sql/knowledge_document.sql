-- 知识文档登记。Milvus 只存分块，这份表给超管查看入库状态。
-- 可在空库执行：不依赖其他表。

CREATE TABLE IF NOT EXISTS `knowledge_document` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '文档 id',
    `title` VARCHAR(256) NOT NULL COMMENT '标题',
    `product_id` VARCHAR(32) NULL COMMENT '可选产品编号',
    `file_type` VARCHAR(16) NOT NULL COMMENT 'pdf/docx/md/txt',
    `storage_key` VARCHAR(512) NOT NULL COMMENT '原文对象存储键',
    `checksum` CHAR(64) NOT NULL COMMENT '原文 SHA-256',
    `status` VARCHAR(16) NOT NULL COMMENT 'processing/available/failed',
    `chunk_count` INT NOT NULL DEFAULT 0 COMMENT '已写入分块数',
    `error_message` VARCHAR(1024) NULL COMMENT '失败原因',
    `operator_id` BIGINT NULL COMMENT '操作者 sys_user id',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_status` (`status`),
    KEY `idx_product_id` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='知识文档登记';
