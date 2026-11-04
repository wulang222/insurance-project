# Spec Delta

## Purpose

让超级管理员查看 C 端用户，并立即撤销指定用户的登录会话。

## ADDED Requirements

### Requirement: Super admin can list app users
The system SHALL return a paginated list of `app_user` records to an authorized super admin, including user id, nickname, and phone number.

#### Scenario: List users
- **WHEN** a super admin requests the app-user list
- **THEN** the system returns the matching users and the page boundaries

#### Scenario: Filter by phone or nickname
- **WHEN** a super admin supplies a phone number or nickname filter
- **THEN** the system returns only users that match the supplied filter

### Requirement: Kick revokes only the app session
The system SHALL remove every active login session for the target user whose source is `app`, and SHALL leave system-user sessions, the account, policies, and chat records in place.

#### Scenario: Logged-in app user is kicked
- **WHEN** a super admin kicks an `app_user` that has an active portal session
- **THEN** that session is deleted and the user's later portal requests with the old token are rejected

#### Scenario: Kick does not delete the account
- **WHEN** a super admin kicks an `app_user`
- **THEN** the user record, related policies, and chat records still exist

#### Scenario: Unknown user
- **WHEN** a super admin kicks a user id that is not an `app_user`
- **THEN** the system rejects the request and does not delete any session

### Requirement: Only a super admin can administer app users
The system SHALL reject app-user listing and kick requests from callers who are not an enabled super admin.

#### Scenario: App user calls the admin list
- **WHEN** a C-end user token is presented to the app-user administration API
- **THEN** the system rejects the request
