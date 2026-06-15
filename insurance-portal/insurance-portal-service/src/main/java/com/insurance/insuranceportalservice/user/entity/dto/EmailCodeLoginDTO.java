package com.insurance.insuranceportalservice.user.entity.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class EmailCodeLoginDTO extends LoginDTO{
    /**
     * 邮箱账号
     */
    @NotBlank(message = "邮箱账号不能为空")
    private String email;

    /**
     * 验证码
     */
    @NotBlank(message = "验证码不能为空")
    private String code;
}
