"""
Ish e'lonlari boti v2 (aiogram 3.x)
- Bosh admin + qo'shimcha adminlar (bot orqali qo'shiladi)
- Har bir admin o'z kartalarini saqlaydi va e'londa tanlaydi
- Foydalanuvchi balansi (to'ldirish, ishga yozilganda avtomatik yechish)
- Admin bilan bog'lanish, foydalanuvchini qidirish va anketasini ko'rish
requirements.txt:  aiogram
"""
import asyncio
import html
import logging
import re
import sqlite3
import time

from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandObject, CommandStart, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, InputMediaPhoto, KeyboardButton,
                           Message, ReplyKeyboardRemove)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = 8554402317          # BOSH ADMIN
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
  username TEXT, balance INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ads(
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, kind TEXT,
  price INTEGER, time TEXT, when_ TEXT, lat REAL, lon REAL, extra TEXT,
  status TEXT DEFAULT 'active', msg_id INTEGER, card TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS apps(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ad_id INTEGER, user_id INTEGER,
  shot1 TEXT, shot2 TEXT, receipt TEXT, status TEXT DEFAULT 'new',
  paid_by TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS admin_cards(
  id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, card TEXT);
CREATE TABLE IF NOT EXISTS topups(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
  status TEXT DEFAULT 'new');
CREATE TABLE IF NOT EXISTS ratings(
  user_id INTEGER, app_id INTEGER, score INTEGER, role TEXT, ts INTEGER,
  PRIMARY KEY(user_id, app_id));
INSERT OR IGNORE INTO settings VALUES('card','Karta raqami kiritilmagan');
INSERT OR IGNORE INTO settings VALUES('fee','10000');
""")
db.commit()
for _stmt in ("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0",
              "ALTER TABLE ads ADD COLUMN card TEXT DEFAULT ''",
              "ALTER TABLE ads ADD COLUMN people INTEGER DEFAULT 1",
              "ALTER TABLE ads ADD COLUMN addr TEXT DEFAULT ''",
              "ALTER TABLE ads ADD COLUMN contact TEXT DEFAULT ''",
              "ALTER TABLE apps ADD COLUMN paid_by TEXT DEFAULT ''",
              "ALTER TABLE apps ADD COLUMN ts INTEGER DEFAULT 0",
              "ALTER TABLE apps ADD COLUMN go TEXT DEFAULT ''"):
    try:
        db.execute(_stmt)
        db.commit()
    except sqlite3.OperationalError:
        pass


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


def fee_int():
    d = re.sub(r"\D", "", setting("fee"))
    return int(d) if d else 0


def is_main(uid):
    return uid == ADMIN_ID


def is_admin(uid):
    return uid == ADMIN_ID or q("SELECT 1 FROM admins WHERE id=?", (uid,), one=True) is not None


def handler_for(ad):
    """Ariza va cheklar kimga boradi: e'lon egasi admin bo'lsa o'zi, aks holda bosh admin."""
    return ad["owner"] if is_admin(ad["owner"]) else ADMIN_ID


def can_manage(uid, ad):
    return uid == ADMIN_ID or uid == handler_for(ad)


class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u and is_admin(u.id))


ADM = IsAdmin()
MAIN = F.from_user.id == ADMIN_ID


# ---------------------------------------------------------------- States
class Reg(StatesGroup):
    name = State(); surname = State(); phone = State()
    address = State(); age = State(); photo = State()


class Ad(StatesGroup):
    kind = State(); price = State(); time = State(); when = State()
    people = State(); addr = State(); contact = State()
    location = State(); extra = State(); card = State(); confirm = State()


class Apply(StatesGroup):
    shot1 = State(); shot2 = State()


class Topup(StatesGroup):
    amount = State(); receipt = State()


class Contact(StatesGroup):
    msg = State()


class Adm(StatesGroup):
    setting = State(); broadcast = State(); ban = State(); unban = State()
    find = State(); bal = State(); addadmin = State(); addcard = State(); reply = State()


router = Router()
pending_apply = {}


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u and u.id != ADMIN_ID:
            row = get_user(u.id)
            if row and row["banned"]:
                return
        return await handler(event, data)


# ---------------------------------------------------------------- Klaviaturalar
def main_menu(uid):
    b = ReplyKeyboardBuilder()
    for t in ("📢 E'lon berish", "📋 Mening ishlarim", "💰 Hisobim", "⭐ Baholar",
              "📞 Admin bilan bog'lanish", "👤 Profilim"):
        b.button(text=t)
    if is_admin(uid):
        b.button(text="🛠 Admin panel")
    b.adjust(2, 2, 2, 1)
    return b.as_markup(resize_keyboard=True)


def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="❌ Bekor qilish")
    return b.as_markup(resize_keyboard=True)


def inline(rows, width=2):
    b = InlineKeyboardBuilder()
    for text, data in rows:
        b.button(text=text, callback_data=data)
    b.adjust(width)
    return b.as_markup()


# ---------------------------------------------------------------- START / RO'YXAT
@router.message(F.text == "❌ Bekor qilish")
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Bekor qilindi.", reply_markup=main_menu(m.from_user.id))


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
    await m.answer("Shaxsiy rasmingizni yuboring 📷\n\n❗️ Hozir <b>old (selfi) kamera</b> bilan o'zingizni rasmga olib yuboring. "
                   "Galereyadan, uzatilgan yoki boshqa odamning rasmi qabul qilinmaydi.")
    await state.set_state(Reg.photo)


@router.message(Reg.photo, F.photo)
async def reg_photo(m: Message, state: FSMContext, bot: Bot):
    if getattr(m, "forward_origin", None) or getattr(m, "forward_date", None):
        return await m.answer("❌ Uzatilgan rasm qabul qilinmaydi. O'zingizni old kamerada rasmga olib yuboring 📷")
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
        f"🏠 {esc(u['address'])}\n🎂 {u['age']} yosh\n💰 Balans: {money(u['balance'])} so'm"))


# ---------------------------------------------------------------- HISOB (BALANS)
@router.message(F.text == "💰 Hisobim")
async def my_balance(m: Message):
    u = get_user(m.from_user.id)
    if not u:
        return await m.answer("Avval /start bosing.")
    await m.answer(
        f"💰 Balansingiz: <b>{money(u['balance'])} so'm</b>\n\n"
        f"Ishga yozilganda xizmat haqi ({money(fee_int())} so'm) shu hisobdan avtomatik yechiladi. "
        "Balans yetmasa, to'lovni kartaga o'tkazib chek yuborasiz.",
        reply_markup=inline([("➕ Hisobni to'ldirish", "topup")], 1))


@router.callback_query(F.data == "topup")
async def topup_start(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Topup.amount)
    await c.message.answer("Qancha so'm to'ldirmoqchisiz? Summani raqamda yozing (masalan: 50000):",
                           reply_markup=cancel_kb())


