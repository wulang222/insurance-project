package com.insurance.insuranceportalservice.user.service.impl;

import com.insurance.insuranceadminapi.appuser.domain.dto.UserEditReqDTO;
import com.insurance.insuranceadminapi.appuser.domain.vo.AppUserVo;
import com.insurance.insuranceadminapi.appuser.feign.AppUserFeignClient;
import com.insurance.insurancecommoncore.utils.VerifyUtil;
import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insurancecommondomain.domain.ResultCode;
import com.insurance.insurancecommondomain.exception.ServiceException;
import com.insurance.insurancecommonmessage.enums.SendType;
import com.insurance.insurancecommonmessage.service.CaptchaService;
import com.insurance.insurancecommonsecurity.domain.dto.LoginUserDTO;
import com.insurance.insurancecommonsecurity.domain.dto.TokenDTO;
import com.insurance.insurancecommonsecurity.service.TokenService;
import com.insurance.insurancecommonsecurity.utils.JwtUtil;
import com.insurance.insurancecommonsecurity.utils.SecurityUtil;
import com.insurance.insuranceportalservice.user.entity.dto.*;
import com.insurance.insuranceportalservice.user.service.IUserService;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * 门户用户服务实现类
 */
@Component
@Slf4j
public class IUserServiceImpl implements IUserService {

    @Autowired
    private AppUserFeignClient appUserFeignClient;

    @Autowired
    private TokenService tokenService;

    @Autowired
    private CaptchaService captchaService;

    /**
     * 登录逻辑
     *
     * @param loginDTO 用户登录DTO
     * @return TokenDTO 加令牌
     */
    @Override
    public TokenDTO login(LoginDTO loginDTO) {
        // 1 需要设置用户声明周期
        LoginUserDTO loginUserDTO = new LoginUserDTO();
        // 2 针对入参进行逻辑分发
        if (loginDTO instanceof WechatLoginDTO wechatLoginDTO) {
            // 3 处理微信登录逻辑
            loginByWechat(wechatLoginDTO, loginUserDTO);
        } else if (loginDTO instanceof CodeLoginDTO codeLoginDTO) {
            // 4 处理验手机号短信验证码登录逻辑
            loginByCode(codeLoginDTO, loginUserDTO);
        } else if(loginDTO instanceof EmailCodeLoginDTO emailCodeLoginDTO) {
            // 5 处理邮箱验证码登录逻辑
            loginByEmailCode(emailCodeLoginDTO, loginUserDTO);
        }
        // 5 设置缓存
        loginUserDTO.setUserFrom("app");
        return tokenService.createToken(loginUserDTO);
    }

