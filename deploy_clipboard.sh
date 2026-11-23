#!/usr/bin/env bash
set -euo pipefail

# 颜色定义
red='\033[0;31m'
green='\033[0;32m'
yellow='\033[0;33m'
plain='\033[0m'

# 必须以 root 或 sudo 权限运行
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${red}错误：请使用 root 权限或 sudo 运行此脚本（例如: sudo bash $0）${plain}"
    exit 1
fi

echo -e "${green}=== [1/4] 安装基础依赖 (python3-flask, gunicorn, nginx, curl, socat) ===${plain}"
apt update
apt install -y python3-flask gunicorn nginx curl socat

echo -e "${green}=== [2/4] 创建目录、下载源码与配置 ===${plain}"
mkdir -p /var/www/clipboard
mkdir -p /root/cert

curl -fsSL "https://raw.githubusercontent.com/zgrdou1875-crypto/paste_server/main/paste_server.py" -o /var/www/clipboard/paste_server.py
curl -fsSL "https://raw.githubusercontent.com/zgrdou1875-crypto/paste_server/main/clipboard.service" -o /etc/systemd/system/clipboard.service
curl -fsSL "https://raw.githubusercontent.com/zgrdou1875-crypto/paste_server/main/clipboard.conf" -o /etc/nginx/conf.d/clipboard.conf

# 在 /etc/nginx/nginx.conf 的 http { ... } 块中添加 client_max_body_size 50M;（若已存在则不重复添加）
if grep -q "client_max_body_size" /etc/nginx/nginx.conf; then
    echo -e "${yellow}检测到 /etc/nginx/nginx.conf 已包含 client_max_body_size，跳过重复添加。${plain}"
else
    sed -i '/http[[:space:]]*{/a \    client_max_body_size 50M;' /etc/nginx/nginx.conf
    echo -e "${green}已添加 client_max_body_size 50M; 到 /etc/nginx/nginx.conf${plain}"
fi

# 辅助函数：替换 /etc/nginx/conf.d/clipboard.conf 中的 server_name
set_server_name() {
    local domain="$1"
    if grep -qE '^\s*server_name\b' /etc/nginx/conf.d/clipboard.conf; then
        sed -i -E "s|(^\s*server_name\s+).*|\1${domain};|" /etc/nginx/conf.d/clipboard.conf
    else
        sed -i -E "s|(server\s*\{)|\1\n    server_name ${domain};|" /etc/nginx/conf.d/clipboard.conf
    fi
}

echo -e "${green}=== [3/4] 证书安装 ===${plain}"
while true; do
    echo "请选择证书安装方式："
    echo "  ① 已有证书 (输入 1)"
    echo "  ② 申请证书 (输入 2)"
    read -r -p "请输入选项 [1/2]: " cert_choice

    case "$cert_choice" in
        1)
            read -r -p "请输入域名: " domain_input
            if [ -z "$domain_input" ]; then
                echo -e "${red}域名不能为空，请重新选择。${plain}"
                continue
            fi
            set_server_name "$domain_input"

            read -r -p "请输入证书路径 (fullchain/crt): " cert_src
            read -r -p "请输入证书密钥路径 (privkey/key): " key_src

            if [ ! -f "$cert_src" ]; then
                echo -e "${red}证书文件不存在: $cert_src${plain}"
                exit 1
            fi
            if [ ! -f "$key_src" ]; then
                echo -r -p "${red}证书密钥文件不存在: $key_src${plain}"
                exit 1
            fi

            cp "$cert_src" /root/cert/fullchain.pem
            chmod 644 /root/cert/fullchain.pem

            cp "$key_src" /root/cert/privkey.pem
            chmod 600 /root/cert/privkey.pem

            echo -e "${green}已有证书已复制并设置权限完成。${plain}"
            break
            ;;
        2)
            if [ ! -f "/root/.acme.sh/acme.sh" ]; then
                echo "acme.sh was not detected on the system; performing offline installation..."
                curl -s https://get.acme.sh | sh > /dev/null 2>&1
                if [ $? -ne 0 ]; then
                    echo -e "${red}Failed to install acme.sh${plain}"
                    exit 1
                else
                    echo -e "${green}acme.sh installed successfully${plain}"
                fi
                # 加载环境变量
                [ -f /root/.bashrc ] && source /root/.bashrc || true
                [ -f /root/.acme.sh/acme.sh.env ] && source /root/.acme.sh/acme.sh.env || true
            fi

            echo -e "${yellow}提示：请确保域名已解析到本机，并且80端口开放不被占用${plain}"
            read -r -p "开始申请证书，请输入域名: " domain_input
            if [ -z "$domain_input" ]; then
                echo -e "${red}域名不能为空，请重新选择。${plain}"
                continue
            fi

            set_server_name "$domain_input"

            # 确保 80 端口不被 nginx 占用导致 standalone 失败
            systemctl stop nginx 2>/dev/null || true

            /root/.acme.sh/acme.sh --set-default-ca --server letsencrypt
            /root/.acme.sh/acme.sh --issue -d "$domain_input" --standalone --keylength ec-256

            # 安装证书到 /root/cert/ 并设置权限
            /root/.acme.sh/acme.sh --install-cert -d "$domain_input" --ecc \
                --fullchain-file /root/cert/fullchain.pem \
                --key-file /root/cert/privkey.pem \
                --reloadcmd "chmod 644 /root/cert/fullchain.pem && chmod 600 /root/cert/privkey.pem"

            chmod 644 /root/cert/fullchain.pem
            chmod 600 /root/cert/privkey.pem

            echo -e "${green}证书申请并安装到 /root/cert/ 完成。${plain}"
            break
            ;;
        *)
            echo -e "${red}无效输入，请输入 1 或 2。${plain}"
            ;;
    esac
done

echo -e "${green}=== [4/4] 启动服务 ===${plain}"
rm -rf /etc/nginx/conf.d/default.conf
rm -rf /etc/nginx/sites-enabled/default
nginx -t

systemctl start nginx 2>/dev/null || true
systemctl daemon-reload
systemctl start clipboard
systemctl enable clipboard
systemctl reload nginx
systemctl restart nginx

echo -e "${green}部署完成！当前服务状态：${plain}"
systemctl --no-pager --full status clipboard | head -n 12
systemctl --no-pager --full status nginx | head -n 12
