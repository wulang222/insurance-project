package com.insurance.insuranceportalservice.chat.service.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.insurance.insuranceportalservice.chat.client.PythonAgentClient;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ChatServiceImplTest {

    @Test
    void buildsRunMetadataForHistoryAndCitationRendering() throws Exception {
        PythonAgentClient.RunResponse response = new PythonAgentClient.RunResponse();
        response.setRunId("run-7");
        response.setStatus("needs_input");
        response.setHandledBy(List.of("profile_agent", "knowledge_agent"));
        response.setCitations(List.of(Map.of(
                "citation_id", "CIT-1",
                "title", "重疾险条款",
                "excerpt", "等待期为九十天"
        )));
        response.setWarnings(List.of("未检索到续保规则"));
        response.setRequiredInput(Map.of(
                "question", "请补充年龄",
                "fields", List.of("age")
        ));
        response.setTrace(Map.of("spans", List.of(Map.of(
                "name", "run run-7",
                "span_id", "trace-root-7"
        ))));

        String metadata = new ChatServiceImpl().buildMetadataJson(response);
        JsonNode json = new ObjectMapper().readTree(metadata);

        assertEquals("run-7", json.get("runId").asText());
        assertEquals("needs_input", json.get("status").asText());
        assertEquals("trace-root-7", json.get("traceId").asText());
        assertEquals(2, json.get("handledBy").size());
        assertEquals("CIT-1", json.get("citations").get(0).get("citation_id").asText());
        assertTrue(json.has("requiredInput"));
    }
}
