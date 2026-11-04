package com.insurance.insuranceadminservice.knowledge.ingest;

import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeDocument;
import com.insurance.insuranceadminservice.knowledge.mapper.KnowledgeDocumentMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
public class KnowledgeIngestWorker {

    @Autowired
    private KnowledgeDocumentMapper documentMapper;

    @Autowired
    private KnowledgeIngestClient ingestClient;

    @Async
    public void ingest(Long documentId, String title, String productId, String checksum, String filename, byte[] content) {
        try {
            int chunkCount = ingestClient.ingest(documentId, title, productId, checksum, filename, content);
            KnowledgeDocument document = documentMapper.selectById(documentId);
            if (document == null) {
                return;
            }
            document.setStatus("available");
            document.setChunkCount(chunkCount);
            document.setErrorMessage(null);
            documentMapper.updateById(document);
        } catch (Exception exception) {
            KnowledgeDocument document = documentMapper.selectById(documentId);
            if (document == null) {
                return;
            }
            document.setStatus("failed");
            String message = exception.getMessage() == null ? "入库失败" : exception.getMessage();
            document.setErrorMessage(message.length() > 1000 ? message.substring(0, 1000) : message);
            documentMapper.updateById(document);
        }
    }
}
