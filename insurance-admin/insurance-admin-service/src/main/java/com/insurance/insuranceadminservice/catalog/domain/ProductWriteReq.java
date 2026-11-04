package com.insurance.insuranceadminservice.catalog.domain;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class ProductWriteReq {

    private Long id;

    private String productId;

    private String productName;

    private String insuranceType;

    private Integer minAge;

    private Integer maxAge;

    private BigDecimal minPrice;

    private BigDecimal maxPrice;

    private String targetOccupations;

    private String description;

    private Boolean active;
}
