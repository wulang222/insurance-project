package com.insurance.insuranceadminservice.catalog.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.insurance.insuranceadminservice.catalog.domain.InsuranceProduct;
import com.insurance.insuranceadminservice.catalog.domain.ProductListReq;
import com.insurance.insuranceadminservice.catalog.domain.ProductWriteReq;
import com.insurance.insuranceadminservice.catalog.mapper.InsuranceProductMapper;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ProductAdminService {

    @Autowired
    private InsuranceProductMapper productMapper;

    public Long save(ProductWriteReq request) {
        validate(request);
        InsuranceProduct sameCode = productMapper.selectOne(
                new QueryWrapper<InsuranceProduct>().eq("product_id", request.getProductId())
        );
        if (request.getId() == null) {
            if (sameCode != null) {
                throw new ServiceException("产品编号已存在", ResultCode.INVALID_PARA.getCode());
            }
            InsuranceProduct created = new InsuranceProduct();
            copy(request, created);
            productMapper.insert(created);
            return created.getId();
        }
        InsuranceProduct current = productMapper.selectById(request.getId());
        if (current == null) {
            throw new ServiceException("产品不存在", ResultCode.INVALID_PARA.getCode());
        }
        if (sameCode != null && !sameCode.getId().equals(request.getId())) {
            throw new ServiceException("产品编号已存在", ResultCode.INVALID_PARA.getCode());
        }
        copy(request, current);
        productMapper.updateById(current);
        return current.getId();
    }

    public BasePageDTO<InsuranceProduct> list(ProductListReq request) {
        int pageNo = request.getPageNo() == null || request.getPageNo() < 1 ? 1 : request.getPageNo();
        int pageSize = request.getPageSize() == null || request.getPageSize() < 1 ? 10 : request.getPageSize();
        QueryWrapper<InsuranceProduct> query = new QueryWrapper<>();
        if (StringUtils.isNotBlank(request.getInsuranceType())) {
            query.eq("insurance_type", request.getInsuranceType());
        }
        if (StringUtils.isNotBlank(request.getProductId())) {
            query.eq("product_id", request.getProductId());
        }
        if (request.getActive() != null) {
            query.eq("is_active", Boolean.TRUE.equals(request.getActive()) ? 1 : 0);
        }
        Long totals = productMapper.selectCount(query);
        BasePageDTO<InsuranceProduct> page = new BasePageDTO<>();
        page.setTotals(totals.intValue());
        page.setTotalPages(BasePageDTO.calculateTotalPages(totals, pageSize));
        query.orderByDesc("id");
        query.last("limit " + ((pageNo - 1) * pageSize) + "," + pageSize);
        List<InsuranceProduct> rows = productMapper.selectList(query);
        page.setList(rows);
        return page;
    }

    private void validate(ProductWriteReq request) {
        if (request == null
                || StringUtils.isBlank(request.getProductId())
                || StringUtils.isBlank(request.getProductName())
                || StringUtils.isBlank(request.getInsuranceType())
                || request.getMinAge() == null
                || request.getMaxAge() == null
                || request.getMinPrice() == null
                || request.getMaxPrice() == null
                || request.getActive() == null) {
            throw new ServiceException("产品字段不完整", ResultCode.INVALID_PARA.getCode());
        }
        if (request.getMinAge() > request.getMaxAge() || request.getMinPrice().compareTo(request.getMaxPrice()) > 0) {
            throw new ServiceException("产品范围不合法", ResultCode.INVALID_PARA.getCode());
        }
    }

    private void copy(ProductWriteReq request, InsuranceProduct product) {
        product.setProductId(request.getProductId());
        product.setProductName(request.getProductName());
        product.setInsuranceType(request.getInsuranceType());
        product.setMinAge(request.getMinAge());
        product.setMaxAge(request.getMaxAge());
        product.setMinPrice(request.getMinPrice());
        product.setMaxPrice(request.getMaxPrice());
        product.setTargetOccupations(StringUtils.defaultString(request.getTargetOccupations()));
        product.setDescription(StringUtils.defaultString(request.getDescription()));
        product.setIsActive(Boolean.TRUE.equals(request.getActive()) ? 1 : 0);
    }
}
