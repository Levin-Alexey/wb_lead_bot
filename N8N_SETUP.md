# Настройка N8N для нотификаций через 24 и 48 часов

## 📋 Описание системы

Система работает следующим образом:
1. Пользователь создает платеж → бот отправляет данные в N8N webhook
2. N8N ждет 24 часа → проверяет статус платежа через ЮKassa API
3. Если платеж не оплачен → N8N отправляет webhook обратно в бота
4. Бот отправляет пользователю уведомление с кнопкой "Подключиться"
5. Аналогично для 48-часового уведомления

## 🔧 Настройка Workflow в N8N

### 1. Создание основного workflow

**Webhook Trigger (Получение данных от бота):**
```json
{
  "webhook": {
    "httpMethod": "POST",
    "path": "a8bbeccf-2982-487b-8ec4-26695ffc412c"
  }
}
```

**Входящие данные от бота:**
```json
{
  "event_type": "payment_created",
  "user_id": 123,
  "payment_id": 456,
  "chat_id": 789,
  "tariff_code": "monthly",
  "amount_rub": 1490.0,
  "provider_payment_id": "2c85b9e1-0008-5000-8000-18cc21ac1801",
  "payment_url": "https://yoomoney.ru/checkout/payments/v2/...",
  "created_at": "2025-01-20T12:00:00Z",
  "delay_hours": 24
}
```

### 2. Workflow структура

#### Node 1: Webhook Trigger
- **Type**: Webhook
- **HTTP Method**: POST
- **Response**: Return JSON: `{"status": "received"}`

#### Node 2: Wait Node (24 часа)
- **Type**: Wait
- **Resume On**: After Time Interval
- **Interval**: 24 hours

#### Node 3: HTTP Request (Проверка статуса в ЮKassa)
- **Type**: HTTP Request
- **Method**: GET
- **URL**: `https://api.yookassa.ru/v3/payments/{{ $node["Webhook"].json["provider_payment_id"] }}`
- **Authentication**: Basic Auth
  - **User**: `{{ $vars.YOOKASSA_SHOP_ID }}` (ваш Shop ID)
  - **Password**: `{{ $vars.YOOKASSA_SECRET_KEY }}` (ваш Secret Key)
- **Headers**:
  ```json
  {
    "Content-Type": "application/json"
  }
  ```

#### Node 4: IF Node (Проверка статуса платежа)
- **Type**: IF
- **Condition**: `{{ $node["HTTP Request"].json["status"] }} !== "succeeded"`

#### Node 5: HTTP Request (Отправка уведомления в бот)
- **Type**: HTTP Request (выполняется только если платеж НЕ оплачен)
- **Method**: POST  
- **URL**: `https://your-bot-webhook-url.com/n8n/notification`
- **Body**:
  ```json
  {
    "delay_hours": "{{ $node['Webhook'].json['delay_hours'] }}",
    "payment_id": "{{ $node['Webhook'].json['payment_id'] }}",
    "chat_id": "{{ $node['Webhook'].json['chat_id'] }}",
    "user_id": "{{ $node['Webhook'].json['user_id'] }}"
  }
  ```

### 3. Переменные окружения в N8N

Добавьте в настройки N8N:
```
YOOKASSA_SHOP_ID=1140150
YOOKASSA_SECRET_KEY=live_CkfBB_hn2U6X1IFycGHoJWf9TITYjlpjt1HxCwBljYc
BOT_WEBHOOK_URL=https://your-bot-domain.com/n8n/notification
```

### 4. Создание второго workflow для 48 часов

Создайте аналогичный workflow, но:
- Измените Wait Node на **48 hours**
- В условии IF проверяйте `delay_hours === 48`
- Используйте тот же webhook URL, но данные будут приходить с `delay_hours: 48`

**Альтернативный вариант**: Создайте единый workflow с разветвлением:
1. **Switch Node** после Webhook для проверки `delay_hours`
2. **Две ветки**: одна для 24ч, другая для 48ч
3. **Разные Wait Node**: 24 hours и 48 hours соответственно

### 5. Тексты уведомлений

**24-часовое уведомление:**
- Текст: Мотивационное сообщение о работе на маркетплейсах
- Кнопка: "Подключиться"

**48-часовое уведомление:**  
- Текст: Отчет о достижениях MarketSkills за 2 недели
- Кнопка: "Вступить в команду!"

## 🧪 Тестирование

### Тест 1: Отправка данных из бота в N8N
```bash
curl -X POST https://saglotiethujo.beget.app/webhook/a8bbeccf-2982-487b-8ec4-26695ffc412c \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "payment_created",
    "user_id": 123,
    "payment_id": 456,
    "chat_id": 789,
    "tariff_code": "monthly",
    "amount_rub": 1490.0,
    "provider_payment_id": "test-payment-id",
    "payment_url": "https://test.com",
    "created_at": "2025-01-20T12:00:00Z",
    "delay_hours": 24
  }'
```

### Тест 2: Эмуляция отправки 24ч уведомления от N8N в бот
```bash
curl -X POST https://your-bot-domain.com/n8n/notification \
  -H "Content-Type: application/json" \
  -d '{
    "delay_hours": 24,
    "payment_id": 456,
    "chat_id": 789,
    "user_id": 123
  }'
```

### Тест 3: Эмуляция отправки 48ч уведомления от N8N в бот
```bash
curl -X POST https://your-bot-domain.com/n8n/notification \
  -H "Content-Type: application/json" \
  -d '{
    "delay_hours": 48,
    "payment_id": 456,
    "chat_id": 789,
    "user_id": 123
  }'
```

### Тест 4: Отправка данных для 48ч уведомления в N8N
```bash
curl -X POST https://saglotiethujo.beget.app/webhook/a8bbeccf-2982-487b-8ec4-26695ffc412c \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "payment_created",
    "user_id": 123,
    "payment_id": 456,
    "chat_id": 789,
    "tariff_code": "monthly",
    "amount_rub": 1490.0,
    "provider_payment_id": "test-payment-id",
    "payment_url": "https://test.com",
    "created_at": "2025-01-20T12:00:00Z",
    "delay_hours": 48
  }'
```

## 📝 Логи и отладка

**В N8N** проверяйте логи выполнения workflow:
- Execution History
- Node outputs
- Error messages

**В боте** проверяйте логи:
```bash
tail -f logs/bot.log | grep "N8N"
```

## 🔄 Workflow JSON для импорта

Экспортируйте готовый workflow в JSON и сохраните для резервной копии.

## ⚠️ Важные моменты

1. **Безопасность**: Используйте HTTPS для всех webhook URL
2. **Таймауты**: Установите таймауты для HTTP запросов (10-30 сек)
3. **Ошибки**: Добавьте обработку ошибок в workflow
4. **Мониторинг**: Настройте уведомления об ошибках в N8N
5. **Backup**: Регулярно экспортируйте workflow в JSON

## 🎯 URL endpoints

- **N8N Webhook**: `https://saglotiethujo.beget.app/webhook/a8bbeccf-2982-487b-8ec4-26695ffc412c`
- **Bot Notification**: `https://your-bot-domain.com/n8n/notification`
- **ЮKassa API**: `https://api.yookassa.ru/v3/payments/{payment_id}`