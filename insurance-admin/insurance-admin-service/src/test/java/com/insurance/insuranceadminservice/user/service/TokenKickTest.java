package com.insurance.insuranceadminservice.user.service;

import com.insurance.insurancecommonredis.service.RedisService;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class TokenKickTest {

    @Mock
    private RedisService redisService;

    @InjectMocks
    private TokenService tokenService;

    @Test
    void kickRemovesAppSessionAndLeavesSysSession() {
        when(redisService.keys("logintoken:*")).thenReturn(List.of("logintoken:app", "logintoken:sys"));
        when(redisService.getCacheObject("logintoken:app", LoginUserDTO.class)).thenReturn(session(5L, "app"));
        when(redisService.getCacheObject("logintoken:sys", LoginUserDTO.class)).thenReturn(session(5L, "sys"));

        tokenService.delLoginUser(5L, "app");

        verify(redisService).deleteObject("logintoken:app");
        verify(redisService, never()).deleteObject("logintoken:sys");
    }

    private LoginUserDTO session(Long userId, String userFrom) {
        LoginUserDTO loginUser = new LoginUserDTO();
        loginUser.setUserId(userId);
        loginUser.setUserFrom(userFrom);
        return loginUser;
    }
}
