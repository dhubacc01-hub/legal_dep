# Legal Department

Веб-приложение юридического департамента на `FastAPI` и `SQLite`.

## Что умеет

- ведение базы должников по Казахстану и Узбекистану;
- импорт клиентов из Excel/CSV через staging-контур;
- авторизация с ролями `owner`, `admin`, `lawyer`;
- подтягивание данных клиента из CRM по номеру договора;
- генерация претензий и исков;
- работа со справочниками городов, судов и компаний;
- ручное добавление пользовательских судов.

## Стек

- `FastAPI`
- `SQLite`
- `Jinja2`
- `Pillow`
- `openpyxl`

## Запуск локально

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

После запуска откройте [http://127.0.0.1:8000](http://127.0.0.1:8000).

## CRM

Для работы CRM-подтяжки приложение читает переменные окружения:

- `DISELL_API_USERNAME`
- `DISELL_API_PASSWORD`
- `DISELL_API_BASE_URL`
- `DISELL_AUTH_BASE_URL`
- `DISELL_API_CLIENT_ID`
- `DISELL_API_CLIENT_SECRET`
- `DISELL_API_GRANT_TYPE`
- `DISELL_API_TIMEOUT`

Для продакшена рекомендуется использовать только `env`/`systemd EnvironmentFile`.

## Структура

- [D:\Projects\Legal_Dep\app\main.py](</D:/Projects/Legal_Dep/app/main.py>) — основной FastAPI-контур, PDF и бизнес-логика.
- [D:\Projects\Legal_Dep\app\database.py](</D:/Projects/Legal_Dep/app/database.py>) — схема SQLite и миграции.
- [D:\Projects\Legal_Dep\app\reference_data.py](</D:/Projects/Legal_Dep/app/reference_data.py>) — справочники категорий, решений, стран и городов.
- [D:\Projects\Legal_Dep\app\court_catalog.py](</D:/Projects/Legal_Dep/app/court_catalog.py>) — сборка каталога судов KZ.
- [D:\Projects\Legal_Dep\app\company_requisites_data.py](</D:/Projects/Legal_Dep/app/company_requisites_data.py>) — встроенный seed реквизитов компаний.
- [D:\Projects\Legal_Dep\app\disell_api.py](</D:/Projects/Legal_Dep/app/disell_api.py>) — клиент CRM API.
- [D:\Projects\Legal_Dep\app\templates\index.html](</D:/Projects/Legal_Dep/app/templates/index.html>) — основная страница.
- [D:\Projects\Legal_Dep\app\templates\login.html](</D:/Projects/Legal_Dep/app/templates/login.html>) — страница входа.
- [D:\Projects\Legal_Dep\app\static\app.js](</D:/Projects/Legal_Dep/app/static/app.js>) — фронтенд-логика.
- [D:\Projects\Legal_Dep\app\static\styles.css](</D:/Projects/Legal_Dep/app/static/styles.css>) — стили.

## Импорт данных

Основной поток:

1. `POST /api/imports/preview-local`
2. просмотр пакета импорта и конфликтов
3. `POST /api/imports/{batch_id}/apply`

В `import_rows` сохраняются:

- исходные данные строки;
- нормализованные данные;
- ошибки и предупреждения;
- предложенная категория;
- связь с созданным должником, если строка применена.

## Деплой на VPS

Готовые серверные файлы лежат в [D:\Projects\Legal_Dep\deploy](</D:/Projects/Legal_Dep/deploy>):

- [D:\Projects\Legal_Dep\deploy\VPS_SETUP.md](</D:/Projects/Legal_Dep/deploy/VPS_SETUP.md>)
- [D:\Projects\Legal_Dep\deploy\legal-dep.service](</D:/Projects/Legal_Dep/deploy/legal-dep.service>)
- [D:\Projects\Legal_Dep\deploy\nginx-legal-dep.conf](</D:/Projects/Legal_Dep/deploy/nginx-legal-dep.conf>)

Рекомендуемый порядок обновления на сервере:

1. коммит и push в Git;
2. `git pull` на VPS;
3. `pip install -r requirements.txt`, если менялись зависимости;
4. `systemctl restart legal-dep`.