@router.message(Topup.amount, F.text)
async def topup_amount(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or int(digits) < 1000:
        return await m.answer("Summani to'g'ri kiriting (kamida 1 000).")
    await state.update_data(amount=int(digits))
    await state.set_state(Topup.receipt)
    await m.answer(f"💳 Shu kartaga <b>{money(int(digits))} so'm</b> o'tkazing:\n"
                   f"<code>{esc(setting('card'))}</code>\n\n"
                   "To'lovdan keyin <b>chek rasmini</b> yuboring 📸")


@router.message(Topup.receipt, F.photo)
async def topup_receipt(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    tid = q("INSERT INTO topups(user_id,amount) VALUES(?,?)", (m.from_user.id, d["amount"]), commit=True)
    u = get_user(m.from_user.id)
    await bot.send_photo(
        ADMIN_ID, m.photo[-1].file_id,
        caption=(f"💰 <b>Balans to'ldirish #{tid}</b>\n👤 {esc(u['name'])} {esc(u['surname'])}\n"
                 f"🆔 <code>{u['id']}</code>\nSumma: <b>{money(d['amount'])} so'm</b>"),
        reply_markup=inline([("✅ Qo'shish", f"tp:ok:{tid}"), ("❌ Rad etish", f"tp:no:{tid}")]))
    await m.answer("⏳ Chek adminga yuborildi. Tasdiqlangach balansingiz to'ldiriladi.",
                   reply_markup=main_menu(m.from_user.id))


@router.callback_query(MAIN, F.data.startswith("tp:"))
async def topup_admin(c: CallbackQuery, bot: Bot):
    _, act, tid = c.data.split(":")
    t = q("SELECT * FROM topups WHERE id=?", (tid,), one=True)
    if not t or t["status"] != "new":
        return await c.answer("Allaqachon ko'rib chiqilgan.", show_alert=True)
    if act == "ok":
        q("UPDATE topups SET status='ok' WHERE id=?", (tid,), commit=True)
        q("UPDATE users SET balance=balance+? WHERE id=?", (t["amount"], t["user_id"]), commit=True)
        bal = get_user(t["user_id"])["balance"]
        await bot.send_message(t["user_id"], f"✅ Hisobingiz {money(t['amount'])} so'mga to'ldirildi.\n"
                                             f"💰 Balans: {money(bal)} so'm")
        await c.message.edit_caption(caption=c.message.html_caption + "\n\n✅ Qo'shildi")
    else:
        q("UPDATE topups SET status='no' WHERE id=?", (tid,), commit=True)
        await bot.send_message(t["user_id"], "❌ To'lov tasdiqlanmadi. Admin bilan bog'laning.")
        await c.message.edit_caption(caption=c.message.html_caption + "\n\n❌ Rad etildi")


# ---------------------------------------------------------------- ADMIN BILAN BOG'LANISH
@router.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_start(m: Message, state: FSMContext):
    if not get_user(m.from_user.id):
        return await m.answer("Avval /start bosing.")
    await state.set_state(Contact.msg)
    await m.answer("Adminga xabaringizni yozing (matn, rasm yoki ovozli xabar):", reply_markup=cancel_kb())


@router.message(Contact.msg)
async def contact_send(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    u = get_user(m.from_user.id)
    await bot.send_message(
        ADMIN_ID, f"📩 <b>Xabar</b>: {esc(u['name'])} {esc(u['surname'])}\n"
                  f"🆔 <code>{u['id']}</code> | 📞 {esc(u['phone'])}",
        reply_markup=inline([("↩️ Javob berish", f"rp:{u['id']}"), ("🔎 Anketa", f"u:{u['id']}")]))
    await bot.copy_message(ADMIN_ID, m.chat.id, m.message_id)
    await m.answer("✅ Xabaringiz adminga yuborildi. Javobni shu yerda olasiz.",
                   reply_markup=main_menu(m.from_user.id))


@router.callback_query(MAIN, F.data.startswith("rp:"))
async def reply_start(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Adm.reply)
    await state.update_data(uid=int(c.data[3:]))
    await c.message.answer("Javobingizni yozing:")


@router.message(MAIN, Adm.reply, F.text)
async def reply_send(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(d["uid"], "📩 <b>Admin javobi:</b>\n\n" + esc(m.text))
        await m.answer("✅ Yuborildi.")
    except Exception:
        await m.answer("Yuborib bo'lmadi.")


# ---------------------------------------------------------------- E'LON BERISH
def row_dict(r):
    d = dict(r)
    d["when"] = d.get("when_")
    return d


def taken_count(ad_id):
    return q("SELECT COUNT(*) FROM apps WHERE ad_id=? AND status='paid'", (ad_id,), one=True)[0]


def reserved_count(ad_id):
    return q("SELECT COUNT(*) FROM apps WHERE ad_id=? AND status IN "
             "('awaiting_pay','paid_check','paid')", (ad_id,), one=True)[0]


def ad_text(a, ad_id=None, status=None):
    lat, lon = a.get("lat"), a.get("lon")
    if lat is not None and lon is not None:
        place = f"📍 <a href=\"https://maps.google.com/?q={lat},{lon}\">Xaritada ko'rish</a>"
        if a.get("addr"):
            place += f"\n🏠 {esc(a['addr'])}"
    else:
        place = f"📍 Manzil: <b>{esc(a.get('addr') or '—')}</b>"
    t = (f"📢 <b>YANGI ISH E'LONI</b>\n\n"
         f"💼 Ish: <b>{esc(a['kind'])}</b>\n"
         f"💰 Narxi: <b>{money(a['price'])} so'm</b>\n"
         f"👥 Odam soni: <b>{a.get('people') or 1}</b>\n"
         f"🕒 Ish vaqti: {esc(a['time'])}\n"
         f"📅 Qachonga: <b>{esc(a['when'])}</b>\n"
         f"{place}\n\n"
         f"ℹ️ {esc(a['extra'])}")
    if ad_id:
        t += f"\n\n🆔 #{ad_id}"
    if status:
        t += f"\n\n📌 Holat: <b>{status}</b>"
    return t


def ad_status(r):
    """Kanal e'loni tagidagi holat matni va 'Ishga yozilish' tugmasi kerakmi."""
    taken = taken_count(r["id"])
    people = r["people"] or 1
    if r["status"] == "closed":
        return ("odam olindi" if taken else "odam olinmadi"), False
    if taken >= people:
        return "odam olindi ✅", False
    return f"odam olinmadi ({taken}/{people})", True


def apply_kb(ad_id):
    b = InlineKeyboardBuilder()
    b.button(text="✍️ Ishga yozilish", url=f"https://t.me/{BOT_USERNAME}?start=apply_{ad_id}")
    return b.as_markup()


async def post_to_channel(bot, ad_id):
    r = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    st, btn = ad_status(r)
    msg = await bot.send_message(CHANNEL_ID, ad_text(row_dict(r), ad_id, st),
                                 reply_markup=apply_kb(ad_id) if btn else None,
                                 disable_web_page_preview=True)
    q("UPDATE ads SET msg_id=?, status='active' WHERE id=?", (msg.message_id, ad_id), commit=True)


async def refresh_channel(bot, ad_id):
    """E'lon kanalda qoladi, faqat tagidagi holat yangilanadi."""
    r = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    if not r or not r["msg_id"] or r["status"] in ("pending", "rejected"):
        return
    st, btn = ad_status(r)
    try:
        await bot.edit_message_text(chat_id=CHANNEL_ID, message_id=r["msg_id"],
                                    text=ad_text(row_dict(r), ad_id, st),
                                    reply_markup=apply_kb(ad_id) if btn else None,
                                    disable_web_page_preview=True)
    except Exception as e:
        logging.warning(e)


def all_admin_ids():
    ids = [ADMIN_ID] + [r["id"] for r in q("SELECT id FROM admins")]
    return list(dict.fromkeys(ids))


adv_msgs = {}


async def send_for_approval(bot, ad_id):
    r = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    owner = get_user(r["owner"])
    text = ("🆕 <b>E'lonni tasdiqlash so'rovi</b>\n"
            f"👤 {esc(owner['name'])} {esc(owner['surname'])} | 🆔 <code>{owner['id']}</code>\n\n"
            + ad_text(row_dict(r), ad_id))
    kb = inline([("✅ Tasdiqlash", f"adv:ok:{ad_id}"), ("❌ Rad etish", f"adv:no:{ad_id}")])
    sent = []
    for aid in all_admin_ids():
        try:
            m = await bot.send_message(aid, text, reply_markup=kb, disable_web_page_preview=True)
            sent.append((aid, m.message_id))
        except Exception as e:
            logging.warning(e)
    adv_msgs[ad_id] = sent


@router.callback_query(ADM, F.data.startswith("adv:"))
async def ad_review(c: CallbackQuery, bot: Bot):
    _, act, ad_id = c.data.split(":")
    ad_id = int(ad_id)
    r = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    if not r or r["status"] != "pending":
        return await c.answer("Allaqachon ko'rib chiqilgan.", show_alert=True)
    who = esc(c.from_user.full_name)
    if act == "ok":
        q("UPDATE ads SET status='active' WHERE id=?", (ad_id,), commit=True)
        await post_to_channel(bot, ad_id)
        note = f"✅ Tasdiqladi: {who}"
        owner_msg = f"✅ E'loningiz #{ad_id} tasdiqlandi va kanalga joylandi."
    else:
        q("UPDATE ads SET status='rejected' WHERE id=?", (ad_id,), commit=True)
        note = f"❌ Rad etdi: {who}"
        owner_msg = f"❌ E'loningiz #{ad_id} rad etildi."
    try:
        await bot.send_message(r["owner"], owner_msg)
    except Exception:
        pass
    for aid, mid in adv_msgs.pop(ad_id, []):
        try:
            await bot.edit_message_reply_markup(chat_id=aid, message_id=mid, reply_markup=None)
        except Exception:
            pass
    await append_note(c.message, note)
    await c.answer()


@router.message(F.text == "📢 E'lon berish")
async def ad_start(m: Message, state: FSMContext):
    if not get_user(m.from_user.id):
        return await m.answer("Avval /start bosib ro'yxatdan o'ting.")
    await state.clear()
    await m.answer("E'lon yaratamiz.", reply_markup=cancel_kb())
    kb = inline([("☀️ Kunlik", "kind:Kunlik"), ("🗓 Oylik", "kind:Oylik")])
    await m.answer("💼 Ish turini tanlang:", reply_markup=kb)
    await state.set_state(Ad.kind)


@router.callback_query(Ad.kind, F.data.startswith("kind:"))
async def ad_kind(c: CallbackQuery, state: FSMContext):
    await state.update_data(kind=c.data[5:])
    kb = inline([(money(p), f"price:{p}") for p in PRICES], 3)
    await c.message.edit_text("💰 Narxni tanlang (so'm):", reply_markup=kb)
    await state.set_state(Ad.price)


@router.callback_query(Ad.price, F.data.startswith("price:"))
async def ad_price(c: CallbackQuery, state: FSMContext):
    await state.update_data(price=int(c.data[6:]))
    kb = inline([(str(i), f"ppl:{i}") for i in range(1, 16)], 5)
    await c.message.edit_text("👥 Nechta odam kerak? Tugmani bosing:", reply_markup=kb)
    await state.set_state(Ad.people)


@router.callback_query(Ad.people, F.data.startswith("ppl:"))
async def ad_people(c: CallbackQuery, state: FSMContext):
    await state.update_data(people=int(c.data[4:]))
    await c.message.edit_text("Ish vaqti uchun tugmani bosing 👇",
                              reply_markup=inline([("🕒 Ish vaqtini yozish", "time_go")], 1))
    await state.set_state(Ad.time)


@router.callback_query(Ad.time, F.data == "time_go")
async def ad_time_btn(c: CallbackQuery):
    await c.message.edit_text("🕒 Ish vaqtini yozing (masalan: 09:00 – 18:00):")


@router.message(Ad.time, F.text)
async def ad_time(m: Message, state: FSMContext):
    await state.update_data(time=m.text.strip())
    kb = inline([("Bugunga", "when:Bugunga"), ("Hozirga", "when:Hozirga"), ("Ertaga", "when:Ertaga")], 3)
    await m.answer("📅 Ish qachonga?", reply_markup=kb)
    await state.set_state(Ad.when)


@router.callback_query(Ad.when, F.data.startswith("when:"))
async def ad_when(c: CallbackQuery, state: FSMContext):
    await state.update_data(when=c.data[5:])
    await c.message.delete()
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(text="📍 Geolokatsiya yuborish", request_location=True))
    text = "📍 Ish manzilini geolokatsiya orqali yuboring:"
    if is_admin(c.from_user.id):
        b.button(text="✏️ Manzilni yozish")
        text = "📍 Geolokatsiya yuboring yoki «✏️ Manzilni yozish» ni bosing:"
    b.button(text="❌ Bekor qilish")
    b.adjust(1)
    await c.message.answer(text, reply_markup=b.as_markup(resize_keyboard=True))
    await state.set_state(Ad.location)


async def ask_extra(m, state):
    await m.answer("ℹ️ Qo'shimcha ma'lumot yozing (ish haqida, talablar...):", reply_markup=cancel_kb())
    await state.set_state(Ad.extra)


@router.message(Ad.location, F.location)
async def ad_location(m: Message, state: FSMContext):
    await state.update_data(lat=m.location.latitude, lon=m.location.longitude, addr="")
    await ask_extra(m, state)


@router.message(Ad.location, ADM, F.text == "✏️ Manzilni yozish")
async def ad_addr_start(m: Message, state: FSMContext):
    await state.set_state(Ad.addr)
    await m.answer("✏️ Ish manzilini yozing (shahar, ko'cha, mo'ljal):", reply_markup=cancel_kb())


@router.message(Ad.addr, F.text)
async def ad_addr(m: Message, state: FSMContext):
    await state.update_data(lat=None, lon=None, addr=m.text.strip())
    await ask_extra(m, state)


async def show_preview(m, state):
    d = await state.get_data()
    kb = inline([("✅ Tasdiqlash", "ad:ok"), ("❌ Bekor qilish", "ad:no")])
    extra_line = ""
    if is_admin(m.chat.id):
        extra_line = (f"\n\n📞 Ish beruvchi raqami: {esc(d.get('contact', ''))}"
                      f"\n💳 To'lov kartasi: <code>{esc(d.get('card') or setting('card'))}</code>")
    else:
        extra_line = "\n\n⏳ E'lon adminlar tasdiqlagandan keyin kanalga joylanadi."
    await m.answer("Tekshiring:\n\n" + ad_text(d) + extra_line, reply_markup=kb,
                   disable_web_page_preview=True)
    await state.set_state(Ad.confirm)


async def ask_card(m, state):
    uid = m.chat.id
    rows = q("SELECT * FROM admin_cards WHERE admin_id=?", (uid,))
    buttons = [(r["card"][:30], f"ac:{r['id']}") for r in rows]
    buttons.append(("⭐ Standart karta", "ac:0"))
    await m.answer("💳 Ishga yozilganlar to'lov qiladigan kartani tanlang:",
                   reply_markup=inline(buttons, 1))
    await state.set_state(Ad.card)


@router.message(Ad.extra, F.text)
async def ad_extra(m: Message, state: FSMContext):
    await state.update_data(extra=m.text.strip(), card="", contact="")
    if not is_admin(m.from_user.id):
        return await show_preview(m, state)
    await m.answer("📞 Ish beruvchining telefon raqamini yozing.\n"
                   "Ishga yozilib to'lov qilganlarga shu raqam beriladi (sizning raqamingiz emas):")
    await state.set_state(Ad.contact)


@router.message(Ad.contact, F.text)
async def ad_contact(m: Message, state: FSMContext):
    if len(re.sub(r"\D", "", m.text)) < 7:
        return await m.answer("Telefon raqamini to'g'ri yozing (masalan: +998901234567).")
    await state.update_data(contact=m.text.strip())
    await ask_card(m, state)


@router.callback_query(Ad.card, F.data.startswith("ac:"))
async def ad_card(c: CallbackQuery, state: FSMContext):
    cid = int(c.data[3:])
    card = ""
    if cid:
        r = q("SELECT * FROM admin_cards WHERE id=? AND admin_id=?", (cid, c.from_user.id), one=True)
        card = r["card"] if r else ""
    await state.update_data(card=card)
    await c.message.delete()
    await show_preview(c.message, state)


@router.callback_query(Ad.confirm, F.data == "ad:no")
async def ad_no(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("❌ E'lon bekor qilindi.")
    await c.message.answer("Menyu:", reply_markup=main_menu(c.from_user.id))


@router.callback_query(Ad.confirm, F.data == "ad:ok")
async def ad_ok(c: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    uid = c.from_user.id
    admin = is_admin(uid)
    ad_id = q("INSERT INTO ads(owner,kind,price,people,time,when_,lat,lon,addr,extra,card,contact,status) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (uid, d["kind"], d["price"], d.get("people", 1), d["time"], d["when"],
               d.get("lat"), d.get("lon"), d.get("addr", ""), d["extra"], d.get("card", ""),
               d.get("contact", ""), "active" if admin else "pending"), commit=True)
    if admin:
        await post_to_channel(bot, ad_id)
        await c.message.edit_text(f"✅ E'lon kanalga joylandi! (#{ad_id})")
        if uid != ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"📢 Yangi e'lon #{ad_id} joylandi. Admin: <code>{uid}</code>")
    else:
        await send_for_approval(bot, ad_id)
        await c.message.edit_text(f"⏳ E'lon #{ad_id} adminlarga yuborildi. "
                                  "Tasdiqlangach kanalga joylanadi.")
    await c.message.answer("Menyu:", reply_markup=main_menu(uid))


# ---------------------------------------------------------------- ISHGA YOZILISH
ACTIVE_ST = ("awaiting_pay", "paid_check", "paid")
HOLD_12H = 12 * 3600


async def append_note(msg, note):
    try:
        if msg.photo or msg.caption is not None:
            await msg.edit_caption(caption=(msg.html_caption or "") + "\n\n" + note, reply_markup=None)
        else:
            await msg.edit_text((msg.html_text or "") + "\n\n" + note, reply_markup=None,
                                disable_web_page_preview=True)
    except Exception as e:
        logging.warning(e)


def place_text(ad):
    if ad["lat"] is not None and ad["lon"] is not None:
        return f"📍 <a href=\"https://maps.google.com/?q={ad['lat']},{ad['lon']}\">Ish manzili</a>" + \
               (f"\n🏠 {esc(ad['addr'])}" if ad["addr"] else "")
    return f"📍 Manzil: {esc(ad['addr'] or '—')}"


async def begin_apply(m: Message, state: FSMContext, ad_id: int):
    uid = m.chat.id
    ad = q("SELECT * FROM ads WHERE id=?", (ad_id,), one=True)
    if not ad or ad["status"] != "active":
        return await m.answer("Bu e'lon topilmadi yoki yopilgan.", reply_markup=main_menu(uid))
    if ad["owner"] == uid:
        return await m.answer("O'z e'loningizga yozila olmaysiz.", reply_markup=main_menu(uid))
    if q("SELECT 1 FROM apps WHERE ad_id=? AND user_id=? AND status NOT IN "
         "('rejected','cancelled','cancelled_admin')", (ad_id, uid), one=True):
        return await m.answer("Siz bu ishga allaqachon yozilgansiz.", reply_markup=main_menu(uid))
    if reserved_count(ad_id) >= (ad["people"] or 1):
        return await m.answer("❌ Afsus, bu e'longa kerakli odam to'lgan.", reply_markup=main_menu(uid))
    last = q("SELECT ts FROM apps WHERE user_id=? AND status IN "
             "('awaiting_pay','paid_check','paid','cancelled') ORDER BY ts DESC LIMIT 1", (uid,), one=True)
    if last and time.time() - last["ts"] < HOLD_12H:
        left = int(HOLD_12H - (time.time() - last["ts"]))
        return await m.answer(f"⏳ 12 soatda faqat 1 ta ishga yozilish mumkin.\n"
                              f"Yana {left // 3600} soat {left % 3600 // 60} daqiqadan keyin yoza olasiz.",
                              reply_markup=main_menu(uid))
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


async def approve_app(bot, app_id):
    """Ariza avtomatik tasdiqlanadi. Balans yetsa avtomatik yechiladi, aks holda chek so'raladi."""
    app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
    ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True)
    user = get_user(app["user_id"])
    fee = fee_int()
    if fee <= 0 or user["balance"] >= fee:
        q("UPDATE users SET balance=balance-? WHERE id=?", (max(fee, 0), user["id"]), commit=True)
        q("UPDATE apps SET status='paid', paid_by='balance' WHERE id=?", (app_id,), commit=True)
        await bot.send_message(user["id"], f"✅ Arizangiz tasdiqlandi!\n💰 Hisobingizdan {money(fee)} so'm "
                                           f"yechildi. Qoldiq: {money(user['balance'] - max(fee, 0))} so'm")
        await release_contacts(bot, app_id)
        await refresh_channel(bot, ad["id"])
        return "balance"
    q("UPDATE apps SET status='awaiting_pay' WHERE id=?", (app_id,), commit=True)
    card = ad["card"] or setting("card")
    await bot.send_message(
        user["id"],
        f"✅ Arizangiz tasdiqlandi!\n\n💳 To'lov kartasi:\n<code>{esc(card)}</code>\n"
        f"💵 Summa: <b>{money(fee)} so'm</b>\n\n"
        "To'lov qilgach, <b>chek rasmini</b> shu yerga yuboring 📸\n"
        "💡 Keyingi safar tezroq bo'lishi uchun «💰 Hisobim» orqali balansni to'ldirib qo'ying.")
    return "card"


@router.message(Apply.shot2, F.photo)
async def apply_shot2(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    ad = q("SELECT * FROM ads WHERE id=?", (d["ad_id"],), one=True)
    if not ad or ad["status"] != "active" or reserved_count(ad["id"]) >= (ad["people"] or 1):
        return await m.answer("❌ Afsus, bu e'longa kerakli odam to'ldi.",
                              reply_markup=main_menu(m.from_user.id))
    app_id = q("INSERT INTO apps(ad_id,user_id,shot1,shot2,ts) VALUES(?,?,?,?,?)",
               (d["ad_id"], m.from_user.id, d["shot1"], m.photo[-1].file_id, int(time.time())),
               commit=True)
    await m.answer("✅ Ariza qabul qilindi.", reply_markup=main_menu(m.from_user.id))
    mode = await approve_app(bot, app_id)
    target = handler_for(ad)
    u = get_user(m.from_user.id)
    try:
        await bot.send_media_group(target, [
            InputMediaPhoto(media=d["shot1"], caption=f"📝 Ariza #{app_id} — ish joyi"),
            InputMediaPhoto(media=m.photo[-1].file_id, caption="Ariza beruvchining joyi")])
        note = ("✅ Balansdan yechildi" if mode == "balance"
                else "⏳ To'lov kutilmoqda (chek kelganda tasdiqlaysiz)")
        await bot.send_message(
            target, f"📝 <b>Ariza #{app_id}</b> (e'lon #{d['ad_id']}) — avtomatik tasdiqlandi\n"
                    f"👤 {esc(u['name'])} {esc(u['surname'])}, {u['age']} yosh\n"
                    f"📞 {esc(u['phone'])}\n🏠 {esc(u['address'])}\n{note}",
            reply_markup=inline([("🚫 Chaqirmaslik (bekor qilish)", f"cx:{app_id}")], 1))
    except Exception as e:
        logging.warning(e)


def rate_kb(app_id):
    return inline([(f"{i}⭐", f"rt:{app_id}:{i}") for i in range(1, 6)], 5)


async def ask_rating(bot, uid, app_id):
    try:
        await bot.send_message(uid, "⭐ Xizmatimizni baholang: 1 — yomon, 5 — a'lo",
                               reply_markup=rate_kb(app_id))
    except Exception:
        pass


async def release_contacts(bot, app_id):
    app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
    ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True)
    owner = get_user(ad["owner"])
    worker = get_user(app["user_id"])
    phone = ad["contact"] or owner["phone"]
    who = ""
    if not is_admin(ad["owner"]):
        who = f"👤 {esc(owner['name'])} {esc(owner['surname'])}\n"
    await bot.send_message(
        app["user_id"],
        f"✅ To'lov qabul qilindi!\n\n📌 E'lon #{ad['id']} ish beruvchisi:\n{who}"
        f"📞 {esc(phone)}\n{place_text(ad)}\n\n"
        "Borishingizni tasdiqlang yoki bekor qiling 👇",
        reply_markup=inline([("✅ Boraman", f"go:y:{app_id}"), ("❌ Bormayman", f"go:n:{app_id}")]),
        disable_web_page_preview=True)
    cap = (f"🙋 E'loningiz #{ad['id']} bo'yicha ishchi topildi:\n"
           f"👤 {esc(worker['name'])} {esc(worker['surname'])}, {worker['age']} yosh\n"
           f"📞 {esc(worker['phone'])}")
    kb = inline([("🚫 Chaqirmaslik (bekor qilish)", f"cx:{app_id}")], 1)
    for t in dict.fromkeys([ad["owner"], handler_for(ad)]):
        try:
            await bot.send_photo(t, worker["photo"], caption=cap, reply_markup=kb)
        except Exception as e:
            logging.warning(e)
    await ask_rating(bot, app["user_id"], app_id)
    await ask_rating(bot, ad["owner"], app_id)


@router.callback_query(F.data.startswith("go:"))
async def worker_choice(c: CallbackQuery, bot: Bot):
    _, act, app_id = c.data.split(":")
    app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
    if not app or app["user_id"] != c.from_user.id or app["status"] not in ACTIVE_ST:
        return await c.answer("Bu ariza endi faol emas.", show_alert=True)
    ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True)
    u = get_user(c.from_user.id)
    targets = list(dict.fromkeys([ad["owner"], handler_for(ad)]))
    who = f"{esc(u['name'])} {esc(u['surname'])}, {esc(u['phone'])}"
    if act == "y":
        q("UPDATE apps SET go='yes' WHERE id=?", (app_id,), commit=True)
        for t in targets:
            try:
                await bot.send_message(t, f"✅ Ishchi {who} e'lon #{ad['id']} ga borishini tasdiqladi.")
            except Exception:
                pass
        await c.answer("Tasdiqlandi ✅")
        await c.message.edit_reply_markup(reply_markup=inline([("❌ Bekor qilish", f"go:n:{app_id}")], 1))
    else:
        q("UPDATE apps SET status='cancelled', go='no' WHERE id=?", (app_id,), commit=True)
        for t in targets:
            try:
                await bot.send_message(t, f"❌ Ishchi {who} e'lon #{ad['id']} ga bormaslikni tanladi (ariza bekor).")
            except Exception:
                pass
        await refresh_channel(bot, ad["id"])
        await c.answer("Bekor qilindi")
        await append_note(c.message, "❌ Siz bu ishni bekor qildingiz.")


@router.callback_query(F.data.startswith("cx:"))
async def cancel_worker(c: CallbackQuery, bot: Bot):
    app = q("SELECT * FROM apps WHERE id=?", (c.data[3:],), one=True)
    ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True) if app else None
    if not app or not ad:
        return await c.answer("Ariza topilmadi.", show_alert=True)
    if not (c.from_user.id == ad["owner"] or can_manage(c.from_user.id, ad)):
        return await c.answer("Bu ariza sizniki emas.", show_alert=True)
    if app["status"] not in ACTIVE_ST:
        return await c.answer("Allaqachon bekor qilingan.", show_alert=True)
    q("UPDATE apps SET status='cancelled_admin', go='no' WHERE id=?", (app["id"],), commit=True)
    try:
        await bot.send_message(app["user_id"], f"❌ Afsus, e'lon #{ad['id']} bo'yicha sizni ishga "
                                               "chaqirmaslikka qaror qilindi. Savollar bo'lsa, "
                                               "«📞 Admin bilan bog'lanish» orqali yozing.")
    except Exception:
        pass
    await refresh_channel(bot, ad["id"])
    await c.answer("Bekor qilindi")
    await append_note(c.message, "🚫 Ishchi chaqirilmaydi (bekor qilindi)")


