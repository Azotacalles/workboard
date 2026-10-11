import { useState } from 'react';
import { getCSRF } from '../api/client.js';

// Общие ошибки и восстановление CSRF одинаковы у входа, регистрации и выхода.
// Ошибки полей формы по-прежнему показывают рядом с соответствующим input.
function AuthError({ error, fields = [], onClearError, onPendingChange, onCheckSession }) {
    const [refreshing, setRefreshing] = useState(false);
    const [recoveryMessage, setRecoveryMessage] = useState('');

    async function handleRefreshCSRF() {
        if (refreshing) return;
        setRefreshing(true);
        onPendingChange(true);
        setRecoveryMessage('');
        try {
            await getCSRF();
            onClearError();
            setRecoveryMessage('Защита формы обновлена. Повторите отправку.');
            // Здесь только GET токена: исходный POST пользователь повторяет сам.
        } catch {
            setRecoveryMessage('Не удалось обновить защиту формы. Проверьте связь с сервером.');
        } finally {
            setRefreshing(false);
            onPendingChange(false);
        }
    }

    let message = '';
    if (error?.authenticatedUser) {
        // Сервер уже выполнил вход; повторная регистрация не исправит ошибку GET.
        message = 'Вход выполнен, но не удалось обновить защиту формы. Проверьте текущую сессию.';
    } else if (error?.data?.code === 'csrf_failed') {
        message = 'Не удалось проверить запрос. Обновите защиту формы и повторите отправку.';
    } else if (error && !error.status) {
        message = 'Не удалось связаться с сервером. Попробуйте ещё раз.';
    } else if (error?.data?.detail) {
        message = error.data.detail;
    } else if (error && !fields.some(field => error.data?.[field])) {
        message = error.message;
    }

    return (
        <>
            {message && <p role="alert">{message}</p>}
            {/* Уведомление о восстановлении не должно перекрывать новую ошибку пароля или поля. */}
            {recoveryMessage && (!error || error.data?.code === 'csrf_failed') && (
                <p role="status">{recoveryMessage}</p>
            )}
            {error?.authenticatedUser && (
                <button type="button" onClick={onCheckSession}>Проверить сессию</button>
            )}
            {!error?.authenticatedUser && error?.data?.code === 'csrf_failed' && (
                <button type="button" disabled={refreshing} onClick={handleRefreshCSRF}>
                    {refreshing ? 'Обновляем…' : 'Обновить защиту формы'}
                </button>
            )}
        </>
    );
}

export default AuthError;
