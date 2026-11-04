package com.insurance.insuranceadminservice.knowledge;

import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeChunkView;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeDocument;
import com.insurance.insuranceadminservice.knowledge.ingest.KnowledgeIngestClient;
import com.insurance.insuranceadminservice.knowledge.ingest.KnowledgeIngestWorker;
import com.insurance.insuranceadminservice.knowledge.mapper.KnowledgeDocumentMapper;
import com.insurance.insuranceadminservice.knowledge.service.KnowledgeDocumentService;
import com.insurance.insuranceadminservice.knowledge.store.OriginalFileStore;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class KnowledgeDocumentServiceTest {

    @Mock
    private KnowledgeDocumentMapper documentMapper;

    @Mock
    private OriginalFileStore fileStore;

    @Mock
    private KnowledgeIngestWorker ingestWorker;

    @Mock
    private KnowledgeIngestClient ingestClient;

    @InjectMocks
    private KnowledgeDocumentService knowledgeDocumentService;

    @InjectMocks
    private KnowledgeIngestWorker ingestWorkerBean;

    @Test
    void rejectedFileTypeDoesNotStoreOrIngest() {
        MockMultipartFile file = new MockMultipartFile("file", "notes.exe", "application/octet-stream", new byte[]{1});

        Assertions.assertThrows(ServiceException.class, () -> knowledgeDocumentService.create(file, "标题", null, 1L));

        verify(fileStore, never()).store(any(), any());
        verify(ingestWorker, never()).ingest(any(), any(), any(), any(), any(), any());
        verify(documentMapper, never()).insert(any(KnowledgeDocument.class));
    }

    @Test
    void emptyFileIsRejected() {
        MockMultipartFile file = new MockMultipartFile("file", "clause.txt", "text/plain", new byte[0]);

        Assertions.assertThrows(ServiceException.class, () -> knowledgeDocumentService.create(file, "标题", null, 1L));

        verify(fileStore, never()).store(any(), any());
    }

    @Test
    void oversizedFileIsRejected() {
        byte[] content = new byte[KnowledgeDocumentService.MAX_BYTES + 1];
        MockMultipartFile file = new MockMultipartFile("file", "clause.txt", "text/plain", content);

        Assertions.assertThrows(ServiceException.class, () -> knowledgeDocumentService.create(file, "标题", null, 1L));

        verify(fileStore, never()).store(any(), any());
    }

    @Test
    void acceptedFileStartsProcessing() {
        when(fileStore.store(eq("clause.md"), any())).thenReturn("oss/clause.md");
        when(documentMapper.insert(any(KnowledgeDocument.class))).thenAnswer(invocation -> {
            KnowledgeDocument document = invocation.getArgument(0);
            document.setId(15L);
            return 1;
        });
        MockMultipartFile file = new MockMultipartFile("file", "clause.md", "text/markdown", "等待期三十天".getBytes());

        KnowledgeDocument created = knowledgeDocumentService.create(file, "重疾条款", "CI001", 1L);

        Assertions.assertEquals("processing", created.getStatus());
        Assertions.assertEquals("CI001", created.getProductId());
        Assertions.assertEquals(64, created.getChecksum().length());
        verify(ingestWorker).ingest(eq(15L), eq("重疾条款"), eq("CI001"), any(), eq("clause.md"), any());
    }

    @Test
    void missingTokenOrIngestFailureStaysFailed() {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setId(15L);
        document.setStatus("processing");
        when(documentMapper.selectById(15L)).thenReturn(document);
        when(ingestClient.ingest(anyLong(), any(), any(), any(), any(), any()))
                .thenThrow(new IllegalStateException("内部入库密钥缺失"));

        ingestWorkerBean.ingest(15L, "重疾条款", "CI001", "abc", "clause.md", new byte[]{1});

        Assertions.assertEquals("failed", document.getStatus());
        Assertions.assertNotEquals("available", document.getStatus());
        verify(documentMapper).updateById(document);
    }

    @Test
    void successfulIngestBecomesAvailable() {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setId(15L);
        document.setStatus("processing");
        when(documentMapper.selectById(15L)).thenReturn(document);
        when(ingestClient.ingest(anyLong(), any(), any(), any(), any(), any())).thenReturn(3);

        ingestWorkerBean.ingest(15L, "重疾条款", "CI001", "abc", "clause.md", new byte[]{1});

        Assertions.assertEquals("available", document.getStatus());
        Assertions.assertEquals(3, document.getChunkCount());
        Assertions.assertNull(document.getErrorMessage());
    }

    @Test
    void listAndChunksExposeStoredFields() {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setId(15L);
        document.setTitle("重疾条款");
        document.setProductId("CI001");
        document.setChecksum("abc");
        document.setStatus("available");
        document.setChunkCount(2);
        when(documentMapper.selectCount(any())).thenReturn(1L);
        when(documentMapper.selectList(any())).thenReturn(List.of(document));
        when(documentMapper.selectById(15L)).thenReturn(document);
        KnowledgeChunkView chunk = new KnowledgeChunkView();
        chunk.setText("等待期三十天");
        chunk.setMetadata(Map.of("title", "重疾条款", "checksum", "abc", "product_id", "CI001"));
        when(ingestClient.chunks(15L)).thenReturn(List.of(chunk));

        KnowledgeDocument listed = knowledgeDocumentService.list(new com.insurance.insuranceadminservice.knowledge.domain.KnowledgeListReq())
                .getList().get(0);
        Assertions.assertEquals("available", listed.getStatus());
        Assertions.assertEquals("重疾条款", listed.getTitle());
        Assertions.assertEquals("CI001", listed.getProductId());
        Assertions.assertEquals("abc", listed.getChecksum());
        Assertions.assertEquals(2, listed.getChunkCount());
        Assertions.assertEquals("等待期三十天", knowledgeDocumentService.chunks(15L).get(0).getText());
        Assertions.assertEquals("CI001", knowledgeDocumentService.chunks(15L).get(0).getMetadata().get("product_id"));
    }

    @Test
    void replaceKeepsTheSameDocumentId() {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setId(15L);
        document.setTitle("旧标题");
        document.setProductId("CI001");
        document.setStatus("available");
        when(documentMapper.selectById(15L)).thenReturn(document);
        when(fileStore.store(eq("next.md"), any())).thenReturn("oss/next.md");
        MockMultipartFile file = new MockMultipartFile("file", "next.md", "text/markdown", "新版本".getBytes());

        KnowledgeDocument replaced = knowledgeDocumentService.replace(15L, file, "新标题", 1L);

        Assertions.assertEquals(15L, replaced.getId());
        Assertions.assertEquals("processing", replaced.getStatus());
        ArgumentCaptor<KnowledgeDocument> captor = ArgumentCaptor.forClass(KnowledgeDocument.class);
        verify(documentMapper).updateById(captor.capture());
        Assertions.assertEquals(15L, captor.getValue().getId());
    }
}
