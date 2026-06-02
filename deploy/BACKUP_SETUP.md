# Google Drive Backup Setup

Инструкция для ежедневных бэкапов базы проекта на Google Drive.

## Что бэкапится

По умолчанию:

- `/opt/legal-dep/data/legal_dep_fixed.db`

Опционально можно включить папку:

- `/opt/legal-dep/data/generated`

## Что нужно сделать вам

### 1. Установить пакеты на VPS

```bash
apt update
apt install -y sqlite3 rclone
```

### 2. Скопировать файлы из проекта

```bash
cd /opt/legal-dep
cp deploy/backup_legal_dep.sh /opt/legal-dep/deploy/backup_legal_dep.sh
chmod +x /opt/legal-dep/deploy/backup_legal_dep.sh
cp deploy/legal-dep-backup.service /etc/systemd/system/legal-dep-backup.service
cp deploy/legal-dep-backup.timer /etc/systemd/system/legal-dep-backup.timer
```

### 3. Разрешить доступ к Google Drive через `rclone`

На VPS выполните:

```bash
rclone config
```

Дальше:

1. `n` — New remote
2. Имя: `gdrive`
3. Storage: `drive`
4. `client_id` — Enter, оставить пустым
5. `client_secret` — Enter, оставить пустым
6. `scope` — `1` (`drive`)
7. `root_folder_id` — Enter, пусто
8. `service_account_file` — Enter, пусто
9. `Edit advanced config?` — `n`
10. `Use auto config?` — `n`

После этого `rclone` покажет ссылку. Ее нужно:

- скопировать,
- открыть в браузере на вашем компьютере,
- войти в нужный Google-аккаунт,
- разрешить доступ,
- вставить полученный код обратно в SSH-сессию.

Потом:

11. `Configure this as a Shared Drive?` — `n`
12. `y` — подтвердить
13. `q` — выйти

### 4. Проверить, что Google Drive подключился

```bash
rclone lsd gdrive:
```

Если команда отрабатывает без ошибки, связь настроена.

### 5. Протестировать бэкап вручную

```bash
systemctl daemon-reload
systemctl start legal-dep-backup.service
systemctl status legal-dep-backup.service --no-pager
```

Проверить локальный архив:

```bash
ls -la /opt/legal-dep/backups
```

Проверить файлы на Google Drive:

```bash
rclone lsf gdrive:legal-dep-backups
```

### 6. Включить ежедневный запуск

```bash
systemctl enable --now legal-dep-backup.timer
systemctl status legal-dep-backup.timer --no-pager
systemctl list-timers --all | grep legal-dep-backup
```

## Что можно менять

Файл:

- `/etc/systemd/system/legal-dep-backup.service`

Параметры:

- `REMOTE_NAME` — имя `rclone` remote
- `REMOTE_DIR` — папка на Google Drive
- `KEEP_LOCAL_DAYS` — сколько дней хранить локальные архивы
- `KEEP_REMOTE_DAYS` — сколько дней хранить архивы на Google Drive
- `INCLUDE_GENERATED=1` — если хотите добавлять `generated/`

После правок:

```bash
systemctl daemon-reload
systemctl restart legal-dep-backup.timer
```
