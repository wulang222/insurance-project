package com.insurance.insuranceadminservice.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.insurance.insuranceadminservice.user.domain.entity.SysUser;
import com.insurance.insuranceadminservice.user.mapper.SysUserMapper;
import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import com.insurance.insurancecommonsecurity.utils.SecurityUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.Set;

/**
 * 管理接口只接受启用中的超级管理员。门户注册和查询仍放行。
 */
@Component
public class SuperAdminAuthInterceptor implements HandlerInterceptor {

    /**
     * 门户通过 Feign 调用的内部接口，不能要求超管令牌。
     */
    private static final Set<String> PORTAL_PATHS = Set.of(
            "/app_user/register/openid",
            "/app_user/open_id_find",
            "/app_user/phone_find",
            "/app_user/email_find",
            "/app_user/register/phone",
            "/app_user/register/register",
            "/app_user/edit",
            "/app_user/id_find",
            "/app_user/list"
    );

    @Autowired
    private TokenService tokenService;

    @Autowired
    private SysUserMapper sysUserMapper;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        String path = request.getRequestURI();
        if (isOpen(path)) {
            return true;
        }
        String token = SecurityUtil.getToken(request);
        if (StringUtils.isEmpty(token)) {
            writeUnauthorized(response, ResultCode.TOKEN_EMPTY);
            return false;
        }
        LoginUserDTO loginUser = tokenService.getLoginUser(token);
        if (loginUser == null || loginUser.getUserId() == null) {
            writeUnauthorized(response, ResultCode.TOKEN_INVALID);
            return false;
        }
        if (!"sys".equals(loginUser.getUserFrom())) {
            writeUnauthorized(response, ResultCode.TOKEN_INVALID);
            return false;
        }
        SysUser sysUser = sysUserMapper.selectById(loginUser.getUserId());
        if (sysUser == null
                || !"super_admin".equals(sysUser.getIdentity())
                || !"enable".equals(sysUser.getStatus())) {
            writeUnauthorized(response, ResultCode.TOKEN_INVALID);
            return false;
        }
        return true;
    }

    static boolean isOpen(String path) {
        if (path == null) {
            return false;
        }
        if (path.contains("/login/")) {
            return true;
        }
        return PORTAL_PATHS.contains(path);
    }

    private void writeUnauthorized(HttpServletResponse response, ResultCode resultCode) throws Exception {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(objectMapper.writeValueAsString(R.fail(resultCode.getCode(), resultCode.getMsg())));
    }
}