@router.message(F.text == "📋 Mening ishlarim")
async def my_jobs(m: Message):
    if not get_user(m.from_user.id):
        return await m.answer("Avval /start bosing.")
    rows = q("SELECT apps.*, ads.kind, ads.price, ads.when_, ads.time AS atime FROM apps "
             "JOIN ads ON ads.id=apps.ad_id WHERE apps.user_id=? AND apps.status IN "
             "('awaiting_pay','paid_check','paid') ORDER BY apps.id DESC LIMIT 10", (m.from_user.id,))
    if not rows:
        return await m.answer("Hozircha faol ishlaringiz yo'q.")
    names = {"awaiting_pay": "💳 to'lov kutilmoqda", "paid_check": "🧾 chek tekshirilmoqda",
             "paid": "✅ to'langan"}
    for r in rows:
        btns = []
        if r["status"] == "paid" and r["go"] != "yes":
            btns.append(("✅ Boraman", f"go:y:{r['id']}"))
        btns.append(("❌ Bekor qilish" if r["go"] == "yes" or r["status"] != "paid"
                     else "❌ Bormayman", f"go:n:{r['id']}"))
        await m.answer(f"📌 E'lon #{r['ad_id']} | {esc(r['kind'])} | {money(r['price'])} so'm\n"
                       f"📅 {esc(r['when_'])} | 🕒 {esc(r['atime'])}\n"
                       f"Holat: {names[r['status']]}" + (" | borishni tasdiqlagansiz" if r["go"] == "yes" else ""),
                       reply_markup=inline(btns, 2))


