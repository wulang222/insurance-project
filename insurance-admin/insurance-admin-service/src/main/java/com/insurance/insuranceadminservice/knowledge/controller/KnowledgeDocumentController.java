package com.insurance.insuranceadminservice.knowledge.controller;

import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeChunkView;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeDocument;
import com.insurance.insuranceadminservice.knowledge.domain.KnowledgeListReq;
import com.insurance.insuranceadminservice.knowledge.service.KnowledgeDocumentService;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insurancecommonsecurity.service.TokenService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/knowledge")
public class KnowledgeDocumentController {

    @Autowired
    private KnowledgeDocumentService knowledgeDocumentService;

    @Autowired
    private TokenService tokenService;

    @PostMapping("/upload")
    public R<KnowledgeDocument> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "title", required = false) String title,
            @RequestParam(value = "productId", required = false) String productId
    ) {
        return R.ok(knowledgeDocumentService.create(file, title, productId, operatorId()));
    }

    @PostMapping("/{id}/replace")
    public R<KnowledgeDocument> replace(
            @PathVariable("id") Long id,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "title", required = false) String title
    ) {
        return R.ok(knowledgeDocumentService.replace(id, file, title, operatorId()));
    }

    @PostMapping("/list")
    public R<BasePageDTO<KnowledgeDocument>> list(@RequestBody KnowledgeListReq request) {
        return R.ok(knowledgeDocumentService.list(request));
    }

    @GetMapping("/{id}/chunks")
    public R<List<KnowledgeChunkView>> chunks(@PathVariable("id") Long id) {
        return R.ok(knowledgeDocumentService.chunks(id));
    }

    private Long operatorId() {
        if (tokenService.getLoginUser() == null) {
            return null;
        }
        return tokenService.getLoginUser().getUserId();
    }
}
