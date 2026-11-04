package com.insurance.insuranceportalservice.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.insurance.insurancecommoncore.utils.BeanCopyUtil;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import com.insurance.insurancecommonredis.service.RedisService;
import com.insurance.insuranceportalservice.chat.entity.ChatMessage;
import com.insurance.insuranceportalservice.chat.entity.ChatSession;
import com.insurance.insuranceportalservice.chat.entity.dto.QueryMessagesDTO;
import com.insurance.insuranceportalservice.chat.entity.dto.SendMessageDTO;
import com.insurance.insuranceportalservice.chat.entity.vo.ChatMessageVO;
import com.insurance.insuranceportalservice.chat.entity.vo.ChatSessionVO;
import com.insurance.insuranceportalservice.chat.mapper.ChatMessageMapper;
import com.insurance.insuranceportalservice.chat.mapper.ChatSessionMapper;
import com.insurance.insuranceportalservice.chat.client.PythonAgentClient;
import com.insurance.insuranceportalservice.chat.service.ChatCacheConstants;
import com.insurance.insuranceportalservice.chat.service.IChatService;
import com.fasterxml.jackson.core.type.TypeReference;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 聊天服务实现
 *
 * Redis 缓存架构:
 * 1. chat:session:{sessionId}:messages  → ZSET  (score=时间戳, member=messageId)
 *    按时间排序的最新消息ID列表，过期1天
 * 2. chat:message:{messageId}            → Value (消息详情JSON)
 *    每条消息的完整内容，过期1天
 *
 * 查询流程:
 * 1. 先查Redis ZSET获取消息ID列表（按时间排序）
 * 2. 再根据消息ID列表批量查Redis获取消息详情
 * 3. Redis未命中时回源MySQL查询
 *
 * 缓存安全:
 * - 消息写入时同时更新MySQL和Redis
 * - Redis缓存过期后自动回源MySQL
 * - 使用事务保证MySQL数据一致性
 *
 * @author insurance
 */
@Slf4j
@Component
public class ChatServiceImpl implements IChatService {

    @Autowired
    private ChatSessionMapper chatSessionMapper;

    @Autowired
    private ChatMessageMapper chatMessageMapper;

    @Autowired
    private RedisService redisService;

    @Autowired
    private PythonAgentClient pythonAgentClient;

    // ==================== 会话列表 ====================

    /**
     * 查询用户的会话列表（按最后消息时间倒序）
     *
     * 先查MySQL获取会话列表，再尝试从Redis获取最后一条消息预览。
     * 会话列表数据量小（每个用户通常几十条），直接查MySQL即可。
     *
     * @param userId 用户ID
     * @return 会话列表（按last_message_time DESC排序）
     */
    @Override
    public List<ChatSessionVO> listSessions(Long userId) {
        // 1. 查询用户未删除的会话，按最后消息时间倒序
        LambdaQueryWrapper<ChatSession> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ChatSession::getUserId, userId)
                .eq(ChatSession::getIsDeleted, 0)
                .orderByDesc(ChatSession::getLastMessageTime);

        List<ChatSession> sessions = chatSessionMapper.selectList(wrapper);
        if (sessions.isEmpty()) {
            return Collections.emptyList();
        }

