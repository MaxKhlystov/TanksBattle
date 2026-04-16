<script setup>
import { ref } from 'vue';

const show = ref(false);
const currentImage = ref('');

function open(imageUrl) {
    if (!imageUrl) return;
    currentImage.value = imageUrl;
    show.value = true;
}

function close() {
    show.value = false;
    currentImage.value = '';
}

defineExpose({ open });
</script>

<template>
    <div v-if="show" class="modal-overlay" @click.self="close">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Просмотр изображения</h5>
                    <button class="close-btn" @click="close">&times;</button>
                </div>
                <div class="custom-modal-body text-center">
                    <img :src="currentImage" style="max-width: 100%; max-height: 70vh; border-radius: 10px;">
                </div>
            </div>
        </div>
    </div>
</template>