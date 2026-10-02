# WorkBoard

Учебный fullstack-проект: приложение для совместного управления проектами и задачами. Архитектура — модульный монолит; backend и frontend находятся в одном репозитории.

## Текущее состояние

Подготовлен development-каркас: Django, React на JavaScript, PostgreSQL, Docker Compose, custom User и два smoke-теста. React запрашивает `/api/v1/` и показывает статус backend.

Бизнес-функции ещё не реализованы. Далее запланированы аутентификация, workspace, роли участников, проекты, задачи, комментарии и история действий. Celery, Redis, production-развёртывание и CI/CD появятся позже.

Этап 1 завершён. Миграции применены в основной development-БД; health endpoint работает через Django REST Framework. Backend-тесты, Django check, ESLint и сборка frontend проходят. Создан superuser; вручную проверены сохранение данных после перезапуска и hot reload backend и frontend. Health endpoint проверяет ответ API, но не доступность БД.

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
  accounts/       # Custom User
  workspaces/     # Каркас приложения
  projects/       # Каркас приложения
  tasks/          # Каркас приложения и текущий health endpoint
frontend/
  src/
  package.json
  package-lock.json
Dockerfile       # Образ backend
.dockerignore
.env.example
requirements.txt
docker-compose.yml
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
```

`DATABASE_URL` и `POSTGRES_*` должны описывать одну базу и одного пользователя. Для собственного пароля со специальными символами используй URL-кодирование в `DATABASE_URL`. `db` — имя сервиса внутри сети Compose, а не адрес для запуска Django напрямую с компьютера.

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

- Frontend: http://localhost:5173 — должны отображаться `WorkBoard React` и `ok`.
- Health endpoint: http://localhost:8000/api/v1/ — ожидается `{"status": "ok"}`.
- Django Admin: http://localhost:8000/admin/ — требует миграций и superuser.

Для текущих CORS-настроек открывай frontend через `localhost`, а не `127.0.0.1`.

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

# Тесты backend
docker compose exec -w /app/backend backend python -m pytest -v

# Проверка frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

Сейчас есть два теста: ответ health endpoint и сохранение custom User в PostgreSQL. pytest-django создаёт отдельную тестовую БД и применяет к ней миграции. Успешные тесты не означают, что миграции применены к основной development-БД. Пользователю PostgreSQL требуется право создавать тестовые базы.

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
