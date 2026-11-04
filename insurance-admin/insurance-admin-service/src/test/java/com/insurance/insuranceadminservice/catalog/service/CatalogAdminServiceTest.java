package com.insurance.insuranceadminservice.catalog.service;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.insurance.insuranceadminservice.catalog.domain.InsuranceProduct;
import com.insurance.insuranceadminservice.catalog.domain.PolicyListReq;
import com.insurance.insuranceadminservice.catalog.domain.PolicyWriteReq;
import com.insurance.insuranceadminservice.catalog.domain.ProductListReq;
import com.insurance.insuranceadminservice.catalog.domain.ProductWriteReq;
import com.insurance.insuranceadminservice.catalog.domain.UserPolicyHistory;
import com.insurance.insuranceadminservice.catalog.mapper.InsuranceProductMapper;
import com.insurance.insuranceadminservice.catalog.mapper.UserPolicyHistoryMapper;
import com.insurance.insuranceadminservice.user.domain.entity.AppUser;
import com.insurance.insuranceadminservice.user.mapper.AppUserMapper;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class CatalogAdminServiceTest {

    @Mock
    private InsuranceProductMapper productMapper;

    @Mock
    private UserPolicyHistoryMapper policyMapper;

    @Mock
    private AppUserMapper appUserMapper;

    @InjectMocks
    private ProductAdminService productAdminService;

    @InjectMocks
    private PolicyAdminService policyAdminService;

    @Test
    void duplicateProductIdLeavesExistingRowUnchanged() {
        InsuranceProduct existing = new InsuranceProduct();
        existing.setId(3L);
        existing.setProductId("CI009");
        existing.setProductName("原名称");
        when(productMapper.selectOne(any())).thenReturn(existing);

        Assertions.assertThrows(ServiceException.class, () -> productAdminService.save(product("CI009", true)));

        Assertions.assertEquals("原名称", existing.getProductName());
        verify(productMapper, never()).insert(any(InsuranceProduct.class));
        verify(productMapper, never()).updateById(any(InsuranceProduct.class));
    }

    @Test
    void deactivateKeepsTheProductAndMarksItInactive() {
        InsuranceProduct current = new InsuranceProduct();
        current.setId(4L);
        current.setProductId("CI004");
        current.setIsActive(1);
        when(productMapper.selectOne(any())).thenReturn(current);
        when(productMapper.selectById(4L)).thenReturn(current);
        ProductWriteReq request = product("CI004", false);
        request.setId(4L);

        Assertions.assertEquals(4L, productAdminService.save(request));

        Assertions.assertEquals(0, current.getIsActive());
        verify(productMapper).updateById(current);
    }

    @Test
    void productListIncludesInactiveRowsUnlessFiltered() {
        InsuranceProduct active = new InsuranceProduct();
        active.setProductId("A");
        active.setIsActive(1);
        InsuranceProduct inactive = new InsuranceProduct();
        inactive.setProductId("B");
        inactive.setIsActive(0);
        when(productMapper.selectCount(any())).thenReturn(2L);
        when(productMapper.selectList(any())).thenReturn(List.of(active, inactive));

        Assertions.assertEquals(2, productAdminService.list(new ProductListReq()).getList().size());
    }

    @Test
    void unknownPolicyHolderIsRejected() {
        when(appUserMapper.selectById(44L)).thenReturn(null);

        Assertions.assertThrows(ServiceException.class, () -> policyAdminService.save(policy(44L, "P-1")));

        verify(policyMapper, never()).insert(any(UserPolicyHistory.class));
    }

    @Test
    void duplicatePolicyNumberLeavesExistingRowUnchanged() {
        when(appUserMapper.selectById(5L)).thenReturn(new AppUser());
        UserPolicyHistory existing = new UserPolicyHistory();
        existing.setId(9L);
        existing.setPolicyNo("P-1");
        existing.setProductName("原保单");
        when(policyMapper.selectOne(any())).thenReturn(existing);

        Assertions.assertThrows(ServiceException.class, () -> policyAdminService.save(policy(5L, "P-1")));

        Assertions.assertEquals("原保单", existing.getProductName());
        verify(policyMapper, never()).insert(any(UserPolicyHistory.class));
        verify(policyMapper, never()).updateById(any(UserPolicyHistory.class));
    }

    @Test
    void policyListCanFilterByUser() {
        when(policyMapper.selectCount(any())).thenAnswer(invocation -> {
            Wrapper<?> wrapper = invocation.getArgument(0);
            Assertions.assertTrue(wrapper.getSqlSegment().contains("user_id"));
            return 1L;
        });
        UserPolicyHistory row = new UserPolicyHistory();
        row.setUserId(5L);
        row.setPolicyNo("P-1");
        when(policyMapper.selectList(any())).thenReturn(List.of(row));
        PolicyListReq request = new PolicyListReq();
        request.setUserId(5L);

        Assertions.assertEquals("P-1", policyAdminService.list(request).getList().get(0).getPolicyNo());
    }

    private ProductWriteReq product(String productId, boolean active) {
        ProductWriteReq request = new ProductWriteReq();
        request.setProductId(productId);
        request.setProductName("新名称");
        request.setInsuranceType("医疗险");
        request.setMinAge(0);
        request.setMaxAge(65);
        request.setMinPrice(new BigDecimal("100.00"));
        request.setMaxPrice(new BigDecimal("2000.00"));
        request.setTargetOccupations("全部职业");
        request.setDescription("说明");
        request.setActive(active);
        return request;
    }

    private PolicyWriteReq policy(Long userId, String policyNo) {
        PolicyWriteReq request = new PolicyWriteReq();
        request.setUserId(userId);
        request.setPolicyNo(policyNo);
        request.setProductName("新保单");
        request.setPremium(new BigDecimal("100.00"));
        request.setSumInsured(new BigDecimal("100000.00"));
        request.setPolicyStatus(1);
        request.setStartDate(LocalDate.of(2026, 1, 1));
        request.setEndDate(LocalDate.of(2027, 1, 1));
        return request;
    }
}
