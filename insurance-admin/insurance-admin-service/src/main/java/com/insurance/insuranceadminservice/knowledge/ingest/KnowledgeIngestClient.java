package com.insurance.insuranceadminservice.knowledge.ingest;

import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeChunkView;

import java.util.List;

public interface KnowledgeIngestClient {

    int ingest(long documentId, String title, String productId, String checksum, String filename, byte[] content);

    List<KnowledgeChunkView> chunks(long documentId);
}
