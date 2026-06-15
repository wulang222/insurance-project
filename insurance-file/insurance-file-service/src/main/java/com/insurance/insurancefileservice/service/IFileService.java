package com.insurance.insurancefileservice.service;

import com.insurance.insurancefileservice.domain.dto.FileDTO;
import com.insurance.insurancefileservice.domain.dto.SignDTO;
import org.springframework.web.multipart.MultipartFile;

public interface IFileService {
    FileDTO upload(MultipartFile file);

    SignDTO getSign();
}
