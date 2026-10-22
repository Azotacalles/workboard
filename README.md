# WorkBoard

Учебный fullstack-проект: приложение для совместного управления проектами и задачами. Архитектура — модульный монолит; backend и frontend находятся в одном репозитории.

## Текущее состояние

Работают регистрация, вход по email, текущий пользователь, выход и восстановление пароля по ссылке из письма. Backend использует сессии Django и CSRF-защиту; React показывает формы, ошибки полей и ошибки связи. После обновления страницы frontend заново проверяет сессию через `/me/`.

Приветственное письмо отправляется после commit регистрации. Восстановление не раскрывает существование аккаунта и не выполняет автоматический вход после смены пароля. Ошибка SMTP логируется и не отменяет созданный аккаунт.

GitHub Actions запускает проверки backend и frontend при push и pull request. Workspace, роли участников, проекты, задачи, комментарии и история действий — следующие этапы. TanStack Query установлен, но пока не используется: запросы написаны через `fetch`, состояние — через React hooks.

Конфигурация предназначена для локальной разработки по HTTP через `localhost`. Production-развёртывание, Celery и Redis пока не подготовлены. Публичный health endpoint проверяет ответ API, но не доступность БД.

## Стек

- Backend: Python 3.14, Django, Django REST Framework, PostgreSQL 17, django-environ.
- Frontend: React, JavaScript + JSX, Vite, ESLint; Node.js 24 в контейнере.
- Тесты: pytest, pytest-django.
- Окружение: Docker Compose.

## Структура

```text
backend/
  manage.py
  pytest.ini
  config/
    settings/
      base.py
      dev.py
      prod.py
  accounts/       # User, auth API, admin-формы, письма и тесты
  workspaces/     # Каркас приложения
  projects/       # Каркас приложения
  tasks/          # Каркас приложения и текущий health endpoint
frontend/
  src/
    api/         # fetch-клиент с cookies и CSRF
    auth/        # Формы входа, регистрации и восстановления
  package.json
  package-lock.json
Dockerfile       # Образ backend
.dockerignore
.env.example
requirements.txt
docker-compose.yml
.github/workflows/ci.yml
```

## Первый запуск

Нужны Git и запущенный Docker Engine с Docker Compose (например, Docker Desktop). Для запуска через контейнеры локальные Python и Node.js не требуются.

Все команды ниже выполняются из корня репозитория, рядом с `docker-compose.yml`.

### 1. Подготовить переменные окружения

После клонирования репозитория создай локальный файл, если его ещё нет:

```bash
cp .env.example .env
```

Заполни `.env`. Пример значений только для локальной разработки:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=local-development-only-change-me
DEBUG=True
DATABASE_URL=postgres://workboard:workboard_dev@db:5432/workboard
POSTGRES_DB=workboard
POSTGRES_USER=workboard
POSTGRES_PASSWORD=workboard_dev
FRONTEND_URL=http://localhost:5173
SMTP_PASSWORD=
```

`DATABASE_URL` и `POSTGRES_*` должны описывать одну базу и одного пользователя. Для собственного пароля со специальными символами используй URL-кодирование в `DATABASE_URL`. `db` — имя сервиса внутри сети Compose, а не адрес для запуска Django напрямую с компьютера.

`FRONTEND_URL` задаёт начало ссылки восстановления. Перед проверкой писем выбери SMTP или console по разделу «Почта» ниже: пустой `SMTP_PASSWORD` не позволяет отправлять письма через Gmail.

`.env` не коммитится и не копируется в backend-образ. Compose передаёт переменные в контейнер через `env_file`. Точки входа Django также умеют читать локальный `.env`, если файл доступен. pytest не запускает `manage.py`, поэтому тесты ниже выполняются в контейнере с уже заданным окружением.

Настройки `dev.py` и `prod.py` явно задают `DEBUG`. Production-конфигурация пока является заготовкой и не готова к публичному развёртыванию.

### 2. Собрать и запустить сервисы

```bash
docker compose up -d --build
```

Backend ждёт успешного healthcheck PostgreSQL. Frontend при запуске выполняет `npm ci`, поэтому первый старт требует загрузки зависимостей и может занять некоторое время.

### 3. Применить миграции

```bash
docker compose exec backend python backend/manage.py migrate
docker compose exec backend python backend/manage.py showmigrations
```

Применённые миграции помечены `[X]`. Запуск сервера сам по себе миграции не применяет.

### 4. Открыть приложение

- [Frontend](http://localhost:5173) — форма входа или приветствие текущего пользователя.
- [Форма запроса восстановления](http://localhost:5173/forgot-password).
- [Health endpoint](http://localhost:8000/api/v1/) — ожидается `{"status": "ok"}`, вход не нужен.
- [Django Admin](http://localhost:8000/admin/) — требует миграций и superuser; вход по email.

Frontend и API должны использовать `localhost`: `127.0.0.1` — другой хост для cookies и другой origin для CORS. В dev разрешён origin `http://localhost:5173`, запросы отправляются с `credentials: 'include'`.

