package com.insurance.insuranceportalservice.user.controller;
import com.insurance.insurancecommonmessage.service.AliSmsService;
import com.insurance.insurancecommonmessage.service.CaptchaService;
import com.insurance.insuranceportalservice.InsurancePortalServiceApplication;
import com.insurance.insuranceportalservice.user.entity.dto.CodeLoginDTO;
import com.insurance.insuranceportalservice.user.entity.dto.WechatLoginDTO;
import com.insurance.insuranceportalservice.user.service.IUserService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * C端用户服务单元测试
 */
@SpringBootTest(classes = InsurancePortalServiceApplication.class)
public class UserControllerTest {

    @Autowired
    private IUserService userService;

    @Autowired
    private AliSmsService aliSmsService;

    @Autowired
    private CaptchaService captchaService;

    @Test
    void login() {
        WechatLoginDTO wechatLoginDTO = new WechatLoginDTO();
        wechatLoginDTO.setOpenId("123456789");
        Assertions.assertTrue(userService.login(wechatLoginDTO) != null);
    }

    @Test
    void sendMessage() {
        aliSmsService.sendMobileCode("15399385964", "123456");
    }

    @Test
    void captcha() {
        Assertions.assertTrue(captchaService.sendCode("15399385964") != null);
    }

    @Test
    void sendCode() {
        Assertions.assertTrue(userService.sendCode("18888888888") != null);
    }

    @Test
    void loginByCode() {
        String phone = "18888888888";
        String code = captchaService.sendCode(phone);
        CodeLoginDTO codeLoginDTO = new CodeLoginDTO();
        codeLoginDTO.setPhone(phone);
        codeLoginDTO.setCode(code);
        Assertions.assertTrue(userService.login(codeLoginDTO) != null);
    }
}
