package com.insurance.insuranceadminservice.user.service;

import com.insurance.insuranceadminapi.appuser.domain.dto.AppUserDTO;
import com.insurance.insuranceadminapi.appuser.domain.dto.AppUserListReqDTO;
import com.insurance.insuranceadminservice.user.domain.entity.AppUser;
import com.insurance.insuranceadminservice.user.mapper.AppUserMapper;
import com.insurance.insuranceadminservice.user.service.impl.AppUserServiceImpl;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommoncore.utils.AESUtil;
import com.insurance.insurancecommondomain.exception.ServiceException;
import com.insurance.insurancecommonsecurity.service.TokenService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class AppUserAdministrationTest {

    @Mock
    private AppUserMapper appUserMapper;

    @Mock
    private TokenService tokenService;

    @InjectMocks
    private AppUserServiceImpl appUserService;

    @Test
    void listFiltersByPhoneAndNickname() {
        AppUserListReqDTO request = new AppUserListReqDTO();
        request.setPhoneNumber("13800138000");
        request.setNickName("张");
        request.setPageNo(1);
        request.setPageSize(10);
        when(appUserMapper.selectCount(request)).thenReturn(1L);
        AppUser stored = new AppUser();
        stored.setId(7L);
        stored.setNickName("张三");
        stored.setPhoneNumber(AESUtil.encryptHex("13800138000"));
        when(appUserMapper.selectPage(request)).thenReturn(List.of(stored));

        BasePageDTO<AppUserDTO> page = appUserService.getUserList(request);

        Assertions.assertEquals(AESUtil.encryptHex("13800138000"), request.getPhoneNumber());
        Assertions.assertEquals("张", request.getNickName());
        Assertions.assertEquals(1, page.getTotals());
        Assertions.assertEquals(1, page.getTotalPages());
        Assertions.assertEquals(7L, page.getList().get(0).getUserId());
        Assertions.assertEquals("张三", page.getList().get(0).getNickName());
        Assertions.assertEquals("13800138000", page.getList().get(0).getPhoneNumber());
    }

    @Test
    void kickUnknownUserDeletesNothing() {
        when(appUserMapper.selectById(99L)).thenReturn(null);

        Assertions.assertThrows(ServiceException.class, () -> appUserService.kick(99L));

        verify(tokenService, never()).delLoginUser(any(), any());
        verify(appUserMapper).selectById(99L);
        verifyNoMoreInteractions(appUserMapper);
    }

    @Test
    void kickRevokesAppSessionAndKeepsAccount() {
        AppUser stored = new AppUser();
        stored.setId(5L);
        stored.setNickName("在线用户");
        when(appUserMapper.selectById(5L)).thenReturn(stored);

        appUserService.kick(5L);

        verify(tokenService).delLoginUser(5L, "app");
        Assertions.assertEquals("在线用户", appUserMapper.selectById(5L).getNickName());
        verify(appUserMapper, times(2)).selectById(5L);
        verifyNoMoreInteractions(appUserMapper);
    }
}
