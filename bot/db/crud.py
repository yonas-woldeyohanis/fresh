from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Material, Payment, PaymentStatus, User, Course
from bot.utils.constants import EXAMS


# ---------- users ----------
async def upsert_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str) -> User:
    stmt = (
        insert(User)
        .values(telegram_id=telegram_id, username=username, full_name=full_name)
        .on_conflict_do_update(
            index_elements=["telegram_id"], set_={"username": username, "full_name": full_name}
        )
        .returning(User)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one()


async def verify_user(session: AsyncSession, telegram_id: int) -> None:
    await session.execute(update(User).where(User.telegram_id == telegram_id).values(is_verified=True))


# ---------- payments ----------
async def get_pending_payment(session: AsyncSession, telegram_id: int) -> Payment | None:
    stmt = select(Payment).where(
        Payment.telegram_id == telegram_id, Payment.status == PaymentStatus.PENDING.value
    )
    return (await session.execute(stmt)).scalars().first()


async def create_payment(session: AsyncSession, telegram_id: int, receipt_file_id: str) -> Payment:
    payment = Payment(telegram_id=telegram_id, receipt_file_id=receipt_file_id)
    session.add(payment)
    await session.flush()  # assigns payment.id
    return payment


async def decide_payment(
    session: AsyncSession, payment_id: int, new_status: PaymentStatus, admin_id: int
) -> Payment | None:
    """Atomically move pending -> approved/rejected. Returns None if already processed."""
    stmt = (
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING.value)
        .values(status=new_status.value, reviewed_by=admin_id)
        .returning(Payment)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ---------- materials ----------
async def get_material(session: AsyncSession, material_id: int) -> Material | None:
    return await session.get(Material, material_id)


async def add_material(
    session: AsyncSession,
    *,
    course_code: str,
    category: str,
    title: str,
    channel_message_id: int,
    file_id: str | None = None,
    exam_year: int | None = None,
    is_sample: bool = False,
) -> Material:
    m = Material(
        course_code=course_code,
        category=category,
        title=title,
        channel_message_id=channel_message_id,
        file_id=file_id,
        exam_year=exam_year,
        is_sample=is_sample,
    )
    session.add(m)
    await session.flush()
    return m


async def list_materials(session: AsyncSession, course_code: str, category: str) -> Sequence[Material]:
    stmt = (
        select(Material)
        .where(Material.course_code == course_code, Material.category == category)
        .order_by(Material.id)
    )
    return (await session.execute(stmt)).scalars().all()


async def list_samples(session: AsyncSession) -> Sequence[Material]:
    stmt = select(Material).where(Material.is_sample.is_(True)).order_by(Material.course_code, Material.id)
    return (await session.execute(stmt)).scalars().all()


async def list_exam_years(session: AsyncSession, course_code: str) -> Sequence[int]:
    stmt = (
        select(Material.exam_year)
        .where(
            Material.course_code == course_code,
            Material.category == EXAMS,
            Material.exam_year.is_not(None),
        )
        .distinct()
        .order_by(Material.exam_year)
    )
    return (await session.execute(stmt)).scalars().all()


async def list_exams(session: AsyncSession, course_code: str, year: int) -> Sequence[Material]:
    stmt = (
        select(Material)
        .where(Material.course_code == course_code, Material.category == EXAMS, Material.exam_year == year)
        .order_by(Material.id)
    )
    return (await session.execute(stmt)).scalars().all()

async def get_analytics(session: AsyncSession) -> dict:
    from sqlalchemy import func
    total_users = (await session.execute(select(func.count(User.telegram_id)))).scalar() or 0
    verified_users = (await session.execute(select(func.count(User.telegram_id)).where(User.is_verified.is_(True)))).scalar() or 0
    total_materials = (await session.execute(select(func.count(Material.id)))).scalar() or 0
    pending_payments = (await session.execute(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.PENDING.value))).scalar() or 0
    approved_payments = (await session.execute(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.APPROVED.value))).scalar() or 0
    
    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "total_materials": total_materials,
        "pending_payments": pending_payments,
        "approved_payments": approved_payments
    }

async def delete_material(session: AsyncSession, material_id: int) -> Material | None:
    m = await get_material(session, material_id)
    if m:
        await session.delete(m)
        await session.commit()
    return m

async def update_material_title(session: AsyncSession, material_id: int, new_title: str) -> None:
    await session.execute(update(Material).where(Material.id == material_id).values(title=new_title))
    await session.commit()

async def add_course(session: AsyncSession, code: str, name: str) -> Course:
    c = Course(code=code, name=name)
    session.add(c)
    await session.commit()
    return c

async def get_courses(session: AsyncSession) -> list[Course]:
    res = await session.execute(select(Course).order_by(Course.code))
    return list(res.scalars().all())

async def get_course(session: AsyncSession, code: str) -> Course | None:
    res = await session.execute(select(Course).where(Course.code == code))
    return res.scalar_one_or_none()

async def delete_course(session: AsyncSession, code: str) -> bool:
    c = await get_course(session, code)
    if c:
        await session.delete(c)
        await session.commit()
        return True
    return False

async def get_course_dict(session: AsyncSession) -> dict[str, str]:
    courses = await get_courses(session)
    return {c.code: c.name for c in courses}

from bot.db.models import KeyValue

async def get_value(session: AsyncSession, key: str) -> str | None:
    res = await session.execute(select(KeyValue).where(KeyValue.key == key))
    kv = res.scalar_one_or_none()
    return kv.value if kv else None

async def set_value(session: AsyncSession, key: str, value: str) -> None:
    res = await session.execute(select(KeyValue).where(KeyValue.key == key))
    kv = res.scalar_one_or_none()
    if kv:
        kv.value = value
    else:
        session.add(KeyValue(key=key, value=value))
    await session.commit()
