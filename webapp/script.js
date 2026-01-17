let tg = window.Telegram.WebApp;

tg.expand();
tg.MainButton.textColor = '#FFFFFF';
tg.MainButton.color = '#6c5ce7';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Default to tasks
    switchTab('tasks', 'Задачи');
});

// Tab Switching
function switchTab(tabId, title) {
    // Update headers
    document.getElementById('page-title').innerText = title;

    // Update Tab Content
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');

    // Update Bottom Nav
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    // Find nav item by index/class - simple approach:
    const navItems = document.querySelectorAll('.nav-item');
    if (tabId === 'tasks') navItems[0].classList.add('active');
    if (tabId === 'habits') navItems[1].classList.add('active');
    if (tabId === 'settings') navItems[2].classList.add('active');
}

// Actions
function sendTask() {
    const text = document.getElementById('taskInput').value.trim();
    if (!text) return;

    sendData({
        action: "add_task",
        text: text
    });
}

function sendHabit() {
    const text = document.getElementById('habitInput').value.trim();
    const time = document.getElementById('habitTimeInput').value;
    if (!text) return;

    sendData({
        action: "add_habit",
        text: text,
        time: time
    });
}

function saveCity() {
    const city = document.getElementById('cityInput').value.trim();
    if (!city) return;

    sendData({
        action: "update_city",
        city: city
    });
}

function saveCity2() {
    const city = document.getElementById('cityInput2').value.trim();
    if (!city) return;

    sendData({
        action: "update_city_2",
        city: city
    });
}

function sendAction(actionName) {
    if (actionName === 'stop_userbot') {
        tg.showConfirm("Вы точно хотите отключить UserBot?", (confirmed) => {
            if (confirmed) {
                sendData({ action: actionName });
            }
        });
    } else {
        sendData({ action: actionName });
    }
}

// Helper to send data
function sendData(data) {
    tg.sendData(JSON.stringify(data));
    // Telegram automatically parses this and closes the WebApp.
    // If we want to keep it open, we must use CloudStorage or external API,
    // which is not possible with GitHub Pages + Local Bot setup.
    // So we just let it accept the data.
}
