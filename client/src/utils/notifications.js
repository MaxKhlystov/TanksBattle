import Swal from 'sweetalert2'

export const showSuccess = (title, message = '') => {
    Swal.fire({
        icon: 'success',
        title: title,
        text: message,
        timer: 2000,
        showConfirmButton: false,
        background: '#2c3e50',
        color: '#fff',
        iconColor: '#28a745'
    })
}

export const showError = (title, message = '') => {
    Swal.fire({
        icon: 'error',
        title: title,
        text: message,
        background: '#2c3e50',
        color: '#fff',
        iconColor: '#dc3545'
    })
}

export const showInfo = (title, message = '') => {
    Swal.fire({
        icon: 'info',
        title: title,
        text: message,
        timer: 1500,
        showConfirmButton: false,
        background: '#2c3e50',
        color: '#fff'
    })
}