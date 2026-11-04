# Spec Delta

## Purpose

让超级管理员维护 Agent 使用的 MySQL 产品目录和用户历史保单，并查看已写入的数据。

## ADDED Requirements

### Requirement: Super admin can write insurance products
The system SHALL create or update an `insurance_products` row when a super admin submits a unique `product_id`, name, insurance type, age range, price range, target occupations, description, and active flag.

#### Scenario: Create a product
- **WHEN** a super admin submits a new product whose `product_id` is unused
- **THEN** the system stores the product and returns its identifier

#### Scenario: Duplicate product id
- **WHEN** a super admin submits a `product_id` that already exists on another product
- **THEN** the system rejects the write and leaves the existing row unchanged

#### Scenario: Deactivate a product
- **WHEN** a super admin sets a product's active flag to inactive
- **THEN** the product remains stored and is marked inactive

### Requirement: Super admin can list products including inactive ones
The system SHALL return a paginated product list to a super admin, including inactive products, and SHALL support filtering by insurance type, product id, and active flag.

#### Scenario: Inactive products remain visible to admin
- **WHEN** a super admin lists products without an active-only filter
- **THEN** both active and inactive products are included

### Requirement: Agents read the uploaded active catalog
The product search used by the insurance agents SHALL return only active products stored in `insurance_products`, including products created through the admin API.

#### Scenario: Newly uploaded active product is searchable
- **WHEN** a super admin creates an active product and an agent searches with matching type, age, and budget
- **THEN** the search result includes that product's stored fields

#### Scenario: Inactive product is hidden from agents
- **WHEN** an agent searches the catalog after a product has been deactivated
- **THEN** that product is absent from the agent result

### Requirement: Super admin can write policy history
The system SHALL create or update a `user_policy_history` row for an existing `app_user`, with a unique policy number, product name, premium, sum insured, status, and effective dates.

#### Scenario: Create a policy for an existing user
- **WHEN** a super admin submits a policy whose user id exists and whose policy number is unused
- **THEN** the system stores the policy and returns its identifier

#### Scenario: Unknown policy holder
- **WHEN** a super admin submits a policy for a user id that is not an `app_user`
- **THEN** the system rejects the write

#### Scenario: Duplicate policy number
- **WHEN** a super admin submits a policy number that already exists
- **THEN** the system rejects the write and leaves the existing policy unchanged

### Requirement: Super admin can list policy history
The system SHALL return a paginated policy list to a super admin and SHALL support filtering by user id and policy status.

#### Scenario: List one user's policies
- **WHEN** a super admin requests policies for a user id
- **THEN** the system returns only that user's stored policies

### Requirement: CRM reads uploaded policies
The CRM portfolio lookup SHALL return the stored `user_policy_history` rows for the requested user and SHALL NOT invent policies when none are stored.

#### Scenario: Portfolio contains the uploaded policy
- **WHEN** CRM loads the portfolio of a user who has an admin-uploaded policy
- **THEN** the portfolio includes that policy's stored number, product name, premium, sum insured, status, and dates

#### Scenario: User has no policies
- **WHEN** CRM loads the portfolio of a user with no policy rows
- **THEN** the portfolio policy list is empty
