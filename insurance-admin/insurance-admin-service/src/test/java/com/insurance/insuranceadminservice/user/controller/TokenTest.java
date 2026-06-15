package com.insurance.insuranceadminservice.user.controller;

import com.insurance.insuranceadminservice.InsuranceAdminServiceApplication;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(classes = InsuranceAdminServiceApplication.class)
public class TokenTest {
    @Autowired
    private TokenService tokenService;

    @Test
    void tokenTest() {
        LoginUserDTO loginUserDTO = new LoginUserDTO();
        loginUserDTO.setUserId(100L);
        loginUserDTO.setUserName("zhangSan");
        loginUserDTO.setUserFrom("sys");
        tokenService.createToken(loginUserDTO);
    }
}
