import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import PasswordResetForm from './auth/PasswordResetForm.jsx';
import PasswordResetConfirmForm from './auth/PasswordResetConfirmForm.jsx';

// Прямой переход и обновление страницы выбирают экран по одному и тому же адресу.
const path = window.location.pathname;
const params = new URLSearchParams(window.location.search);
let page;

if (path === '/forgot-password') {
    page = <PasswordResetForm />;
} else if (path === '/reset-password') {
    // Эти значения приходят из письма. Пароли человек введёт в самой форме.
    page = <PasswordResetConfirmForm uid={params.get('uid')} token={params.get('token')} />;
} else {
    // После сброса заново монтируем App: он снова проверит реальную сессию через /me/.
    page = <App resetCompleted={path === '/login' && params.get('reset') === 'success'} />;
}

createRoot(document.getElementById('root')).render(
    <StrictMode>{page}</StrictMode>,
);
