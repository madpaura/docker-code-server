# https://hub.docker.com/r/mysql/mysql-server/
sudo docker pull mysql
sudo docker run --name=mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=12qwaszx -d mysql
sudo docker exec -it mysql mysql -uroot -p
CREATE DATABASE user_auth_db