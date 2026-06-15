package com.insurance.insuranceportalservice.chat.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.insurance.insurancecommoncore.domain.entity.BaseDO;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDateTime;

/**
 * 聊天会话实体
 *
 * @author insurance
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("chat_session")
public class ChatSession extends BaseDO {

    /**
     * 会话ID（UUID）
     */
    private String sessionId;

    /**
     * 用户ID
     */
    private Long userId;

    /**
     * 会话标题（取首条用户消息前30字）
     */
    private String title;

    /**
     * 使用的Agent类型
     */
    private String agentType;

    /**
     * 最后一条消息时间（用于排序）
     */
    private LocalDateTime lastMessageTime;

    /**
     * 消息总数
     */
    private Integer messageCount;

    /**
     * 逻辑删除: 0未删除 1已删除
     */
    private Integer isDeleted;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
}
