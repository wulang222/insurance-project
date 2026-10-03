package com.insurance.insuranceportalservice.chat.controller;

import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insuranceportalservice.chat.entity.dto.QueryMessagesDTO;
import com.insurance.insuranceportalservice.chat.entity.dto.SendMessageDTO;
import com.insurance.insuranceportalservice.chat.entity.vo.ChatMessageVO;
import com.insurance.insuranceportalservice.chat.entity.vo.ChatSessionVO;
import com.insurance.insuranceportalservice.chat.service.IChatService;
import com.insurance.insurancecommonsecurity.utils.SecurityUtil;
import com.insurance.insurancecommonsecurity.utils.JwtUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

/**
 * 聊天控制器
 *
 * 提供会话管理 + 消息收发 + 历史查询的REST API
 *
 * @author insurance
 */
@Slf4j
@RestController
@RequestMapping("/chat")
public class ChatController {

    @Autowired
    private IChatService chatService;

    // ==================== 会话管理 ====================

    /**
     * 获取当前用户的会话列表（按最后消息时间倒序）
     *
     * @return 会话列表
     */
    @GetMapping("/sessions")
    public R<List<ChatSessionVO>> listSessions() {
        Long userId = getCurrentUserId();
        List<ChatSessionVO> sessions = chatService.listSessions(userId);
        return R.ok(sessions);
    }

    /**
     * 删除会话（逻辑删除）
     *
     * @param sessionId 会话ID
     * @return 操作结果
     */
    @DeleteMapping("/session/{sessionId}")
    public R<Void> deleteSession(@PathVariable String sessionId) {
        Long userId = getCurrentUserId();
        chatService.deleteSession(sessionId, userId);
        return R.ok();
    }

    /**
     * 更新会话标题
     *
     * @param sessionId 会话ID
     * @param title     新标题
     * @return 操作结果
     */
    @PutMapping("/session/{sessionId}/title")
    public R<Void> updateSessionTitle(@PathVariable String sessionId,
                                       @RequestParam String title) {
        Long userId = getCurrentUserId();
        chatService.updateSessionTitle(sessionId, title, userId);
        return R.ok();
    }

    // ==================== 消息收发 ====================

    /**
     * 发送消息并获取AI回复
     *
     * - 如果传了sessionId则追加到已有会话
     * - 如果不传sessionId则自动创建新会话
     *
     * @param sendMessageDTO 消息请求
     * @return AI回复消息
     */
    @PostMapping("/send")
    public R<ChatMessageVO> sendMessage(@RequestBody @Validated SendMessageDTO sendMessageDTO) {
        Long userId = getCurrentUserId();
        ChatMessageVO reply = chatService.sendMessage(sendMessageDTO, userId);
        return R.ok(reply);
    }

    /**
     * 查询会话历史消息（支持分页）
     *
     * 查询流程:
     * 1. 从Redis ZSET获取会话的消息ID列表（按时间排序）
     * 2. 批量从Redis获取消息详情
     * 3. Redis未命中时回源MySQL
     *
     * @param queryDTO 查询条件
     * @return 消息列表
     */
    @PostMapping("/messages")
    public R<List<ChatMessageVO>> queryMessages(@RequestBody @Validated QueryMessagesDTO queryDTO) {
        Long userId = getCurrentUserId();
        List<ChatMessageVO> messages = chatService.queryMessages(queryDTO, userId);
        return R.ok(messages);
    }

    // ==================== 流式消息（SSE） ====================

    /**
     * 流式发送消息 — 通过 SSE 实时返回 AI 回复
     *
     * 流程: 前端 → Java Controller → Python AI Server (SSE) → 前端
     * 适用于需要实时打字效果的对话场景
     *
     * @param sendMessageDTO 消息请求
     * @return SseEmitter
     */
    @PostMapping("/send/stream")
    public SseEmitter sendMessageStream(@RequestBody @Validated SendMessageDTO sendMessageDTO) {
        Long userId = getCurrentUserId();
        log.info("流式对话请求: userId={}, sessionId={}", userId,
                sendMessageDTO.getSessionId());
        return chatService.sendMessageStream(sendMessageDTO, userId);
    }

    // ==================== 工具方法 ====================

    /**
     * 从当前请求的Token中解析用户ID
     *
     * @return 用户ID
     */
    private Long getCurrentUserId() {
        String token = SecurityUtil.getToken();
        String userIdStr = JwtUtil.getUserId(token);
        return Long.valueOf(userIdStr);
    }
}