        // 2. 转换为VO，并填充最后一条消息预览
        List<ChatSessionVO> result = new ArrayList<>(sessions.size());
        for (ChatSession session : sessions) {
            ChatSessionVO vo = new ChatSessionVO();
            vo.setSessionId(session.getSessionId());
            vo.setTitle(session.getTitle());
            vo.setAgentType(session.getAgentType());
            vo.setLastMessageTime(session.getLastMessageTime());
            vo.setMessageCount(session.getMessageCount());
            // 尝试从Redis获取最后一条消息的预览
            vo.setLastMessagePreview(getLastMessagePreview(session.getSessionId()));
            result.add(vo);
        }
        return result;
    }

    /**
     * 从Redis获取会话的最后一条消息预览（最多50字）
     */
    private String getLastMessagePreview(String sessionId) {
        try {
            String key = ChatCacheConstants.sessionMessagesKey(sessionId);
            // 使用 getCacheZSet 获取ZSET中score最大的1条（最新消息）
            // getCacheZSet 返回正序（score从小到大），取最后一条即最新
            Set<String> messageIds = redisService.getCacheZSet(key,
                    new TypeReference<LinkedHashSet<String>>() {});
            if (messageIds != null && !messageIds.isEmpty()) {
                String lastMessageId = new ArrayList<>(messageIds).get(messageIds.size() - 1);
                ChatMessage msg = getMessageFromCache(lastMessageId);
                if (msg != null && StringUtils.isNotBlank(msg.getContent())) {
                    String content = msg.getContent();
                    return content.length() > 50 ? content.substring(0, 50) + "..." : content;
                }
            }
        } catch (Exception e) {
            log.debug("获取最后消息预览失败: sessionId={}", sessionId, e);
        }
        return "";
    }

    // ==================== 查询历史消息 ====================

    /**
     * 查询会话的历史消息
     *
     * 流程:
     * 1. 从Redis ZSET获取消息ID列表（按score倒序 = 最新消息先出）
     * 2. 根据消息ID批量从Redis查消息详情
     * 3. Redis未命中时回源MySQL
     *
     * @param queryDTO 查询条件（sessionId + 分页）
     * @param userId   用户ID（权限校验）
     * @return 消息列表
     */
    @Override
    public List<ChatMessageVO> queryMessages(QueryMessagesDTO queryDTO, Long userId) {
        String sessionId = queryDTO.getSessionId();

        // 1. 校验会话归属
        checkSessionOwnership(sessionId, userId);

        // 2. 从Redis ZSET获取消息ID列表（倒序: 最新在前）
        String zsetKey = ChatCacheConstants.sessionMessagesKey(sessionId);
        Set<String> messageIdSet = redisService.getCacheZSetDesc(zsetKey,
                new TypeReference<LinkedHashSet<String>>() {});

        List<String> messageIds;
        if (messageIdSet != null && !messageIdSet.isEmpty()) {
            // Redis命中: 使用缓存的消息ID列表
            messageIds = new ArrayList<>(messageIdSet);
            log.debug("Redis ZSET命中: sessionId={}, 消息数={}", sessionId, messageIds.size());
        } else {
            // Redis未命中: 回源MySQL加载消息ID列表
            messageIds = loadMessageIdsFromDb(sessionId);
            log.debug("Redis ZSET未命中，回源MySQL: sessionId={}, 消息数={}", sessionId, messageIds.size());
            // 预热缓存
            rebuildSessionCache(sessionId, messageIds);
        }

        // 3. 分页处理（客户端分页: 倒序列表取第N页）
        int pageNum = queryDTO.getPageNum() != null ? queryDTO.getPageNum() : 1;
        int pageSize = queryDTO.getPageSize() != null ? queryDTO.getPageSize() : 20;
        int fromIndex = (pageNum - 1) * pageSize;
        int toIndex = Math.min(fromIndex + pageSize, messageIds.size());

        if (fromIndex >= messageIds.size()) {
            return Collections.emptyList();
        }

        List<String> pageMessageIds = messageIds.subList(fromIndex, toIndex);

        // 4. 根据消息ID批量获取消息详情（先查Redis，再回源MySQL）
        List<ChatMessage> messages = batchGetMessages(pageMessageIds);

        // 5. 转换为VO并反转顺序（前端需要正序显示: 旧消息在前，新消息在后）
        List<ChatMessageVO> voList = new ArrayList<>(messages.size());
        for (ChatMessage msg : messages) {
            voList.add(convertToVO(msg));
        }
        // 按createTime正序排列
        voList.sort((a, b) -> {
            if (a.getCreateTime() == null) return 1;
            if (b.getCreateTime() == null) return -1;
            return a.getCreateTime().compareTo(b.getCreateTime());
        });
        return voList;
    }

    /**
     * 从MySQL加载会话的消息ID列表（正序）
     */
    private List<String> loadMessageIdsFromDb(String sessionId) {
        LambdaQueryWrapper<ChatMessage> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ChatMessage::getSessionId, sessionId)
                .orderByAsc(ChatMessage::getCreateTime);
        List<ChatMessage> messages = chatMessageMapper.selectList(wrapper);
        return messages.stream()
                .map(ChatMessage::getMessageId)
                .collect(Collectors.toList());
    }

    /**
     * 批量获取消息详情（先查Redis缓存，未命中则查MySQL并回写缓存）
     */
    private List<ChatMessage> batchGetMessages(List<String> messageIds) {
        List<ChatMessage> result = new ArrayList<>(messageIds.size());
        List<String> missedIds = new ArrayList<>();

        // 先查Redis
        for (String msgId : messageIds) {
            ChatMessage cached = getMessageFromCache(msgId);
            if (cached != null) {
                result.add(cached);
            } else {
                missedIds.add(msgId);
            }
        }

        // Redis未命中 → 回源MySQL
        if (!missedIds.isEmpty()) {
            List<ChatMessage> dbMessages = chatMessageMapper.selectList(
                    new LambdaQueryWrapper<ChatMessage>()
                            .in(ChatMessage::getMessageId, missedIds)
                            .orderByAsc(ChatMessage::getCreateTime)
            );
            for (ChatMessage msg : dbMessages) {
                result.add(msg);
                // 回写Redis缓存
                cacheMessage(msg);
            }
        }

        return result;
    }

    /**
     * 从Redis读取单条消息
     */
    private ChatMessage getMessageFromCache(String messageId) {
        try {
            String key = ChatCacheConstants.messageDetailKey(messageId);
            return redisService.getCacheObject(key, ChatMessage.class);
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 重建会话的Redis缓存（Redis过期/未命中时回源MySQL重建）
     */
    private void rebuildSessionCache(String sessionId, List<String> messageIds) {
        if (messageIds.isEmpty()) {
            return;
        }
        try {
            String zsetKey = ChatCacheConstants.sessionMessagesKey(sessionId);
            for (String msgId : messageIds) {
                ChatMessage msg = getMessageFromCache(msgId);
                if (msg == null) {
                    msg = chatMessageMapper.selectOne(
                            new LambdaQueryWrapper<ChatMessage>()
                                    .eq(ChatMessage::getMessageId, msgId)
                    );
                }
                if (msg != null) {
                    long score = msg.getCreateTime() != null
                            ? msg.getCreateTime().atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli()
                            : System.currentTimeMillis();
                    redisService.addMemberZSet(zsetKey, msgId, score);
                }
            }
            redisService.expire(zsetKey, ChatCacheConstants.CHAT_CACHE_TTL_SECONDS);
        } catch (Exception e) {
            log.warn("重建会话缓存失败: sessionId={}", sessionId, e);
        }
    }

    // ==================== 发送消息 ====================

    /**
     * 发送消息并获取AI回复
     *
     * 流程:
     * 1. 如果没有sessionId，创建新会话
     * 2. 保存用户消息到MySQL + Redis
     * 3. 调用AI Agent获取回复（TODO: 对接Python LangGraph）
     * 4. 保存AI回复到MySQL + Redis
     * 5. 更新会话的最后消息时间
     *
     * @param sendMessageDTO 消息请求
     * @param userId         用户ID
     * @return AI回复消息VO
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public ChatMessageVO sendMessage(SendMessageDTO sendMessageDTO, Long userId) {
        // 1. 获取或创建会话
        ChatSession session = getOrCreateSession(sendMessageDTO.getSessionId(), userId, sendMessageDTO);

        // 2. 保存用户消息
        ChatMessage userMessage = saveMessage(
                session.getSessionId(), userId, "user",
                sendMessageDTO.getContent(), "text", null
        );

        // 3. 生成AI回复（TODO: 对接Python LangGraph agent）
        String aiContent = generateAiReply(session, sendMessageDTO.getContent());

        // 4. 保存AI回复
        ChatMessage aiMessage = saveMessage(
                session.getSessionId(), userId, "assistant",
                aiContent, "text", null
        );

        // 5. 更新会话信息
        updateSessionAfterMessage(session, sendMessageDTO.getContent(), aiMessage.getCreateTime());

        return convertToVO(aiMessage);
    }

    /**
     * 获取或创建会话
     */
    private ChatSession getOrCreateSession(String sessionId, Long userId, SendMessageDTO dto) {
        if (StringUtils.isNotBlank(sessionId)) {
            ChatSession existing = chatSessionMapper.selectOne(
                    new LambdaQueryWrapper<ChatSession>()
                            .eq(ChatSession::getSessionId, sessionId)
                            .eq(ChatSession::getUserId, userId)
                            .eq(ChatSession::getIsDeleted, 0)
            );
            if (existing != null) {
                return existing;
            }
            throw new ServiceException("会话不存在", ResultCode.INVALID_PARA.getCode());
        }

        // 创建新会话
        ChatSession newSession = new ChatSession();
        newSession.setSessionId(UUID.randomUUID().toString().replace("-", ""));
        newSession.setUserId(userId);
        // 标题取首条消息前30字
        String content = dto.getContent();
        String title = content.length() > 30 ? content.substring(0, 30) : content;
        newSession.setTitle(title.replace("\n", " "));
        newSession.setLastMessageTime(LocalDateTime.now());
        newSession.setMessageCount(0);
        newSession.setIsDeleted(0);
        newSession.setCreateTime(LocalDateTime.now());
        newSession.setUpdateTime(LocalDateTime.now());
        chatSessionMapper.insert(newSession);
        log.info("创建新会话: sessionId={}, userId={}", newSession.getSessionId(), userId);
        return newSession;
    }

    /**
     * 保存消息到MySQL并写入Redis缓存
     */
    private ChatMessage saveMessage(String sessionId, Long userId, String role,
                                     String content, String messageType, String metadataJson) {
        ChatMessage message = new ChatMessage();
        message.setMessageId(UUID.randomUUID().toString().replace("-", ""));
        message.setSessionId(sessionId);
        message.setUserId(userId);
        message.setRole(role);
        message.setContent(content);
        message.setMessageType(messageType);
        message.setMetadataJson(metadataJson);
        message.setCreateTime(LocalDateTime.now());
        chatMessageMapper.insert(message);

        // 写入Redis缓存
        cacheMessage(message);

        return message;
    }

    /**
     * 将消息写入Redis缓存
     *
     * 1. 更新ZSET: chat:session:{sessionId}:messages
     *    score = 消息创建时间戳（毫秒），member = messageId
     * 2. 保存Value: chat:message:{messageId} = 消息JSON
     * 3. 设置TTL = 1天
     */
    private void cacheMessage(ChatMessage message) {
        try {
            // 1. ZSET: 会话→消息ID映射，score=时间戳
            String zsetKey = ChatCacheConstants.sessionMessagesKey(message.getSessionId());
            long score = message.getCreateTime()
                    .atZone(java.time.ZoneId.systemDefault())
                    .toInstant()
                    .toEpochMilli();
            redisService.addMemberZSet(zsetKey, message.getMessageId(), (double) score);
            redisService.expire(zsetKey, ChatCacheConstants.CHAT_CACHE_TTL_SECONDS);

            // 2. Value: 消息详情
            String detailKey = ChatCacheConstants.messageDetailKey(message.getMessageId());
            redisService.setCacheObject(detailKey, message,
                    ChatCacheConstants.CHAT_CACHE_TTL_SECONDS, TimeUnit.SECONDS);
        } catch (Exception e) {
            // 缓存写入失败不影响主流程（MySQL已有数据）
            log.warn("消息缓存写入失败: messageId={}", message.getMessageId(), e);
        }
    }

    /**
     * 更新会话信息（发送消息后）
     */
    private void updateSessionAfterMessage(ChatSession session, String firstMessage, LocalDateTime msgTime) {
        boolean isFirstMessage = session.getMessageCount() == 0;
        LambdaUpdateWrapper<ChatSession> wrapper = new LambdaUpdateWrapper<>();
        wrapper.eq(ChatSession::getSessionId, session.getSessionId())
                .set(ChatSession::getLastMessageTime, msgTime)
                .setSql("message_count = message_count + 2"); // 用户消息 + AI回复
        if (isFirstMessage) {
            // 首条消息: 设置标题
            String title = firstMessage.length() > 30 ? firstMessage.substring(0, 30) : firstMessage;
            wrapper.set(ChatSession::getTitle, title.replace("\n", " "));
        }
        chatSessionMapper.update(null, wrapper);
    }

    /**
     * 生成AI回复 — 调用 Python LangGraph Agent 服务
     *
     * 通过 HTTP 调用 Python AI Server（FastAPI），由 Python 端
     * 驱动 LangGraph 工作流（保险推荐 / 知识问答 / 通用对话）
     */
    private String generateAiReply(ChatSession session, String userContent) {
        log.info("调用Python主Agent: sessionId={}", session.getSessionId());

        return pythonAgentClient.sendMessage(
                session.getSessionId(),
                String.valueOf(session.getUserId()),
                userContent
        );
    }

    // ==================== 删除会话 ====================

    /**
     * 逻辑删除会话
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteSession(String sessionId, Long userId) {
        checkSessionOwnership(sessionId, userId);

        LambdaUpdateWrapper<ChatSession> wrapper = new LambdaUpdateWrapper<>();
        wrapper.eq(ChatSession::getSessionId, sessionId)
                .eq(ChatSession::getUserId, userId)
                .set(ChatSession::getIsDeleted, 1);
        chatSessionMapper.update(null, wrapper);

        // 清除Redis缓存
        try {
            redisService.deleteObject(ChatCacheConstants.sessionMessagesKey(sessionId));
        } catch (Exception e) {
            log.warn("删除会话缓存失败: sessionId={}", sessionId, e);
        }

        log.info("会话已删除: sessionId={}, userId={}", sessionId, userId);
    }

    // ==================== 更新标题 ====================

    /**
     * 更新会话标题
     */
    @Override
    public void updateSessionTitle(String sessionId, String title, Long userId) {
        checkSessionOwnership(sessionId, userId);

        LambdaUpdateWrapper<ChatSession> wrapper = new LambdaUpdateWrapper<>();
        wrapper.eq(ChatSession::getSessionId, sessionId)
                .eq(ChatSession::getUserId, userId)
                .set(ChatSession::getTitle, title);
        chatSessionMapper.update(null, wrapper);
    }

    // ==================== 工具方法 ====================

    /**
     * 校验会话是否属于当前用户
     */
    private void checkSessionOwnership(String sessionId, Long userId) {
        ChatSession session = chatSessionMapper.selectOne(
                new LambdaQueryWrapper<ChatSession>()
                        .eq(ChatSession::getSessionId, sessionId)
                        .eq(ChatSession::getUserId, userId)
                        .eq(ChatSession::getIsDeleted, 0)
        );
        if (session == null) {
            throw new ServiceException("会话不存在或无权访问", ResultCode.INVALID_PARA.getCode());
        }
    }

    /**
     * 实体转VO
     */
    private ChatMessageVO convertToVO(ChatMessage message) {
        ChatMessageVO vo = new ChatMessageVO();
        vo.setMessageId(message.getMessageId());
        vo.setSessionId(message.getSessionId());
        vo.setRole(message.getRole());
        vo.setContent(message.getContent());
        vo.setMessageType(message.getMessageType());
        vo.setMetadataJson(message.getMetadataJson());
        vo.setCreateTime(message.getCreateTime());
        return vo;
    }
}
