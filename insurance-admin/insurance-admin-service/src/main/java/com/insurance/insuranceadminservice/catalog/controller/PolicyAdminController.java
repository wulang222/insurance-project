package com.insurance.insuranceadminservice.catalog.controller;

import com.insurance.insuranceadminservice.catalog.domain.PolicyListReq;
import com.insurance.insuranceadminservice.catalog.domain.PolicyWriteReq;
import com.insurance.insuranceadminservice.catalog.domain.UserPolicyHistory;
import com.insurance.insuranceadminservice.catalog.service.PolicyAdminService;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.R;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/policy")
public class PolicyAdminController {

    @Autowired
    private PolicyAdminService policyAdminService;

    @PostMapping("/save")
    public R<Long> save(@RequestBody PolicyWriteReq request) {
        return R.ok(policyAdminService.save(request));
    }

    @PostMapping("/list")
    public R<BasePageDTO<UserPolicyHistory>> list(@RequestBody PolicyListReq request) {
        return R.ok(policyAdminService.list(request));
    }
}
