import json
import os
import threading
import time
from flask import Flask
from telebot import TeleBot, types

# ================= SOZLAMALAR =================
TOKEN = "8603747344:AAECBz0DiO3ZCfUknqXtfreLYxc5LNdnCOs"
BOT_USERNAME = "Master_rabotnikbot"
CHANNEL_ID = "@ish_keremidi"
ADMIN_ID = 8554402317  # Sizning Telegram ID-ingiz

KARTA_RAQAMI = "4413 5976 0016 9336"
KARTA_EGASI = "Rajabov Dilmurod"
XIZMAT_HAQQI = "30 000"
# ==============================================

# --- 24/7 Server qismi (Replit uxlab qolmasligi uchun) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Master Rabotnik Bot ishlamoqda!"


def run_flask():
  app.run(host="0.0.0.0", port=8080)


threading.Thread(target=run_flask, daemon=True).start()
bot = TeleBot(TOKEN)

# Bot buyruqlari va qolgan qismi...


# --- Ma'lumotlar bazasini yuklash va saqlash ---
def load_data(filename):
  if os.path.exists(filename):
    try:
      with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}


def save_data(filename, data):
  with open(filename, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)


users_db = load_data("users.json")
posts_db = load_data("posts.json")
user_temp = {}


# --- 1. START BUYRUG'I VA BLOK/RO'YXAT TEKSHIRUVI ---
@bot.message_handler(commands=["start"])
def start_command(message):
  user_id = str(message.from_user.id)
  args = message.text.split()

  # Bloklangan foydalanuvchini tekshirish
  if users_db.get(user_id, {}).get("warnings", 0) >= 3 or users_db.get(
      user_id, {}
  ).get("blocked"):
    bot.send_message(
        user_id,
        "🚫 Siz feyk chek yuborganingiz uchun tizimdan avtomatik bloklangansiz!",
    )
    return

  # Ro'yxatdan o'tmagan bo'lsa
  if user_id not in users_db or not users_db[user_id].get("registered"):
    user_temp[user_id] = {"step": "name", "target_job": None}
    if len(args) > 1 and args[1].startswith("job_"):
      user_temp[user_id]["target_job"] = args[1].replace("job_", "")

    bot.send_message(
        user_id,
        "👋 Salom! Ishga yozilish uchun avval ro'yxatdan o'tishingiz kerak.\n\n"
        "1️⃣ Ism va familiyangizni kiriting:\n*(Masalan: Ali Valiyev)*",
        parse_mode="Markdown",
    )
    return

  # Ro'yxatdan o'tgan bo'lsa va e'lon orqali kirgan bo'lsa
  if len(args) > 1 and args[1].startswith("job_"):
    send_payment_info(user_id, args[1].replace("job_", ""))
  else:
    bot.send_message(
        user_id,
        "Siz ro'yxatdan o'tgansiz! Ishga yozilish uchun @ish_keremidi kanalidan e'lonni tanlang.",
    )


# --- 2. RO'YXATDAN O'TISH BOSQICHLARI ---
@bot.message_handler(
    func=lambda msg: str(msg.from_user.id) in user_temp
    and user_temp[str(msg.from_user.id)].get("step") == "name"
)
def reg_name(message):
  user_id = str(message.from_user.id)
  user_temp[user_id]["full_name"] = message.text
  user_temp[user_id]["step"] = "phone"

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
  markup.add(
      types.KeyboardButton(
          "📱 Telefon raqamni yuborish", request_contact=True
      )
  )
  bot.send_message(
      user_id,
      "2️⃣ Telefon raqamingizni yuboring:",
      reply_markup=markup,
      parse_mode="Markdown",
  )


@bot.message_handler(
    content_types=["contact", "text"],
    func=lambda msg: str(msg.from_user.id) in user_temp
    and user_temp[str(msg.from_user.id)].get("step") == "phone",
)
def reg_phone(message):
  user_id = str(message.from_user.id)
  phone = (
      message.contact.phone_number
      if message.contact
      else message.text
  )
  user_temp[user_id]["phone"] = phone
  user_temp[user_id]["step"] = "age"

  bot.send_message(
      user_id,
      "3️⃣ Yoshingizni kiriting:",
      reply_markup=types.ReplyKeyboardRemove(),
      parse_mode="Markdown",
  )
