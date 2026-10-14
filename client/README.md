2. Скачать проект

powershell
cd "D:\Projects"          # любая папка
git clone https://github.com/ВАШ_ЛОГИН/ВАШ_РЕПОЗИТОРИЙ.git
cd ВАШ_РЕПОЗИТОРИЙ

3. Бэкенд

powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py test tanks
Если Activate.ps1 не запускается из-за политики выполнения скриптов, выполните один раз Set-ExecutionPolicy -Scope CurrentUser RemoteSigned.
После создания .venv не переносите и не переименовывайте папку проекта: именно это сломало pytest у вас. Если всё же перенесли, удалите .venv и повторите этот шаг.

4. Тестовые данные (если база пустая)

powershell
python manage.py generate_data --users 20 --tanks 60 --battles 200

У сгенерированных игроков логины user_1, user_2… и пароль testpass123. Без параметров команда создаст 250 игроков, 1500 танков и 5000 боёв.

5. Фронтенд

powershell
cd client
npm ci

npm ci ставит пакеты строго по package-lock.json, поэтому версии будут те же, что у вас сейчас.

6. Запуск (два терминала)

powershell
# терминал 1, корень проекта, с активированным .venv
python manage.py runserver

# терминал 2
cd client
npm run dev

Откройте http://localhost:5173.

7. 2FA для админа
Войдите под суперпользователем, нажмите «🔐 2FA» и отсканируйте QR-код в приложении-аутентификаторе. На новой базе ключ новый, поэтому привязку нужно сделать заново: старая запись в приложении работать не будет.

Если после изменений снова потянете проект на этот компьютер командой git pull, повторите три команды:

python -m pip install -r requirements.txt;
python manage.py migrate;
npm ci в папке client.