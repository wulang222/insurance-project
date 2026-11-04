package com.insurance.insuranceadminservice.knowledge.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.insurance.insurancecommoncore.domain.entity.BaseDO;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("knowledge_document")
public class KnowledgeDocument extends BaseDO {

    private String title;

    private String productId;

    private String fileType;

    private String storageKey;

    private String checksum;

    private String status;

    private Integer chunkCount;

    private String errorMessage;

    private Long operatorId;
}
