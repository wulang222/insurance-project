-- =====================================================
-- 聊天功能表 — 会话表 + 消息表
-- 数据库: insurance_dev
-- =====================================================

-- 会话表：记录每次用户与AI的对话会话
CREATE TABLE IF NOT EXISTS `chat_session` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `session_id`  VARCHAR(64)  NOT NULL COMMENT '会话ID（UUID）',
    `user_id`     BIGINT       NOT NULL COMMENT '用户ID',
    `title`       VARCHAR(128) NOT NULL DEFAULT '新对话' COMMENT '会话标题（取首条用户消息前30字）',
    `agent_type`  VARCHAR(32)  NOT NULL DEFAULT 'insurance_agent' COMMENT '使用的Agent: insurance_agent/knowledge_agent',
    `last_message_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后一条消息时间（用于排序）',
    `message_count`     INT     NOT NULL DEFAULT 0 COMMENT '消息总数',
    `is_deleted`  TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0未删除 1已删除',
    `create_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_session_id` (`session_id`),
    KEY `idx_user_id_last_time` (`user_id`, `last_message_time` DESC),
    KEY `idx_user_id_deleted` (`user_id`, `is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='聊天会话表';


-- 消息表：记录会话中的每一条消息
CREATE TABLE IF NOT EXISTS `chat_message` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `message_id`    VARCHAR(64)  NOT NULL COMMENT '消息ID（UUID）',
    `session_id`    VARCHAR(64)  NOT NULL COMMENT '所属会话ID',
    `user_id`       BIGINT       NOT NULL COMMENT '用户ID',
    `role`          VARCHAR(16)  NOT NULL COMMENT '角色: user / assistant',
    `content`       MEDIUMTEXT   NOT NULL COMMENT '消息内容',
    `message_type`  VARCHAR(32)  NOT NULL DEFAULT 'text' COMMENT '消息类型: text / recommendation / knowledge',
    `metadata_json` TEXT         NULL     COMMENT '扩展元数据（JSON）',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_message_id` (`message_id`),
    KEY `idx_session_id_time` (`session_id`, `create_time`),
    KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='聊天消息表';
