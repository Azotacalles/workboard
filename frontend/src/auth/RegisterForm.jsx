import { useState } from 'react';
import { register } from '../api/client.js';
import AuthError from './AuthError.jsx';

function RegisterForm({ onLogin, onPendingChange, onCheckSession }) {
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    function handlePending(pending) {
        setLoading(pending);
        onPendingChange(pending);
    }

    async function handleSubmit(e) {
        e.preventDefault();
        if (loading || error?.authenticatedUser) return;
        setError(null);
        handlePending(true);
        try {
            const data = await register({ email, username, password, password_confirm: passwordConfirm });
            // Пароли очищаем после успеха; при ошибках полей сохраняем ввод для исправления.
            setPassword('');
            setPasswordConfirm('');
            onLogin(data);
        } catch (error) {
            setError(error);
            if (error.authenticatedUser) {
                setPassword('');
                setPasswordConfirm('');
            }
        } finally {
            handlePending(false);
        }
    }

    return (
        <div>
            <AuthError
                error={error}
                fields={['email', 'username', 'password', 'password_confirm']}
                onClearError={() => setError(null)}
                onPendingChange={handlePending}
                onCheckSession={onCheckSession}
            />
            <form onSubmit={handleSubmit}>
                <fieldset disabled={loading || Boolean(error?.authenticatedUser)}>
                    <legend>Регистрация</legend>
                    <label>
                        Email:
                        <input name="email" value={email} type="email" required autoComplete="username"
                            onChange={e => setEmail(e.target.value)} />
                    </label>
                    {error?.data?.email && <p role="alert">{error.data.email.join(' ')}</p>}
                    <label>
                        Имя пользователя:
                        <input name="username" value={username} required maxLength={50} autoComplete="nickname"
                            onChange={e => setUsername(e.target.value)} />
                    </label>
                    {error?.data?.username && <p role="alert">{error.data.username.join(' ')}</p>}
                    <label>
                        Пароль:
                        <input name="password" value={password} type="password" required autoComplete="new-password"
                            onChange={e => setPassword(e.target.value)} />
                    </label>
                    {error?.data?.password && <p role="alert">{error.data.password.join(' ')}</p>}
                    <label>
                        Повтор пароля:
                        <input name="password_confirm" value={passwordConfirm} type="password" required autoComplete="new-password"
                            onChange={e => setPasswordConfirm(e.target.value)} />
                    </label>
                    {/* Ключ ошибки совпадает с полем API: password_confirm. */}
                    {error?.data?.password_confirm && <p role="alert">{error.data.password_confirm.join(' ')}</p>}
                    <button type="submit">{loading ? 'Регистрируем…' : 'Зарегистрироваться'}</button>
                </fieldset>
            </form>
        </div>
    );
}

export default RegisterForm;
