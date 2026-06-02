# VPS Setup

Инструкция рассчитана на `Ubuntu 22.04/24.04` без домена, с доступом по IP.

## 1. Системные пакеты

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

## 2. Клонирование проекта

```bash
cd /opt
sudo git clone https://github.com/dhubacc01-hub/legal_dep.git legal-dep
sudo chown -R $USER:$USER /opt/legal-dep
cd /opt/legal-dep
```

## 3. Python-окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Данные приложения

Рабочая база:

`/opt/legal-dep/data/legal_dep_fixed.db`

Если нужно поднять проект с уже существующими данными, загрузите рабочую SQLite-базу именно под этим именем.

Минимум:

```bash
mkdir -p /opt/legal-dep/data/generated
```

## 5. CRM-переменные окружения

Создайте файл окружения, например:

`/etc/legal-dep.env`

Пример:

```bash
DISELL_API_USERNAME=your_login
DISELL_API_PASSWORD=your_password
DISELL_API_BASE_URL=https://disell.eu/api/v1
DISELL_AUTH_BASE_URL=https://disell.eu/api
DISELL_API_CLIENT_ID=crm_api
DISELL_API_CLIENT_SECRET=crm_pass
DISELL_API_GRANT_TYPE=password
DISELL_API_TIMEOUT=20
```

## 6. Systemd

Скопируйте сервис:

```bash
sudo cp deploy/legal-dep.service /etc/systemd/system/legal-dep.service
```

Проверьте в файле:

- `User=`
- `Group=`
- `WorkingDirectory=`
- `ExecStart=`
- `EnvironmentFile=`

Потом:

```bash
sudo systemctl daemon-reload
sudo systemctl enable legal-dep
sudo systemctl start legal-dep
sudo systemctl status legal-dep
```

## 7. Nginx

```bash
sudo cp deploy/nginx-legal-dep.conf /etc/nginx/sites-available/legal-dep
sudo ln -sf /etc/nginx/sites-available/legal-dep /etc/nginx/sites-enabled/legal-dep
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## 8. Проверка

На сервере:

```bash
curl http://127.0.0.1:8000
curl http://127.0.0.1
```

Снаружи:

```text
http://YOUR_SERVER_IP/
```

## 9. Обновление проекта

```bash
cd /opt/legal-dep
git pull
source .venv/bin/activate
python -m pip install -r requirements.txt
sudo systemctl restart legal-dep
```

## 10. Полезные команды

```bash
sudo systemctl status legal-dep --no-pager
sudo journalctl -u legal-dep -n 200 --no-pager
sudo systemctl status nginx --no-pager
sudo tail -n 200 /var/log/nginx/error.log
```
