import Swal from 'sweetalert2'

// Общее оформление всех всплывающих окон приложения
const theme = { background: '#2c3e50', color: '#fff' }

export const showSuccess = (title, message = '') => {
    Swal.fire({
        ...theme,
        icon: 'success',
        title: title,
        text: message,
        timer: 2000,
        showConfirmButton: false,
        iconColor: '#28a745'
    })
}

export const showError = (title, message = '') => {
    Swal.fire({
        ...theme,
        icon: 'error',
        title: title,
        text: message,
        iconColor: '#dc3545'
    })
}

// Окно подтверждения; возвращает true, если пользователь нажал «Да»
export const showConfirm = async (title, message = '', confirmText = 'Да, удалить') => {
    const result = await Swal.fire({
        ...theme,
        icon: 'warning',
        title: title,
        text: message,
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: confirmText,
        cancelButtonText: 'Отмена'
    })
    return result.isConfirmed
}

// Текст ошибки из ответа API: {"error": ...}, ошибки полей DRF ({"name": [...]}) или {"detail": ...}
export const getErrorMessage = (error, fallback = 'Произошла ошибка') => {
    const data = error?.response?.data
    if (!data || typeof data !== 'object') return fallback
    if (data.error) return data.error
    if (data.detail) return data.detail
    const firstField = Object.values(data).find(v => Array.isArray(v) && v.length)
    return firstField ? firstField[0] : fallback
}