# ---- baholash
def stars(avg):
    n = int(round(avg))
    return "⭐" * n + "☆" * (5 - n)


@router.message(F.text == "⭐ Baholar")
async def ratings_panel(m: Message):
    rows = q("SELECT score, role FROM ratings")
    if not rows:
        t = "⭐ Hali baholar yo'q. Birinchi bo'lib baholang!"
    else:
        n = len(rows)
        avg = sum(r["score"] for r in rows) / n
        t = (f"⭐ <b>Xizmatimiz bahosi</b>\n\nUmumiy o'rtacha: <b>{avg:.1f} / 5</b> {stars(avg)}\n"
             f"Baholar soni: {n}\n\n")
        for sc in (5, 4, 3, 2, 1):
            t += f"{sc}⭐ — {sum(1 for r in rows if r['score'] == sc)} ta\n"
        for role, label in (("owner", "📢 E'lon beruvchilar"), ("worker", "👷 Ishga boruvchilar")):
            sub = [r["score"] for r in rows if r["role"] == role]
            if sub:
                t += f"\n{label}: {sum(sub) / len(sub):.1f} / 5 ({len(sub)} ta)"
    await m.answer(t, reply_markup=inline([("⭐ Baholash", "rt_open")], 1))


@router.callback_query(F.data == "rt_open")
async def rate_open(c: CallbackQuery):
    await c.answer()
    await c.message.answer("Xizmatimizni baholang: 1 — yomon, 5 — a'lo", reply_markup=rate_kb(0))


