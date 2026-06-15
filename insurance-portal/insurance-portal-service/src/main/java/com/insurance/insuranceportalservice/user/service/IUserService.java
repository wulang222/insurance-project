package com.insurance.insuranceportalservice.user.service;

import com.insurance.insuranceadminapi.appuser.domain.dto.UserEditReqDTO;
import com.insurance.insurancecommonsecurity.domain.dto.TokenDTO;
import com.insurance.insuranceportalservice.user.entity.dto.LoginDTO;
import com.insurance.insuranceportalservice.user.entity.dto.UserDTO;

/**
 * 门户用户服务接口
 */
public interface IUserService {

    TokenDTO login(LoginDTO loginDTO);

    String sendCode(String phone);

    void edit(UserEditReqDTO userEditReqDTO);

    UserDTO getLoginUser();

    void logout();

    String emailSendCode(String email);
}
