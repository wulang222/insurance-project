package com.insurance.insuranceadminservice.user.controller;

import com.insurance.insuranceadminapi.appuser.domain.dto.UserEditReqDTO;
import com.insurance.insuranceadminservice.InsuranceAdminServiceApplication;
import com.insurance.insuranceadminservice.user.service.IAppUserService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;

@SpringBootTest(classes = InsuranceAdminServiceApplication.class)
public class AppUserControllerTest {
    @Autowired
    private IAppUserService iAppUserService;

    @Test
    @Transactional
    void registerByOpenId() {
        String openId = "212121212";
        Assertions.assertTrue(iAppUserService.registerByOpenId(openId) != null);
    }

    @Test
    void findByPhone() {
        String phone = "18888888888";
        Assertions.assertTrue(iAppUserService.findByPhone(phone) == null);
    }

    @Test
    void registerByPhone() {
        String phone = "18888888887";
        Assertions.assertTrue(iAppUserService.registerByPhone(phone) != null);
    }

    @Test
    void edit() {
        UserEditReqDTO userEditReqDTO = new UserEditReqDTO();
        userEditReqDTO.setUserId(10000004L);
        userEditReqDTO.setNickName("李四");
        userEditReqDTO.setAvtar("https://insurancejiaoyan.oss-cn-chengdu.aliyuncs.com/insurancehouse/web/profile/default-avatar.png");
        iAppUserService.edit(userEditReqDTO);
    }

    @Test
    void list() {
        Assertions.assertTrue(iAppUserService.findById(10000001L) != null);
        Assertions.assertTrue(iAppUserService.getUserList(Arrays.asList(10000001L, 10000002L)).size() == 2);
    }
}
