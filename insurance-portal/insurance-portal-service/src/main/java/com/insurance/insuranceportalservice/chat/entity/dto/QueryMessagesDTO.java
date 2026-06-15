package com.insurance.insuranceportalservice.chat.entity.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 查询历史消息请求DTO
 *
 * @author insurance
 */
@Data
public class QueryMessagesDTO {

    /**
     * 会话ID
     */
    @NotBlank(message = "会话ID不能为空")
    private String sessionId;

    /**
     * 页码（从1开始）
     */
    private Integer pageNum = 1;

    /**
     * 每页大小
     */
    private Integer pageSize = 20;
}
