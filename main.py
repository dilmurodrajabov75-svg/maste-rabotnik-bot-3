import json
import os
import threading
import time
from flask import Flask
from telebot import TeleBot, types

# ==================== SOZLAMALAR ====================
TOKEN = "8603747344:AAECBz0DiO3ZCfUknqXtfreLYxc5LNdnCOs"
BOT_USERNAME = "Master_rabotnikbot"
CHANNEL_ID = "@ish_keremidi"
ADMIN_ID = 8554402317  # Sizning Telegram ID-ingiz

KARTA_RAQAMI = "4413 5976 0016 9336"
KARTA_EGASI = "Rajabov Dilmurod"
XIZMAT_HAQQI = "30 000"
# ====================================================

# --- 24/7 Server qismi ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Master Rabotnik Bot ishlamoqda!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask, daemon=True).start()

bot = TeleBot(TOKEN)

# --- Ma'lumotlar bazasi ---
def load_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

users_db = load_data("users.json")
posts_db = load_data("posts.json")
user_temp = {}
admin_post_temp = {}


# --- 1. START ---
@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = str(message.from_user.id)
    args = message.text.split()

    if len(args) > 1 and args[0].startswith("/start"):
        param = args[1]
        if param.startswith("job_"):
            post_id = param.replace("job_", "")
            if post_id in posts_db:
                post = posts_db[post_id]
                text = (
                    f"📌 **E'lon ma'lumotlari:**\n\n"
                    f"🏢 **Hudud:** {post['manzil']}\n"
                    f"💰 **Ish haqqi:** {post['ish_haqqi']}\n"
                    f"📞 **Aloqa:** {post['phone']}\n\n"
                    f"⚠️ Bog'lanish uchun yuqoridagi raqamga qo'ng'iroq qiling yoki yozing."
                )
                bot.send_message(message.chat.id, text, parse_mode="Markdown")
                return

    if user_id in users_db:
        if users_db[user_id].get("status") == "blocked":
            bot.send_message(message.chat.id, "❌ Siz botdan foydalanish huquqidan mahrum qilingansiz.")
            return
        if users_db[user_id].get("status") == "pending":
            bot.send_message(message.chat.id, "⏳ Sizning to'lovingiz adminga yuborilgan. Tasdiqlashini kuting.")
            return
        if users_db[user_id].get("status") == "active":
            main_menu(message.chat.id)
            return

    user_temp[user_id] = {"step": "full_name"}
    bot.send_message(
        message.chat.id,
        "👋 Assalomu alaykum! Master Rabotnik botiga xush kelibsiz.\n\n"
        "Ro'yxatdan o'tish uchun F.I.O. (Familiya Ism Sharifingizni) kiriting:"
    )


# --- 2. RO'YXATDAN O'TISH ---
@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_temp and user_temp[str(msg.from_user.id)]["step"] == "full_name")
def get_full_name(message):
    user_id = str(message.from_user.id)
    user_temp[user_id]["full_name"] = message.text
    user_temp[user_id]["step"] = "phone"
    bot.send_message(message.chat.id, "📞 Telefon raqamingizni yuboring (Masalan: +998901234567):")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_temp and user_temp[str(msg.from_user.id)]["step"] == "phone")
def get_phone(message):
    user_id = str(message.from_user.id)
    user_temp[user_id]["phone"] = message.text
    user_temp[user_id]["step"] = "region"
    bot.send_message(message.chat.id, "📍 Qaysi viloyatdansiz?:")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_temp and user_temp[str(msg.from_user.id)]["step"] == "region")
def get_region(message):
    user_id = str(message.from_user.id)
    user_temp[user_id]["region"] = message.text
    user_temp[user_id]["step"] = "district"
    bot.send_message(message.chat.id, "🏙️ Tuman yoki shahringizni kiriting:")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_temp and user_temp[str(msg.from_user.id)]["step"] == "district")
def get_district(message):
    user_id = str(message.from_user.id)
    user_temp[user_id]["district"] = message.text
    user_temp[user_id]["step"] = "profession"
    bot.send_message(message.chat.id, "🛠️ Mutaxassisligingiz (Masalan: Santexnik, Malyar):")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_temp and user_temp[str(msg.from_user.id)]["step"] == "profession")
