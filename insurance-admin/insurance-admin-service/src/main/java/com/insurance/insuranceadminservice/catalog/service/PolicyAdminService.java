package com.insurance.insuranceadminservice.catalog.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.insurance.insuranceadminservice.catalog.domain.PolicyListReq;
import com.insurance.insuranceadminservice.catalog.domain.PolicyWriteReq;
import com.insurance.insuranceadminservice.catalog.domain.UserPolicyHistory;
import com.insurance.insuranceadminservice.catalog.mapper.UserPolicyHistoryMapper;
import com.insurance.insuranceadminservice.user.mapper.AppUserMapper;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class PolicyAdminService {

    @Autowired
    private UserPolicyHistoryMapper policyMapper;

    @Autowired
    private AppUserMapper appUserMapper;

    public Long save(PolicyWriteReq request) {
        validate(request);
        if (appUserMapper.selectById(request.getUserId()) == null) {
            throw new ServiceException("用户不存在", ResultCode.INVALID_PARA.getCode());
        }
        UserPolicyHistory sameNumber = policyMapper.selectOne(
                new QueryWrapper<UserPolicyHistory>().eq("policy_no", request.getPolicyNo())
        );
        if (request.getId() == null) {
            if (sameNumber != null) {
                throw new ServiceException("保单号已存在", ResultCode.INVALID_PARA.getCode());
            }
            UserPolicyHistory created = new UserPolicyHistory();
            copy(request, created);
            policyMapper.insert(created);
            return created.getId();
        }
        UserPolicyHistory current = policyMapper.selectById(request.getId());
        if (current == null) {
            throw new ServiceException("保单不存在", ResultCode.INVALID_PARA.getCode());
        }
        if (sameNumber != null && !sameNumber.getId().equals(request.getId())) {
            throw new ServiceException("保单号已存在", ResultCode.INVALID_PARA.getCode());
        }
        copy(request, current);
        policyMapper.updateById(current);
        return current.getId();
    }

    public BasePageDTO<UserPolicyHistory> list(PolicyListReq request) {
        int pageNo = request.getPageNo() == null || request.getPageNo() < 1 ? 1 : request.getPageNo();
        int pageSize = request.getPageSize() == null || request.getPageSize() < 1 ? 10 : request.getPageSize();
        QueryWrapper<UserPolicyHistory> query = new QueryWrapper<>();
        if (request.getUserId() != null) {
            query.eq("user_id", request.getUserId());
        }
        if (request.getPolicyStatus() != null) {
            query.eq("policy_status", request.getPolicyStatus());
        }
        Long totals = policyMapper.selectCount(query);
        BasePageDTO<UserPolicyHistory> page = new BasePageDTO<>();
        page.setTotals(totals.intValue());
        page.setTotalPages(BasePageDTO.calculateTotalPages(totals, pageSize));
        query.orderByDesc("id");
        query.last("limit " + ((pageNo - 1) * pageSize) + "," + pageSize);
        page.setList(policyMapper.selectList(query));
        return page;
    }

    private void validate(PolicyWriteReq request) {
        if (request == null
                || request.getUserId() == null
                || StringUtils.isBlank(request.getPolicyNo())
                || StringUtils.isBlank(request.getProductName())
                || request.getPremium() == null
                || request.getSumInsured() == null
                || request.getPolicyStatus() == null
                || request.getStartDate() == null
                || request.getEndDate() == null) {
            throw new ServiceException("保单字段不完整", ResultCode.INVALID_PARA.getCode());
        }
        if (request.getPolicyStatus() < 1 || request.getPolicyStatus() > 4) {
            throw new ServiceException("保单状态不合法", ResultCode.INVALID_PARA.getCode());
        }
        if (request.getEndDate().isBefore(request.getStartDate())) {
            throw new ServiceException("保单日期不合法", ResultCode.INVALID_PARA.getCode());
        }
    }

    private void copy(PolicyWriteReq request, UserPolicyHistory policy) {
        policy.setUserId(request.getUserId());
        policy.setPolicyNo(request.getPolicyNo());
        policy.setProductName(request.getProductName());
        policy.setPremium(request.getPremium());
        policy.setSumInsured(request.getSumInsured());
        policy.setPolicyStatus(request.getPolicyStatus());
        policy.setStartDate(request.getStartDate());
        policy.setEndDate(request.getEndDate());
        if (policy.getPurchaseTime() == null) {
            policy.setPurchaseTime(request.getStartDate().atStartOfDay());
        }
    }
}