Для pgAdmin на компьютере: host `localhost`, port `5433`, имя БД/пользователь/пароль из `POSTGRES_*`. Внутри Compose Django подключается к `db:5432`. В CI Python работает на runner и подключается к опубликованному порту PostgreSQL через `localhost:5432`.

## Правила аккаунта и сессии

- Email обязателен и уникален без учёта регистра. Пробелы по краям удаляются, весь адрес сохраняется в нижнем регистре. Точки и часть после `+` сохраняются.
- Username обязателен и используется как отображаемое имя. Повторы разрешены; регистр сохраняется. Для связей с пользователем используется `id`.
- Пароль проверяют валидаторы Django, в БД хранится хеш. Пробелы в пароле не обрезаются.
- Регистрация автоматически выполняет вход. Повторный login/register вошедшего клиента возвращает `409`, не переключая аккаунт.
- Сессия действует 14 дней и не продлевается каждым запросом. Session cookie — `HttpOnly`; обе cookies — `SameSite=Lax`, в dev `Secure=False`.
- Все auth POST требуют CSRF, в том числе анонимные login/register/reset. После входа CSRF-секрет меняется; клиент получает свежий токен.
- Logout удаляет текущую серверную сессию. Повторный logout с правильным CSRF допустим; другие сессии не завершаются.
- Ссылка восстановления действует один час. После смены пароля ссылка и прежние сессии теряют пригодность; далее нужен обычный вход. Владение email при регистрации пока не подтверждается.

## Auth API

Все пути начинаются с `/api/v1/auth/`. Объект пользователя содержит `id`, `username`, `email`.

| Метод и путь | Данные запроса | Успешный ответ |
| --- | --- | --- |
| `GET csrf/` | Без тела | `200`, `{"csrfToken": "..."}` и CSRF-cookie |
| `POST register/` | `email`, `username`, `password`, `password_confirm` | `201`, пользователь и сессия |
| `POST login/` | `email`, `password` | `200`, пользователь и сессия |
| `GET me/` | Session cookie | `200`, пользователь |
| `POST logout/` | Без тела | `204`, пустой ответ |
| `POST password-reset/` | `email` | `200`, нейтральное сообщение |
| `POST password-reset/confirm/` | `uid`, `token`, `password`, `password_confirm` | `204`, пустой ответ |

Для POST сначала получи `csrfToken` через GET, затем отправляй cookies и заголовок `X-CSRFToken`. Cookies браузер хранит и прикладывает сам; токен для заголовка хранит JS-клиент. При `csrf_failed` форма предлагает получить свежий токен, после чего пользователь сам повторяет отправку. POST автоматически не повторяется.

Ошибки полей возвращаются с `400` и списками сообщений, например `{"email": ["Этот email уже занят."]}`. Общие ошибки имеют форму `{"code": "...", "detail": "..."}`:

| Статус | Code | Причина |
| --- | --- | --- |
| `400` | `invalid_credentials` | Неверные данные входа или неактивный аккаунт |
| `400` | `invalid_reset_link` | Неверная, просроченная или использованная ссылка |
| `403` | `not_authenticated` | Нет действующей сессии для `/me/` |
| `403` | `csrf_failed` | Не прошла проверка CSRF или Origin |
| `409` | `already_authenticated` | Уже есть сессия при login/register |

