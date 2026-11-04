package com.insurance.insuranceadminservice.catalog.controller;

import com.insurance.insuranceadminservice.catalog.domain.InsuranceProduct;
import com.insurance.insuranceadminservice.catalog.domain.ProductListReq;
import com.insurance.insuranceadminservice.catalog.domain.ProductWriteReq;
import com.insurance.insuranceadminservice.catalog.service.ProductAdminService;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.R;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/product")
public class ProductAdminController {

    @Autowired
    private ProductAdminService productAdminService;

    @PostMapping("/save")
    public R<Long> save(@RequestBody ProductWriteReq request) {
        return R.ok(productAdminService.save(request));
    }

    @PostMapping("/list")
    public R<BasePageDTO<InsuranceProduct>> list(@RequestBody ProductListReq request) {
        return R.ok(productAdminService.list(request));
    }
}
