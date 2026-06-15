package com.insurance.insuranceportalservice.chat.service;

/**
 * 聊天缓存常量
 *
 * Redis 缓存架构:
 * 会话ID → 消息ID列表（ZSET，score=时间戳，最新消息排前面）
 * 消息ID → 消息详情（Hash/Value，过期时间1天）
 *
 * @author insurance
 */
public class ChatCacheConstants {

    /**
     * 缓存前缀
     */
    public static final String CHAT_PREFIX = "chat";

    /**
     * 会话消息列表Key: chat:session:{sessionId}:messages
     * ZSET类型: member=messageId, score=timestamp
     */
    public static final String SESSION_MESSAGES_KEY = CHAT_PREFIX + ":session:%s:messages";

    /**
     * 消息详情Key: chat:message:{messageId}
     * Value类型: 存储消息JSON
     */
    public static final String MESSAGE_DETAIL_KEY = CHAT_PREFIX + ":message:%s";

    /**
     * 用户会话列表缓存Key: chat:user:{userId}:sessions
     */
    public static final String USER_SESSIONS_KEY = CHAT_PREFIX + ":user:%s:sessions";

    /**
     * 缓存失效时间: 1天（秒）
     */
    public static final long CHAT_CACHE_TTL_SECONDS = 86400L;

    /**
     * 生成会话消息ZSET的Key
     *
     * @param sessionId 会话ID
     * @return Redis Key
     */
    public static String sessionMessagesKey(String sessionId) {
        return String.format(SESSION_MESSAGES_KEY, sessionId);
    }

    /**
     * 生成消息详情的Key
     *
     * @param messageId 消息ID
     * @return Redis Key
     */
    public static String messageDetailKey(String messageId) {
        return String.format(MESSAGE_DETAIL_KEY, messageId);
    }

    /**
     * 生成用户会话列表的Key
     *
     * @param userId 用户ID
     * @return Redis Key
     */
    public static String userSessionsKey(Long userId) {
        return String.format(USER_SESSIONS_KEY, userId);
    }
}
