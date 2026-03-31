from typing import AsyncGenerator

from datetime import datetime, timedelta
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.models import User


class UserActions:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_user(self, tg_id: int, username: str, status: str = "unblocked", language_code: str = None, is_premium: bool = False):
        user = User(
            tg_id=tg_id, 
            username=username, 
            status=status, 
            language_code=language_code, 
            is_premium=is_premium
        )
        self.session.add(user)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def get_user(self, tg_id: int):
        stmt = select(User).where(User.tg_id == tg_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str):
        if username.startswith("@"):
            username = username[1:]
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_user(self):
        stmt = select(User)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_registration_stats(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        year_ago = now - timedelta(days=365)

        # Total
        stmt_total = select(func.count(User.tg_id))
        total = (await self.session.execute(stmt_total)).scalar()

        # Day
        stmt_day = select(func.count(User.tg_id)).where(User.created_at >= day_ago)
        day = (await self.session.execute(stmt_day)).scalar()

        # Month
        stmt_month = select(func.count(User.tg_id)).where(User.created_at >= month_ago)
        month = (await self.session.execute(stmt_month)).scalar()

        # Week
        stmt_week = select(func.count(User.tg_id)).where(User.created_at >= week_ago)
        week = (await self.session.execute(stmt_week)).scalar()

        # Year
        stmt_year = select(func.count(User.tg_id)).where(User.created_at >= year_ago)
        year = (await self.session.execute(stmt_year)).scalar()
        
        # New Stats: Premium & Language
        stmt_premium = select(func.count(User.tg_id)).where(User.is_premium == True)
        premium_count = (await self.session.execute(stmt_premium)).scalar()
        
        stmt_langs = select(User.language_code, func.count(User.tg_id)).group_by(User.language_code).order_by(func.count(User.tg_id).desc()).limit(5)
        langs_result = (await self.session.execute(stmt_langs)).all()
        langs_stats = [{"code": row[0] or "unknown", "count": row[1]} for row in langs_result]

        # New: Revenue and VIP counts
        # We fetch all users with non-empty payment history or active VIP
        # (For optimization in larger DBs, we'd use a separate Payment table)
        stmt_vip = select(func.count(User.tg_id)).where(User.vip_status == "active")
        active_vip_count = (await self.session.execute(stmt_vip)).scalar()

        # Revenue intervals
        revenue = {
            "day": {"uzs": 0, "stars": 0},
            "week": {"uzs": 0, "stars": 0},
            "month": {"uzs": 0, "stars": 0},
            "year": {"uzs": 0, "stars": 0},
            "total": {"uzs": 0, "stars": 0}
        }
        
        now = datetime.utcnow() + timedelta(hours=5)
        
        stmt_all = select(User.vip_payment_history).where(User.vip_payment_history != None)
        result = await self.session.execute(stmt_all)
        for history in result.scalars():
            if not history: continue
            if isinstance(history, dict): history = [history]
            for payment in history:
                amount = payment.get("amount", 0)
                currency = payment.get("currency", "").upper()
                date_str = payment.get("date", "") # format: %d.%m.%Y %H:%M or %d.%m.%Y
                
                try:
                    if " " in date_str:
                        p_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                    else:
                        p_date = datetime.strptime(date_str, "%d.%m.%Y")
                except:
                    continue

                is_uzs = currency in ["UZS", "SUM"]
                is_stars = currency in ["XTR", "STARS"]
                
                def add_rev(key):
                    if is_uzs: revenue[key]["uzs"] += amount
                    if is_stars: revenue[key]["stars"] += amount

                add_rev("total")
                if p_date >= now - timedelta(days=1): add_rev("day")
                if p_date >= now - timedelta(days=7): add_rev("week")
                if p_date >= now - timedelta(days=30): add_rev("month")
                if p_date >= now - timedelta(days=365): add_rev("year")

        return {
            "total": total,
            "day": day,
            "week": week,
            "month": month,
            "year": year,
            "premium": premium_count,
            "languages": langs_stats,
            "active_vip": active_vip_count,
            "revenue": revenue
        }

    async def update_user(self, tg_id: int, **kwargs):
        stmt = update(User).where(User.tg_id == tg_id).values(**kwargs)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_user_status(self, new_status: str, tg_id: int):
        await self.update_user(tg_id, status=new_status)

    async def increment_joined_count(self, tg_id: int) -> int:
        from sqlalchemy import func as sa_func
        stmt = (
            update(User)
            .where(User.tg_id == tg_id)
            .values(joined_count=sa_func.coalesce(User.joined_count, 0) + 1)
            .returning(User.joined_count)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        value = result.scalar()
        return value if value is not None else 0


    async def get_user_ids_batch(self, offset: int, limit: int = 5000) -> list[int]:
        stmt = select(User.tg_id).order_by(User.tg_id).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def iterate_user_ids(
        self,
        batch_size: int = 5000,
        exclude_vip: bool = False
    ) -> AsyncGenerator[tuple[list[int], int], None]:

        offset = 0

        while True:
            # We construct a custom get_user_ids_batch to filter VIPs
            stmt = select(User.tg_id).order_by(User.tg_id)
            if exclude_vip:
                stmt = stmt.where((User.vip_status != "active") | (User.vip_status.is_(None)))
            stmt = stmt.offset(offset).limit(batch_size)
            result = await self.session.execute(stmt)
            user_ids = list(result.scalars().all())

            if not user_ids:
                break

            yield user_ids, offset
            offset += len(user_ids)
