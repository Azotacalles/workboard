import { useState, useEffect } from 'react';
import './App.css';
import { getMe, logout } from './api/client.js';
import LoginForm from './auth/LoginForm.jsx';
import RegisterForm from './auth/RegisterForm.jsx';
import AuthError from './auth/AuthError.jsx';

function App({ resetCompleted = false }) {
    const [user, setUser] = useState(null);
    const [status, setStatus] = useState('loading');
    const [errorMessage, setErrorMessage] = useState('');
    const [attempt, setAttempt] = useState(0);
    const [loggingOut, setLoggingOut] = useState(false);
    const [logoutError, setLogoutError] = useState(null);
    const [form, setForm] = useState('login');
    const [submitting, setSubmitting] = useState(false);
    // Это временное уведомление о сбросе, а не постоянный признак страницы.
    const [showResetNotice, setShowResetNotice] = useState(resetCompleted);

    useEffect(() => {
        let ignore = false;

        async function loadMe() {
            try {
                const data = await getMe();
                if (ignore) return;
                setUser(data);
                setStatus('success');
            } catch (error) {
                if (ignore) return;
                const isGuest = error.status === 403 && error.data?.code === 'not_authenticated';
                if (isGuest) {
                    setUser(null);
                    setStatus('success');
                } else {
                    setErrorMessage('Не удалось проверить вход. Попробуйте ещё раз.');
                    setStatus('error');
                }
            }
        }

        loadMe();
        // Ответ прошлой проверки не должен менять уже неактуальное состояние.
        return () => { ignore = true; };
    }, [attempt]);

    function handleRetry() {
        if (submitting || loggingOut) return;
        setErrorMessage('');
        setStatus('loading');
        setAttempt(previousAttempt => previousAttempt + 1);
    }

    function handleLogin(userData) {
        setUser(userData);
        setStatus('success');
        setErrorMessage('');
        setLogoutError(null);
        setShowResetNotice(false);
        if (resetCompleted) {
            // После входа обновление страницы не должно возвращать уведомление о сбросе.
            const url = new URL(window.location.href);
            url.searchParams.delete('reset');
            window.history.replaceState(null, '', url.pathname + url.search + url.hash);
        }
    }

    async function handleLogout() {
        // Проверяем занятость до очистки ошибки и до try/finally.
        if (loggingOut) return;
        setLogoutError(null);
        setLoggingOut(true);
        try {
            await logout();
            // Гостя показываем только после успешного серверного выхода.
            setUser(null);
            setForm('login');
        } catch (error) {
            setLogoutError(error);
        } finally {
            setLoggingOut(false);
        }
    }

    return (
        <>
            <h1>WorkBoard React</h1>
            {showResetNotice && status === 'success' && !user && (
                <p role="status">Пароль изменён. Для входа используйте новый пароль.</p>
            )}
            {status === 'loading' && <p>Проверяем вход…</p>}
            {status === 'error' && (
                <div>
                    {/* Ошибку проверки показываем один раз, вместе с повтором GET. */}
                    <p role="alert">{errorMessage}</p>
                    <button type="button" onClick={handleRetry}>Повторить</button>
                </div>
            )}
            {status === 'success' && (
                user ? (
                    <div>
                        {/* /me/ определяет реальную сессию, а не владельца ссылки из письма. */}
                        {showResetNotice && (
                            <p>Пароль изменён. Сейчас открыта сессия пользователя {user.username}. Для входа в восстановленный аккаунт завершите эту сессию.</p>
                        )}
                        <p>Привет, {user.username}</p>
                        <AuthError
                            error={logoutError}
                            onClearError={() => setLogoutError(null)}
                            onPendingChange={setLoggingOut}
                            onCheckSession={handleRetry}
                        />
                        <button type="button" onClick={handleLogout} disabled={loggingOut}>
                            {loggingOut ? 'Подождите…' : 'Выйти'}
                        </button>
                    </div>
                ) : (
                    <div>
                        {/* Одновременно видна одна форма: вход и регистрация не конкурируют. */}
                        {form === 'login' ? (
                            <LoginForm onLogin={handleLogin} onPendingChange={setSubmitting} onCheckSession={handleRetry} />
                        ) : (
                            <RegisterForm onLogin={handleLogin} onPendingChange={setSubmitting} onCheckSession={handleRetry} />
                        )}
                        <button type="button" disabled={submitting}
                            onClick={() => setForm(form === 'login' ? 'register' : 'login')}>
                            {form === 'login' ? 'Создать аккаунт' : 'Уже есть аккаунт? Войти'}
                        </button>
                    </div>
                )
            )}
        </>
    );
}

export default App;
