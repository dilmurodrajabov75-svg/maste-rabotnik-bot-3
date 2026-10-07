"""
Ish e'lonlari boti (aiogram 3.x)

O'rnatish:   pip install aiogram
Ishga tushirish (Linux/Mac):
    export BOT_TOKEN="yangi_token"
    export ADMIN_ID="123456789"        # sizning Telegram ID
    export CHANNEL_ID="-1001234567890" # kanal ID (bot kanalda admin bo'lsin)
    python bot.py
"""
import asyncio
import html
import logging
import os
import sqlite3

from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, InputMediaPhoto, KeyboardButton,
                           Message, ReplyKeyboardRemove)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

BOT_TOKEN = "8350987756:AAGRA2u9YejsHkiv8euNCB-Eyrz8pPqOZqk"
ADMIN_ID = 8554402317
CHANNEL_ID = "@ish_keremidi"

PRICES = [100000, 150000, 180000, 200000, 250000, 300000, 400000]
BOT_USERNAME = ""

# ---------------------------------------------------------------- DB
db = sqlite3.connect("bot.db")
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, surname TEXT, phone TEXT,
  address TEXT, age INTEGER, photo TEXT, banned INTEGER DEFAULT 0,
  username TEXT);
CREATE TABLE IF NOT EXISTS ads(
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, kind TEXT,
  price INTEGER, time TEXT, when_ TEXT, lat REAL, lon REAL, extra TEXT,
  status TEXT DEFAULT 'active', msg_id INTEGER);
