package com.insurance.insuranceportalservice.chat.client;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Python Agent HTTP 客户端
 *
 * 调用 Python AI 服务（FastAPI），支持同步和流式两种模式
 *
 * @author insurance
 */
@Slf4j
@Component
public class PythonAgentClient {

    @Value("${insurance.ai.python.url:http://localhost:18084}")
    private String pythonBaseUrl;

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public PythonAgentClient() {
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    // ==================== 请求/响应模型 ====================

    @Data
    public static class ChatRequest {
        @JsonProperty("session_id")
        private String sessionId;
        @JsonProperty("user_id")
        private String userId;
        private String message;
    }

    @Data
    public static class ChatResponse {
        @JsonProperty("session_id")
        private String sessionId;
        @JsonProperty("message_id")
        private String messageId;
        private String content;
        @JsonProperty("handled_by")
        private String handledBy;
        private String route;
        @JsonProperty("route_reason")
        private String routeReason;
        private String error;
    }

    @Data
    public static class StreamDelta {
        @JsonProperty("session_id")
        private String sessionId;
        @JsonProperty("message_id")
        private String messageId;
        private String delta;
        @JsonProperty("handled_by")
        private String handledBy;
        private String route;
        @JsonProperty("route_reason")
        private String routeReason;
        private boolean done;
        private String error;
    }

    // ==================== 同步调用 ====================

    /**
     * 同步发送消息给 Python AI 服务
     *
     * @param sessionId 会话ID（新会话可为空）
     * @param userId    用户ID
     * @param message   用户消息
     * @return AI回复
     */
    public String sendMessage(String sessionId, String userId, String message) {
        String url = pythonBaseUrl + "/chat";
        log.info("调用Python AI服务: url={}, sessionId={}", url, sessionId);

        try {
            Map<String, Object> body = new HashMap<>();
            body.put("session_id", sessionId != null ? sessionId : "");
            body.put("user_id", userId != null ? userId : "");
            body.put("message", message);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

            ResponseEntity<Map> response = restTemplate.postForEntity(url, request, Map.class);

            if (response.getBody() != null) {
                Object content = response.getBody().get("content");
                if (content != null) {
                    return content.toString();
                }
                Object error = response.getBody().get("error");
                if (error != null) {
                    log.error("Python AI服务返回错误: {}", error);
                    return "AI服务暂不可用，请稍后重试。";
                }
            }
            return "AI服务返回为空，请稍后重试。";
        } catch (Exception e) {
            log.error("调用Python AI服务失败: url={}, error={}", url, e.getMessage(), e);
            return "您好！AI服务暂时无法连接，请稍后重试。\n\n（提示：请确保 Python AI Server 已启动在 " + pythonBaseUrl + "）";
        }
    }

    // ==================== 流式调用（SSE） ====================

    /**
     * 流式发送消息给 Python AI 服务，返回 SseEmitter
     *
     * @param sessionId 会话ID
     * @param userId    用户ID
     * @param message   用户消息
     * @return SseEmitter 流式响应
     */
    public SseEmitter sendMessageStream(String sessionId, String userId, String message) {
        SseEmitter emitter = new SseEmitter(300000L); // 5分钟超时

        CompletableFuture.runAsync(() -> {
            HttpURLConnection connection = null;
            try {
                String url = pythonBaseUrl + "/chat/stream";
                Map<String, Object> body = new HashMap<>();
                body.put("session_id", sessionId != null ? sessionId : "");
                body.put("user_id", userId != null ? userId : "");
                body.put("message", message);

                String jsonBody = objectMapper.writeValueAsString(body);

                URI uri = URI.create(url);
                connection = (HttpURLConnection) uri.toURL().openConnection();
                connection.setRequestMethod("POST");
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setRequestProperty("Accept", "text/event-stream");
                connection.setDoOutput(true);
                connection.setConnectTimeout(30000);
                connection.setReadTimeout(300000);

                // 写入请求体
                try (var os = connection.getOutputStream()) {
                    os.write(jsonBody.getBytes(StandardCharsets.UTF_8));
                    os.flush();
                }

                // 读取 SSE 流
                int responseCode = connection.getResponseCode();
                if (responseCode != 200) {
                    emitter.completeWithError(new RuntimeException("Python AI服务返回错误码: " + responseCode));
                    return;
                }

                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    StringBuilder dataBuffer = new StringBuilder();
                    while ((line = reader.readLine()) != null) {
                        if (line.startsWith("data: ")) {
                            String data = line.substring(6);
                            StreamDelta delta = objectMapper.readValue(data, StreamDelta.class);

                            if (delta.getError() != null) {
                                emitter.completeWithError(new RuntimeException(delta.getError()));
                                return;
                            }

                            if (delta.isDone()) {
                                // 发送完成事件
                                SseEmitter.SseEventBuilder event = SseEmitter.event()
                                        .name("done")
                                        .data(objectMapper.writeValueAsString(delta));
                                emitter.send(event);
                                emitter.complete();
                                return;
                            }

                            // 发送增量内容
                            SseEmitter.SseEventBuilder event = SseEmitter.event()
                                    .name("delta")
                                    .data(objectMapper.writeValueAsString(delta));
                            emitter.send(event);
                        }
                    }
                }
                emitter.complete();
            } catch (Exception e) {
                log.error("流式调用Python AI服务失败", e);
                try {
                    SseEmitter.SseEventBuilder errorEvent = SseEmitter.event()
                            .name("error")
                            .data("{\"error\": \"" + e.getMessage() + "\"}");
                    emitter.send(errorEvent);
                } catch (Exception ignored) {}
                emitter.completeWithError(e);
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }
        });

        return emitter;
    }

    /**
     * 健康检查
     */
    public boolean isHealthy() {
        try {
            String url = pythonBaseUrl + "/health";
            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            return false;
        }
    }
}
