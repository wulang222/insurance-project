package com.insurance.insuranceadminservice.knowledge.ingest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeChunkView;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class HttpKnowledgeIngestClient implements KnowledgeIngestClient {

    private final RestTemplate restTemplate = new RestTemplate();

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${knowledge.service-url:http://127.0.0.1:18084}")
    private String serviceUrl;

    @Value("${knowledge.internal-token:}")
    private String internalToken;

    @Override
    public int ingest(long documentId, String title, String productId, String checksum, String filename, byte[] content) {
        requireToken();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("document_id", documentId);
        payload.put("filename", filename);
        payload.put("content_base64", Base64.getEncoder().encodeToString(content));
        payload.put("title", title);
        payload.put("checksum", checksum);
        payload.put("product_id", productId);
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(
                    serviceUrl + "/internal/knowledge/ingest",
                    new HttpEntity<>(objectMapper.writeValueAsString(payload), jsonHeaders()),
                    String.class
            );
            return objectMapper.readTree(response.getBody()).path("chunk_count").asInt();
        } catch (RuntimeException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalStateException("入库失败", exception);
        }
    }

    @Override
    public List<KnowledgeChunkView> chunks(long documentId) {
        requireToken();
        ResponseEntity<String> response = restTemplate.exchange(
                serviceUrl + "/internal/knowledge/documents/" + documentId + "/chunks",
                HttpMethod.GET,
                new HttpEntity<>(jsonHeaders()),
                String.class
        );
        try {
            JsonNode rows = objectMapper.readTree(response.getBody()).path("chunks");
            List<KnowledgeChunkView> chunks = new ArrayList<>();
            if (rows.isArray()) {
                for (JsonNode row : rows) {
                    KnowledgeChunkView view = new KnowledgeChunkView();
                    view.setText(row.path("text").asText(""));
                    view.setMetadata(objectMapper.convertValue(row.path("metadata"), objectMapper.getTypeFactory()
                            .constructMapType(java.util.LinkedHashMap.class, String.class, Object.class)));
                    chunks.add(view);
                }
            }
            return chunks;
        } catch (Exception exception) {
            throw new IllegalStateException("读取分块失败", exception);
        }
    }

    private void requireToken() {
        if (StringUtils.isBlank(internalToken)) {
            throw new IllegalStateException("内部入库密钥缺失");
        }
    }

    private HttpHeaders jsonHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", internalToken);
        return headers;
    }
}
