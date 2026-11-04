package com.insurance.insuranceadminservice.knowledge.store;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

@Component
public class HttpOriginalFileStore implements OriginalFileStore {

    private final RestTemplate restTemplate = new RestTemplate();

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${file.service-url:http://127.0.0.1:18080/file/upload}")
    private String uploadUrl;

    @Override
    public String store(String filename, byte[] content) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new NamedBytes(filename, content));
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(
                    uploadUrl,
                    new HttpEntity<>(body, headers),
                    String.class
            );
            JsonNode root = objectMapper.readTree(response.getBody());
            if (root.path("code").asInt() != ResultCode.SUCCESS.getCode()) {
                throw new ServiceException("原文保存失败", ResultCode.ERROR.getCode());
            }
            String key = root.path("data").path("key").asText("");
            if (key.isBlank()) {
                throw new ServiceException("原文保存失败", ResultCode.ERROR.getCode());
            }
            return key;
        } catch (ServiceException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new ServiceException("原文保存失败", ResultCode.ERROR.getCode());
        }
    }

    private static final class NamedBytes extends ByteArrayResource {
        private final String filename;

        private NamedBytes(String filename, byte[] content) {
            super(content);
            this.filename = filename;
        }

        @Override
        public String getFilename() {
            return filename;
        }
    }
}
