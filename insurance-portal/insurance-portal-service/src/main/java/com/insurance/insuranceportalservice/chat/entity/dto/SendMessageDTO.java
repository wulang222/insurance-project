package com.insurance.insuranceportalservice.chat.entity.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 发送消息请求DTO
 *
 * @author insurance
 */
@Data
public class SendMessageDTO {

    /**
     * 会话ID（新会话时为空，由后端创建）
     */
    private String sessionId;

    /**
     * 消息内容
     */
    @NotBlank(message = "消息内容不能为空")
    private String content;

}
