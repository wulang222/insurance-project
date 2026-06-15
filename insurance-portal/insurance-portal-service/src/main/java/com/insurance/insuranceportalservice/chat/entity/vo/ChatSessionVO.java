package com.insurance.insuranceportalservice.chat.entity.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会话列表VO
 *
 * @author insurance
 */
@Data
public class ChatSessionVO {

    /**
     * 会话ID
     */
    private String sessionId;

    /**
     * 会话标题
     */
    private String title;

    /**
     * Agent类型
     */
    private String agentType;

    /**
     * 最后一条消息时间
     */
    private LocalDateTime lastMessageTime;

    /**
     * 消息总数
     */
    private Integer messageCount;

    /**
     * 最后一条消息预览（前50字）
     */
    private String lastMessagePreview;
}
