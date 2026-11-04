# Spec Delta

## Purpose

只允许启用中的超级管理员登录管理端，并拒绝其他身份调用管理接口。

## ADDED Requirements

### Requirement: Super admin can log in
The system SHALL issue an access token only when the password matches an enabled `sys_user` whose identity is `super_admin`.

#### Scenario: Enabled super admin logs in
- **WHEN** an enabled `super_admin` submits the correct phone number and password to `/admin/sys_user/login/password`
- **THEN** the system returns an access token that identifies that user as a system user

#### Scenario: Wrong password
- **WHEN** a `super_admin` submits a password that does not match the stored password
- **THEN** the system rejects the login and does not issue a token

### Requirement: Non-super identities cannot log in
The system SHALL reject management login for every `sys_user` identity other than `super_admin`, including `platform_admin`.

#### Scenario: Platform admin attempts login
- **WHEN** an enabled `platform_admin` submits the correct phone number and password
- **THEN** the system rejects the login and does not issue a token

#### Scenario: Disabled super admin attempts login
- **WHEN** a `super_admin` whose status is disabled submits the correct password
- **THEN** the system rejects the login and does not issue a token

### Requirement: Management APIs require a live super admin session
The system SHALL reject management API calls that lack a token, use an expired or revoked token, or use a token whose current `sys_user` identity is not an enabled `super_admin`.

#### Scenario: Previously issued non-super token
- **WHEN** a caller presents a still-unexpired token that was issued to a `platform_admin`
- **THEN** the management API rejects the call

#### Scenario: Super admin token is accepted
- **WHEN** an enabled `super_admin` calls a management API with a valid unexpired token
- **THEN** the system authorizes the call

### Requirement: Customer login stays unchanged
The system SHALL keep C-end portal login independent of the super-admin restriction.

#### Scenario: App user logs in to the portal
- **WHEN** an existing C-end user logs in through the portal
- **THEN** the portal still issues an app session and does not require `super_admin`