def get_profession(message):
    user_id = str(message.from_user.id)
    user_temp[user_id]["profession"] = message.text
    user_temp[user_id]["step"] = "waiting_receipt"

    text = (
        f"✅ Ma'lumotlaringiz olindi!\n\n"
        f"Xizmat haqqi: **{XIZMAT_HAQQI} so'm**.\n"
        f"💳 **Karta raqami:** `{KARTA_RAQAMI}`\n"
        f"👤 **Karta egasi:** {KARTA_EGASI}\n\n"
        f"Pulni o'tkazgach, chek rasmini yuboring!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# --- 3. CHEK ---
@bot.message_handler(content_types=['photo'], func=lambda msg: str(msg.from_user.id) in user_temp and user_temp[str(msg.from_user.id)]["step"] == "waiting_receipt")
def get_receipt(message):
    user_id = str(message.from_user.id)
    photo_id = message.photo[-1].file_id
    data = user_temp[user_id]

    users_db[user_id] = {
        "full_name": data["full_name"],
        "phone": data["phone"],
        "region": data["region"],
        "district": data["district"],
        "profession": data["profession"],
        "status": "pending"
    }
    save_data("users.json", users_db)
    del user_temp[user_id]

    admin_text = (
        f"🔔 **Yangi to'lov cheki!**\n\n"
        f"👤 F.I.O: {data['full_name']}\n"
        f"📞 Tel: {data['phone']}\n"
        f"📍 Manzil: {data['region']}, {data['district']}\n"
        f"🛠️ Kasbi: {data['profession']}\n"
        f"🆔 ID: `{user_id}`"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")
    )

    bot.send_photo(ADMIN_ID, photo_id, caption=admin_text, reply_markup=markup, parse_mode="Markdown")
    bot.send_message(message.chat.id, "⏳ Chekingiz adminga yuborildi.")


# --- 4. MENYU ---
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📋 Ish e'lon qilish", "👤 Profilim")
    bot.send_message(chat_id, "Asosiy menyu:", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "👤 Profilim")
def profile_handler(message):
    user_id = str(message.from_user.id)
    if user_id in users_db:
        u = users_db[user_id]
        text = (
            f"👤 **Profil:**\n\n"
            f"F.I.O: {u['full_name']}\n"
            f"Tel: {u['phone']}\n"
            f"Hudud: {u['region']}, {u['district']}\n"
            f"Kasb: {u['profession']}\n"
            f"Status: Faol ✅"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")


# --- 5. E'LON BERISH ---
@bot.message_handler(func=lambda msg: msg.text == "📋 Ish e'lon qilish")
def post_job_start(message):
    user_id = str(message.from_user.id)
    if user_id not in users_db or users_db[user_id].get("status") != "active":
        bot.send_message(message.chat.id, "❌ Siz ro'yxatdan o'tmagansiz yoki to'lovingiz tasdiqlanmagan.")
        return

    admin_post_temp[user_id] = {"step": "region"}
    bot.send_message(message.chat.id, "📍 E'lon uchun viloyatni kiriting:")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in admin_post_temp and admin_post_temp[str(msg.from_user.id)]["step"] == "region")
def post_region(message):
    user_id = str(message.from_user.id)
    admin_post_temp[user_id]["region"] = message.text
    admin_post_temp[user_id]["step"] = "district"
    bot.send_message(message.chat.id, "🏙️ Tumanni kiriting:")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in admin_post_temp and admin_post_temp[str(msg.from_user.id)]["step"] == "district")
def post_district(message):
    user_id = str(message.from_user.id)
    admin_post_temp[user_id]["district"] = message.text
    admin_post_temp[user_id]["step"] = "workers"
    bot.send_message(message.chat.id, "👷 Kerakli ishchilar soni va mutaxassisligi:")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in admin_post_temp and admin_post_temp[str(msg.from_user.id)]["step"] == "workers")
def post_workers(message):
    user_id = str(message.from_user.id)
    admin_post_temp[user_id]["workers"] = message.text
    admin_post_temp[user_id]["step"] = "salary"
    bot.send_message(message.chat.id, "💰 Ish haqqi qancha?")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in admin_post_temp and admin_post_temp[str(msg.from_user.id)]["step"] == "salary")
def post_salary(message):
    user_id = str(message.from_user.id)
    admin_post_temp[user_id]["salary"] = message.text
    admin_post_temp[user_id]["step"] = "date"
    bot.send_message(message.chat.id, "📅 Qachonga kerak?")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in admin_post_temp and admin_post_temp[str(msg.from_user.id)]["step"] == "date")
def post_date(message):
    user_id = str(message.from_user.id)
    admin_post_temp[user_id]["date"] = message.text
    admin_post_temp[user_id]["step"] = "details"
    bot.send_message(message.chat.id, "📝 Qo'shimcha ma'lumot yoki aloqa uchun telefon/username:")


@bot.message_handler(func=lambda msg: str(msg.from_user.id) in admin_post_temp and admin_post_temp[str(msg.from_user.id)]["step"] == "details")
def post_details(message):
    user_id = str(message.from_user.id)
    data = admin_post_temp[user_id]
    data["details"] = message.text

    post_id = str(int(time.time()))[-4:]
    posts_db[post_id] = {
        "ish_haqqi": data["salary"],
        "manzil": f"{data['region']}, {data['district']}",
        "phone": data["details"],
    }
    save_data("posts.json", posts_db)

    caption = (
        f"📍 Hudud: {data['region']} ({data['district']})\n"
        f"👷 Ishchilar: {data['workers']}\n"
        f"💰 Ish haqqi: {data['salary']}\n"
        f"📅 Sana: {data['date']}\n"
        f"📝 Batafsil: {data['details']}\n\n"
        f"🟢 Holat: Faol\n"
        f"#{post_id}"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "📋 Ishga yozilish",
            url=f"https://t.me/{BOT_USERNAME}?start=job_{post_id}",
        )
    )

    bot.send_message(CHANNEL_ID, caption, reply_markup=keyboard, parse_mode="Markdown")
    bot.send_message(message.chat.id, f"✅ E'lon kanalga joylandi! (ID: #{post_id})", parse_mode="Markdown")
    del admin_post_temp[user_id]


# --- 6. CALLBACK ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    if data.startswith("approve_"):
        user_id = data.replace("approve_", "")
        if user_id in users_db:
            users_db[user_id]["status"] = "active"
            save_data("users.json", users_db)
            bot.send_message(user_id, "✅ To'lovingiz tasdiqlandi!")
            bot.answer_callback_query(call.id, "Tasdiqlandi!")
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n✅ **TASDIQLANDI**", parse_mode="Markdown")
    elif data.startswith("reject_"):
        user_id = data.replace("reject_", "")
        if user_id in users_db:
            users_db[user_id]["status"] = "blocked"
            save_data("users.json", users_db)
            bot.send_message(user_id, "❌ To'lovingiz rad etildi.")
            bot.answer_callback_query(call.id, "Rad etildi!")
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n❌ **RAD ETILDI**", parse_mode="Markdown")


if __name__ == "__main__":
    bot.infinity_polling()
  