CREATE TABLE IF NOT EXISTS apps(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ad_id INTEGER, user_id INTEGER,
  shot1 TEXT, shot2 TEXT, receipt TEXT, status TEXT DEFAULT 'new');
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
INSERT OR IGNORE INTO settings VALUES('card','Karta raqami kiritilmagan');
INSERT OR IGNORE INTO settings VALUES('fee','10 000');
""")
db.commit()


def q(sql, args=(), one=False, commit=False):
    cur = db.execute(sql, args)
    if commit:
        db.commit()
        return cur.lastrowid
    return cur.fetchone() if one else cur.fetchall()


def setting(k):
    return q("SELECT v FROM settings WHERE k=?", (k,), one=True)["v"]


def get_user(uid):
    return q("SELECT * FROM users WHERE id=?", (uid,), one=True)


def esc(s):
    return html.escape(str(s))


def money(n):
    return f"{int(n):,}".replace(",", " ")


# ---------------------------------------------------------------- States
class Reg(StatesGroup):
    name = State(); surname = State(); phone = State()
    address = State(); age = State(); photo = State()


class Ad(StatesGroup):
    kind = State(); price = State(); time = State(); when = State()
    location = State(); extra = State(); confirm = State()


class Apply(StatesGroup):
    shot1 = State(); shot2 = State()


class Adm(StatesGroup):
    setting = State(); broadcast = State(); ban = State(); unban = State()


router = Router()
pending_apply = {}  # user_id -> ad_id (ro'yxatdan o'tgach davom ettirish uchun)


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u and u.id != ADMIN_ID:
            row = get_user(u.id)
            if row and row["banned"]:
                return
        return await handler(event, data)


# ---------------------------------------------------------------- Keyboards
def main_menu(uid):
    b = ReplyKeyboardBuilder()
    b.button(text="📢 E'lon berish")
    b.button(text="👤 Profilim")
    if uid == ADMIN_ID:
        b.button(text="🛠 Admin panel")
    b.adjust(2, 1)
    return b.as_markup(resize_keyboard=True)


def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="❌ Bekor qilish")
    return b.as_markup(resize_keyboard=True)


def inline(rows):
    b = InlineKeyboardBuilder()
    for text, data in rows:
        b.button(text=text, callback_data=data)
    return b


# ---------------------------------------------------------------- START / RO'YXAT
@router.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    arg = command.args or ""
    if arg.startswith("apply_") and arg[6:].isdigit():
        pending_apply[m.from_user.id] = int(arg[6:])
    if not get_user(m.from_user.id):
        await m.answer("Assalomu alaykum! Avval ro'yxatdan o'ting.\n\n✏️ Ismingizni yozing:",
                       reply_markup=ReplyKeyboardRemove())
        await state.set_state(Reg.name)
        return
    if m.from_user.id in pending_apply:
        await begin_apply(m, state, pending_apply.pop(m.from_user.id))
        return
    await m.answer("Asosiy menyu:", reply_markup=main_menu(m.from_user.id))


@router.message(Reg.name, F.text)
async def reg_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await m.answer("Familiyangizni yozing:")
    await state.set_state(Reg.surname)


@router.message(Reg.surname, F.text)
async def reg_surname(m: Message, state: FSMContext):
    await state.update_data(surname=m.text.strip())
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(text="📞 Raqamni yuborish", request_contact=True))
    await m.answer("Telefon raqamingizni tugma orqali yuboring:",
                   reply_markup=b.as_markup(resize_keyboard=True))
    await state.set_state(Reg.phone)


@router.message(Reg.phone, F.contact)
async def reg_phone(m: Message, state: FSMContext):
    await state.update_data(phone=m.contact.phone_number)
    await m.answer("Yashash manzilingiz (shahar/tuman):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Reg.address)


@router.message(Reg.address, F.text)
async def reg_address(m: Message, state: FSMContext):
    await state.update_data(address=m.text.strip())
    await m.answer("Yoshingiz (raqam bilan):")
    await state.set_state(Reg.age)


@router.message(Reg.age, F.text)
async def reg_age(m: Message, state: FSMContext):
    if not m.text.isdigit() or not 14 <= int(m.text) <= 80:
        return await m.answer("Yoshni to'g'ri kiriting (14–80).")
    await state.update_data(age=int(m.text))
    await m.answer("Shaxsiy rasmingizni (selfi) yuboring 📷:")
    await state.set_state(Reg.photo)


@router.message(Reg.photo, F.photo)
async def reg_photo(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    file_id = m.photo[-1].file_id
    q("INSERT OR REPLACE INTO users(id,name,surname,phone,address,age,photo,username) "
      "VALUES(?,?,?,?,?,?,?,?)",
      (m.from_user.id, d["name"], d["surname"], d["phone"], d["address"],
       d["age"], file_id, m.from_user.username or ""), commit=True)
    await state.clear()
    await bot.send_photo(
        ADMIN_ID, file_id,
        caption=(f"🆕 <b>Yangi foydalanuvchi</b>\n\n👤 {esc(d['name'])} {esc(d['surname'])}\n"
                 f"📞 {esc(d['phone'])}\n🏠 {esc(d['address'])}\n🎂 {d['age']} yosh\n"
                 f"🆔 <code>{m.from_user.id}</code>\n"
                 f"🔗 @{esc(m.from_user.username or '—')}"))
    await m.answer("✅ Ro'yxatdan o'tdingiz!", reply_markup=main_menu(m.from_user.id))
    if m.from_user.id in pending_apply:
        await begin_apply(m, state, pending_apply.pop(m.from_user.id))


@router.message(F.text == "👤 Profilim")
async def profile(m: Message):
    u = get_user(m.from_user.id)
    if not u:
        return await m.answer("Avval /start bosing.")
    await m.answer_photo(u["photo"], caption=(
        f"👤 {esc(u['name'])} {esc(u['surname'])}\n📞 {esc(u['phone'])}\n"
        f"🏠 {esc(u['address'])}\n🎂 {u['age']} yosh"))


# ---------------------------------------------------------------- E'LON BERISH
@router.message(F.text == "❌ Bekor qilish")
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Bekor qilindi.", reply_markup=main_menu(m.from_user.id))


@router.message(F.text == "📢 E'lon berish")
async def ad_start(m: Message, state: FSMContext):
    if not get_user(m.from_user.id):
        return await m.answer("Avval /start bosib ro'yxatdan o'ting.")
    await state.clear()
    await m.answer("E'lon yaratamiz.", reply_markup=cancel_kb())
    kb = inline([("☀️ Kunlik", "kind:Kunlik"), ("🗓 Oylik", "kind:Oylik")]).adjust(2)
    await m.answer("💼 Ish turini tanlang:", reply_markup=kb.as_markup())
    await state.set_state(Ad.kind)


@router.callback_query(Ad.kind, F.data.startswith("kind:"))
async def ad_kind(c: CallbackQuery, state: FSMContext):
    await state.update_data(kind=c.data[5:])
    kb = inline([(money(p), f"price:{p}") for p in PRICES]).adjust(3)
    await c.message.edit_text("💰 Narxni tanlang (so'm):", reply_markup=kb.as_markup())
    await state.set_state(Ad.price)


@router.callback_query(Ad.price, F.data.startswith("price:"))
async def ad_price(c: CallbackQuery, state: FSMContext):
    await state.update_data(price=int(c.data[6:]))
    kb = inline([("🕒 Ish vaqtini yozish", "time_go")])
    await c.message.edit_text("Ish vaqti uchun tugmani bosing 👇", reply_markup=kb.as_markup())
    await state.set_state(Ad.time)


@router.callback_query(Ad.time, F.data == "time_go")
async def ad_time_btn(c: CallbackQuery):
    await c.message.edit_text("🕒 Ish vaqtini yozing (masalan: 09:00 – 18:00):")


@router.message(Ad.time, F.text)
async def ad_time(m: Message, state: FSMContext):
    await state.update_data(time=m.text.strip())
    kb = inline([("Bugunga", "when:Bugunga"), ("Hozirga", "when:Hozirga"),
                 ("Ertaga", "when:Ertaga")]).adjust(3)
    await m.answer("📅 Ish qachonga?", reply_markup=kb.as_markup())
    await state.set_state(Ad.when)


@router.callback_query(Ad.when, F.data.startswith("when:"))
async def ad_when(c: CallbackQuery, state: FSMContext):
    await state.update_data(when=c.data[5:])
    await c.message.delete()
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(text="📍 Geolokatsiya yuborish", request_location=True))
    b.button(text="❌ Bekor qilish")
    b.adjust(1)
    await c.message.answer("📍 Ish manzilini geolokatsiya orqali yuboring:",
                           reply_markup=b.as_markup(resize_keyboard=True))
    await state.set_state(Ad.location)


@router.message(Ad.location, F.location)
async def ad_location(m: Message, state: FSMContext):
    await state.update_data(lat=m.location.latitude, lon=m.location.longitude)
    await m.answer("ℹ️ Qo'shimcha ma'lumot yozing (ish haqida, talablar...):",
                   reply_markup=cancel_kb())
    await state.set_state(Ad.extra)


def ad_text(a):
    return (f"📢 <b>YANGI ISH E'LONI</b>\n\n"
            f"💼 Ish: <b>{esc(a['kind'])}</b>\n"
            f"💰 Narxi: <b>{money(a['price'])} so'm</b>\n"
            f"🕒 Ish vaqti: {esc(a['time'])}\n"
            f"📅 Qachonga: <b>{esc(a['when'])}</b>\n"
            f"📍 <a href=\"https://maps.google.com/?q={a['lat']},{a['lon']}\">Xaritada ko'rish</a>\n\n"
            f"ℹ️ {esc(a['extra'])}")


@router.message(Ad.extra, F.text)
async def ad_extra(m: Message, state: FSMContext):
    await state.update_data(extra=m.text.strip())
    d = await state.get_data()
    kb = inline([("✅ Tasdiqlash", "ad:ok"), ("❌ Bekor qilish", "ad:no")]).adjust(2)
    await m.answer("Tekshiring:\n\n" + ad_text(d), reply_markup=kb.as_markup(),
                   disable_web_page_preview=True)
    await state.set_state(Ad.confirm)


@router.callback_query(Ad.confirm, F.data == "ad:no")
async def ad_no(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("❌ E'lon bekor qilindi.")
    await c.message.answer("Menyu:", reply_markup=main_menu(c.from_user.id))


@router.callback_query(Ad.confirm, F.data == "ad:ok")
async def ad_ok(c: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    ad_id = q("INSERT INTO ads(owner,kind,price,time,when_,lat,lon,extra) VALUES(?,?,?,?,?,?,?,?)",
              (c.from_user.id, d["kind"], d["price"], d["time"], d["when"],
               d["lat"], d["lon"], d["extra"]), commit=True)
    kb = inline([]).as_markup()
    b = InlineKeyboardBuilder()
    b.button(text="✍️ Ishga yozilish", url=f"https://t.me/{BOT_USERNAME}?start=apply_{ad_id}")
    msg = await bot.send_message(CHANNEL_ID, ad_text(d) + f"\n\n🆔 #{ad_id}",
                                 reply_markup=b.as_markup(), disable_web_page_preview=True)
    q("UPDATE ads SET msg_id=? WHERE id=?", (msg.message_id, ad_id), commit=True)
    await state.clear()
    await c.message.edit_text(f"✅ E'lon kanalga joylandi! (#{ad_id})")
    await c.message.answer("Menyu:", reply_markup=main_menu(c.from_user.id))
    await bot.send_message(ADMIN_ID, f"📢 Yangi e'lon #{ad_id} joylandi. Egasi: <code>{c.from_user.id}</code>")


# ---------------------------------------------------------------- ISHGA YOZILISH
async def begin_apply(m: Message, state: FSMContext, ad_id: int):
    ad = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    if not ad or ad["status"] != "active":
        return await m.answer("Bu e'lon topilmadi yoki yopilgan.", reply_markup=main_menu(m.chat.id))
    if ad["owner"] == m.chat.id:
        return await m.answer("O'z e'loningizga yozila olmaysiz.", reply_markup=main_menu(m.chat.id))
    if q("SELECT 1 FROM apps WHERE ad_id=? AND user_id=? AND status!='rejected'",
         (ad_id, m.chat.id), one=True):
        return await m.answer("Siz bu ishga allaqachon yozilgansiz.", reply_markup=main_menu(m.chat.id))
    await state.set_state(Apply.shot1)
    await state.update_data(ad_id=ad_id)
    await m.answer(f"✍️ E'lon #{ad_id} ga yozilish.\n\n"
                   "1️⃣ Bormoqchi bo'lgan <b>ish joyingiz</b> skrinshotini yuboring:",
                   reply_markup=cancel_kb())


@router.message(Apply.shot1, F.photo)
async def apply_shot1(m: Message, state: FSMContext):
    await state.update_data(shot1=m.photo[-1].file_id)
    await m.answer("2️⃣ Endi hozir <b>turgan joyingiz</b> skrinshotini yuboring:")
    await state.set_state(Apply.shot2)


@router.message(Apply.shot2, F.photo)
async def apply_shot2(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    app_id = q("INSERT INTO apps(ad_id,user_id,shot1,shot2) VALUES(?,?,?,?)",
               (d["ad_id"], m.from_user.id, d["shot1"], m.photo[-1].file_id), commit=True)
    await state.clear()
    u = get_user(m.from_user.id)
    await bot.send_media_group(ADMIN_ID, [
        InputMediaPhoto(media=d["shot1"], caption=f"📝 Ariza #{app_id} — ish joyi"),
        InputMediaPhoto(media=m.photo[-1].file_id, caption="Ariza beruvchining joyi")])
    kb = inline([("✅ Tasdiqlash", f"ap:ok:{app_id}"), ("❌ Rad etish", f"ap:no:{app_id}")]).adjust(2)
    await bot.send_message(
        ADMIN_ID, f"📝 <b>Ariza #{app_id}</b> (e'lon #{d['ad_id']})\n"
                  f"👤 {esc(u['name'])} {esc(u['surname'])}, {u['age']} yosh\n"
                  f"📞 {esc(u['phone'])}\n🏠 {esc(u['address'])}",
        reply_markup=kb.as_markup())
    await m.answer("⏳ Arizangiz adminga yuborildi. Tasdiqlashni kuting.",
                   reply_markup=main_menu(m.from_user.id))


@router.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("ap:"))
async def admin_app(c: CallbackQuery, bot: Bot):
    _, act, app_id = c.data.split(":")
    app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
    if not app or app["status"] != "new":
        return await c.answer("Allaqachon ko'rib chiqilgan.", show_alert=True)
    if act == "ok":
        q("UPDATE apps SET status='awaiting_pay' WHERE id=?", (app_id,), commit=True)
        await bot.send_message(
            app["user_id"],
            f"✅ Arizangiz tasdiqlandi!\n\n💳 To'lov kartasi:\n<code>{esc(setting('card'))}</code>\n"
            f"💵 Summa: <b>{esc(setting('fee'))} so'm</b>\n\n"
            "To'lov qilgach, <b>chek rasmini</b> shu yerga yuboring 📸")
        await c.message.edit_text(c.message.text + "\n\n✅ Tasdiqlandi")
    else:
        q("UPDATE apps SET status='rejected' WHERE id=?", (app_id,), commit=True)
        await bot.send_message(app["user_id"], "❌ Afsus, arizangiz rad etildi.")
        await c.message.edit_text(c.message.text + "\n\n❌ Rad etildi")


@router.message(StateFilter(None), F.photo)
async def receipt(m: Message, bot: Bot):
    app = q("SELECT * FROM apps WHERE user_id=? AND status='awaiting_pay' ORDER BY id DESC",
            (m.from_user.id,), one=True)
    if not app:
        return
    q("UPDATE apps SET receipt=?, status='paid_check' WHERE id=?",
      (m.photo[-1].file_id, app["id"]), commit=True)
    kb = inline([("✅ To'lov keldi", f"pay:ok:{app['id']}"),
                 ("❌ Yo'q", f"pay:no:{app['id']}")]).adjust(2)
    await bot.send_photo(ADMIN_ID, m.photo[-1].file_id,
                         caption=f"🧾 Ariza #{app['id']} to'lov cheki\n🆔 <code>{m.from_user.id}</code>",
                         reply_markup=kb.as_markup())
    await m.answer("⏳ Chek adminga yuborildi. Tekshirilgach xabar beramiz.")


@router.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("pay:"))
async def admin_pay(c: CallbackQuery, bot: Bot):
    _, act, app_id = c.data.split(":")
    app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
    if not app or app["status"] != "paid_check":
        return await c.answer("Allaqachon ko'rib chiqilgan.", show_alert=True)
    if act == "ok":
        q("UPDATE apps SET status='paid' WHERE id=?", (app_id,), commit=True)
        ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True)
        owner = get_user(ad["owner"])
        worker = get_user(app["user_id"])
        await bot.send_message(
            app["user_id"],
            f"✅ To'lov tasdiqlandi!\n\n📌 E'lon #{ad['id']} egasi:\n"
            f"👤 {esc(owner['name'])} {esc(owner['surname'])}\n📞 {esc(owner['phone'])}\n"
            f"📍 <a href=\"https://maps.google.com/?q={ad['lat']},{ad['lon']}\">Ish manzili</a>")
        await bot.send_message(
            ad["owner"],
            f"🙋 E'loningiz #{ad['id']} bo'yicha ishchi topildi:\n"
            f"👤 {esc(worker['name'])} {esc(worker['surname'])}, {worker['age']} yosh\n"
            f"📞 {esc(worker['phone'])}")
        await bot.send_photo(ad["owner"], worker["photo"])
        await c.message.edit_caption(caption=c.message.caption + "\n\n✅ Tasdiqlandi")
    else:
        q("UPDATE apps SET status='awaiting_pay' WHERE id=?", (app_id,), commit=True)
        await bot.send_message(app["user_id"], "❌ To'lov tasdiqlanmadi. To'g'ri chekni qayta yuboring.")
        await c.message.edit_caption(caption=c.message.caption + "\n\n❌ Rad etildi")


# ---------------------------------------------------------------- ADMIN PANEL
def admin_kb():
    return inline([
        ("📊 Statistika", "adm:stats"), ("👥 Foydalanuvchilar", "adm:users"),
        ("📢 E'lonlar", "adm:ads"), ("📝 Yangi arizalar", "adm:apps"),
        ("💳 Karta raqami", "adm:card"), ("💵 To'lov summasi", "adm:fee"),
        ("📨 Xabar yuborish", "adm:bc"), ("🚫 Bloklash", "adm:ban"),
        ("♻️ Blokdan chiqarish", "adm:unban"),
    ]).adjust(2)


@router.message(F.from_user.id == ADMIN_ID, F.text == "🛠 Admin panel")
async def admin_panel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Admin panel</b>", reply_markup=admin_kb().as_markup())


@router.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("adm:"))
async def admin_cb(c: CallbackQuery, state: FSMContext):
    act = c.data[4:]
    await c.answer()
    if act == "stats":
        total_users = q("SELECT COUNT(*) FROM users", one=True)[0]
        banned = q("SELECT COUNT(*) FROM users WHERE banned=1", one=True)[0]
        total_ads = q("SELECT COUNT(*) FROM ads", one=True)[0]
        total_apps = q("SELECT COUNT(*) FROM apps", one=True)[0]
        paid = q("SELECT COUNT(*) FROM apps WHERE status='paid'", one=True)[0]
        text = "📊 Foydalanuvchilar: " + str(total_users)
        text += "\n🚫 Bloklangan: " + str(banned)
        text += "\n📢 E'lonlar: " + str(total_ads)
        text += "\n📝 Arizalar: " + str(total_apps)
        text += "\n✅ To'langan: " + str(paid)
        await c.message.answer(text)
    elif act == "users":
        rows = q("SELECT * FROM users ORDER BY rowid DESC LIMIT 20")
        t = "\n".join(f"<code>{r['id']}</code> {esc(r['name'])} {esc(r['surname'])} {esc(r['phone'])}"
                      f"{' 🚫' if r['banned'] else ''}" for r in rows) or "Yo'q"
        await c.message.answer("👥 Oxirgi 20 ta:\n\n" + t)
    elif act == "ads":
        rows = q("SELECT * FROM ads ORDER BY id DESC LIMIT 10")
        if not rows:
            return await c.message.answer("E'lonlar yo'q.")
        for r in rows:
            kb = inline([("🔒 Yopish", f"adclose:{r['id']}")]) if r["status"] == "active" else None
            await c.message.answer(
                f"#{r['id']} | {r['kind']} | {money(r['price'])} | {r['when_']} | {r['status']}",
                reply_markup=kb.as_markup() if kb else None)
    elif act == "apps":
        rows = q("SELECT * FROM apps WHERE status IN ('new','paid_check') ORDER BY id DESC LIMIT 20")
        await c.message.answer("\n".join(f"Ariza #{r['id']} — {r['status']}" for r in rows)
                               or "Kutilayotgan arizalar yo'q.")
    elif act in ("card", "fee"):
        await state.set_state(Adm.setting)
        await state.update_data(key=act)
        await c.message.answer("Yangi qiymatni yozing:" if act == "fee"
                               else "Yangi karta raqami (va egasi ismini) yozing:")
    elif act == "bc":
        await state.set_state(Adm.broadcast)
        await c.message.answer("Hammaga yuboriladigan xabarni yozing:")
    elif act == "ban":
        await state.set_state(Adm.ban)
        await c.message.answer("Bloklanadigan foydalanuvchi ID sini yozing:")
    elif act == "unban":
        await state.set_state(Adm.unban)
        await c.message.answer("Blokdan chiqariladigan ID ni yozing:")


@router.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("adclose:"))
async def ad_close(c: CallbackQuery, bot: Bot):
    ad_id = int(c.data.split(":")[1])
    ad = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    q("UPDATE ads SET status='closed' WHERE id=?", (ad_id,), commit=True)
    try:
        await bot.edit_message_reply_markup(chat_id=CHANNEL_ID, message_id=ad["msg_id"], reply_markup=None)
        await bot.edit_message_text(chat_id=CHANNEL_ID, message_id=ad["msg_id"],
                                    text=f"❌ E'lon #{ad_id} yopildi.")
    except Exception as e:
        logging.warning(e)
    await c.message.edit_text(f"#{ad_id} yopildi 🔒")


@router.message(F.from_user.id == ADMIN_ID, Adm.setting, F.text)
async def adm_setting(m: Message, state: FSMContext):
    d = await state.get_data()
    q("UPDATE settings SET v=? WHERE k=?", (m.text.strip(), d["key"]), commit=True)
    await state.clear()
    await m.answer("✅ Saqlandi.")


@router.message(F.from_user.id == ADMIN_ID, Adm.broadcast, F.text)
async def adm_bc(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    ok = 0
    for r in q("SELECT id FROM users WHERE banned=0"):
        try:
            await bot.send_message(r["id"], m.text)
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await m.answer(f"📨 Yuborildi: {ok}")


@router.message(F.from_user.id == ADMIN_ID, Adm.ban, F.text)
async def adm_ban(m: Message, state: FSMContext):
    await state.clear()
    if m.text.strip().isdigit():
        q("UPDATE users SET banned=1 WHERE id=?", (int(m.text),), commit=True)
        await m.answer("🚫 Bloklandi.")


@router.message(F.from_user.id == ADMIN_ID, Adm.unban, F.text)
async def adm_unban(m: Message, state: FSMContext):
    await state.clear()
    if m.text.strip().isdigit():
        q("UPDATE users SET banned=0 WHERE id=?", (int(m.text),), commit=True)
        await m.answer("♻️ Blokdan chiqarildi.")


# ---------------------------------------------------------------- RUN
async def health(request):
    return web.Response(text="Bot ishlayapti")


async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", "10000")))
    await site.start()


async def main():
    global BOT_USERNAME
    await start_web()
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    BOT_USERNAME = (await bot.get_me()).username
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(BanMiddleware())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