@bot.message_handler(
    func=lambda msg: str(msg.from_user.id) in user_temp
    and user_temp[str(msg.from_user.id)].get("step") == "age"
)
def reg_age(message):
  user_id = str(message.from_user.id)
  user_temp[user_id]["age"] = message.text
  user_temp[user_id]["step"] = "gender"

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
  markup.add("👨 Erkak", "👩 Ayol")
  bot.send_message(
      user_id,
      "4️⃣ Jinsingizni tanlang:",
      reply_markup=markup,
      parse_mode="Markdown",
  )


@bot.message_handler(
    func=lambda msg: str(msg.from_user.id) in user_temp
    and user_temp[str(msg.from_user.id)].get("step") == "gender"
)
def reg_gender(message):
  user_id = str(message.from_user.id)
  user_temp[user_id]["gender"] = message.text
  user_temp[user_id]["step"] = "passport"

  bot.send_message(
      user_id,
      "5️⃣ Pasportingiz rasmini yuboring:",
      reply_markup=types.ReplyKeyboardRemove(),
      parse_mode="Markdown",
  )


@bot.message_handler(
    content_types=["photo"],
    func=lambda msg: str(msg.from_user.id) in user_temp
    and user_temp[str(msg.from_user.id)].get("step") == "passport",
)
def reg_passport(message):
  user_id = str(message.from_user.id)
  user_temp[user_id]["passport_photo"] = message.photo[-1].file_id
  user_temp[user_id]["step"] = "photo"

  bot.send_message(
      user_id,
      "6️⃣ O'zingizning shaxsiy 1 ta rasmingizni yuboring:",
      parse_mode="Markdown",
  )


@bot.message_handler(
    content_types=["photo"],
    func=lambda msg: str(msg.from_user.id) in user_temp
    and user_temp[str(msg.from_user.id)].get("step") == "photo",
)
def reg_photo(message):
  user_id = str(message.from_user.id)
  data = user_temp[user_id]
  selfie_photo = message.photo[-1].file_id

  # Bazaga saqlash
  users_db[user_id] = {
      "registered": True,
      "full_name": data["full_name"],
      "phone": data["phone"],
      "age": data["age"],
      "gender": data["gender"],
      "passport": data["passport_photo"],
      "selfie": selfie_photo,
      "warnings": 0,
      "status": "free",
  }
  save_data("users.json", users_db)

  # FAQAT ADMINGA SHAXSIY MA'LUMOTLARNI YUBORISH
  admin_caption = (
      f"🆕 Yangi ishchi ro'yxatdan o'tdi!\n\n"
      f"👤 Ism-Familiya: {data['full_name']}\n"
      f"📞 Tel: {data['phone']}\n"
      f"🎂 Yosh: {data['age']}\n"
      f"🚻 Jins: {data['gender']}\n"
      f"🆔 Telegram ID: {user_id}"
  )

  try:
    bot.send_photo(
        ADMIN_ID,
        data["passport_photo"],
        caption=f"📋 {data['full_name']} ning Pasport rasmi",
    )
    bot.send_photo(ADMIN_ID, selfie_photo, caption=admin_caption)
  except Exception as e:
    print(f"Adminga ma'lumot yuborishda xatolik: {e}")

  target_job = data.get("target_job")
  del user_temp[user_id]

  bot.send_message(
      user_id,
      "🎉 Muvaffaqiyatli ro'yxatdan o'tdingiz!",
      parse_mode="Markdown",
  )

  if target_job:
    send_payment_info(user_id, target_job)


# --- 3. TO'LOV MA'LUMOTINI YUBORISH VA CHEK QABUL QILISH ---
def send_payment_info(user_id, post_id):
  job_info = posts_db.get(post_id)

  if not job_info:
    bot.send_message(
        user_id, "❌ Ushbu e'lon topilmadi yoki o'chirilgan!"
    )
    return

  users_db[user_id]["status"] = "waiting_receipt"
  users_db[user_id]["current_job"] = post_id
  users_db[user_id]["job_info"] = job_info
  save_data("users.json", users_db)

  msg = (
      f"📋 Ishga yozilish: #{post_id}\n\n"
      f"💰 Ish haqqi: {job_info['ish_haqqi']} so'm\n"
      f"⭐️ Xizmat haqqi: {XIZMAT_HAQQI} so'm\n\n"
      f"💳 To'lov uchun karta:\n{KARTA_RAQAMI}\n"
      f"👤 Egasining ismi: {KARTA_EGASI}\n\n"
      f"📥 Ushbu karta raqamiga {XIZMAT_HAQQI} so'm to'lab, chek rasmini botga yuboring.\n"
      f"⚠️ *Feyk chek yuborsangiz ogohlantirish beriladi va 3 ta ogohlantirishdan so'ng bloklanasiz!*"
  )
  bot.send_message(int(user_id), msg, parse_mode="Markdown")
