package com.insurance.insuranceportalservice.chat.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.insurance.insurancecommoncore.domain.entity.BaseDO;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDateTime;

/**
 * 聊天消息实体
 *
 * @author insurance
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("chat_message")
public class ChatMessage extends BaseDO {

    /**
     * 消息ID（UUID）
     */
    private String messageId;

    /**
     * 所属会话ID
     */
    private String sessionId;

    /**
     * 用户ID
     */
    private Long userId;

    /**
     * 角色: user / assistant
     */
    private String role;

    /**
     * 消息内容
     */
    private String content;

    /**
     * 消息类型: text / recommendation / knowledge
     */
    private String messageType;

    /**
     * 扩展元数据（JSON）
     */
    private String metadataJson;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}
