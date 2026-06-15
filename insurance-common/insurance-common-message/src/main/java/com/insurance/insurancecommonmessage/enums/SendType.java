package com.insurance.insurancecommonmessage.enums;

/**
 * 验证码发送类型
 */
public enum SendType {

    SMS(1),
    EMAIL(2);

    private final int value;

    SendType(int value) {
        this.value = value;
    }

    public int getValue() {
        return value;
    }
}
