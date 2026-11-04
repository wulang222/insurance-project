package com.insurance.insuranceadminservice.security;

import com.insurance.insuranceadminservice.user.domain.entity.SysUser;
import com.insurance.insuranceadminservice.user.mapper.SysUserMapper;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class SuperAdminAuthInterceptorTest {

    @Mock
    private TokenService tokenService;

    @Mock
    private SysUserMapper sysUserMapper;

    @InjectMocks
    private SuperAdminAuthInterceptor interceptor;

    @Test
    void missingTokenIsRejected() throws Exception {
        MockHttpServletRequest request = request("/product/list", null);
        MockHttpServletResponse response = new MockHttpServletResponse();

        Assertions.assertFalse(interceptor.preHandle(request, response, new Object()));
        Assertions.assertEquals(401, response.getStatus());
        Assertions.assertTrue(response.getContentAsString().contains(String.valueOf(ResultCode.TOKEN_EMPTY.getCode())));
    }

    @Test
    void expiredTokenIsRejected() throws Exception {
        MockHttpServletRequest request = request("/product/list", "Bearer expired");
        when(tokenService.getLoginUser("expired")).thenReturn(null);
        MockHttpServletResponse response = new MockHttpServletResponse();

        Assertions.assertFalse(interceptor.preHandle(request, response, new Object()));
        Assertions.assertTrue(response.getContentAsString().contains(String.valueOf(ResultCode.TOKEN_INVALID.getCode())));
    }

    @Test
    void platformAdminTokenIsRejected() throws Exception {
        stubLogin(8L, "sys");
        SysUser user = new SysUser();
        user.setId(8L);
        user.setIdentity("platform_admin");
        user.setStatus("enable");
        when(sysUserMapper.selectById(8L)).thenReturn(user);
        MockHttpServletResponse response = new MockHttpServletResponse();

        Assertions.assertFalse(interceptor.preHandle(request("/argument/list", "Bearer old"), response, new Object()));
    }

    @Test
    void enabledSuperAdminIsAllowed() throws Exception {
        stubLogin(1L, "sys");
        SysUser user = new SysUser();
        user.setId(1L);
        user.setIdentity("super_admin");
        user.setStatus("enable");
        when(sysUserMapper.selectById(1L)).thenReturn(user);

        Assertions.assertTrue(interceptor.preHandle(request("/product/list", "Bearer live"), new MockHttpServletResponse(), new Object()));
    }

    @Test
    void appUserCannotListAdminUsers() throws Exception {
        stubLogin(3L, "app");
        MockHttpServletResponse response = new MockHttpServletResponse();

        Assertions.assertFalse(interceptor.preHandle(
                request("/app_user/list/search", "Bearer app"),
                response,
                new Object()
        ));
    }

    @Test
    void portalRegistrationStaysOpen() throws Exception {
        Assertions.assertTrue(interceptor.preHandle(
                request("/app_user/register/phone", null),
                new MockHttpServletResponse(),
                new Object()
        ));
    }

    @Test
    void nonSuperAdminCannotUploadKnowledge() throws Exception {
        stubLogin(8L, "sys");
        SysUser user = new SysUser();
        user.setId(8L);
        user.setIdentity("platform_admin");
        user.setStatus("enable");
        when(sysUserMapper.selectById(8L)).thenReturn(user);

        Assertions.assertFalse(interceptor.preHandle(
                request("/knowledge/upload", "Bearer old"),
                new MockHttpServletResponse(),
                new Object()
        ));
    }

    private void stubLogin(Long userId, String userFrom) {
        LoginUserDTO loginUser = new LoginUserDTO();
        loginUser.setUserId(userId);
        loginUser.setUserFrom(userFrom);
        lenient().when(tokenService.getLoginUser("live")).thenReturn(loginUser);
        lenient().when(tokenService.getLoginUser("old")).thenReturn(loginUser);
        lenient().when(tokenService.getLoginUser("app")).thenReturn(loginUser);
    }

    private MockHttpServletRequest request(String path, String authorization) {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRequestURI(path);
        if (authorization != null) {
            request.addHeader("Authorization", authorization);
        }
        return request;
    }
}