@router.callback_query(F.data.startswith("rt:"))
async def rate_cb(c: CallbackQuery):
    _, app_id, score = c.data.split(":")
    app_id, score = int(app_id), int(score)
    if not 1 <= score <= 5:
        return await c.answer()
    role = "general"
    if app_id:
        app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
        if not app:
            return await c.answer("Topilmadi.", show_alert=True)
        role = "worker" if c.from_user.id == app["user_id"] else "owner"
    q("INSERT OR REPLACE INTO ratings(user_id,app_id,score,role,ts) VALUES(?,?,?,?,?)",
      (c.from_user.id, app_id, score, role, int(time.time())), commit=True)
    await c.answer("Rahmat!")
    try:
        await c.message.edit_text(f"⭐ Baholaganingiz uchun rahmat! Bahoyingiz: {score}/5")
    except Exception:
        pass


@router.message(StateFilter(None), F.photo)
async def receipt(m: Message, bot: Bot):
    app = q("SELECT * FROM apps WHERE user_id=? AND status='awaiting_pay' ORDER BY id DESC",
            (m.from_user.id,), one=True)
    if not app:
        return await m.answer("Hozir sizdan chek kutilmayapti. Menyudan tanlang 👇",
                              reply_markup=main_menu(m.from_user.id))
    ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True)
    q("UPDATE apps SET receipt=?, status='paid_check' WHERE id=?",
      (m.photo[-1].file_id, app["id"]), commit=True)
    await bot.send_photo(handler_for(ad), m.photo[-1].file_id,
                         caption=f"🧾 Ariza #{app['id']} to'lov cheki\n🆔 <code>{m.from_user.id}</code>",
                         reply_markup=inline([("✅ To'lov keldi", f"pay:ok:{app['id']}"),
                                              ("❌ Yo'q", f"pay:no:{app['id']}")]))
    await m.answer("⏳ Chek tekshirilmoqda. Tasdiqlangach xabar beramiz.")


