package com.insurance.insuranceadminservice.catalog.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.insurance.insurancecommoncore.domain.entity.BaseDO;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("user_policy_history")
public class UserPolicyHistory extends BaseDO {

    private Long userId;

    private String policyNo;

    private String productName;

    private BigDecimal premium;

    private BigDecimal sumInsured;

    private Integer policyStatus;

    private LocalDate startDate;

    private LocalDate endDate;

    private LocalDateTime purchaseTime;
}
