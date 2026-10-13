import { useState } from 'react';
import { login } from '../api/client.js';
import AuthError from './AuthError.jsx';

function LoginForm({ onLogin, onPendingChange, onCheckSession }) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // App тоже знает об отправке: переключение форм во время запроса недоступно.
    function handlePending(pending) {
        setLoading(pending);
        onPendingChange(pending);
    }

    async function handleSubmit(e) {
        e.preventDefault();
        // Проверка перед try: ранний return не должен сбрасывать loading в finally.
        if (loading || error?.authenticatedUser) return;
        setError(null);
        handlePending(true);
        try {
            const data = await login({ email, password });
            setPassword('');
            onLogin(data);
        } catch (error) {
            setError(error);
            if (error.authenticatedUser) setPassword('');
        } finally {
            handlePending(false);
        }
    }

    return (
        <div>
            <AuthError
                error={error}
                fields={['email', 'password']}
                onClearError={() => setError(null)}
                onPendingChange={handlePending}
                onCheckSession={onCheckSession}
            />
            {/* onSubmit обрабатывает и кнопку, и Enter; fieldset блокирует все поля. */}
            <form onSubmit={handleSubmit}>
                <fieldset disabled={loading || Boolean(error?.authenticatedUser)}>
                    <legend>Вход</legend>
                    <label>
                        Email:
                        <input name="email" value={email} type="email" required autoComplete="username"
                            onChange={e => setEmail(e.target.value)} />
                    </label>
                    {/* Ответ сериализатора находится в error.data, а не error.detail. */}
                    {error?.data?.email && <p role="alert">{error.data.email.join(' ')}</p>}
                    <label>
                        Пароль:
                        <input name="password" value={password} type="password" required autoComplete="current-password"
                            onChange={e => setPassword(e.target.value)} />
                    </label>
                    {error?.data?.password && <p role="alert">{error.data.password.join(' ')}</p>}
                    <button type="submit">{loading ? 'Входим…' : 'Войти'}</button>
                </fieldset>
            </form>
            {/* Ссылка открывает форму frontend; к API форма обращается при отправке. */}
            <a href="/forgot-password">Забыли пароль?</a>
        </div>
    );
}

export default LoginForm;
