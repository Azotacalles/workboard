import { useState } from 'react';
import { confirmPasswordReset } from '../api/client.js';
import AuthError from './AuthError.jsx';

function PasswordResetConfirmForm({ uid, token }) {
    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const invalidLink = !uid || !token || error?.data?.code === 'invalid_reset_link';

    async function handleSubmit(event) {
        event.preventDefault();
        if (loading || invalidLink) return;
        setError(null);
        setLoading(true);
        try {
            await confirmPasswordReset({ uid, token, password, password_confirm: passwordConfirm });
            setPassword('');
            setPasswordConfirm('');
            // Полный переход убирает uid/token из адреса и запускает проверку /me/ заново.
            // Сброс пароля сам не выполняет login.
            window.location.replace('/login?reset=success');
        } catch (error) {
            setError(error);
        } finally {
            setLoading(false);
        }
    }

    // Hooks находятся выше: наличие параметров ссылки не должно менять порядок их вызовов.
    if (invalidLink) {
        return (
            <>
                <h1>Восстановление пароля</h1>
                <p role="alert">
                    {!uid || !token
                        ? 'Ссылка восстановления неполная. Запросите новую ссылку.'
                        : 'Ссылка недействительна или устарела. Запросите новую ссылку.'}
                </p>
                <a href="/forgot-password">Запросить новую ссылку</a>
            </>
        );
    }

    return (
        <>
            <h1>Новый пароль</h1>
            {/* Владельца аккаунта определяет backend по uid/token, а не сессия браузера. */}
            <p>Установите новый пароль для аккаунта, указанного в письме.</p>
            <AuthError error={error} fields={['uid', 'token', 'password', 'password_confirm']}
                onClearError={() => setError(null)} onPendingChange={setLoading} />
            {/* Ошибки структуры ссылки тоже не должны остаться невидимыми. */}
            {error?.data?.uid && <p role="alert">{error.data.uid.join(' ')}</p>}
            {error?.data?.token && <p role="alert">{error.data.token.join(' ')}</p>}
            <form onSubmit={handleSubmit}>
                <fieldset disabled={loading}>
                    <legend>Смена пароля</legend>
                    <label>
                        Новый пароль:
                        <input name="password" value={password} type="password" required autoComplete="new-password"
                            onChange={event => setPassword(event.target.value)} />
                    </label>
                    {error?.data?.password && <p role="alert">{error.data.password.join(' ')}</p>}
                    <label>
                        Повтор нового пароля:
                        <input name="password_confirm" value={passwordConfirm} type="password" required autoComplete="new-password"
                            onChange={event => setPasswordConfirm(event.target.value)} />
                    </label>
                    {error?.data?.password_confirm && <p role="alert">{error.data.password_confirm.join(' ')}</p>}
                    <button type="submit">{loading ? 'Сохраняем…' : 'Сохранить пароль'}</button>
                </fieldset>
            </form>
            <a href="/forgot-password">Запросить новую ссылку</a>
        </>
    );
}

export default PasswordResetConfirmForm;
