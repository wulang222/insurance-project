package com.insurance.insuranceportalservice;

import lombok.extern.slf4j.Slf4j;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 
 */
@Slf4j
@MapperScan("com.insurance.**.mapper")
@EnableFeignClients(basePackages = {"com.insurance.**.feign"})
@SpringBootApplication
public class InsurancePortalServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(InsurancePortalServiceApplication.class, args);
        log.info("门户服务启动成功");
    }
}