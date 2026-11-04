package com.insurance.insuranceadminservice.catalog.domain;

import lombok.Data;

@Data
public class ProductListReq {

    private Integer pageNo = 1;

    private Integer pageSize = 10;

    private String insuranceType;

    private String productId;

    private Boolean active;
}
