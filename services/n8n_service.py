# services/n8n_service.py
import os
import asyncio
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class N8NService:
    def __init__(self):
        self.webhook_url_24h = os.getenv("N8N_WEBHOOK_URL_24H")
        self.webhook_url_48h = os.getenv("N8N_WEBHOOK_URL_48H")
        self.timeout = 10.0
    
    async def send_payment_created_notification(
        self, 
        user_id: int, 
        payment_id: int, 
        chat_id: int,
        tariff_code: str,
        amount_rub: float,
        provider_payment_id: str,
        payment_url: str
    ) -> bool:
        """
        Отправляет уведомление в N8N о создании платежа для 24-часовой нотификации
        """
        if not self.webhook_url_24h:
            logger.warning("N8N_WEBHOOK_URL_24H не настроен")
            return False
        
        payload = {
            "event_type": "payment_created",
            "user_id": user_id,
            "payment_id": payment_id,
            "chat_id": chat_id,
            "tariff_code": tariff_code,
            "amount_rub": amount_rub,
            "provider_payment_id": provider_payment_id,
            "payment_url": payment_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "delay_hours": 24  # Для 24-часового уведомления
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url_24h,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info(f"Успешно отправлено 24ч уведомление в N8N для платежа {payment_id}")
                    return True
                else:
                    logger.error(f"Ошибка отправки 24ч уведомления в N8N: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout при отправке уведомления в N8N для платежа {payment_id}")
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в N8N: {e}")
            return False
    
    async def send_48h_payment_created_notification(
        self, 
        user_id: int, 
        payment_id: int, 
        chat_id: int,
        tariff_code: str,
        amount_rub: float,
        provider_payment_id: str,
        payment_url: str
    ) -> bool:
        """
        Отправляет уведомление в N8N о создании платежа для 48-часовой нотификации
        """
        if not self.webhook_url_48h:
            logger.warning("N8N_WEBHOOK_URL_48H не настроен")
            return False
        
        payload = {
            "event_type": "payment_created",
            "user_id": user_id,
            "payment_id": payment_id,
            "chat_id": chat_id,
            "tariff_code": tariff_code,
            "amount_rub": amount_rub,
            "provider_payment_id": provider_payment_id,
            "payment_url": payment_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "delay_hours": 48  # Для 48-часового уведомления
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url_48h,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info(f"Успешно отправлено 48ч уведомление в N8N для платежа {payment_id}")
                    return True
                else:
                    logger.error(f"Ошибка отправки 48ч уведомления в N8N: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout при отправке 48ч уведомления в N8N для платежа {payment_id}")
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки 48ч уведомления в N8N: {e}")
            return False

# Глобальный экземпляр сервиса
n8n_service = N8NService()