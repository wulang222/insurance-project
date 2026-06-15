package com.insurance.insuranceportalservice.chat.entity.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 消息VO
 *
 * @author insurance
 */
@Data
public class ChatMessageVO {

    /**
     * 消息ID
     */
    private String messageId;

    /**
     * 会话ID
     */
    private String sessionId;

    /**
     * 角色: user / assistant
     */
    private String role;

    /**
     * 消息内容
     */
    private String content;

    /**
     * 消息类型
     */
    private String messageType;

    /**
     * 扩展元数据（JSON字符串）
     */
    private String metadataJson;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}
