#!/usr/bin/env python3
"""
VPS Sentinel & Telegram Monitor Bot (V7 User Management & Role Control)
Администратор (1447443197) имеет право:
- Управлять пользователями через кнопки / команды (/users, /add <id>, /del <id>).
- Видеть все сервисы и получать алерты по всем группам.
Остальные пользователи видят строго разрешённые группы (Партнёрка + ЦЖ).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import subprocess
import threading
import socket
from datetime import datetime

# Безопасная кодировка для stdout/stderr
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
STATE_PATH = os.path.join(SCRIPT_DIR, "state.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Ошибка: Файл конфигурации {CONFIG_PATH} не найден!")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения config.json: {e}")

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.token = config["telegram"]["bot_token"]
        self.allowed_chat_ids = config["telegram"]["allowed_chat_ids"]
        self.admin_chat_ids = config["telegram"].get("admin_chat_ids", [1447443197])
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def reload_users(self, config):
        self.config = config
        self.allowed_chat_ids = config["telegram"]["allowed_chat_ids"]
        self.admin_chat_ids = config["telegram"].get("admin_chat_ids", [1447443197])

    def is_admin(self, chat_id):
        return chat_id in self.admin_chat_ids

    def send_message(self, chat_id, text, reply_markup=None):
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Telegram Send Error ({chat_id}): {e}")
            return None

    def broadcast(self, text, reply_markup=None, admin_only=False):
        results = []
        target_ids = self.admin_chat_ids if admin_only else self.allowed_chat_ids
        for chat_id in target_ids:
            res = self.send_message(chat_id, text, reply_markup=reply_markup)
            results.append((chat_id, res))
        return results

    def answer_callback_query(self, callback_query_id, text=""):
        url = f"{self.base_url}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id, "text": text}
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

    def get_updates(self, offset=0):
        url = f"{self.base_url}/getUpdates?offset={offset}&timeout=20"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
        except Exception:
            pass
        return []

class VPSMonitor:
    def __init__(self, config):
        self.config = config

    def reload_config(self, config):
        self.config = config

    def get_system_resources(self):
        res = {"cpu": 0.0, "ram_total": 0, "ram_used": 0, "ram_percent": 0.0, "disks": []}
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
                mem = {}
                for line in lines:
                    parts = line.split(":")
                    if len(parts) == 2:
                        mem[parts[0].strip()] = int(parts[1].strip().split()[0])
                total = mem.get("MemTotal", 1)
                avail = mem.get("MemAvailable", mem.get("MemFree", 0))
                used = total - avail
                res["ram_total"] = round(total / 1048576, 1)
                res["ram_used"] = round(used / 1048576, 1)
                res["ram_percent"] = round((used / total) * 100, 1)
        except Exception:
            pass

        try:
            with open("/proc/loadavg", "r") as f:
                res["cpu"] = float(f.read().split()[0])
        except Exception:
            pass

        try:
            out = subprocess.check_output(["df", "-h", "/"], text=True)
            lines = out.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                res["disks"].append({
                    "mount": "/", "size": parts[1], "used": parts[2], "avail": parts[3], "percent": parts[4]
                })
        except Exception:
            pass

        return res

    def format_vps_info_report(self):
        sys_res = self.get_system_resources()
        ram_p = sys_res['ram_percent']
        ram_mark = "[Внимание]" if ram_p > 85 else "[Ок]"

        lines = [
            "<b>Инфо о VPS (ресурсы сервера)</b>",
            f"Время: <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
            f"ОЗУ (RAM): <b>{sys_res['ram_used']} GB</b> из {sys_res['ram_total']} GB ({ram_p}%) {ram_mark}"
        ]
        if sys_res["disks"]:
            d = sys_res["disks"][0]
            lines.append(f"Диск ({d['mount']}): <b>{d['used']}</b> из {d['size']} ({d['percent']})")
        lines.append(f"Нагрузка CPU: <b>{sys_res['cpu']}</b>")

        return "\n".join(lines)

    def get_pm2_processes(self):
        pm2_list = {}
        try:
            out = subprocess.check_output(["pm2", "jlist"], text=True, stderr=subprocess.DEVNULL)
            data = json.loads(out)
            for proc in data:
                name = proc.get("name")
                status = proc.get("pm2_env", {}).get("status", "stopped")
                pm2_list[name] = (status == "online")
        except Exception:
            pass
        return pm2_list

    def get_ps_aux_output(self):
        try:
            return subprocess.check_output(["ps", "aux"], text=True)
        except Exception:
            return ""

    def check_tcp_port(self, host, port, timeout=2):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def check_service_status(self, service_id):
        pm2_procs = self.get_pm2_processes()
        ps_output = self.get_ps_aux_output()

        if service_id == "cabinet-backend":
            is_pm2_ok = pm2_procs.get("cabinet-backend", False)
            is_port_ok = self.check_tcp_port("127.0.0.1", 3000)
            return (is_pm2_ok or is_port_ok), "работает" if (is_pm2_ok or is_port_ok) else "остановлен"

        elif service_id == "partner_frontend":
            is_port_ok = self.check_tcp_port("127.0.0.1", 80)
            is_ps_ok = "nginx: worker process" in ps_output or "nginx: master process" in ps_output
            return (is_port_ok or is_ps_ok), "работает" if (is_port_ok or is_ps_ok) else "остановлен"

        elif service_id == "postgres":
            is_port_ok = self.check_tcp_port("127.0.0.1", 5432)
            is_ps_ok = "postgres" in ps_output
            return (is_port_ok or is_ps_ok), "работает" if (is_port_ok or is_ps_ok) else "остановлен"

        elif service_id == "evgeniy_bot":
            is_ok = "telegram_bot" in ps_output or "/home/evgeniy" in ps_output
            return is_ok, "работает" if is_ok else "остановлен"

        elif service_id == "kurrsator_bot":
            is_ok = "kurrsator_bot.py" in ps_output
            return is_ok, "работает" if is_ok else "остановлен"

        elif service_id == "main_bot":
            is_ok = ("main.py" in ps_output) and ("botuser" in ps_output or "Kurrsator" in ps_output)
            return is_ok, "работает" if is_ok else "остановлен"

        elif service_id == "app_venv_bot":
            is_ok = "/app/venv" in ps_output or "transutka" in ps_output
            return is_ok, "работает" if is_ok else "остановлен"

        is_pm2 = pm2_procs.get(service_id, False)
        is_ps = service_id in ps_output
        is_ok = is_pm2 or is_ps
        return is_ok, "работает" if is_ok else "остановлен"

    def restart_service(self, service_id):
        if service_id == "cabinet-backend":
            try:
                out = subprocess.check_output(["pm2", "restart", "cabinet-backend"], text=True)
                return True, f"PM2: {out.strip()}"
            except Exception as e:
                return False, str(e)
        elif service_id == "partner_frontend":
            try:
                out = subprocess.check_output(["sudo", "systemctl", "restart", "nginx"], text=True)
                return True, f"Nginx: {out.strip()}"
            except Exception as e:
                return False, str(e)
        else:
            try:
                out = subprocess.check_output(["pm2", "restart", service_id], text=True)
                return True, f"PM2: {out.strip()}"
            except Exception:
                return False, f"Ошибка перезапуска {service_id}"

    def restart_group(self, group_id):
        group = next((g for g in self.config.get("groups", []) if g["id"] == group_id), None)
        if not group:
            return False, "Группа не найдена"
        
        log_msgs = []
        all_ok = True
        for s in group["services"]:
            ok, msg = self.restart_service(s["id"])
            log_msgs.append(f"• {s['name']}: {'успешно' if ok else 'ошибка'}")
            if not ok:
                all_ok = False
        return all_ok, "\n".join(log_msgs)

    def get_groups_info(self, is_admin=False):
        result = {}
        for g in self.config.get("groups", []):
            gid = g["id"]
            admin_only = g.get("admin_only", False)
            
            if admin_only and not is_admin:
                continue

            gname = g["name"]
            auto_restart = g.get("auto_restart", False)
            
            services_info = []
            group_all_ok = True
            
            for s in g["services"]:
                sid = s["id"]
                sname = s["name"]
                is_running, status_text = self.check_service_status(sid)
                if not is_running:
                    group_all_ok = False
                services_info.append({
                    "id": sid,
                    "name": sname,
                    "is_running": is_running,
                    "status_text": status_text
                })

            result[gid] = {
                "id": gid,
                "name": gname,
                "is_running": group_all_ok,
                "auto_restart": auto_restart,
                "admin_only": admin_only,
                "services": services_info
            }
        return result

    def format_all_status_report(self, is_admin=False):
        groups = self.get_groups_info(is_admin=is_admin)
        lines = [f"<b>Отчет о состоянии всех сервисов</b>\nВремя: <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n"]

        for gid, ginfo in groups.items():
            g_mark = "[Ок]" if ginfo["is_running"] else "[Сбой]"
            lines.append(f"{g_mark} <b>{ginfo['name']}</b>")
            for s in ginfo["services"]:
                s_mark = "  ├ [Ок]" if s["is_running"] else "  ├ [Сбой]"
                lines.append(f"{s_mark} {s['name']} (<i>{s['status_text']}</i>)")
            lines.append("")

        return "\n".join(lines)

    def format_group_report(self, group_key, is_admin=False):
        groups = self.get_groups_info(is_admin=is_admin)
        if group_key not in groups:
            return f"Группа <code>{group_key}</code> не найдена или доступ ограничен.", None

        g = groups[group_key]
        status_text = "[Ок] Все компоненты работают" if g["is_running"] else "[Сбой] Есть остановленные компоненты"
        auto_rest_text = "Включен" if g.get("auto_restart") else "Выключен"
        
        lines = [
            f"<b>{g['name']}</b>",
            f"----------------------------------",
            f"Состояние группы: {status_text}",
            f"Авто-восстановление: <i>{auto_rest_text}</i>\n",
            f"<b>Компоненты группы:</b>"
        ]

        for s in g["services"]:
            s_mark = "[Ок]" if s["is_running"] else "[Сбой]"
            lines.append(f"  • {s_mark} <b>{s['name']}</b>: <i>{s['status_text']}</i>")
            
        lines.append(f"\nВремя проверки: {datetime.now().strftime('%H:%M:%S')}")
        
        kb = {
            "inline_keyboard": [
                [{"text": f"Перезапустить {g['name']}", "callback_data": f"rst_g:{g['id']}"}],
                [{"text": "Назад к списку", "callback_data": "chk_back"}]
            ]
        }
        return "\n".join(lines), kb

def make_inline_keyboard_for_containers(monitor, is_admin=False):
    groups = monitor.get_groups_info(is_admin=is_admin)
    keyboard = [[{"text": "Проверить все сервисы", "callback_data": "chk_all"}]]
    
    row = []
    for gid, info in groups.items():
        mark = "[Ок]" if info["is_running"] else "[Сбой]"
        btn_text = f"{mark} {info['name']}"
        row.append({"text": btn_text, "callback_data": f"chk_g:{gid}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    return {"inline_keyboard": keyboard}

def make_main_reply_keyboard(is_admin=False):
    kb = [
        [{"text": "Проверить состояние"}],
        [{"text": "Инфо о VPS"}]
    ]
    if is_admin:
        kb.append([{"text": "Пользователи бота"}])
    return {"keyboard": kb, "resize_keyboard": True}

def make_user_management_keyboard(config):
    users = config["telegram"]["allowed_chat_ids"]
    admins = config["telegram"].get("admin_chat_ids", [1447443197])
    
    keyboard = []
    for u in users:
        is_adm = u in admins
        role_mark = "(Админ)" if is_adm else ""
        if not is_adm:
            keyboard.append([{"text": f"Удалить ID: {u} {role_mark}", "callback_data": f"del_u:{u}"}])
        else:
            keyboard.append([{"text": f"Главный Админ ID: {u}", "callback_data": "none"}])
            
    return {"inline_keyboard": keyboard}

def background_watchdog(config, bot, monitor):
    print("Фоновый мониторинг запущен...")
    interval = config.get("settings", {}).get("check_interval_seconds", 30)
    hourly_digest = config.get("settings", {}).get("hourly_digest", True)
    
    last_hourly_sent = 0

    while True:
        try:
            state = load_state()
            groups = monitor.get_groups_info(is_admin=True)
            now_ts = time.time()

            if hourly_digest and (now_ts - last_hourly_sent >= 3500):
                current_min = datetime.now().minute
                if current_min == 0:
                    admin_report = monitor.format_all_status_report(is_admin=True)
                    bot.broadcast(f"<b>Почасовой отчет VPS</b>\n\n{admin_report}", admin_only=True)
                    
                    user_report = monitor.format_all_status_report(is_admin=False)
                    for uid in bot.allowed_chat_ids:
                        if uid not in bot.admin_chat_ids:
                            bot.send_message(uid, f"<b>Почасовой отчет VPS</b>\n\n{user_report}")
                            
                    last_hourly_sent = now_ts

            for gid, info in groups.items():
                prev_running = state.get(gid, {}).get("is_running", True)
                curr_running = info["is_running"]
                custom_name = info["name"]
                auto_restart = info.get("auto_restart", False)
                admin_only = info.get("admin_only", False)
                
                if prev_running and not curr_running:
                    alert_msg = (
                        f"<b>Внимание! Сбой в группе {custom_name}!</b>\n\n"
                        f"Компоненты со сбоем выявлены в {custom_name}.\n"
                        f"Время: {datetime.now().strftime('%H:%M:%S')}"
                    )
                    kb = {
                        "inline_keyboard": [[
                            {"text": f"Перезапустить {custom_name}", "callback_data": f"rst_g:{gid}"}
                        ]]
                    }
                    bot.broadcast(alert_msg, reply_markup=kb, admin_only=admin_only)

                    if auto_restart:
                        bot.broadcast(f"<i>Попытка авто-восстановления группы {custom_name}...</i>", admin_only=admin_only)
                        ok, rst_msg = monitor.restart_group(gid)
                        if ok:
                            bot.broadcast(f"<b>Авто-восстановление успешно:</b> Группа {custom_name} перезапущена.", admin_only=admin_only)
                            curr_running = True
                        else:
                            bot.broadcast(f"<b>Результаты авто-восстановления:</b>\n{rst_msg}", admin_only=admin_only)

                elif not prev_running and curr_running:
                    bot.broadcast(f"<b>Группа восстановлена:</b> <b>{custom_name}</b> работает штатно.", admin_only=admin_only)

                state[gid] = {
                    "is_running": curr_running,
                    "last_check": datetime.now().isoformat()
                }

            save_state(state)
        except Exception as e:
            print(f"Ошибка в watchdog: {e}")

        time.sleep(interval)

def main():
    config = load_config()
    bot = TelegramBot(config)
    monitor = VPSMonitor(config)

    if "--test" in sys.argv:
        print(f"Рассылка тестового сообщения...")
        res_list = bot.broadcast("<b>VPS Sentinel подключен и работает!</b>", reply_markup=make_main_reply_keyboard(True))
        for cid, res in res_list:
            if res and res.get("ok"):
                print(f"  [ID: {cid}] Успешно доставлено")
            else:
                print(f"  [ID: {cid}] Ошибка доставки: {res}")
        return

    t = threading.Thread(target=background_watchdog, args=(config, bot, monitor), daemon=True)
    t.start()

    print("VPS Sentinel с управлением пользователями запущен...")
    offset = 0

    while True:
        try:
            updates = bot.get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                
                if "message" in u:
                    msg = u["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "").strip()
                    
                    if bot.allowed_chat_ids and chat_id not in bot.allowed_chat_ids:
                        bot.send_message(chat_id, "Доступ запрещен.")
                        continue

                    is_admin_user = bot.is_admin(chat_id)

                    if text == "/start":
                        welcome_text = (
                            f"<b>VPS Sentinel Monitoring Bot</b>\n\n"
                            f"• Нажмите <b>Проверить состояние</b> для просмотра сервисов\n"
                            f"• Нажмите <b>Инфо о VPS</b> для просмотра ресурсов сервера (ОЗУ/CPU/Диск)"
                        )
                        if is_admin_user:
                            welcome_text += "\n• Раздел <b>Пользователи бота</b> доступен для управления доступом."
                        bot.send_message(chat_id, welcome_text, reply_markup=make_main_reply_keyboard(is_admin_user))

                    elif text == "Инфо о VPS":
                        vps_report = monitor.format_vps_info_report()
                        bot.send_message(chat_id, vps_report, reply_markup=make_main_reply_keyboard(is_admin_user))

                    elif text == "Проверить состояние":
                        kb = make_inline_keyboard_for_containers(monitor, is_admin=is_admin_user)
                        bot.send_message(
                            chat_id,
                            "<b>Выберите группу сервисов или нажмите 'Проверить все сервисы':</b>",
                            reply_markup=kb
                        )

                    # --- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (ТОЛЬКО ДЛЯ АДМИНА) ---
                    elif is_admin_user and text in ["Пользователи бота", "/users"]:
                        kb = make_user_management_keyboard(config)
                        info_msg = (
                            "<b>Управление доступом пользователей</b>\n\n"
                            "Для добавления пользователя отправьте команду:\n"
                            "<code>/add 123456789</code>\n\n"
                            "Список текущих разрешенных ID:"
                        )
                        bot.send_message(chat_id, info_msg, reply_markup=kb)

                    elif is_admin_user and text.startswith("/add "):
                        try:
                            new_id = int(text.split("/add ")[1].strip())
                            if new_id not in config["telegram"]["allowed_chat_ids"]:
                                config["telegram"]["allowed_chat_ids"].append(new_id)
                                save_config(config)
                                bot.reload_users(config)
                                monitor.reload_config(config)
                                bot.send_message(chat_id, f"Пользователь <code>{new_id}</code> успешно добавлен!")
                            else:
                                bot.send_message(chat_id, f"Пользователь <code>{new_id}</code> уже в списке.")
                        except ValueError:
                            bot.send_message(chat_id, "Ошибка: Укажите числовой Chat ID. Пример: <code>/add 123456789</code>")

                    elif is_admin_user and text.startswith("/del "):
                        try:
                            del_id = int(text.split("/del ")[1].strip())
                            if del_id in config["telegram"].get("admin_chat_ids", []):
                                bot.send_message(chat_id, "Ошибка: Нельзя удалить Главного Администратора!")
                            elif del_id in config["telegram"]["allowed_chat_ids"]:
                                config["telegram"]["allowed_chat_ids"].remove(del_id)
                                save_config(config)
                                bot.reload_users(config)
                                monitor.reload_config(config)
                                bot.send_message(chat_id, f"Пользователь <code>{del_id}</code> удален!")
                            else:
                                bot.send_message(chat_id, f"Пользователь <code>{del_id}</code> не найден в списке.")
                        except ValueError:
                            bot.send_message(chat_id, "Ошибка: Укажите числовой Chat ID. Пример: <code>/del 123456789</code>")

                elif "callback_query" in u:
                    cb = u["callback_query"]
                    chat_id = cb["message"]["chat"]["id"]
                    cb_id = cb["id"]
                    data = cb.get("data", "")

                    if bot.allowed_chat_ids and chat_id not in bot.allowed_chat_ids:
                        bot.answer_callback_query(cb_id, "Доступ запрещен.")
                        continue

                    is_admin_user = bot.is_admin(chat_id)
                    bot.answer_callback_query(cb_id, "Обработка...")

                    if data == "chk_all":
                        report = monitor.format_all_status_report(is_admin=is_admin_user)
                        bot.send_message(chat_id, report)

                    elif data == "chk_back":
                        kb = make_inline_keyboard_for_containers(monitor, is_admin=is_admin_user)
                        bot.send_message(chat_id, "<b>Список групп:</b>", reply_markup=kb)

                    elif data.startswith("chk_g:"):
                        gid = data.split("chk_g:")[1]
                        report, kb = monitor.format_group_report(gid, is_admin=is_admin_user)
                        bot.send_message(chat_id, report, reply_markup=kb)

                    elif data.startswith("rst_g:"):
                        gid = data.split("rst_g:")[1]
                        bot.send_message(chat_id, f"<i>Перезапуск группы...</i>")
                        ok, rst_msg = monitor.restart_group(gid)
                        if ok:
                            bot.send_message(chat_id, f"<b>Успешно перезапущена группа:</b>\n{rst_msg}")
                        else:
                            bot.send_message(chat_id, f"<b>Результаты перезапуска группы:</b>\n{rst_msg}")

                    elif is_admin_user and data.startswith("del_u:"):
                        del_id = int(data.split("del_u:")[1])
                        if del_id in config["telegram"].get("admin_chat_ids", []):
                            bot.send_message(chat_id, "Ошибка: Нельзя удалить Администратора!")
                        elif del_id in config["telegram"]["allowed_chat_ids"]:
                            config["telegram"]["allowed_chat_ids"].remove(del_id)
                            save_config(config)
                            bot.reload_users(config)
                            monitor.reload_config(config)
                            bot.send_message(chat_id, f"Пользователь <code>{del_id}</code> удален!")
                            kb = make_user_management_keyboard(config)
                            bot.send_message(chat_id, "Обновленный список пользователей:", reply_markup=kb)

        except KeyboardInterrupt:
            print("\nОстановка бота...")
            break
        except Exception as e:
            print(f"Ошибка главного цикла: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
