package com.insurance.insuranceadminservice.user.domain.vo;

import com.insurance.insurancecommondomain.domain.vo.LoginUserVO;
import lombok.Data;

/**
 * B端用户登录信息
 */
@Data
public class SysUserLoginVO extends LoginUserVO {
    /**
     * 昵称
     */
    private String nickName;

    /**
     * 身份
     */
    private String identity;

    /**
     * 状态
     */
    private String status;
}