@router.callback_query(ADM, F.data.startswith("pay:"))
async def admin_pay(c: CallbackQuery, bot: Bot):
    _, act, app_id = c.data.split(":")
    app = q("SELECT * FROM apps WHERE id=?", (app_id,), one=True)
    if not app or app["status"] != "paid_check":
        return await c.answer("Allaqachon ko'rib chiqilgan.", show_alert=True)
    ad = q("SELECT * FROM ads WHERE id=?", (app["ad_id"],), one=True)
    if not can_manage(c.from_user.id, ad):
        return await c.answer("Bu ariza sizniki emas.", show_alert=True)
    if act == "ok":
        q("UPDATE apps SET status='paid', paid_by='card' WHERE id=?", (app_id,), commit=True)
        await release_contacts(bot, int(app_id))
        await refresh_channel(bot, ad["id"])
        await c.message.edit_caption(caption=c.message.html_caption + "\n\n✅ Tasdiqlandi")
    else:
        q("UPDATE apps SET status='awaiting_pay' WHERE id=?", (app_id,), commit=True)
        await bot.send_message(app["user_id"], "❌ To'lov tasdiqlanmadi. To'g'ri chekni qayta yuboring.")
        await c.message.edit_caption(caption=c.message.html_caption + "\n\n❌ Rad etildi")


# ---------------------------------------------------------------- ADMIN PANEL
def admin_kb(uid):
    if is_main(uid):
        return inline([
            ("📊 Statistika", "adm:stats"), ("🔎 Foydalanuvchi qidirish", "adm:find"),
            ("👥 Foydalanuvchilar", "adm:users"), ("📢 E'lonlar", "adm:ads"),
            ("📝 Arizalar", "adm:apps"), ("💰 Balans berish", "adm:bal"),
            ("👮 Adminlar", "adm:admins"), ("💳 Kartalarim", "adm:cards"),
            ("⭐ Standart karta", "set:card"), ("💵 Xizmat narxi", "set:fee"),
            ("📨 Xabar yuborish", "adm:bc"), ("🚫 Bloklash", "adm:ban"),
            ("♻️ Blokdan chiqarish", "adm:unban"),
        ])
    return inline([("🔎 Foydalanuvchi qidirish", "adm:find"), ("👥 Foydalanuvchilar", "adm:users"),
                   ("💳 Kartalarim", "adm:cards"), ("📝 Arizalarim", "adm:apps")], 1)


@router.message(ADM, F.text == "🛠 Admin panel")
async def admin_panel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Admin panel</b>", reply_markup=admin_kb(m.from_user.id))


async def send_user_card(m, uid):
    u = get_user(uid)
    if not u:
        return await m.answer("Foydalanuvchi topilmadi.")
    ads_n = q("SELECT COUNT(*) FROM ads WHERE owner=?", (uid,), one=True)[0]
    apps_n = q("SELECT COUNT(*) FROM apps WHERE user_id=?", (uid,), one=True)[0]
    role = "👮 Admin" if is_admin(uid) else "Foydalanuvchi"
    blocked = "ha" if u["banned"] else "yo'q"
    cap = (f"👤 <b>{esc(u['name'])} {esc(u['surname'])}</b> ({role})\n"
           f"📞 {esc(u['phone'])}\n🏠 {esc(u['address'])}\n🎂 {u['age']} yosh\n"
           f"🆔 <code>{uid}</code>\n🔗 @{esc(u['username'] or '—')}\n"
           f"💰 Balans: <b>{money(u['balance'])} so'm</b>\n"
           f"📢 E'lonlari: {ads_n} | 📝 Arizalari: {apps_n}\n🚫 Bloklangan: {blocked}")
    kb = None
    if is_main(m.chat.id):
        kb = inline([
            ("💰 Balans o'zgartirish", f"bal:{uid}"), ("✉️ Xabar yozish", f"rp:{uid}"),
            ("♻️ Blokdan chiqarish" if u["banned"] else "🚫 Bloklash",
             f"unban:{uid}" if u["banned"] else f"ban:{uid}"),
        ], 1)
    await m.answer_photo(u["photo"], caption=cap, reply_markup=kb)


def users_buttons(rows):
    return inline([(f"{r['name']} {r['surname']} | {r['phone']}", f"u:{r['id']}") for r in rows], 1)


def search_users(t):
    t = t.strip()
    if t.isdigit():
        r = get_user(int(t))
        if r:
            return [r]
        return q("SELECT * FROM users WHERE REPLACE(phone,'+','') LIKE ? LIMIT 10", ("%" + t[-9:] + "%",))
    if t.startswith("@"):
        return q("SELECT * FROM users WHERE username=? COLLATE NOCASE", (t[1:],))
    like = "%" + t + "%"
    return q("SELECT * FROM users WHERE name LIKE ? OR surname LIKE ? OR username LIKE ? LIMIT 10",
             (like, like, like))