Auth-ответы имеют `Cache-Control: no-store`. Успешный logout и подтверждение сброса не содержат JSON: у них статус `204`.

## Почта

Настройка находится в `MAILERS['default']` в `backend/config/settings/base.py`. Сейчас выбран SMTP Gmail: `smtp.gmail.com`, порт `587`, STARTTLS, timeout 10 секунд.

Для своего Gmail-аккаунта:

1. Включи двухэтапную аутентификацию и создай [пароль приложения Google](https://support.google.com/accounts/answer/185833?hl=ru).
2. Запиши пароль приложения в `.env` как `SMTP_PASSWORD`, без разделяющих пробелов. Обычный пароль Google здесь не используется.
3. SMTP `username` пока задан прямо в `base.py`. Укажи свой адрес и тот же адрес отправителя в обеих функциях `backend/accounts/emails.py`. Переменной `SMTP_USERNAME` в проекте пока нет.
4. После изменения `.env` пересоздай backend, чтобы Compose передал новое окружение:

```bash
docker compose up -d --force-recreate backend
```

Обычный `docker compose restart backend` не обновляет окружение контейнера. SMTP-пароль не нужно коммитить или добавлять в CI: pytest использует memory backend; CI задаёт только непустую заглушку для чтения настроек.

Для разработки без настоящей доставки замени настройку `MAILERS` на console backend:

```python
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
```

Console печатает письмо в `docker compose logs -f backend`; в реальный ящик ничего не приходит. SMTP отправляет в ящик. Memory backend в тестах сохраняет письма в `mailoutbox`. Подробности: [Django: email backends](https://docs.djangoproject.com/en/6.1/topics/email/#email-backends).

Ожидаемые ошибки SMTP и подключения логируются в `smtp.log`. В контейнере это `/app/smtp.log`; посмотреть:

```bash
docker compose exec backend tail -n 30 /app/smtp.log
```

Успешная регистрация подтверждает создание аккаунта, но не доставку письма. Запрос восстановления возвращает одинаковое сообщение для существующего и неизвестного адреса. При проблеме доставки сначала проверь выбранный backend и лог SMTP; VPN может мешать подключению к SMTP-серверу.

## Повседневные команды

```bash
# Запустить / посмотреть состояние
docker compose up -d
docker compose ps

# Следить за логами (Ctrl+C прекращает просмотр)
docker compose logs -f backend frontend db

# Остановить контейнеры
docker compose stop

# Удалить контейнеры и сеть, сохранив named volumes
docker compose down

# Django shell / пользователь администратора
docker compose exec backend python backend/manage.py shell
docker compose exec backend python backend/manage.py createsuperuser

# Создать миграции после изменения моделей и применить их
docker compose exec backend python backend/manage.py makemigrations
docker compose exec backend python backend/manage.py migrate
```

PostgreSQL хранит данные в named volume `postgres_data`. Команда `docker compose down -v` удаляет volumes, включая данные БД; для обычной остановки её не используй. Изменение `POSTGRES_*` в `.env` не перенастраивает уже инициализированную базу.

## Проверки

Сначала запусти сервисы, затем выполни:

```bash
# Конфигурация Django
docker compose exec backend python backend/manage.py check

# Модели должны соответствовать сохранённым миграциям
docker compose exec backend python backend/manage.py makemigrations --check --dry-run

# Тесты backend
docker compose exec -w /app/backend backend python -m pytest -v

# Проверка frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

Тесты сгруппированы по назначению в пакетах `tests/` внутри приложений:

- `backend/accounts/tests/`: модели, auth и сессии, регистрация, восстановление пароля, безопасность, письма и Admin.
- `backend/workspaces/tests/`: модели, serializers, маршруты, создание, список и detail API.
- `backend/tasks/tests/test_health.py`: health endpoint.
- `backend/projects/tests/`: пакет для будущих тестов проектов, пока без сценариев.

Общие `user_factory` и `logged_in_client` находятся в `backend/conftest.py`. Подготовка письма восстановления — в `accounts/tests/conftest.py`, данные workspace — в `workspaces/tests/conftest.py`. В тестах сохранены комментарии к сценариям.

pytest-django создаёт отдельную PostgreSQL-БД и применяет к ней миграции; тестовые письма наружу не отправляются. Успешные тесты не означают, что миграции применены к основной development-БД. Пользователю PostgreSQL требуется право создавать тестовые базы. `makemigrations --check --dry-run` проверяет описание моделей, но не применяет миграции.

Для отдельного сценария:

```bash
docker compose exec -w /app/backend backend python -m pytest accounts/tests/test_auth.py::test_user_logout -v
docker compose exec -w /app/backend backend python -m pytest workspaces/tests/test_api_detail.py -v
docker compose exec -w /app/backend backend python -m pytest -k password_reset -v
```

### GitHub Actions

Workflow `.github/workflows/ci.yml` выполняет Django check, проверку миграций, pytest, ESLint и Vite build. Посмотреть результат можно во вкладке [Actions](https://github.com/Azotacalles/workboard/actions): открой запуск для нужного commit, затем job `backend` или `frontend`. Зелёный запуск старого commit не проверяет локальные изменения; для новых изменений нужен commit и push.

### Приёмка этапа 2

1. Зарегистрируй аккаунт, проверь приветствие, письмо и сохранение входа после обновления страницы.
2. Выйди и обнови страницу: должна остаться форма входа. Проверь вход с другим регистром email и ошибку неверного пароля.
3. Через «Забыли пароль?» получи письмо, открой ссылку, сохрани новый пароль. Старый пароль, старые сессии и использованная ссылка должны перестать работать; новый пароль должен подходить.
4. Проверь отдельный профиль браузера, ошибки связи при недоступном API, Admin и публичный health endpoint.
5. Выполни команды проверок выше и проверь CI именно для отправленного commit.

На 13 октября 2026 локально проходят 81 тест, Django check, проверка миграций, ESLint и сборка Vite. В браузере проверены вход с другим регистром email, неверный пароль, сохранение входа после reload, logout/reload, истечение серверной сессии и ошибки связи без ложного успеха. Для ошибок связи использовалась временная имитация отказа `fetch`, без остановки backend.

Регистрация, восстановление, старые пароли/сессии, повтор ссылки, независимость клиентов и сохранение пользователя через Admin покрыты интеграционными тестами PostgreSQL. Отдельный браузерный профиль в этой приёмке не проверялся вручную; перед итоговой отметкой проверь вход в обычном окне и отсутствие этой сессии в инкогнито.

Реальная доставка письма восстановления через Gmail подтверждена пользователем. **Доставка приветственного письма в настоящий ящик ещё не проверена**; memory-тесты обоих писем проходят.

Последний просмотренный [CI для `69f36db`](https://github.com/Azotacalles/workboard/actions/runs/38425534805) завершился ошибкой backend; frontend прошёл. Детальные логи GitHub требуют авторизации. Исправления обработки повреждённого `uid`, формата ошибки email и расширенные тесты из 2.24–2.25 пока находятся в локальных изменениях. Для окончательной приёмки нужен успешный CI после их push, проверка отдельного профиля и настоящего приветственного письма.

## Изменение кода и зависимостей

Исходники подключены через bind mounts:

- `./backend` → `/app/backend`;
- `./frontend` → `/app`.

Изменение Python-кода вызывает перезапуск Django; изменение React-компонента подхватывает Vite. Для проверки измени текст в `frontend/src/App.jsx`, сохрани и проверь страницу без ручной перезагрузки. Перезапуск Django виден в логах backend.

После изменения `requirements.txt` пересобери backend:

```bash
docker compose up -d --build backend
```

После согласованного обновления `package.json` и `package-lock.json` перезапусти frontend: при старте он заново установит зависимости по lock-файлу.

```bash
docker compose restart frontend
```

Зависимости frontend в контейнере хранятся в отдельном volume `frontend_node_modules`, поэтому не смешиваются с зависимостями, установленными на Mac. Миграции Django и `package-lock.json` нужно хранить в Git.

## Проверка сохранения данных

После применения миграций создай superuser командой выше. Убедись, что можешь войти в Admin. Затем выполни:

```bash
docker compose stop
docker compose up -d
```

Повторный вход тем же пользователем и сохранённые отметки `[X]` в `showmigrations` подтвердят, что данные пережили остановку контейнеров.
