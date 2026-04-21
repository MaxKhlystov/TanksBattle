<script setup>
import axios from 'axios';
import Cookies from 'js-cookie';
import { onBeforeMount, ref, provide } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import ImageViewer from '@/views/ImageViewer.vue';
import { showSuccess, showError, showInfo } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);

const showNav = ref(false);
const showDropdown = ref(false);
const showLoginModal = ref(false);
const showRegisterModal = ref(false);
const show2FAModal = ref(false);
const twoFACode = ref('');
const qrcodeUrl = ref('');
const totpUrl = ref('');

const loginUsername = ref('');
const loginPassword = ref('');
const loginError = ref('');

const regUsername = ref('');
const regEmail = ref('');
const regPassword = ref('');
const regConfirmPassword = ref('');
const regError = ref('');

const imageViewer = ref(null);

provide('openImageViewer', (url) => {
    if (imageViewer.value) imageViewer.value.open(url);
});

async function getTotpKey() {
    try {
        let r = await axios.get('/api/user/get-totp/');
        totpUrl.value = r.data.url;
        const QRCode = (await import('qrcode')).default;
        qrcodeUrl.value = await QRCode.toDataURL(totpUrl.value);
        show2FAModal.value = true;
    } catch (error) {
        console.error(error);
        alert('Ошибка получения QR-кода');
    }
}

async function verify2FA() {
    try {
        await axios.post('/api/user/second-login/', { key: twoFACode.value });
        await userStore.checkLogin();
        twoFACode.value = '';
        showSuccess('2FA активирована', 'Двухфакторная аутентификация успешно включена');
    } catch (error) {
        showError('Ошибка', 'Неверный код');
    }
    show2FAModal.value = false;
}

// В handleLogin после успешного входа
async function handleLogin() {
    loginError.value = '';
    try {
        await userStore.login(loginUsername.value, loginPassword.value);
        if (userInfo.value.is_authenticated) {
            showLoginModal.value = false;
            loginUsername.value = '';
            loginPassword.value = '';
            
            // 👇 Принудительно обновляем данные ангара и пользователя
            await tanksStore.fetchMyTanks();
            await tanksStore.fetchLevels();
            await tanksStore.fetchNations();
            await tanksStore.fetchBattles();
            if (userInfo.value.is_staff && userInfo.value.second) {
                await tanksStore.fetchAllCrewmen();
            }
            // Обновляем CSRF-токен (см. пункт 15)
            const csrfToken = Cookies.get("csrftoken");
            if (csrfToken) {
                axios.defaults.headers.common['X-CSRFToken'] = csrfToken;
            }
        }
    } catch (error) {
        loginError.value = 'Неверное имя пользователя или пароль';
    }
}

async function handleRegister() {
    regError.value = '';
    if (regPassword.value !== regConfirmPassword.value) {
        regError.value = 'Пароли не совпадают';
        return;
    }
    if (regPassword.value.length < 6) {
        regError.value = 'Пароль должен быть не менее 6 символов';
        return;
    }
    try {
        await userStore.register(regUsername.value, regPassword.value, regEmail.value);
        if (userInfo.value.is_authenticated) {
            showRegisterModal.value = false;
            regUsername.value = '';
            regEmail.value = '';
            regPassword.value = '';
            regConfirmPassword.value = '';
        }
    } catch (error) {
        regError.value = error.response?.data?.error || 'Ошибка регистрации';
    }
}

// В handleLogout убираем лишнее и вызываем сброс стора
async function handleLogout() {
    try {
        await axios.post('/api/user/logout-2fa/');
    } catch (error) {
        console.error('Error resetting 2FA:', error);
    }
    await userStore.logout();
    tanksStore.resetStore();           // очищаем все данные
    sessionStorage.removeItem('selectedUserId');
    showDropdown.value = false;
    // 👇 Принудительно переходим на главную и обновляем состояние
    await router.push('/');
    // Не делаем перезагрузку страницы, чтобы сохранить SPA-поведение
}

onBeforeMount(async () => {
    axios.defaults.withCredentials = true;
    
    try {
        await axios.get('/api/nations/');
    } catch (e) {}
    
    const csrfToken = Cookies.get("csrftoken");
    if (csrfToken) {
        axios.defaults.headers.common['X-CSRFToken'] = csrfToken;
    }
    
    userStore.checkLogin();
    tanksStore.fetchNations();
    tanksStore.fetchLevels();
});
</script>

