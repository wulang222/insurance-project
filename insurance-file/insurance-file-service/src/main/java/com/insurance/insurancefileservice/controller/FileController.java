package com.insurance.insurancefileservice.controller;

import com.insurance.insurancecommoncore.utils.BeanCopyUtil;
import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insurancefileservice.domain.dto.FileDTO;
import com.insurance.insurancefileservice.domain.dto.SignDTO;
import com.insurance.insurancefileservice.domain.vo.FileVO;
import com.insurance.insurancefileservice.domain.vo.SignVO;
import com.insurance.insurancefileservice.service.IFileService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@Slf4j
public class FileController {

    @Autowired
    private IFileService fileService;

    @PostMapping("/upload")
    public R<FileVO> upload(MultipartFile file) {
        FileDTO fileDTO = fileService.upload(file);
        FileVO fileVO = new FileVO();
        BeanCopyUtil.copyProperties(fileDTO, fileVO);
        return R.ok(fileVO);
    }

    @GetMapping("/sign")
    public R<SignVO> getSign() {
        SignDTO signDTO = fileService.getSign();
        SignVO signVO = new SignVO();
        BeanCopyUtil.copyProperties(signDTO, signVO);
        return R.ok(signVO);
    }
}
