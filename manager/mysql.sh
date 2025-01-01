# https://hub.docker.com/r/mysql/mysql-server/
sudo docker pull mysql/mysql-server
sudo docker run --name=mysql1 -d mysql/mysql-server
sudo docker logs mysql1 | grep GENERATED
sudo docker exec -it mysql1 mysql -uroot -p
ALTER USER 'root'@'localhost' IDENTIFIED BY '12qwaszx';