import { defineStore } from "pinia";
import { ref } from "vue";
import axios from "axios";

export const useUserStore = defineStore("userStore", () => {
    const userInfo = ref({
        is_authenticated: false,
        username: null,
        is_staff: false,
        credits: 0,
        garage_slots: 3,
        second: false
    });
    
    async function checkLogin() {
        try {
            let r = await axios.get("/api/user/info/");
            userInfo.value = r.data;
        } catch (error) {
            userInfo.value = {
                is_authenticated: false,
                username: null,
                is_staff: false,
                credits: 0,
                garage_slots: 3,
                second: false
            };
        }
    }
    
    async function login(username, password) {
        await axios.post("/api/user/login/", { username, password });
        await checkLogin();
    }
    
    async function register(username, password, email) {
        const response = await axios.post("/api/crewman/register/", {
            username, password, email
        });
        await checkLogin();  
        return response.data;
}
    
    async function logout() {
        try {
            await axios.post("/api/user/logout/");
        } catch (error) {
            console.error("Logout error:", error);
        } finally {
            userInfo.value = {
                is_authenticated: false,
                username: null,
                is_staff: false,
                credits: 0,
                garage_slots: 3,
                second: false
            };
        }
    }
    
    async function expandGarage() {
        const response = await axios.post("/api/crewman/expand-garage/");
        await checkLogin();
        return response.data;
    }
    
    return {
        userInfo,
        checkLogin,
        login,
        register,
        logout,
        expandGarage
    };
});