@bot.message_handler(
    content_types=["photo"],
    func=lambda msg: users_db.get(str(msg.from_user.id), {}).get("status")
    == "waiting_receipt",
)
def handle_receipt(message):
  user_id = str(message.from_user.id)
  users_db[user_id]["status"] = "checking"
  save_data("users.json", users_db)

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "✅ Tasdiqlash", callback_data=f"approve_{user_id}"
      ),
      types.InlineKeyboardButton(
          "❌ Feyk (Ogohlantirish)", callback_data=f"fake_{user_id}"
      ),
  )

  caption = (
      f"📥 Yangi to'lov cheki keldi!\n\n"
      f"👤 Ishchi: {users_db[user_id]['full_name']}\n"
      f"📞 Tel: {users_db[user_id]['phone']}\n"
      f"📋 E'lon ID: #{users_db[user_id]['current_job']}\n"
      f"⚠️ Ogohlantirishlari: {users_db[user_id]['warnings']}/3"
  )

  bot.send_photo(
      ADMIN_ID,
      message.photo[-1].file_id,
      caption=caption,
      reply_markup=markup,
      parse_mode="Markdown",
  )
  bot.reply_to(
      message,
      "⏳ Chekingiz admin tekshiruviga yuborildi. Tez orada tasdiqlanadi.",
  )


# --- 4. ADMIN HARAKATLARI (TASDIQLASH/FEYK) ---
@bot.callback_query_handler(func=lambda call: True)
def admin_callback(call):
  if call.from_user.id != ADMIN_ID:
    return

  data_parts = call.data.split("_")
  action = data_parts[0]
  target_user_id = data_parts[1]

  if action == "approve":
    users_db[target_user_id]["status"] = "active"
    job_info = users_db[target_user_id]["job_info"]
    post_id = users_db[target_user_id]["current_job"]
    save_data("users.json", users_db)

    success_text = (
        f"✅ To'lov tasdiqlandi!\n\n"
        f"📋 E'lon ID: #{post_id}\n"
        f"📍 Aniq manzil: {job_info['manzil']}\n"
        f"📞 Ish beruvchi telefoni: {job_info['phone']}"
    )
    bot.send_message(
        int(target_user_id), success_text, parse_mode="Markdown"
    )
    bot.edit_message_caption(
        call.message.caption + "\n\n✅ ADMIN TASDIQLADI",
        call.message.chat.id,
        call.message.message_id,
    )

  elif action == "fake":
    users_db[target_user_id]["warnings"] += 1
    warn_count = users_db[target_user_id]["warnings"]
    users_db[target_user_id]["status"] = "free"

    if warn_count >= 3:
      users_db[target_user_id]["blocked"] = True
      bot.send_message(
          int(target_user_id),
          "🚫 Siz 3 marta feyk chek yuborganingiz uchun botdan butunlay bloklandingiz!",
      )
      bot.edit_message_caption(
          call.message.caption + "\n\n❌ FEYK CHEK - FOYDALANUVCHI BLOKLANDI!",
          call.message.chat.id,
          call.message.message_id,
      )
    else:
      bot.send_message(
          int(target_user_id),
          f"⚠️ OGOHLANTIRISH!\n\nSiz yuborgan chek soxta deb topildi. Ogohlantirish: {warn_count}/3",
          parse_mode="Markdown",
      )
      bot.edit_message_caption(
          call.message.caption
          + f"\n\n⚠️ OGOHLANTIRISH BERILDI ({warn_count}/3)",
          call.message.chat.id,
          call.message.message_id,
      )
    save_data("users.json", users_db)


