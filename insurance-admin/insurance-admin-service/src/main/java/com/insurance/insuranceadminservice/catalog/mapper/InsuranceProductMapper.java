package com.insurance.insuranceadminservice.catalog.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.insurance.insuranceadminservice.catalog.domain.InsuranceProduct;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface InsuranceProductMapper extends BaseMapper<InsuranceProduct> {
}