<template>
    <nav class="custom-navbar">
        <div class="custom-container">
            <div class="navbar-content">
                <button class="navbar-toggler" @click="showNav = !showNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="navbar-links" :class="{ show: showNav }">
                    <ul class="nav-list">
                        <li v-if="userInfo && userInfo.is_authenticated">
                            <router-link class="nav-link" to="/">Ангар</router-link>
                        </li>
                        <li v-if="userInfo && userInfo.is_authenticated">
                            <router-link class="nav-link" to="/tanks">Создать танк</router-link>
                        </li>
                        <li v-if="userInfo && userInfo.is_authenticated">
                            <router-link class="nav-link" to="/battles">Сражения</router-link>
                        </li>
                        <li v-if="userInfo && userInfo.is_authenticated">
                            <router-link class="nav-link" to="/battle-history">История</router-link>
                        </li>
                        <li v-if="userInfo.is_staff">
                            <router-link class="nav-link" to="/levels">Уровни</router-link>
                        </li>
                        <li v-if="userInfo.is_staff">
                            <router-link class="nav-link" to="/nations">Нации</router-link>
                        </li>
                        <li v-if="userInfo.is_staff">
                            <router-link class="nav-link" to="/stats">Статистика</router-link>
                        </li>
                        <li v-if="userInfo.is_staff && userInfo.second">
                            <router-link class="nav-link" to="/crewmen">Пользователи</router-link>
                        </li>
                    </ul>
                    <ul class="nav-list ms-auto">
                        <li v-if="userInfo && userInfo.is_authenticated && userInfo.is_staff && !userInfo.second">
                            <button class="btn-custom-warning" @click="getTotpKey">
                                🔐 2FA
                            </button>
                        </li>
                        <li v-if="userInfo && userInfo.is_authenticated && userInfo.second">
                            <span class="badge-2fa-active">2FA</span>
                        </li>
                        <li v-if="!userInfo || !userInfo.is_authenticated">
                            <button class="btn-custom-primary" @click="showLoginModal = true">Вход</button>
                        </li>
                        <li v-if="!userInfo || !userInfo.is_authenticated">
                            <button class="btn-custom-danger" @click="showRegisterModal = true">Регистрация</button>
                        </li>
                        <li class="dropdown" v-if="userInfo && userInfo.is_authenticated">
                            <a class="nav-link dropdown-toggle" href="#" @click.prevent="showDropdown = !showDropdown">
                                {{ userInfo.username }}
                            </a>
                            <ul class="dropdown-menu-custom" v-if="showDropdown">
                                <li><a href="/admin">Админка</a></li>
                                <li><hr style="margin: 5px 0;"></li>
                                <li><a href="#" @click="handleLogout">Выйти</a></li>
                            </ul>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </nav>

    <div class="custom-container main-content">
        <router-view />
    </div>
    <div class="bg__own"></div>

    <ImageViewer ref="imageViewer" />

    <!-- Модальное окно входа -->
    <div v-if="showLoginModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Вход в аккаунт</h5>
                    <button class="close-btn" @click="showLoginModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <div class="form-group">
                        <label>Имя пользователя</label>
                        <input type="text" class="custom-form-control" v-model="loginUsername">
                    </div>
                    <div class="form-group">
                        <label>Пароль</label>
                        <input type="password" class="custom-form-control" v-model="loginPassword">
                    </div>
                    <div v-if="loginError" class="alert-custom-danger">{{ loginError }}</div>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showLoginModal = false">Отмена</button>
                    <button class="btn-custom-danger" @click="handleLogin">Войти</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно регистрации -->
    <div v-if="showRegisterModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Регистрация</h5>
                    <button class="close-btn" @click="showRegisterModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <div class="form-group">
                        <label>Имя пользователя</label>
                        <input type="text" class="custom-form-control" v-model="regUsername">
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" class="custom-form-control" v-model="regEmail">
                    </div>
                    <div class="form-group">
                        <label>Пароль</label>
                        <input type="password" class="custom-form-control" v-model="regPassword">
                    </div>
                    <div class="form-group">
                        <label>Подтвердите пароль</label>
                        <input type="password" class="custom-form-control" v-model="regConfirmPassword">
                    </div>
                    <div v-if="regError" class="alert-custom-danger">{{ regError }}</div>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showRegisterModal = false">Отмена</button>
                    <button class="btn-custom-success" @click="handleRegister">Зарегистрироваться</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно 2FA -->
    <div v-if="show2FAModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Двухфакторная аутентификация</h5>
                    <button class="close-btn" @click="show2FAModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <p>Отсканируйте QR-код в приложении (Google Authenticator, Яндекс Ключ и т.д.)</p>
                    <img v-if="qrcodeUrl" :src="qrcodeUrl" style="max-width: 100%; margin-bottom: 15px;">
                    <div class="form-group">
                        <label>Введите 6-значный код из приложения</label>
                        <input type="text" class="custom-form-control" v-model="twoFACode" placeholder="000000">
                    </div>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="show2FAModal = false">Отмена</button>
                    <button class="btn-custom-warning" @click="verify2FA", "show2FAModal = false>Активировать</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.badge-2fa-active {
    background-color: #28a745;
    color: white;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 14px;
    display: inline-block;
}

.main-content {
    margin-top: 30px;
}
</style>