# --- 5. ADMIN ORQALI KANALGA E'LON JOYLAH ---
@bot.message_handler(commands=["post"])
def create_post(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = (
      "📝 E'lon joylash formati:\n\n"
      "Ish haqqi | Ovqat | Vaqt | Manzil | Qo'shimcha | Ish beruvchi tel\n\n"
      "Namuna:\n"
      "200 000 | Bor | 08:00 - 18:00 | Yunusobod 4-mavze | Usta yordamchisi kerak | +998901234567"
  )
  bot.reply_to(message, msg, parse_mode="Markdown")


@bot.message_handler(
    func=lambda msg: "|" in msg.text
    and not msg.text.startswith("/")
    and msg.from_user.id == ADMIN_ID
)
def handle_new_job_post(message):
  try:
    data = [item.strip() for item in message.text.split("|")]
    if len(data) < 6:
      bot.reply_to(
          message,
          "❌ Format noto'g'ri! Ma'lumotlarni 6 ta qismga | belgisida ajratib yozing.",
      )
      return
post_id = str(int(time.time()))[-4:]
    posts_db[post_id] = {
        "ish_haqqi": data[0],
        "ovqat": data[1],
        "vaqt": data[2],
        "manzil": data[3],
        "qoshimcha": data[4],
        "phone": data[5],
    }
    save_data("posts.json", posts_db)

    caption = (
        f"👷‍♂️ Ishchilar kanali\n\n💰 Ish haqqi: {data[0]} so'm\n"
        f"🍲 Ovqat: {data[1]}\n⏰ Vaqt: {data[2]}\n📍 Manzil: {data[3]}\n"
        f"⭐️ Xizmat haqqi: {XIZMAT_HAQQI} so'm\n📝 Qo'shimcha: {data[4]}\n\n🟢 Holat: Faol\n№ {post_id}"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "📝 Ishga yozilish",
            url=f"https://t.me/{BOT_USERNAME}?start=job_{post_id}",
        )
    )

    bot.send_message(
        CHANNEL_ID, caption, reply_markup=keyboard, parse_mode="Markdown"
    )
    bot.reply_to(message, f"✅ E'lon {CHANNEL_ID} ga joylandi! (ID: #{post_id})")
  except Exception as e:
    bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")


print("Master_rabotnikbot muvaffaqiyatli ishga tushdi!")
bot.polling(non_stop=True)
@bot.message_handler(commands=['post'])
def create_post(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = (
      "📝 Yangilangan e'lon joylash formati:\n\n"
      "Ish haqqi | Ovqat | Vaqt | Manzil | Xizmat haqi | Sana | Qo'shimcha | Ish beruvchi tel\n\n"
      "Siz xohlagan namuna:\n"
      "150 mingdan | 1 mahal | 10:00 dan ish tugaguncha | Lakatsiya beriladi | 0 so'm | Ertaga | Padez uborkasi 2 ta ayol qiz kerak Yaxshi ishlaydigan | +998901234567"
  )
  bot.reply_to(message, msg, parse_mode="Markdown")


@bot.message_handler(
    func=lambda msg: "|" in msg.text
    and not msg.text.startswith("/")
    and msg.from_user.id == ADMIN_ID
)
def handle_new_job_post(message):
  try:
    data = [item.strip() for item in message.text.split("|")]
    if len(data) < 8:
      bot.reply_to(
          message,
          "❌ Format noto'g'ri! Ma'lumotlarni 8 ta qismga | belgisida ajratib yozing.",
      )
      return

    post_id = str(int(time.time()))[-4:]
    posts_db[post_id] = {
        "ish_haqqi": data[0],
        "ovqat": data[1],
        "vaqt": data[2],
        "manzil": data[3],
        "xizmat_haqi": data[4],
        "sana": data[5],
        "qoshimcha": data[6],
        "phone": data[7],
    }
    save_data("posts.json", posts_db)

    caption = (
        f"💰 Ish haqqi: {data[0]}\n"
        f"🍛 Ovqat: {data[1]}\n"
        f"⏰ Vaqt: {data[2]}\n"
        f"📱 Manzil: {data[3]}\n"
        f"🌟 Xizmat haqi: {data[4]}\n"
        f"📝 Qo'shimcha: {data[6]}\n\n"
        f"🟢 Holat: Faol\n"
        f"📅 Sana: {data[5]}\n"
        f"#{post_id}"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "📝 Ishga yozilish",
            url=f"https://t.me/{BOT_USERNAME}?start=job_{post_id}",
        )
    )

    bot.send_message(
        CHANNEL_ID, caption, reply_markup=keyboard, parse_mode="Markdown"
    )
    bot.reply_to(message, f"✅ E'lon {CHANNEL_ID} ga joylandi! (ID: #{post_id})")
  except Exception as e:
    bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")
