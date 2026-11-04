package com.insurance.insuranceadminservice.catalog.domain;

import lombok.Data;

@Data
public class PolicyListReq {

    private Integer pageNo = 1;

    private Integer pageSize = 10;

    private Long userId;

    private Integer policyStatus;
}