@router.callback_query(ADM, F.data.startswith("u:"))
async def user_card_cb(c: CallbackQuery):
    await c.answer()
    await send_user_card(c.message, int(c.data[2:]))


@router.message(ADM, Adm.find, F.text)
async def adm_find(m: Message, state: FSMContext):
    await state.clear()
    rows = search_users(m.text)
    if not rows:
        return await m.answer("Hech narsa topilmadi.")
    if len(rows) == 1:
        return await send_user_card(m, rows[0]["id"])
    await m.answer("Topilganlar, birini tanlang:", reply_markup=users_buttons(rows))


SET_PROMPTS = {
    "card": "Standart karta raqami (va egasi) ni yozing.\n"
            "U balans to'ldirish va oddiy foydalanuvchilar e'lonlari uchun ishlatiladi:",
    "fee": "Ishga yozilish xizmat haqini yozing (faqat raqam, masalan: 10000):",
}


@router.callback_query(MAIN, F.data.startswith("set:"))
async def set_start(c: CallbackQuery, state: FSMContext):
    key = c.data[4:]
    await c.answer()
    await state.set_state(Adm.setting)
    await state.update_data(key=key)
    await c.message.answer(SET_PROMPTS[key])


@router.message(MAIN, Adm.setting, F.text)
async def set_save(m: Message, state: FSMContext):
    d = await state.get_data()
    val = m.text.strip()
    if d["key"] == "fee":
        digits = re.sub(r"\D", "", val)
        if not digits:
            return await m.answer("Faqat raqam yozing.")
        val = digits
    q("UPDATE settings SET v=? WHERE k=?", (val, d["key"]), commit=True)
    await state.clear()
    await m.answer("✅ Saqlandi.")


# ---- kartalar (hamma adminlar uchun)
async def show_cards(m, uid):
    rows = q("SELECT * FROM admin_cards WHERE admin_id=?", (uid,))
    for r in rows:
        await m.answer(f"💳 <code>{esc(r['card'])}</code>",
                       reply_markup=inline([("🗑 O'chirish", f"dc:{r['id']}")], 1))
    if not rows:
        await m.answer("Sizda saqlangan karta yo'q.")
    await m.answer("E'lon berayotganda shu kartalardan birini tanlaysiz.",
                   reply_markup=inline([("➕ Karta qo'shish", "addcard")], 1))


@router.callback_query(ADM, F.data == "addcard")
async def addcard_start(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Adm.addcard)
    await c.message.answer("Karta raqami va egasi ismini yozing\n(masalan: 8600 1234 5678 9012 Ali V.):")


@router.message(ADM, Adm.addcard, F.text)
async def addcard_save(m: Message, state: FSMContext):
    await state.clear()
    q("INSERT INTO admin_cards(admin_id,card) VALUES(?,?)", (m.from_user.id, m.text.strip()[:80]), commit=True)
    await m.answer("✅ Karta saqlandi.")


@router.callback_query(ADM, F.data.startswith("dc:"))
async def delcard(c: CallbackQuery):
    q("DELETE FROM admin_cards WHERE id=? AND admin_id=?", (int(c.data[3:]), c.from_user.id), commit=True)
    await c.answer("O'chirildi", show_alert=True)
    await c.message.delete()


# ---- Arizalar ro'yxati
@router.callback_query(ADM, F.data == "adm:apps")
async def adm_apps(c: CallbackQuery):
    await c.answer()
    base = ("SELECT apps.*, ads.owner, u.name, u.surname, u.phone FROM apps "
            "JOIN ads ON ads.id=apps.ad_id JOIN users u ON u.id=apps.user_id "
            "WHERE apps.status IN ('awaiting_pay','paid_check','paid') ")
    if is_main(c.from_user.id):
        rows = q(base + "ORDER BY apps.id DESC LIMIT 15")
    else:
        rows = q(base + "AND ads.owner=? ORDER BY apps.id DESC LIMIT 15", (c.from_user.id,))
    if not rows:
        return await c.message.answer("Faol arizalar yo'q.")
    names = {"awaiting_pay": "to'lov kutilmoqda", "paid_check": "chek tekshiriladi", "paid": "to'langan"}
    for r in rows:
        go = " | borishini tasdiqlagan" if r["go"] == "yes" else ""
        await c.message.answer(
            f"Ariza #{r['id']} (e'lon #{r['ad_id']}) — {esc(r['name'])} {esc(r['surname'])}, "
            f"{esc(r['phone'])}\nHolat: {names[r['status']]}{go}",
            reply_markup=inline([("🚫 Chaqirmaslik (bekor qilish)", f"cx:{r['id']}")], 1))


@router.callback_query(ADM, F.data == "adm:find")
async def adm_find_start(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Adm.find)
    await c.message.answer("Qidirish uchun ism, familiya, telefon, @username yoki ID yozing:",
                           reply_markup=cancel_kb())


@router.callback_query(ADM, F.data == "adm:users")
async def adm_users(c: CallbackQuery):
    await c.answer()
    rows = q("SELECT * FROM users ORDER BY rowid DESC LIMIT 20")
    if not rows:
        return await c.message.answer("Foydalanuvchilar yo'q.")
    await c.message.answer("👥 Oxirgi 20 ta. Anketasini ko'rish uchun tanlang:",
                           reply_markup=users_buttons(rows))


@router.callback_query(ADM, F.data == "adm:cards")
async def adm_cards(c: CallbackQuery):
    await c.answer()
    await show_cards(c.message, c.from_user.id)


# ---- bosh admin funksiyalari
@router.callback_query(MAIN, F.data.startswith("adm:"))
async def admin_cb(c: CallbackQuery, state: FSMContext):
    act = c.data[4:]
    await c.answer()
    if act == "stats":
        def n(sql):
            return q(sql, one=True)[0]
        t = "📊 Foydalanuvchilar: " + str(n("SELECT COUNT(*) FROM users"))
        t += "\n👮 Qo'shimcha adminlar: " + str(n("SELECT COUNT(*) FROM admins"))
        t += "\n🚫 Bloklangan: " + str(n("SELECT COUNT(*) FROM users WHERE banned=1"))
        t += "\n📢 E'lonlar: " + str(n("SELECT COUNT(*) FROM ads"))
        t += "\n⏳ Tasdiq kutayotgan e'lonlar: " + str(n("SELECT COUNT(*) FROM ads WHERE status='pending'"))
        t += "\n📝 Arizalar: " + str(n("SELECT COUNT(*) FROM apps"))
        t += "\n✅ To'langan: " + str(n("SELECT COUNT(*) FROM apps WHERE status='paid'"))
        avg = n("SELECT COALESCE(AVG(score),0) FROM ratings")
        t += f"\n⭐ O'rtacha baho: {avg:.1f} ({n('SELECT COUNT(*) FROM ratings')} ta)"
        t += "\n💰 Jami balanslar: " + money(n("SELECT COALESCE(SUM(balance),0) FROM users")) + " so'm"
        await c.message.answer(t)
    elif act == "ads":
        rows = q("SELECT * FROM ads ORDER BY id DESC LIMIT 10")
        if not rows:
            return await c.message.answer("E'lonlar yo'q.")
        for r in rows:
            kb = None
            if r["status"] == "active":
                kb = inline([("🔒 Yopish", f"adclose:{r['id']}")], 1)
            elif r["status"] == "pending":
                kb = inline([("✅ Tasdiqlash", f"adv:ok:{r['id']}"), ("❌ Rad etish", f"adv:no:{r['id']}")])
            await c.message.answer(
                f"#{r['id']} | {r['kind']} | {money(r['price'])} | {r['when_']} | {r['status']} | egasi: {r['owner']}",
                reply_markup=kb)
    elif act == "bal":
        await state.set_state(Adm.bal)
        await state.update_data(uid=0)
        await c.message.answer("Format: <code>ID summa</code> (masalan: 123456789 50000)\n"
                               "Ayirish uchun minus: <code>123456789 -20000</code>")
    elif act == "admins":
        rows = q("SELECT * FROM admins")
        for r in rows:
            u = get_user(r["id"])
            name = f"{u['name']} {u['surname']}" if u else "Noma'lum"
            await c.message.answer(f"👮 {esc(name)} (<code>{r['id']}</code>)",
                                   reply_markup=inline([("🗑 Olib tashlash", f"da:{r['id']}")], 1))
        if not rows:
            await c.message.answer("Qo'shimcha adminlar yo'q.")
        await c.message.answer("Yangi admin qo'shish:", reply_markup=inline([("➕ Admin qo'shish", "addadmin")], 1))
    elif act == "bc":
        await state.set_state(Adm.broadcast)
        await c.message.answer("Hammaga yuboriladigan xabarni yozing:")
    elif act == "ban":
        await state.set_state(Adm.ban)
        await c.message.answer("Bloklanadigan foydalanuvchi ID sini yozing:")
    elif act == "unban":
        await state.set_state(Adm.unban)
        await c.message.answer("Blokdan chiqariladigan ID ni yozing:")