# ================= 5. ADMIN ORQALI KANALGA E'LON JOYLASH (BOSQICHMA-BOSQICH) =================
admin_post_temp = {}

# Viloyatlarga mos tumanlar ro'yxati
TUMANLAR = {
    "Toshkent shahri": ["Yunusobod", "Chilonzor", "Mirzo Ulug'bek", "Yashnobod", "Olmazor", "Mirobod", "Sergeli", "Yakkasaroy", "Uchtepa", "Bektemir", "Yangihayot"],
    "Toshkent viloyati": ["Chirchiq", "Olmaliq", "Angren", "Yangiyo'l", "Bekobod", "Qibray", "Zangiota", "Toshkent t.", "Parkent"],
    "Farg'ona": ["Farg'ona sh.", "Marg'ilon sh.", "Qo'qon sh.", "Quva", "Oltiariq", "Rishtan", "Buvayda", "Uchko'prik", "Beshariq", "Bag'dod"],
    "Andijon": ["Andijon sh.", "Asaka", "Shahrixon", "Xo'jaobod", "Buloqboshi", "Marhamat", "Izboskan", "Paxtaobod"],
    "Namangan": ["Namangan sh.", "Chust", "Pop", "Kosonsoy", "Uychi", "To'raqo'rg'on", "Uchqo'rg'on"],
    "Samarqand": ["Samarqand sh.", "Kattaqo'rg'on", "Pastdarg'om", "Jomboy", "Toyloq", "Urgut", "Bulung'ur", "Ishtixon"],
    "Buxoro": ["Buxoro sh.", "Kogon sh.", "G'ijduvon", "Jondor", "Peshku", "Romitan", "Vobkent", "Qorakul"],
    "Xorazm": ["Urganch sh.", "Xiva sh.", "Xonqa", "Gurlan", "Shovot", "Yangiariq", "Bog'ot"],
    "Qashqadaryo": ["Qarshi sh.", "Shahrisabz sh.", "Kitob", "Yakkabog'", "Kamashi", "G'uzor", "Nishan", "Kasbi"],
    "Surxondaryo": ["Termiz sh.", "Denov", "Sherobod", "Sariosiyo", "Qumqo'rg'on", "Jarqo'rg'on", "Boysun"],
    "Navoiy": ["Navoiy sh.", "Zarafshon sh.", "Karmana", "Qiziltepa", "Xatirchi", "Uchquduq", "Nurota"],
    "Jizzax": ["Jizzax sh.", "Zomin", "G'allaorol", "Paxtakor", "Do'stlik", "Zarbdor", "Sharof Rashidov"],
    "Sirdaryo": ["Guliston sh.", "Yangiyer sh.", "Shirin sh.", "Sardoba", "Boyovut", "Sayxunobod", "Oqoltin"]
}


@bot.message_handler(commands=["post"])
def start_post_creation(message):
    if message.from_user.id != ADMIN_ID:
        return

    admin_post_temp[message.chat.id] = {}

    # 1-bosqich: Viloyatni tanlash
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        "Toshkent shahri",
        "Toshkent viloyati",
        "Samarqand",
        "Farg'ona",
        "Andijon",
        "Namangan",
    )
    markup.add(
        "Buxoro",
        "Xorazm",
        "Qashqadaryo",
        "Surxondaryo",
        "Navoiy",
        "Jizzax",
        "Sirdaryo",
    )

    msg = bot.send_message(
        message.chat.id,
        "📍 1/6. Viloyatni tanlang (yoki yozing):",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_step_region)