    /**
     * 通过邮箱验证码登录
     * @param emailCodeLoginDTO
     * @param loginUserDTO
     */
    private void loginByEmailCode(EmailCodeLoginDTO emailCodeLoginDTO, LoginUserDTO loginUserDTO) {
        // 1 校验邮格式是否正确
        if (!VerifyUtil.checkEmail(emailCodeLoginDTO.getEmail())) {
            throw new ServiceException("邮箱格式", ResultCode.INVALID_PARA.getCode());
        }
        // 2 执行远程调用
        AppUserVo appUserVo;

        R<AppUserVo> result = appUserFeignClient.findByEmail(emailCodeLoginDTO.getEmail());
        // 3 查不到人的处理逻辑
        if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
            //查无此人, 则进行注册
            appUserVo = register(emailCodeLoginDTO);
        } else {
            //查到了 那就直接登录
            appUserVo = result.getData();
        }
        // 4 校验验证码
        String cacheCode = captchaService.getCode(emailCodeLoginDTO.getEmail());
        if (cacheCode == null) {
            //redis中压根没有对应手机号or邮箱为key的验证码缓存
            throw new ServiceException("验证码无效", ResultCode.INVALID_PARA.getCode());
        }
        if (!cacheCode.equals(emailCodeLoginDTO.getCode())) {
            //有验证码, 但是和用户前端输入传过来的不一样
            throw new ServiceException("验证码错误", ResultCode.INVALID_PARA.getCode());
        }
        // 5 校验验证码通过
        captchaService.deleteCode(emailCodeLoginDTO.getEmail());
        // 6 设置登录信息
        loginUserDTO.setUserId(appUserVo.getUserId());
        loginUserDTO.setUserName(appUserVo.getNickName());
    }


    /**
     * 发送手机短信验证码
     *
     * @param phone 手机号
     * @return 验证码
     */
    @Override
    public String sendCode(String phone) {
        if (!VerifyUtil.checkPhone(phone)) {
            throw new ServiceException("手机号格式错误", ResultCode.INVALID_PARA.getCode());
        }
        return captchaService.sendCode(phone, 1);
    }

    /**
     * 发送邮箱验证码
     *
     * @param email
     * @return
     */
    @Override
    public String emailSendCode(String email) {
        //由于urlencode了 所以需要先解码
        System.out.println("email" + email);
        if (!VerifyUtil.checkEmail(email)) {
            throw new ServiceException("邮箱账号格式错误",
                    ResultCode.INVALID_PARA.getCode());
        }
        return captchaService.sendCode(email, SendType.EMAIL.getValue());
    }

    /**
     * 修改用户信息
     *
     * @param userEditReqDTO C端用户编辑DTO
     */
    @Override
    public void edit(UserEditReqDTO userEditReqDTO) {
        R<Void> result = appUserFeignClient.edit(userEditReqDTO);
        if (result == null || result.getCode() != ResultCode.SUCCESS.getCode()) {
            throw new ServiceException("修改用户失败");
        }
    }

    /**
     * 获取用户登录信息
     *
     * @return 用户信息DTO
     */
    @Override
    public UserDTO getLoginUser() {
        // 1 获取当前登录的用户
        LoginUserDTO loginUserDTO = tokenService.getLoginUser();
        if (loginUserDTO == null) {
            throw new ServiceException("用户令牌有误", ResultCode.INVALID_PARA.getCode());
        }
        // 2 远程调用获取用户信息
        R<AppUserVo> result = appUserFeignClient.findById(loginUserDTO.getUserId());
        if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
            throw new ServiceException("查询用户失败", ResultCode.INVALID_PARA.getCode());
        }
        // 3 对象拼装，返回结果
        UserDTO userDTO = new UserDTO();
        BeanUtils.copyProperties(loginUserDTO, userDTO);
        BeanUtils.copyProperties(result.getData(), userDTO);
        return userDTO;
    }

    /**
     * 退出登录
     */
    @Override
    public void logout() {
        // 1 解析令牌
        String token = SecurityUtil.getToken();
        if (StringUtils.isEmpty(token)) {
            return;
        }
        String userName = JwtUtil.getUserName(token);
        String userId = JwtUtil.getUserId(token);
        log.info("{}退出了系统, 用户ID{}", userName, userId);
        // 2 删除用户缓存记录
        tokenService.delLoginUser(token);
    }


    /**
     * 处理微信登录逻辑
     *
     * @param wechatLoginDTO 微信登录DTO
     * @param loginUserDTO   用户生命周期对象
     */
    private void loginByWechat(WechatLoginDTO wechatLoginDTO, LoginUserDTO loginUserDTO) {
        AppUserVo appUserVo;
        // 1 根据openId进行查询
        R<AppUserVo> result = appUserFeignClient.findByOpenId(wechatLoginDTO.getOpenId());
        // 2 对查询结果进行判断
        if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
            // 3 没查到，需要进行注册
            appUserVo = register(wechatLoginDTO);
        } else {
            appUserVo = result.getData();
        }
        // 4 设置登录信息
        loginUserDTO.setUserId(appUserVo.getUserId());
        loginUserDTO.setUserName(appUserVo.getNickName());
    }

    /**
     * 验证码登录处理逻辑
     *
     * @param codeLoginDTO 验证码登录DTO
     * @param loginUserDTO 用户信息上下文DTO
     */
    private void loginByCode(CodeLoginDTO codeLoginDTO, LoginUserDTO loginUserDTO) {
        // 1 校验手机号
        if (!VerifyUtil.checkPhone(codeLoginDTO.getPhone())) {
            throw new ServiceException("手机号格式错误", ResultCode.INVALID_PARA.getCode());
        }
        // 2 执行远程调用
        AppUserVo appUserVo;

        R<AppUserVo> result = appUserFeignClient.findByPhone(codeLoginDTO.getPhone());
        // 3 查不到人的处理逻辑
        if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
            appUserVo = register(codeLoginDTO);
        } else {
            appUserVo = result.getData();
        }
        // 4 校验验证码
        String cacheCode = captchaService.getCode(codeLoginDTO.getPhone());
        if (cacheCode == null) {
            throw new ServiceException("验证码无效", ResultCode.INVALID_PARA.getCode());
        }
        if (!cacheCode.equals(codeLoginDTO.getCode())) {
            throw new ServiceException("验证码错误", ResultCode.INVALID_PARA.getCode());
        }
        // 5 校验验证码通过
        captchaService.deleteCode(codeLoginDTO.getPhone());
        // 6 设置登录信息
        loginUserDTO.setUserId(appUserVo.getUserId());
        loginUserDTO.setUserName(appUserVo.getNickName());
    }

    /**
     * 根据入参来注册
     *
     * @param loginDTO 用户生命周期信息
     * @return 用户VO
     */
    private AppUserVo register(LoginDTO loginDTO) {

        R<AppUserVo> result = null;

        // 1 针对入参进行逻辑分发
        if (loginDTO instanceof WechatLoginDTO wechatLoginDTO) {
            // 2 处理微信注册逻辑
            result = appUserFeignClient.registerByOpenId(wechatLoginDTO.getOpenId());
            if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
                log.error("用户注册失败! {}", wechatLoginDTO.getOpenId());
            }
        } else if (loginDTO instanceof CodeLoginDTO codeLoginDTO) {
            // 3 处理手机号注册逻辑
            result = appUserFeignClient.registerByPhone(codeLoginDTO.getPhone());
            if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
                log.error("用户注册失败! {}", codeLoginDTO.getPhone());
            }
        } else if(loginDTO instanceof EmailCodeLoginDTO emailCodeLoginDTO) {
            // 4 邮箱注册
            result = appUserFeignClient.registerByEmail(emailCodeLoginDTO.getEmail());
            if (result == null || result.getCode() != ResultCode.SUCCESS.getCode() || result.getData() == null) {
                log.error("用户注册失败! {}", emailCodeLoginDTO.getEmail());
            }
        }
        return result == null ? null : result.getData();
    }
}
