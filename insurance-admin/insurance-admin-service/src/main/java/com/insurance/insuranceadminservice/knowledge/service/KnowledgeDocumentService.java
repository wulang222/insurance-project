package com.insurance.insuranceadminservice.knowledge.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeChunkView;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeDocument;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeListReq;
import com.insurance.insuranceadminservice.knowledge.ingest.KnowledgeIngestClient;
import com.insurance.insuranceadminservice.knowledge.ingest.KnowledgeIngestWorker;
import com.insurance.insuranceadminservice.knowledge.mapper.KnowledgeDocumentMapper;
import com.insurance.insuranceadminservice.knowledge.store.OriginalFileStore;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Service
public class KnowledgeDocumentService {

    public static final int MAX_BYTES = 20 * 1024 * 1024;

    private static final Set<String> ALLOWED = Set.of("pdf", "docx", "md", "txt");

    @Autowired
    private KnowledgeDocumentMapper documentMapper;

    @Autowired
    private OriginalFileStore fileStore;

    @Autowired
    private KnowledgeIngestWorker ingestWorker;

    @Autowired
    private KnowledgeIngestClient ingestClient;

    public KnowledgeDocument create(MultipartFile file, String title, String productId, Long operatorId) {
        byte[] content = readAllowed(file);
        String filename = file.getOriginalFilename();
        String storageKey = fileStore.store(filename, content);
        KnowledgeDocument document = new KnowledgeDocument();
        document.setTitle(StringUtils.defaultIfBlank(title, filename));
        document.setProductId(StringUtils.trimToNull(productId));
        document.setFileType(extension(filename));
        document.setStorageKey(storageKey);
        document.setChecksum(sha256(content));
        document.setStatus("processing");
        document.setChunkCount(0);
        document.setOperatorId(operatorId);
        documentMapper.insert(document);
        ingestWorker.ingest(document.getId(), document.getTitle(), document.getProductId(), document.getChecksum(), filename, content);
        return document;
    }

    public KnowledgeDocument replace(Long documentId, MultipartFile file, String title, Long operatorId) {
        KnowledgeDocument document = documentMapper.selectById(documentId);
        if (document == null) {
            throw new ServiceException("文档不存在", ResultCode.INVALID_PARA.getCode());
        }
        byte[] content = readAllowed(file);
        String filename = file.getOriginalFilename();
        document.setStorageKey(fileStore.store(filename, content));
        document.setChecksum(sha256(content));
        document.setFileType(extension(filename));
        if (StringUtils.isNotBlank(title)) {
            document.setTitle(title);
        }
        document.setStatus("processing");
        document.setErrorMessage(null);
        document.setOperatorId(operatorId);
        documentMapper.updateById(document);
        ingestWorker.ingest(document.getId(), document.getTitle(), document.getProductId(), document.getChecksum(), filename, content);
        return document;
    }

    public BasePageDTO<KnowledgeDocument> list(KnowledgeListReq request) {
        int pageNo = request.getPageNo() == null || request.getPageNo() < 1 ? 1 : request.getPageNo();
        int pageSize = request.getPageSize() == null || request.getPageSize() < 1 ? 10 : request.getPageSize();
        QueryWrapper<KnowledgeDocument> query = new QueryWrapper<>();
        if (StringUtils.isNotBlank(request.getStatus())) {
            query.eq("status", request.getStatus());
        }
        Long totals = documentMapper.selectCount(query);
        BasePageDTO<KnowledgeDocument> page = new BasePageDTO<>();
        page.setTotals(totals.intValue());
        page.setTotalPages(BasePageDTO.calculateTotalPages(totals, pageSize));
        query.orderByDesc("id");
        query.last("limit " + ((pageNo - 1) * pageSize) + "," + pageSize);
        page.setList(documentMapper.selectList(query));
        return page;
    }

    public List<KnowledgeChunkView> chunks(Long documentId) {
        if (documentMapper.selectById(documentId) == null) {
            throw new ServiceException("文档不存在", ResultCode.INVALID_PARA.getCode());
        }
        return ingestClient.chunks(documentId);
    }

    private byte[] readAllowed(MultipartFile file) {
        if (file == null || file.getOriginalFilename() == null) {
            throw new ServiceException("文件不能为空", ResultCode.INVALID_PARA.getCode());
        }
        String type = extension(file.getOriginalFilename());
        if (!ALLOWED.contains(type)) {
            throw new ServiceException("只接受 pdf、docx、md、txt", ResultCode.INVALID_PARA.getCode());
        }
        byte[] content;
        try {
            content = file.getBytes();
        } catch (Exception exception) {
            throw new ServiceException("文件读取失败", ResultCode.INVALID_PARA.getCode());
        }
        if (content.length == 0) {
            throw new ServiceException("文件不能为空", ResultCode.INVALID_PARA.getCode());
        }
        if (content.length > MAX_BYTES) {
            throw new ServiceException("文件超过 20MB", ResultCode.INVALID_PARA.getCode());
        }
        return content;
    }

    private static String extension(String filename) {
        int dot = filename.lastIndexOf('.');
        if (dot < 0 || dot == filename.length() - 1) {
            return "";
        }
        return filename.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private static String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (Exception exception) {
            throw new ServiceException("无法计算校验和", ResultCode.ERROR.getCode());
        }
    }
}
