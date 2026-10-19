import { defineStore } from "pinia";
import { ref } from "vue";
import axios from "axios";

function emptyUser() {
    return {
        is_authenticated: false,
        username: null,
        is_staff: false,
        credits: 0,
        garage_slots: 0,
        second: false,
        crewman_id: null
    };
}

export const useUserStore = defineStore("userStore", () => {
    const userInfo = ref(emptyUser());

    async function checkLogin() {
        const r = await axios.get("/api/user/info/");
        userInfo.value = Object.assign({}, emptyUser(), r.data);
    }

    async function login(username, password) {
        await axios.post("/api/user/login/", { username, password });
        await checkLogin();
    }

    async function register(username, password, email) {
        await axios.post("/api/crewman/register/", { username, password, email });
        await checkLogin();
    }

    async function logout() {
        await axios.post("/api/user/logout/");
        userInfo.value = emptyUser();
    }

    async function expandGarage() {
        await axios.post("/api/crewman/expand-garage/");
        await checkLogin();
    }

    return { userInfo, checkLogin, login, register, logout, expandGarage };
});
