<script setup>
import axios from 'axios';
import { ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const router = useRouter();

const loginForm = ref({ username: '', password: '' });
const registerForm = ref({ username: '', email: '', password: '', password2: '' });
const qrcodeUrl = ref('');
const twoFACode = ref('');

async function onLogin() {
    try {
        await userStore.login(loginForm.value.username, loginForm.value.password);
        loginForm.value = { username: '', password: '' };
    } catch (error) {
        alert('Неверное имя пользователя или пароль');
    }
}

async function onRegister() {
    if (registerForm.value.password !== registerForm.value.password2) {
        alert('Пароли не совпадают');
        return;
    }
    try {
        await userStore.register(registerForm.value.username, registerForm.value.password, registerForm.value.email);
        registerForm.value = { username: '', email: '', password: '', password2: '' };
    } catch (error) {
        alert(error.response.data.error);
    }
}

async function onLogout() {
    await userStore.logout();
    tanksStore.resetStore();
    router.push('/');
}

async function onOpen2FA() {
    const r = await axios.get('/api/user/get-totp/');
    if (r.data.url) {
        const QRCode = (await import('qrcode')).default;
        qrcodeUrl.value = await QRCode.toDataURL(r.data.url);
    } else {
        qrcodeUrl.value = '';
    }
}

async function onCheck2FA() {
    try {
        await axios.post('/api/user/second-login/', { key: twoFACode.value });
        await userStore.checkLogin();
        twoFACode.value = '';
    } catch (error) {
        alert('Неверный код');
    }
}
</script>

<template>
    <nav class="navbar navbar-expand navbar-dark bg-dark mb-4">
        <div class="container">
            <ul class="navbar-nav me-auto">
                <template v-if="userInfo.is_authenticated">
                    <li class="nav-item"><router-link class="nav-link" to="/">Ангар</router-link></li>
                    <li class="nav-item"><router-link class="nav-link" to="/tanks">Создать танк</router-link></li>
                    <li class="nav-item"><router-link class="nav-link" to="/battles">Сражения</router-link></li>
                    <li class="nav-item"><router-link class="nav-link" to="/battle-history">История</router-link></li>
                </template>
                <template v-if="userInfo.is_staff">
                    <li class="nav-item"><router-link class="nav-link" to="/levels">Уровни</router-link></li>
                    <li class="nav-item"><router-link class="nav-link" to="/nations">Нации</router-link></li>
                    <li class="nav-item"><router-link class="nav-link" to="/stats">Статистика</router-link></li>
                </template>
                <li class="nav-item" v-if="userInfo.is_staff && userInfo.second">
                    <router-link class="nav-link" to="/crewmen">Пользователи</router-link>
                </li>
            </ul>
            <ul class="navbar-nav">
                <template v-if="!userInfo.is_authenticated">
                    <li class="nav-item">
                        <button class="btn btn-primary me-2" data-bs-toggle="modal" data-bs-target="#loginModal">Вход</button>
                    </li>
                    <li class="nav-item">
                        <button class="btn btn-success" data-bs-toggle="modal" data-bs-target="#registerModal">Регистрация</button>
                    </li>
                </template>
                <template v-else>
                    <li class="nav-item" v-if="userInfo.is_staff && !userInfo.second">
                        <button class="btn btn-warning me-2" data-bs-toggle="modal" data-bs-target="#twoFAModal" @click="onOpen2FA">2FA</button>
                    </li>
                    <li class="nav-item" v-if="userInfo.second">
                        <span class="navbar-text me-3">2FA пройдена</span>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">{{ userInfo.username }}</a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li v-if="userInfo.is_staff"><a class="dropdown-item" href="/admin">Админка</a></li>
                            <li><a class="dropdown-item" href="#" @click.prevent="onLogout">Выйти</a></li>
                        </ul>
                    </li>
                </template>
            </ul>
        </div>
    </nav>

    <div class="container">
        <router-view />
    </div>

    <div class="modal" id="loginModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Вход</h5>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Имя пользователя</label>
                        <input type="text" class="form-control" v-model="loginForm.username">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Пароль</label>
                        <input type="password" class="form-control" v-model="loginForm.password">
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button class="btn btn-primary" data-bs-dismiss="modal" @click="onLogin">Войти</button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="registerModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Регистрация</h5>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Имя пользователя</label>
                        <input type="text" class="form-control" v-model="registerForm.username">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-control" v-model="registerForm.email">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Пароль</label>
                        <input type="password" class="form-control" v-model="registerForm.password">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Повторите пароль</label>
                        <input type="password" class="form-control" v-model="registerForm.password2">
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button class="btn btn-success" data-bs-dismiss="modal" @click="onRegister">Зарегистрироваться</button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="twoFAModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Двухфакторная аутентификация</h5>
                </div>
                <div class="modal-body">
                    <div v-if="qrcodeUrl" class="text-center mb-3">
                        <p>Отсканируйте QR-код в приложении-аутентификаторе</p>
                        <img :src="qrcodeUrl">
                    </div>
                    <label class="form-label">Код из приложения</label>
                    <input type="text" class="form-control" v-model="twoFACode">
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button class="btn btn-warning" data-bs-dismiss="modal" @click="onCheck2FA">Подтвердить</button>
                </div>
            </div>
        </div>
    </div>
</template>
