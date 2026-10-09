const API_URL = 'http://localhost:8000/api/v1';

// Токен живёт в памяти модуля; cookies хранит и отправляет браузер.
let csrfToken = null;

export async function getCSRF() {
    const data = await apiRequest('/auth/csrf/');
    csrfToken = data.csrfToken;
    return csrfToken;
}

export async function apiRequest(path, { method = 'GET', data } = {}) {
    method = method.toUpperCase();
    const headers = {};

    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        // Перед первым изменяющим запросом дожидаемся токена и CSRF-cookie.
        if (!csrfToken) {
            await getCSRF();
        }
        headers['X-CSRFToken'] = csrfToken;
    }

    if (data !== undefined) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_URL}${path}`, {
        method,
        headers,
        credentials: 'include',
        body: data === undefined ? undefined : JSON.stringify(data),
    });

    // У logout нет тела: попытка прочитать JSON дала бы ошибку.
    if (response.status === 204) {
        return null;
    }

    // При серверном сбое может прийти HTML вместо JSON.
    const isJSON = response.headers.get('Content-Type')?.includes('application/json');
    const result = isJSON ? await response.json() : null;

    if (!response.ok) {
        const error = new Error(result?.detail || `Ошибка запроса: ${response.status}`);
        error.status = response.status;
        error.data = result;
        // Форме понадобятся и общий code, и ошибки отдельных полей из data.
        throw error;
    }

    return result;
}

async function authenticate(path, data) {
    const user = await apiRequest(path, { method: 'POST', data });
    // Вход меняет CSRF-секрет. Старый токен больше не используем.
    csrfToken = null;
    await getCSRF();
    return user;
}

export function register(data) {
    return authenticate('/auth/register/', data);
}

export function login(data) {
    return authenticate('/auth/login/', data);
}

export function logout() {
    return apiRequest('/auth/logout/', { method: 'POST' });
}

export function getMe() {
    return apiRequest('/auth/me/');
}
