import { useState } from 'react';
import { requestPasswordReset } from '../api/client.js';
import AuthError from './AuthError.jsx';

function PasswordResetForm() {
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [message, setMessage] = useState('');

    async function handleSubmit(event) {
        event.preventDefault();
        if (loading) return;
        setError(null);
        setMessage('');
        setLoading(true);
        try {
            const data = await requestPasswordReset(email);
            // Сервер даёт одинаковый ответ для существующего и неизвестного email.
            setMessage(data.detail);
        } catch (error) {
            setError(error);
        } finally {
            setLoading(false);
        }
    }

    return (
        <>
            <h1>Восстановление пароля</h1>
            <p>Введите email аккаунта, чтобы запросить ссылку для смены пароля.</p>
            <AuthError error={error} fields={['email']}
                onClearError={() => setError(null)} onPendingChange={setLoading} />
            {message && <p role="status">{message}</p>}
            <form onSubmit={handleSubmit}>
                <fieldset disabled={loading}>
                    <legend>Запрос ссылки</legend>
                    <label>
                        Email:
                        <input name="email" value={email} type="email" required autoComplete="email"
                            onChange={event => setEmail(event.target.value)} />
                    </label>
                    {error?.data?.email && <p role="alert">{error.data.email.join(' ')}</p>}
                    <button type="submit">{loading ? 'Отправляем…' : 'Запросить ссылку'}</button>
                </fieldset>
            </form>
            <a href="/">Вернуться ко входу</a>
        </>
    );
}

export default PasswordResetForm;
