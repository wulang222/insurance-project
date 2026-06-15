package com.insurance.insuranceadminservice.user.contorller;

import com.insurance.insuranceadminapi.appuser.domain.dto.AppUserDTO;
import com.insurance.insuranceadminapi.appuser.domain.dto.AppUserListReqDTO;
import com.insurance.insuranceadminapi.appuser.domain.dto.UserEditReqDTO;
import com.insurance.insuranceadminapi.appuser.domain.vo.AppUserVo;
import com.insurance.insuranceadminapi.appuser.feign.AppUserFeignClient;
import com.insurance.insuranceadminservice.user.service.IAppUserService;
import com.insurance.insurancecommoncore.domain.dto.BasePageDTO;
import com.insurance.insurancecommondomain.domain.R;
import com.insurance.insurancecommondomain.domain.vo.BasePageVO;
import com.insurance.insurancecommondomain.exception.ServiceException;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * C端用户相关接口实现
 */
@RestController
@RequestMapping("/app_user")
public class AppUserController implements AppUserFeignClient {

    @Autowired
    private IAppUserService appUserService;

    /**
     * 根据微信注册用户
     * @param openId 用户微信ID
     * @return C端用户VO
     */
    @Override
    public R<AppUserVo> registerByOpenId(String openId) {
        return R.ok(appUserService.registerByOpenId(openId).convertToVO());
    }

    /**
     * 根据openId查询用户信息
     * @param openId 用户微信ID
     * @return C端用户VO
     */
    @Override
    public R<AppUserVo> findByOpenId(String openId) {
        AppUserDTO appUserDTO = appUserService.findByOpenId(openId);
        if (appUserDTO == null) {
            return R.ok();
        }
        return R.ok(appUserDTO.convertToVO());
    }

    /**
     * 根据手机号查询用户信息
     * @param phoneNumber 手机号
     * @return C端用户VO
     */
    @Override
    public R<AppUserVo> findByPhone(String phoneNumber) {
        AppUserDTO appUserDTO = appUserService.findByPhone(phoneNumber);
        if (appUserDTO == null) {
            return R.ok();
        }
        return R.ok(appUserDTO.convertToVO());
    }

    /**
     * 根据邮箱查询用户
     * @param email 手机号
     * @return
     */
    @Override
    public R<AppUserVo> findByEmail(String email) {
        AppUserDTO appUserDTO = appUserService.findByEmail(email);
        if (appUserDTO == null) {
            return R.ok();
        }
        return R.ok(appUserDTO.convertToVO());
    }

    /**
     * 根据手机号注册用户
     * @param phoneNumber 手机号
     * @return C端用户VO
     */
    @Override
    public R<AppUserVo> registerByPhone(String phoneNumber) {
        AppUserDTO appUserDTO = appUserService.registerByPhone(phoneNumber);
        if (appUserDTO == null) {
            throw new ServiceException("注册失败");
        }
        return R.ok(appUserDTO.convertToVO());
    }

    /**
     * 根据邮箱注册用户
     *
     * @param email 手机号
     * @return C端用户VO
     */
    @Override
    public R<AppUserVo> registerByEmail(String email) {
        AppUserDTO appUserDTO = appUserService.registerByEmail(email);
        if (appUserDTO == null) {
            throw new ServiceException("注册失败");
        }
        return R.ok(appUserDTO.convertToVO());
    }

    /**
     * 编辑C端用户
     * @param userEditReqDTO C端用户DTO
     * @return void
     */
    @Override
    public R<Void> edit(UserEditReqDTO userEditReqDTO) {
        appUserService.edit(userEditReqDTO);
        return R.ok();
    }

    /**
     * 根据用户ID获取用户信息
     * @param userId 用户ID
     * @return C端用户VO
     */
    @Override
    public R<AppUserVo> findById(Long userId) {
        AppUserDTO appUserDTO = appUserService.findById(userId);
        if (appUserDTO == null) {
            return R.ok();
        }
        return R.ok(appUserDTO.convertToVO());
    }

    /**
     * 根据用户ID列表获取用户列表信息
     * @param userIds 用户ID列表
     * @return C端用户VO列表
     */
    @Override
    public R<List<AppUserVo>> list(List<Long> userIds) {
        List<AppUserDTO> appUserDTOList = appUserService.getUserList(userIds);
        return R.ok(appUserDTOList.stream()
                .filter(Objects::nonNull)
                .map(AppUserDTO::convertToVO)
                .collect(Collectors.toList())
        );
    }

    /**
     * 查询C端用户
     * @param appUserListReqDTO 查询C端用户DTO
     * @return C端用户分页结果
     */
    @PostMapping("/list/search")
    public R<BasePageVO<AppUserVo>> list(@RequestBody AppUserListReqDTO appUserListReqDTO) {
        BasePageDTO<AppUserDTO> appUserDTOList = appUserService.getUserList(appUserListReqDTO);
        BasePageVO<AppUserVo> result = new BasePageVO<>();
        BeanUtils.copyProperties(appUserDTOList, result);
        return R.ok(result);
    }
}
