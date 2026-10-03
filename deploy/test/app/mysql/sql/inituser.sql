# 1、初始化数据库：创建nacos外接数据库insurance_nacos_dev和脚手架业务数据库insurance_dev
# 2、部署前将占位符替换为安全密码，或通过受管初始化流程创建用户
# 3、授予insurancedev用户特定权限

CREATE database if NOT EXISTS `insurance_nacos_test` default character set utf8mb4 collate utf8mb4_general_ci;
CREATE database if NOT EXISTS `insurance_test` default character set utf8mb4 collate utf8mb4_general_ci;

CREATE USER 'insurancedev'@'%' IDENTIFIED BY '__MYSQL_SERVICE_PASSWORD__';
grant replication slave, replication client on *.* to 'insurancedev'@'%';

GRANT ALL PRIVILEGES ON insurance_nacos_test.* TO  'insurancedev'@'%';
GRANT ALL PRIVILEGES ON insurance_test.* TO  'insurancedev'@'%';

FLUSH PRIVILEGES;
