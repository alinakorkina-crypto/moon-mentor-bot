"""Reserve/finalize a credit independently of Telegram delivery cancellation."""
import asyncio
import json


class PaidReadings:
    def __init__(self, payments, readings, draw_cards):
        self.payments = payments
        self.readings = readings
        self.draw_cards = draw_cards
        self.tasks = {}
        self.owners = {}

    def has(self, key):
        return key in self.tasks

    async def prepare(self, key, *, user_id, mode, question):
        if key in self.owners and self.owners[key] != user_id:
            return "unavailable"
        if key not in self.tasks:
            self.owners[key] = user_id
            self.tasks[key] = asyncio.create_task(self._prepare(
                key, user_id=user_id, mode=mode, question=question))
        return await asyncio.shield(self.tasks[key])

    async def _prepare(self, key, *, user_id, mode, question):
        from payments_service import PaymentError
        try:
            row, is_new = await self.payments.reserve(key, user_id, allow_new=self.payments.ready)
            if row is None:
                return "empty"
            if not is_new:
                if row["status"] != "completed":
                    # A reserved operation from another process/restart has an
                    # unknown model outcome: never regenerate or refund blindly.
                    return "failed" if row["status"] == "released" else "pending"
                saved = json.loads(row["result_json"])
                operation = self.readings.restore(key, mode=saved["mode"],
                    question=saved["question"], cards=saved["cards"],
                    result={"status": "success", "text": saved["text"]})
                operation.history_recorded = bool(row["history_recorded"])
                operation.delivered = bool(row["delivered"])
                return "ready"
            try:
                cards = self.draw_cards(3)
                operation = self.readings.start(key, mode=mode, question=question, cards=cards)
                result = await operation.result()
            except Exception:
                await self.payments.finish(key, success=False)
                return "failed"
            success = result.get("status") == "success" and isinstance(result.get("text"), str)
            saved = {"text": result["text"], "mode": mode, "question": question,
                     "cards": cards} if success else None
            await self.payments.finish(key, success=success, result=saved)
            return "ready" if success else "failed"
        except (PaymentError, ValueError, KeyError, TypeError):
            return "unavailable"
