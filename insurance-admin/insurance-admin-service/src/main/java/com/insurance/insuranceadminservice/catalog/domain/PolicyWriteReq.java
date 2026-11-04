package com.insurance.insuranceadminservice.catalog.domain;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
public class PolicyWriteReq {

    private Long id;

    private Long userId;

    private String policyNo;

    private String productName;

    private BigDecimal premium;

    private BigDecimal sumInsured;

    private Integer policyStatus;

    private LocalDate startDate;

    private LocalDate endDate;
}
