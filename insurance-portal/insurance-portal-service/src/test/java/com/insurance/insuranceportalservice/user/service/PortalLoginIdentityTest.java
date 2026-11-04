package com.insurance.insuranceportalservice.user.service;

import com.insurance.insuranceadminapi.appuser.domain.vo.AppUserVo;
import com.insurance.insuranceadminapi.appuser.feign.AppUserFeignClient;
import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insurancecommonmessage.service.CaptchaService;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.domain.dto.TokenDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import com.insurance.insuranceportalservice.user.entity.dto.WechatLoginDTO;
import com.insurance.insuranceportalservice.user.service.impl.IUserServiceImpl;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class PortalLoginIdentityTest {

    @Mock
    private AppUserFeignClient appUserFeignClient;

    @Mock
    private TokenService tokenService;

    @Mock
    private CaptchaService captchaService;

    @InjectMocks
    private IUserServiceImpl userService;

    @Test
    void portalLoginIssuesAppSessionWithoutSuperAdmin() {
        AppUserVo appUser = new AppUserVo();
        appUser.setUserId(9L);
        appUser.setNickName("客户");
        when(appUserFeignClient.findByOpenId("openid-1")).thenReturn(R.ok(appUser));
        when(tokenService.createToken(any())).thenAnswer(invocation -> {
            TokenDTO token = new TokenDTO();
            token.setAccessToken("app-token");
            return token;
        });

        WechatLoginDTO login = new WechatLoginDTO();
        login.setOpenId("openid-1");
        Assertions.assertEquals("app-token", userService.login(login).getAccessToken());

        ArgumentCaptor<LoginUserDTO> captor = ArgumentCaptor.forClass(LoginUserDTO.class);
        verify(tokenService).createToken(captor.capture());
        Assertions.assertEquals("app", captor.getValue().getUserFrom());
        Assertions.assertEquals(9L, captor.getValue().getUserId());
        Assertions.assertEquals("客户", captor.getValue().getUserName());
    }
}