def process_step_region(message):
    region = message.text
    admin_post_temp[message.chat.id]["region"] = region

    # Tanlangan viloyat tumanlarini olish
    tumanlar_list = TUMANLAR.get(region, [])
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    if tumanlar_list:
        # Tumanlarni tugmalarga 2 tadan qilib taxlash
        for i in range(0, len(tumanlar_list), 2):
            pair = tumanlar_list[i:i+2]
            markup.add(*pair)
        
        msg_text = f"🏙 2/6. *{region}* bo'yicha tumanni tanlang (yoki yozing):"
    else:
        markup = types.ReplyKeyboardRemove()
        msg_text = "🏙 2/6. Tuman yoki aniq manzilni kiriting:\n*(Masalan: Yunusobod tumani / Lokatsiya beriladi)*"

    msg = bot.send_message(
        message.chat.id,
        msg_text,
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_step_district)


def process_step_district(message):
    admin_post_temp[message.chat.id]["district"] = message.text

    # 3-bosqich: Nechta odam kerakligi
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("1 ta", "2 ta", "3 ta", "4-5 ta", "Jamoa kerak")

    msg = bot.send_message(
        message.chat.id,
        "👥 3/6. Nechta ishchi kerakligini tanlang (yoki yozing):",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_step_workers)


def process_step_workers(message):
    admin_post_temp[message.chat.id]["workers"] = message.text

    # 4-bosqich: Ish haqqi
    msg = bot.send_message(
        message.chat.id,
        "💰 4/6. Ish haqqini kiriting:\n*(Masalan: 150 mingdan / 200.000 so'm)*",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_step_salary)


def process_step_salary(message):
    admin_post_temp[message.chat.id]["salary"] = message.text

    # 5-bosqich: Ish kuni / Sana
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Bugun", "Ertaga", "Doimiy ish")

    msg = bot.send_message(
        message.chat.id,
        "📅 5/6. Ish kunini tanlang:",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_step_date)


def process_step_date(message):
    admin_post_temp[message.chat.id]["date"] = message.text

    # 6-bosqich: Qo'shimcha ma'lumot va Tel raqam
    msg = bot.send_message(
        message.chat.id,
        "📝 6/6. Qo'shimcha ma'lumot va ish beruvchi telefonini kiriting:\n*(Masalan: Padez uborkasi uchun ayollar kerak | +998901234567)*",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_step_final)


def process_step_final(message):
    chat_id = message.chat.id
    data = admin_post_temp.get(chat_id, {})
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
        f"👥 Kerakli ishchilar: {data['workers']}\n"
        f"💰 Ish haqqi: {data['salary']}\n"
        f"📅 Sana: {data['date']}\n"
        f"📝 Batafsil: {data['details']}\n\n"
        f"🟢 Holat: Faol\n"
        f"#{post_id}"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "📥 Ishga yozilish",
            url=f"https://t.me/{BOT_USERNAME}?start=job_{post_id}",
        )
    )

    bot.send_message(CHANNEL_ID, caption, reply_markup=keyboard)
    bot.send_message(chat_id, f"✅ E'lon #{post_id} muvaffaqiyatli kanalga joylandi!")
# 6-bosqich: Qo'shimcha ma'lumot va Tel raqam
  msg = bot.send_message(
      message.chat.id,
      "📝 6/6. Qo'shimcha ma'lumot va ish beruvchi telefonini kiriting:\n*(Masalan: Padez uborkasi uchun ayollar kerak | +998901234567)*",
      reply_markup=types.ReplyKeyboardRemove(),
      parse_mode="Markdown",
  )
  bot.register_next_step_handler(msg, process_step_final)


def process_step_final(message):
  chat_id = message.chat.id
  data = admin_post_temp.get(chat_id, {})
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
      f"👥 Kerakli ishchilar: {data['workers']}\n"
      f"💰 Ish haqqi: {data['salary']}\n"
      f"📅 Sana: {data['date']}\n"
      f"📝 Batafsil: {data['details']}\n\n"
      f"🟢 Holat: Faol\n"
      f"#{post_id}"
  )

  keyboard = types.InlineKeyboardMarkup()
  keyboard.add(
      types.InlineKeyboardButton(
          "📝 Ishga yozilish",
          url=f"https://t.me/{BOT_USERNAME}?start=job_{post_id}",
      )
  )
bot.send_message(
      CHANNEL_ID, caption, reply_markup=keyboard, parse_mode="Markdown"
  )
  bot.send_message(
      chat_id,
      f"✅ E'lon muvaffaqiyatli kanalga joylandi! (ID: #{post_id})",
      parse_mode="Markdown",
  )
  del admin_post_temp[chat_id]
if __name__ == "__main__":
    bot.infinity_polling()
