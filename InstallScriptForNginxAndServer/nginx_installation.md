# Script

## Use launch-template from SPOT INSTANCE

## Key_pair -> mjay_m1

## User - ec2-user
   
## Installation Script

```bash
#!/bin/bash
sudo yum update -y 
sudo yum -y install git
sudo yum -y install go
sudo yum -y install python3 
sudo amazon-linux-extras install nginx1 -y
sudo systemctl start nginx &
git clone https://github.com/mjaysonnn/BurScale.git
cd BurScale/loadcat
go get github.com/mjaysonnn/loadcat/cmd/loadcatd 
sudo ~/go/bin/loadcatd &  
git config credential.helper store
```


## Nginx Configuration

> sudo vim /etc/sysctl.conf
                       



```editorconfig
net.core.somaxconn = 65536
net.ipv4.tcp_max_tw_buckets = 1440000
net.ipv4.ip_local_port_range = 1024 65000
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_max_syn_backlog = 3240000
```



> sudo vim /etc/security/limits.conf
```
soft nofile 4096
hard nofile 100000
```



> sudo vim /etc/nginx/nginx.conf 
```editorconfig
# For more information on configuration, see:
#   * Official English Documentation: http://nginx.org/en/docs/
#   * Official Russian Documentation: http://nginx.org/ru/docs/

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
worker_rlimit_nofile 100000;

# Load dynamic modules. See /usr/share/doc/nginx/README.dynamic.
include /usr/share/nginx/modules/*.conf;

events {

    worker_connections 25000;
    use epoll;

    multi_accept on;

}

http {
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
    '$status $body_bytes_sent "$http_referer" '
    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;

    types_hash_max_size 4096;

    client_header_timeout 1m;
    client_body_timeout 1m;
    client_max_body_size 1024M;

    keepalive_requests 100000;
    keepalive_timeout 20m;

    proxy_connect_timeout 120;
    proxy_send_timeout 120;
    proxy_read_timeout 120;

    send_timeout 120;

    proxy_buffers 16 16k;
    proxy_buffer_size 32k;

    fastcgi_buffers 16 16k;
    fastcgi_buffer_size 32k;
    fastcgi_read_timeout 120;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Load modular configuration files from the /etc/nginx/conf.d directory.
    # See http://nginx.org/en/docs/ngx_core_module.html#include
    # for more information.
    include /etc/nginx/conf.d/*.conf;
    include /home/ec2-user/BurScale/loadcat/out/*/nginx.conf;
    server {
        listen 80;
        listen [::]:80;
        server_name _;
        root /usr/share/nginx/html;

        # Load configuration files for the default server block.
        include /etc/nginx/default.d/*.conf;

        error_page 404 /404.html;
        location = /40x.html {
        }

        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
        }
    }
}
```

sudo nginx -s reload

### Loadbalancer configuration
                    
Go to EC2 Instance Port 26590

#### Make loadbalancer

Make New Loadbalancer
    HostName - EC2 IP address
    Port - 80
    Least-connection



#### Initially, doesn't have server so **make dummy one** 

    New Server
        any ip address
        make sure put weight = 1 and unavailable

# For loadbalancer

    Get fetch balancer id 
    Put loadbalancer id in loadbalancer.py 