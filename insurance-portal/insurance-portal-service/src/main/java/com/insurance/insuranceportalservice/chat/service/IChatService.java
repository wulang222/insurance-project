package com.insurance.insuranceportalservice.chat.service;

import com.insurance.insuranceportalservice.chat.entity.dto.QueryMessagesDTO;
import com.insurance.insuranceportalservice.chat.entity.dto.SendMessageDTO;
import com.insurance.insuranceportalservice.chat.entity.vo.ChatMessageVO;
import com.insurance.insuranceportalservice.chat.entity.vo.ChatSessionVO;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

/**
 * 聊天服务接口
 *
 * @author insurance
 */
public interface IChatService {

    /**
     * 查询用户的会话列表（按最后消息时间倒序）
     *
     * @param userId 用户ID
     * @return 会话列表
     */
    List<ChatSessionVO> listSessions(Long userId);

    /**
     * 查询会话的历史消息（先查Redis zset获取消息ID列表，再根据消息ID查详情）
     *
     * @param queryDTO 查询条件
     * @param userId   用户ID
     * @return 消息列表
     */
    List<ChatMessageVO> queryMessages(QueryMessagesDTO queryDTO, Long userId);

    /**
     * 发送消息（保存到MySQL + 更新Redis缓存）
     *
     * @param sendMessageDTO 消息请求
     * @param userId         用户ID
     * @return AI回复消息
     */
    ChatMessageVO sendMessage(SendMessageDTO sendMessageDTO, Long userId);

    /**
     * 流式发送消息，并在收到标准 run.result 事件后持久化完整元数据。
     */
    SseEmitter sendMessageStream(SendMessageDTO sendMessageDTO, Long userId);

    /**
     * 删除会话（逻辑删除）
     *
     * @param sessionId 会话ID
     * @param userId    用户ID
     */
    void deleteSession(String sessionId, Long userId);

    /**
     * 更新会话标题
     *
     * @param sessionId 会话ID
     * @param title     新标题
     * @param userId    用户ID
     */
    void updateSessionTitle(String sessionId, String title, Long userId);
}
