#!/usr/bin/env python3
"""
Скрипт для исправления периодов подписок в базе данных.
Обновляет end_at для существующих подписок согласно правильной логике:
- monthly: +1 месяц от start_at
- stable: +3 месяца от start_at

Использование:
1. Установить переменную окружения DATABASE_URL
2. Запустить: python fix_subscriptions.py
"""

import asyncio
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, update

# Устанавливаем DATABASE_URL ДО импорта db
os.environ["DATABASE_URL"] = "postgresql+asyncpg://safa:SafaWSXqa12!@31.129.100.230:5432/main_db"

from db import get_session
from models import Subscription, Payment
from services.subscriptions import activate_or_extend_subscription

async def fix_subscriptions():
    """Исправляет периоды подписок согласно тарифу"""
    
    print("🔗 Подключение к базе данных...")
    
    async with get_session() as session:
        # Сначала показываем ВСЕ платежи
        print("=== ВСЕ ПЛАТЕЖИ ===")
        try:
            result = await session.execute(
                select(Payment.id, Payment.user_id, Payment.tariff_code, 
                       Payment.amount_rub, Payment.paid_at, Payment.status)
                .order_by(Payment.created_at.desc())
            )
            all_payments = result.all()
            
            print(f"Всего платежей в БД: {len(all_payments)}")
            for p in all_payments:
                print(f"ID: {p.id}, User: {p.user_id}, Tariff: {p.tariff_code}")
                print(f"  Amount: {p.amount_rub} руб., Status: {p.status}")
                print(f"  Paid: {p.paid_at}")
                print()
                
            # Теперь только успешные
            succeeded_payments = [p for p in all_payments if str(p.status) == 'succeeded']
            print(f"\n=== УСПЕШНЫЕ ПЛАТЕЖИ ({len(succeeded_payments)}) ===")
            payments = succeeded_payments
            
            if not payments:
                print("❌ Нет успешных платежей!")
                return
                
        except Exception as e:
            print(f"Ошибка при получении платежей: {e}")
            return
        
        print("=" * 50)
        # Теперь работаем с подписками
        try:
            # Получаем все подписки для анализа
            result = await session.execute(
                select(Subscription)
                .order_by(Subscription.created_at.desc())
            )
            subscriptions = result.scalars().all()
            
            print(f"📊 Найдено подписок: {len(subscriptions)}")
            
            if not subscriptions:
                print("✅ Подписки не найдены")
                return
            
            # Группируем по тарифам
            monthly_subs = []
            stable_subs = []
            other_subs = []
            
            for sub in subscriptions:
                if sub.tariff_code == "monthly":
                    monthly_subs.append(sub)
                elif sub.tariff_code == "stable":
                    stable_subs.append(sub)
                else:
                    other_subs.append(sub)
            
            print(f"📈 Monthly подписок: {len(monthly_subs)}")
            print(f"📈 Stable подписок: {len(stable_subs)}")
            print(f"📈 Других подписок: {len(other_subs)}")
            
            print("\n=== ТЕКУЩИЕ ПОДПИСКИ ===")
            for sub in subscriptions:
                print(f"ID: {sub.id}, User: {sub.user_id}, Tariff: {sub.tariff_code}")
                print(f"  Start: {sub.start_at}")
                print(f"  End: {sub.end_at}")
                print(f"  Status: {sub.status}")
                print()
            
            # Проверяем, есть ли подписки для всех платежей
            print("\n=== АНАЛИЗ ПЛАТЕЖЕЙ БЕЗ ПОДПИСОК ===")
            payments_without_subs = []
            for payment in payments:
                # Ищем подписку для этого пользователя и тарифа
                has_subscription = any(
                    sub.user_id == payment.user_id and sub.tariff_code == payment.tariff_code 
                    for sub in subscriptions
                )
                if not has_subscription:
                    payments_without_subs.append(payment)
                    print(f"⚠️  Платеж ID {payment.id} (User: {payment.user_id}, Tariff: {payment.tariff_code}) - НЕТ ПОДПИСКИ!")
            
            if payments_without_subs:
                print(f"\n🚨 Найдено {len(payments_without_subs)} платежей без подписок!")
                create_response = input("🔄 Создать подписки для платежей? (y/N): ").strip().lower()
                if create_response == 'y':
                    await create_missing_subscriptions(session, payments_without_subs)
            
            if not subscriptions:
                print("✅ Подписки не найдены, но платежи есть - создадим их")
                return
            
            # Спрашиваем подтверждение для исправления периодов
            response = input("🔄 Исправить периоды существующих подписок? (y/N): ").strip().lower()
            if response != 'y':
                print("❌ Операция отменена")
                return
            
            updated_count = 0
            
            # Исправляем monthly подписки (+1 месяц)
            for sub in monthly_subs:
                correct_end = sub.start_at + relativedelta(months=1)
                if sub.end_at != correct_end:
                    old_end = sub.end_at
                    sub.end_at = correct_end
                    updated_count += 1
                    print(f"✅ Monthly подписка ID {sub.id}: {old_end} → {correct_end}")
            
            # Исправляем stable подписки (+3 месяца)
            for sub in stable_subs:
                correct_end = sub.start_at + relativedelta(months=3)
                if sub.end_at != correct_end:
                    old_end = sub.end_at
                    sub.end_at = correct_end
                    updated_count += 1
                    print(f"✅ Stable подписка ID {sub.id}: {old_end} → {correct_end}")
            
            # Сохраняем изменения
            if updated_count > 0:
                await session.commit()
                print(f"\n🎉 Обновлено подписок: {updated_count}")
            else:
                print("\n✅ Все подписки уже имеют корректные периоды")
            
            # Показываем итоговое состояние
            print("\n=== ОБНОВЛЕННЫЕ ПОДПИСКИ ===")
            result = await session.execute(
                select(Subscription)
                .order_by(Subscription.created_at.desc())
            )
            updated_subs = result.scalars().all()
            
            for sub in updated_subs:
                print(f"ID: {sub.id}, User: {sub.user_id}, Tariff: {sub.tariff_code}")
                print(f"  Start: {sub.start_at}")
                print(f"  End: {sub.end_at}")
                print(f"  Status: {sub.status}")
                print()
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await session.rollback()
            raise

async def create_missing_subscriptions(session, payments_without_subs):
    """Создает подписки для платежей, у которых их нет"""
    print(f"\n🔨 Создание подписок для {len(payments_without_subs)} платежей...")
    
    created_count = 0
    for payment in payments_without_subs:
        try:
            # Используем ту же логику, что и в webhook
            subscription = await activate_or_extend_subscription(
                session=session,
                user_id=payment.user_id,
                tariff_code=payment.tariff_code
            )
            created_count += 1
            print(f"✅ Создана подписка для платежа ID {payment.id} (User: {payment.user_id}, Tariff: {payment.tariff_code})")
            print(f"   Период: {subscription.start_at} → {subscription.end_at}")
            
        except Exception as e:
            print(f"❌ Ошибка при создании подписки для платежа ID {payment.id}: {e}")
    
    if created_count > 0:
        await session.commit()
        print(f"\n🎉 Создано подписок: {created_count}")
    else:
        print("\n❌ Не удалось создать ни одной подписки")

if __name__ == "__main__":
    print("🔧 Скрипт исправления подписок")
    print("=" * 50)
    
    asyncio.run(fix_subscriptions())