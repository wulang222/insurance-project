package com.insurance.insuranceadminservice.security;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class SuperAdminWebConfig implements WebMvcConfigurer {

    @Autowired
    private SuperAdminAuthInterceptor superAdminAuthInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(superAdminAuthInterceptor).addPathPatterns("/**");
    }
}
