package com.insurance.insuranceadminservice.knowledge.domain;

import lombok.Data;

import java.util.Map;

@Data
public class KnowledgeChunkView {

    private String text;

    private Map<String, Object> metadata;
}
