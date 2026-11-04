package com.insurance.insuranceadminservice.catalog.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.insurance.insurancecommoncore.domain.entity.BaseDO;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("insurance_products")
public class InsuranceProduct extends BaseDO {

    private String productId;

    private String productName;

    private String insuranceType;

    private Integer minAge;

    private Integer maxAge;

    private BigDecimal minPrice;

    private BigDecimal maxPrice;

    private String targetOccupations;

    private String description;

    @TableField("is_active")
    private Integer isActive;
}
