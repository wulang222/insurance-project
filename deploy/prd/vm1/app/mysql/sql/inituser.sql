# 1、初始化数据库：创建nacos外接数据库insurance_nacos_dev和脚手架业务数据库insurance_dev
# 2、创建用户，用户名：insurancedev 密码：insurance@123
# 3、授予insurancedev用户特定权限

CREATE database if NOT EXISTS `insurance_nacos_prd` default character set utf8mb4 collate utf8mb4_general_ci;
CREATE database if NOT EXISTS `insurance_prd` default character set utf8mb4 collate utf8mb4_general_ci;

CREATE USER 'insurancedev'@'%' IDENTIFIED BY 'insurance@123';
grant replication slave, replication client on *.* to 'insurancedev'@'%';

GRANT ALL PRIVILEGES ON insurance_nacos_prd.* TO  'insurancedev'@'%';
GRANT ALL PRIVILEGES ON insurance_prd.* TO  'insurancedev'@'%';

FLUSH PRIVILEGES;
