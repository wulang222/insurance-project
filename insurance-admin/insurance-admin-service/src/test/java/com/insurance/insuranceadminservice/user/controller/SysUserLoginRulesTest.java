package com.insurance.insuranceadminservice.user.controller;

import cn.hutool.crypto.digest.DigestUtil;
import com.insurance.insuranceadminservice.user.domain.dto.PasswordLoginDTO;
import com.insurance.insuranceadminservice.user.domain.entity.SysUser;
import com.insurance.insuranceadminservice.user.mapper.SysUserMapper;
import com.insurance.insuranceadminservice.user.service.impl.SysUserServiceImpl;
import com.insurance.insurancecommoncore.utils.AESUtil;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.domain.dto.TokenDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 管理端登录规则。不启动 Spring，避免依赖 Nacos 和 MySQL。
 */
@ExtendWith(MockitoExtension.class)
public class SysUserLoginRulesTest {

    @Mock
    private SysUserMapper sysUserMapper;

    @Mock
    private TokenService tokenService;

    @InjectMocks
    private SysUserServiceImpl sysUserService;

    @Test
    void enabledSuperAdminReceivesToken() {
        stubUser("super_admin", "enable", "secret123");
        TokenDTO tokenDTO = new TokenDTO();
        tokenDTO.setAccessToken("super-token");
        when(tokenService.createToken(any())).thenReturn(tokenDTO);

        TokenDTO result = sysUserService.login(login("secret123"));

        Assertions.assertEquals("super-token", result.getAccessToken());
        ArgumentCaptor<LoginUserDTO> captor = ArgumentCaptor.forClass(LoginUserDTO.class);
        verify(tokenService).createToken(captor.capture());
        Assertions.assertEquals("sys", captor.getValue().getUserFrom());
    }

    @Test
    void wrongPasswordDoesNotIssueToken() {
        stubUser("super_admin", "enable", "secret123");

        ServiceException error = Assertions.assertThrows(
                ServiceException.class,
                () -> sysUserService.login(login("wrong-pass"))
        );

        Assertions.assertEquals("密码不正确", error.getMessage());
        verify(tokenService, never()).createToken(any());
    }

    @Test
    void platformAdminIsRejected() {
        stubUser("platform_admin", "enable", "secret123");

        ServiceException error = Assertions.assertThrows(
                ServiceException.class,
                () -> sysUserService.login(login("secret123"))
        );

        Assertions.assertEquals(ResultCode.INVALID_PARA.getCode(), error.getCode());
        verify(tokenService, never()).createToken(any());
    }

    @Test
    void disabledSuperAdminIsRejected() {
        stubUser("super_admin", "disable", "secret123");

        ServiceException error = Assertions.assertThrows(
                ServiceException.class,
                () -> sysUserService.login(login("secret123"))
        );

        Assertions.assertEquals(ResultCode.USER_DISABLE.getCode(), error.getCode());
        verify(tokenService, never()).createToken(any());
    }

    private void stubUser(String identity, String status, String rawPassword) {
        SysUser sysUser = new SysUser();
        sysUser.setId(100L);
        sysUser.setNickName("管理员");
        sysUser.setIdentity(identity);
        sysUser.setStatus(status);
        sysUser.setPassword(DigestUtil.sha256Hex(rawPassword));
        when(sysUserMapper.selectByPhoneNumber(AESUtil.encryptHex("13800138000"))).thenReturn(sysUser);
    }

    private PasswordLoginDTO login(String rawPassword) {
        PasswordLoginDTO dto = new PasswordLoginDTO();
        dto.setPhone("13800138000");
        dto.setPassword(AESUtil.encryptHex(rawPassword));
        return dto;
    }
}
