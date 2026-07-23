# PowerShell script to deploy VPS Monitor to remote server
$SSH_KEY = "$env:USERPROFILE\.ssh\kurrsator_key"
$VPS_HOST = "antigravity@45.150.192.62"

Write-Host "📦 Создание папки /opt/vps-monitor на VPS..." -ForegroundColor Cyan
ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new $VPS_HOST "sudo mkdir -p /opt/vps-monitor && sudo chown -R antigravity:antigravity /opt/vps-monitor"

Write-Host "📤 Копирование файлов бота на VPS..." -ForegroundColor Cyan
scp -i $SSH_KEY f:\Vibecoding\Antigravity\execution\vps_monitor.py "${VPS_HOST}:/opt/vps-monitor/"
scp -i $SSH_KEY f:\Vibecoding\Antigravity\execution\config.json "${VPS_HOST}:/opt/vps-monitor/"
scp -i $SSH_KEY f:\Vibecoding\Antigravity\execution\vps-monitor.service "${VPS_HOST}:/tmp/"

Write-Host "⚙️ Настройка systemd службы..." -ForegroundColor Cyan
ssh -i $SSH_KEY $VPS_HOST "sudo cp /tmp/vps-monitor.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now vps-monitor"

Write-Host "✅ Развёртывание завершено! Проверка статуса службы:" -ForegroundColor Green
ssh -i $SSH_KEY $VPS_HOST "sudo systemctl status vps-monitor --no-pager"
