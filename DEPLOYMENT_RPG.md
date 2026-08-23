# Деплой Vardren на сервер (89.127.200.98, vardren.ru)

На сервере уже работают два других бота — этот гайд рассчитан именно на
добавление **третьего**, изолированного стека рядом с ними, без единого
изменения в их файлах, контейнерах или конфигах. Всё, что относится к
Vardren, живёт в своих собственных файлах (`docker-compose.rpg.prod.yml`,
`rpg-nginx/`, `rpg-backend/`, `rpg-bot/`) и в собственном Docker Compose
проекте `rpg-game` — он не пересекается по имени с существующими стеками.

## Что получится в итоге

```
Интернет → vardren.ru (DNS) → сервер (89.127.200.98)
                                    │
                       Caddy (443/80, уже стоит на сервере —
                       ДОБАВЛЯЕМ блок, не трогая существующие)
                                    │  reverse_proxy 127.0.0.1:<PORT>
                                    ▼
                     docker-compose.rpg.prod.yml (проект "rpg-game"):
                     ├── nginx    (127.0.0.1:<PORT>→80, раздаёт фронтенд + проксирует /api, /static, /bot/webhook)
                     ├── backend  (FastAPI, uvicorn, изолированная сеть rpg_network)
                     ├── bot      (aiogram, webhook-режим, без публикации порта на хост)
                     └── postgres (свой volume rpg_postgres_data, свой контейнер rpg-postgres)
```

Ничего из этого не публикуется на 80/443 напрямую — только Caddy снаружи, как
и для двух других ботов.

---

## Шаг 0. Перед тем как трогать что-либо на сервере

Подключитесь и **посмотрите, что уже занято**, прежде чем что-либо
добавлять — цель шага именно в этом, ничего не меняем:

```bash
ssh root@89.127.200.98

# какие Docker Compose проекты/контейнеры уже есть
docker ps -a
docker compose ls

# какие порты уже слушают на хосте (чтобы не выбрать занятый для rpg-nginx)
sudo ss -tlnp | grep LISTEN

# текущий Caddyfile — посмотреть, НЕ редактировать пока
cat /etc/caddy/Caddyfile
```

Запишите себе: (а) какой порт вы выберете для `RPG_NGINX_PORT` (любой
свободный, например `8091`, `8092` — главное, чтобы не совпадал с портами
двух других ботов из вывода `ss` выше), (б) что в `/etc/caddy/Caddyfile` уже
есть — при редактировании в Шаге 5 вы **дописываете** новый блок в конец
файла, а не заменяете его содержимое.

---

## Шаг 1. DNS для vardren.ru

В панели регистратора домена vardren.ru добавьте A-запись:

- **Subdomain/Имя**: `@` (сам домен)
- **IP-адрес**: `89.127.200.98`

При желании то же самое с `www`. Проверить, что применилось:

```bash
nslookup vardren.ru
```

Должен вернуться `89.127.200.98`. Можно продолжать, не дожидаясь полного
распространения DNS по всему миру.

---

## Шаг 2. Скачать код на сервер

Репозиторий уже запушен на GitHub (публичный):

```bash
cd /opt   # или любая другая директория, куда вы обычно кладёте проекты
git clone https://github.com/lesha2701/rpgGame.git vardren
cd vardren
```

Обратите внимание: в этом же репозитории лежит и старый football-cards
проект — если он у вас уже отдельно развёрнут из **другого** клона/директории
на этом сервере, эта новая директория `vardren/` с ним никак не связана и не
конфликтует (в этом клоне football-cards код уже удалён — см. `git log`).

---

## Шаг 3. Настроить `.env.rpg.local`

```bash
cp .env.rpg.example .env.rpg.local
nano .env.rpg.local
```

Заполните/проверьте:

| Переменная | Что поставить |
|---|---|
| `RPG_DB_PASSWORD` | случайный пароль: `openssl rand -hex 24` |
| `RPG_ADMIN_TELEGRAM_IDS` | ваш Telegram ID (узнать — написать [@userinfobot](https://t.me/userinfobot)) |
| `RPG_JWT_SECRET` | случайная строка: `openssl rand -hex 32` |
| `RPG_TELEGRAM_BOT_TOKEN` | токен `@VardrenBot` от [@BotFather](https://t.me/BotFather) (см. Шаг 4) |
| `RPG_TELEGRAM_BOT_USERNAME` | `VardrenBot` |
| `RPG_MINI_APP_URL` | `https://vardren.ru` |
| `RPG_BOT_MODE` | `webhook` (обязательно — `polling` для прода не годится) |
| `RPG_BOT_WEBHOOK_URL` | `https://vardren.ru/bot/webhook` |
| `RPG_BOT_WEBHOOK_SECRET` | случайная строка: `openssl rand -hex 32` |

Дополнительно добавьте в конец файла (их нет в `.env.rpg.example`, они
только для прод-компоуза):

```bash
echo "RPG_NGINX_PORT=8091" >> .env.rpg.local   # порт из Шага 0, если 8091 занят — впишите свободный
```

`RPG_DB_NAME`/`RPG_DB_USER` можно оставить как в примере (`rpg_game`/
`rpg_admin`) — они не пересекаются с двумя другими ботами, у каждого своя
база в своём контейнере `rpg-postgres`.

---

## Шаг 4. Бот уже создан — донастроить меню

Токен и `@VardrenBot` у вас уже есть. Осталось направить кнопку меню на
боевой домен (сейчас она может указывать на localhost для локальной
разработки):

Откройте [@BotFather](https://t.me/BotFather) → `/setmenubutton` → выберите
`@VardrenBot` → текст кнопки (например, «⚔ Играть») → URL:
`https://vardren.ru`.

---

## Шаг 5. Caddy — добавить блок, НЕ трогая существующие

Откройте текущий конфиг:

```bash
sudo nano /etc/caddy/Caddyfile
```

Вы увидите блоки двух уже работающих ботов — **не удаляйте и не
редактируйте их**. Просто добавьте в конец файла новый блок (порт — тот же,
что вы вписали в `RPG_NGINX_PORT` на Шаге 3):

```
vardren.ru, www.vardren.ru {
    reverse_proxy 127.0.0.1:8091
}
```

Сохраните и перезапустите Caddy (перезапуск затронет только сам процесс
Caddy — уже выданные сертификаты и работающие прокси для двух других ботов
не пострадают, Caddy просто перечитает весь файл целиком и продолжит
обслуживать все блоки, включая новый):

```bash
sudo systemctl reload caddy   # reload, не restart — не разрывает существующие соединения
sudo systemctl status caddy
```

Caddy сам получит сертификат Let's Encrypt для vardren.ru при первом
запросе (DNS из Шага 1 уже должен указывать на сервер).

---

## Шаг 6. Запустить стек Vardren

```bash
cd /opt/vardren
docker compose -f docker-compose.rpg.prod.yml --env-file .env.rpg.local up -d --build
```

Это создаёт **новые, отдельные** контейнеры (`rpg-postgres`, `rpg-backend`,
`rpg-bot`, `rpg-nginx`) и отдельную сеть `rpg_network` — ни один из них не
называется так же и не пересекается по портам/сети с контейнерами двух
других ботов.

Проверить, что всё поднялось:

```bash
docker compose -f docker-compose.rpg.prod.yml ps
docker compose -f docker-compose.rpg.prod.yml logs -f bot      # Ctrl+C для выхода
```

В логах `bot` не должно быть `TelegramUnauthorizedError` (если есть —
проверьте `RPG_TELEGRAM_BOT_TOKEN` в `.env.rpg.local`).

---

## Шаг 7. Наполнить каталог (сиды)

```bash
docker compose -f docker-compose.rpg.prod.yml exec backend python -m app.seed
```

---

## Шаг 8. Проверить

- `https://vardren.ru` открывается в браузере (сертификат HTTPS должен быть
  валиден — Caddy выдал его автоматически).
- В Telegram: `@VardrenBot` → `/start` → кнопка открывает приложение.
- Два других бота продолжают отвечать как ни в чём не бывало — если что-то
  из вышесказанного их задело, значит где-то в Шаге 5 был отредактирован (а
  не дополнен) существующий блок Caddyfile — это единственный файл, общий
  для всех трёх ботов.

---

## Если сервер — российский хостинг и Telegram API недоступен по IPv4

Раз два других бота уже работают на этом сервере, скорее всего это уже не
проблема (иначе они бы тоже не работали) — но если `rpg-bot` не может
достучаться до Telegram, проверьте:

```bash
curl -4 -s -o /dev/null -w "IPv4: %{http_code}\n" --max-time 8 https://api.telegram.org
curl -6 -s -o /dev/null -w "IPv6: %{http_code}\n" --max-time 8 https://api.telegram.org
```

Если IPv4 не отвечает, а IPv6 отвечает — понадобится включить IPv6 в
Docker-сети `rpg_network` (добавить `enable_ipv6: true` и подсеть в секцию
`networks` файла `docker-compose.rpg.prod.yml` — выберите подсеть, которая
точно не совпадает с уже занятыми двумя другими стеками, например
`fd00:vard:ren::/64`) и убедиться, что `ip6tables: true` стоит в
`/etc/docker/daemon.json` (общий для всего хоста — если он уже включён для
других ботов, трогать не нужно).

---

## Обновление в будущем

```bash
cd /opt/vardren
git pull
docker compose -f docker-compose.rpg.prod.yml --env-file .env.rpg.local up -d --build
```

Это пересобирает и перезапускает **только** контейнеры Vardren — Caddy и два
других бота не перезапускаются и не пересобираются этой командой.
