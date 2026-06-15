# 该命令以节点1为例
docker exec -it insurance-rabbitmq02 /bin/bash

#ram节点加入集群

rabbitmqctl stop_app
rabbitmqctl reset
rabbitmqctl join_cluster --ram insurance-rabbitmq01@insurance-rabbitmq01
rabbitmqctl start_app