@router.callback_query(MAIN, F.data == "addadmin")
async def addadmin_start(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Adm.addadmin)
    await c.message.answer("Yangi admin ID, telefon yoki @username ini yozing.\n"
                           "(U avval botga /start bosib ro'yxatdan o'tgan bo'lishi kerak)")


@router.message(MAIN, Adm.addadmin, F.text)
async def addadmin_save(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    rows = search_users(m.text)
    if len(rows) != 1:
        return await m.answer("Aniq bitta foydalanuvchi topilmadi. ID bilan urinib ko'ring.")
    u = rows[0]
    if is_admin(u["id"]):
        return await m.answer("Bu foydalanuvchi allaqachon admin.")
    q("INSERT OR IGNORE INTO admins VALUES(?)", (u["id"],), commit=True)
    await m.answer(f"✅ {esc(u['name'])} {esc(u['surname'])} admin qilindi.")
    try:
        await bot.send_message(u["id"], "👮 Siz admin etib tayinlandingiz!\n"
                                        "/start bosing, menyuda «🛠 Admin panel» chiqadi. "
                                        "U yerdan o'z kartangizni qo'shing.")
    except Exception:
        pass


@router.callback_query(MAIN, F.data.startswith("da:"))
async def deladmin(c: CallbackQuery, bot: Bot):
    uid = int(c.data[3:])
    q("DELETE FROM admins WHERE id=?", (uid,), commit=True)
    q("DELETE FROM admin_cards WHERE admin_id=?", (uid,), commit=True)
    await c.answer("Admin olib tashlandi", show_alert=True)
    await c.message.delete()
    try:
        await bot.send_message(uid, "Siz endi admin emassiz.", reply_markup=main_menu(uid))
    except Exception:
        pass


# ---- balans berish
@router.callback_query(MAIN, F.data.startswith("bal:"))
async def bal_from_card(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Adm.bal)
    await state.update_data(uid=int(c.data[4:]))
    await c.message.answer("Summani yozing (qo'shish uchun 50000, ayirish uchun -20000):")


@router.message(MAIN, Adm.bal, F.text)
async def bal_save(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    parts = m.text.split()
    uid = d.get("uid", 0)
    if uid:
        amount_s = parts[0] if parts else ""
    else:
        if len(parts) != 2 or not parts[0].isdigit():
            return await m.answer("Format noto'g'ri. Masalan: 123456789 50000")
        uid, amount_s = int(parts[0]), parts[1]
    if not re.fullmatch(r"-?\d+", amount_s):
        return await m.answer("Summa faqat raqam bo'lishi kerak.")
    u = get_user(uid)
    if not u:
        await state.clear()
        return await m.answer("Foydalanuvchi topilmadi.")
    amount = int(amount_s)
    new = u["balance"] + amount
    if new < 0:
        return await m.answer(f"Balans manfiy bo'lib qoladi (hozir {money(u['balance'])}). Boshqa summa yozing.")
    q("UPDATE users SET balance=? WHERE id=?", (new, uid), commit=True)
    await state.clear()
    await m.answer(f"✅ {esc(u['name'])} balansi: {money(u['balance'])} → <b>{money(new)} so'm</b>")
    sign = "to'ldirildi" if amount >= 0 else "kamaytirildi"
    try:
        await bot.send_message(uid, f"💰 Hisobingiz {money(abs(amount))} so'mga {sign}.\n"
                                    f"Balans: {money(new)} so'm")
    except Exception:
        pass


# ---- e'lonni yopish, bloklash, xabar
@router.callback_query(MAIN, F.data.startswith("adclose:"))
async def ad_close(c: CallbackQuery, bot: Bot):
    ad_id = int(c.data.split(":")[1])
    q("UPDATE ads SET status='closed' WHERE id=?", (ad_id,), commit=True)
    await refresh_channel(bot, ad_id)
    await c.message.edit_text(f"#{ad_id} yopildi 🔒 (kanalda holati bilan qoladi)")


@router.callback_query(MAIN, F.data.startswith("ban:"))
async def ban_cb(c: CallbackQuery):
    q("UPDATE users SET banned=1 WHERE id=?", (int(c.data[4:]),), commit=True)
    await c.answer("Bloklandi", show_alert=True)


@router.callback_query(MAIN, F.data.startswith("unban:"))
async def unban_cb(c: CallbackQuery):
    q("UPDATE users SET banned=0 WHERE id=?", (int(c.data[6:]),), commit=True)
    await c.answer("Blokdan chiqarildi", show_alert=True)


@router.message(MAIN, Adm.broadcast, F.text)
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


@router.message(MAIN, Adm.ban, F.text)
async def adm_ban(m: Message, state: FSMContext):
    await state.clear()
    if m.text.strip().isdigit():
        q("UPDATE users SET banned=1 WHERE id=?", (int(m.text),), commit=True)
        await m.answer("🚫 Bloklandi.")


@router.message(MAIN, Adm.unban, F.text)
async def adm_unban(m: Message, state: FSMContext):
    await state.clear()
    if m.text.strip().isdigit():
        q("UPDATE users SET banned=0 WHERE id=?", (int(m.text),), commit=True)
        await m.answer("♻️ Blokdan chiqarildi.")


# ---------------------------------------------------------------- Javobsiz xabarlar
@router.message(StateFilter(None))
async def fallback(m: Message):
    if get_user(m.from_user.id):
        await m.answer("Menyudan tanlang 👇", reply_markup=main_menu(m.from_user.id))
    else:
        await m.answer("Boshlash uchun /start bosing.")


@router.message(~StateFilter(None))
async def wrong_input(m: Message):
    await m.answer("Iltimos, so'ralgan ma'lumotni yuboring yoki «❌ Bekor qilish» ni bosing.")


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
    return runner


async def main():
    global BOT_USERNAME
    logging.basicConfig(level=logging.INFO)
    runner = await start_web()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        BOT_USERNAME = (await bot.get_me()).username
        dp = Dispatcher(storage=MemoryStorage())
        dp.update.outer_middleware(BanMiddleware())
        dp.include_router(router)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
