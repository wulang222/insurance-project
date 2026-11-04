package com.insurance.insuranceadminservice.knowledge.domain;

import lombok.Data;

@Data
public class KnowledgeListReq {

    private Integer pageNo = 1;

    private Integer pageSize = 10;

    private String status;
}
