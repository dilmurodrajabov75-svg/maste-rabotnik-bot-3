import json
import os
import time
from telebot import TeleBot, types

# ==============================================================================
# 1. ASOSIY KONFIGURATSIYA VA GLOBAL SOZLAMALAR
# ==============================================================================
TOKEN = "8603747344:AAECBz0DiO3ZCfUknqXtfreLYxc5LNdnCOs"
BOT_USERNAME = "Master_rabotnikbot"
CHANNEL_ID = "@ish_keremidi"
CHANNEL_USERNAME = "ish_keremidi"
ADMIN_ID = 8554402317

KARTA_RAQAMI = "4413 5976 0016 9336"
KARTA_EGASI = "Rajabov Dilmurod"
XIZMAT_HAQQI = "20 000"

USERS_FILE = "users.json"
POSTS_FILE = "posts.json"

# ==============================================================================
# 2. MA'LUMOTLAR BAZASINI YUKLASH VA SAQLASH FUNKSIYALARI
# ==============================================================================
def load_data(file_name):
    if os.path.exists(file_name):
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(file_name, data):
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ma'lumotlarni saqlashda xatolik yuz berdi: {e}")

users_db = load_data(USERS_FILE)
posts_db = load_data(POSTS_FILE)

temp_data = {}
admin_post_temp = {}

# ==============================================================================
# 3. HUDUDLAR VA TUMANLAR LUG'ATI (TO'LIQ BAZA)
# ==============================================================================
TUMANLAR = {
    "Toshkent shahri": [
        "Yunusobod", "Chilonzor", "Mirzo Ulug'bek", "Yashnobod", 
        "Olmazor", "Mirobod", "Sergeli", "Yakkasaroy", 
        "Uchtepa", "Bektemir", "Yangihayot", "Shayxontohur"
    ],
    "Toshkent viloyati": [
        "Chirchiq sh.", "Olmaliq sh.", "Angren sh.", "Yangiyo'l sh.", 
        "Bekobod sh.", "Qibray", "Zangiota", "Toshkent t.", 
        "Parkent", "Pskent", "O'rtachirchiq", "Quyichirchiq", 
        "Buka", "Chinaz", "Oqqurg'on", "Bostanliq"
    ],
    "Farg'ona": [
        "Farg'ona sh.", "Marg'ilon sh.", "Qo'qon sh.", "Quvasoy sh.", 
        "Quva", "Oltiariq", "Rishtan", "Buvayda", 
        "Uchko'prik", "Beshariq", "Bag'dod", "Farg'ona t.", 
        "O'zbekiston t.", "Toshloq", "Yozyovon", "Sox"
    ],
    "Andijon": [
        "Andijon sh.", "Xonobod sh.", "Asaka", "Shahrixon", 
        "Xo'jaobod", "Buloqboshi", "Marhamat", "Izboskan", 
        "Paxtaobod", "Andijon t.", "Oltinko'l", "Jalaquduq", 
        "Boz", "Ulug'nor", "Qurg'ontepa"
    ],
    "Namangan": [
        "Namangan sh.", "Chust", "Pop", "Kosonsoy", 
        "Uychi", "To'raqo'rg'on", "Uchqo'rg'on", "Mingbulaq", 
        "Namangan t.", "Norin", "Yangiqo'rg'on"
    ],
    "Samarqand": [
        "Samarqand sh.", "Kattaqo'rg'on sh.", "Pastdarg'om", "Jomboy", 
        "Toyloq", "Urgut", "Bulung'ur", "Ishtixon", 
        "Paxtachi", "Payariq", "Qo'shrabot", "Narpay", 
        "Samarqand t.", "Nurobod"
    ],
    "Buxoro": [
        "Buxoro sh.", "Kogon sh.", "G'ijduvon", "Jondor", 
        "Peshku", "Romitan", "Vobkent", "Qorakul", 
        "Olot", "Qorovulbozor", "Shofirkon", "Buxoro t."
    ],
    "Xorazm": [
        "Urganch sh.", "Xiva sh.", "Xonqa", "Gurlan", 
        "Shovot", "Yangiariq", "Bog'ot", "Qo'shko'pir", 
        "Yangiqala", "Hazorasp", "Tuproqqala", "Urganch t."
    ],
    "Qashqadaryo": [
        "Qarshi sh.", "Shahrisabz sh.", "Kitob", "Yakkabog'", 
        "Kamashi", "G'uzor", "Nishan", "Kasbi", 
        "Chiroqchi", "Dehqonobod", "Muborak", "Qarshi t.", 
        "Shahrisabz t.", "Ko'kdala"
    ],
    "Surxondaryo": [
        "Termiz sh.", "Denov", "Sherobod", "Sariosiyo", 
        "Qumqo'rg'on", "Jarqo'rg'on", "Boysun", "Uzun", 
        "Oltinsoy", "Angor", "Muzrabot", "Termiz t.", "Bandixon"
    ],
    "Navoiy": [
        "Navoiy sh.", "Zarafshon sh.", "Karmana", "Qiziltepa", 
        "Xatirchi", "Uchquduq", "Nurota", "Navbahor", 
        "Konimex", "Tomdi"
    ],
    "Jizzax": [
        "Jizzax sh.", "Zomin", "G'allaorol", "Paxtakor", 
        "Do'stlik", "Zarbdor", "Sharof Rashidov", "Forish", 
        "Baxmal", "Mirzacho'l", "Yangiobod", "Arnasoy"
    ],
    "Sirdaryo": [
        "Guliston sh.", "Yangiyer sh.", "Shirin sh.", "Sardoba", 
        "Boyovut", "Sayxunobod", "Oqoltin", "Xovos", 
        "Mirzaobod", "Guliston t."
    ],
    "Qoraqalpog'iston": [
        "Nukus sh.", "Turtko'l", "Beruniy", "Xo'jayli", 
        "Chimboy", "Qo'ng'irot", "Mo'ynoq", "Amudaryo", 
        "Ellikqala", "Kegeyli", "Qonliko'l", "Qorao'zak", 
        "Taxtako'pir", "Shumanay", "Bozataw"
    ]
}

bot = TeleBot(TOKEN)

# ==============================================================================
# 4. KANALGA OBUNANI TEKSHIRISH MEXANIZMI
# ==============================================================================
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return False

def send_subscription_prompt(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_channel = types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME}")
    btn_check = types.InlineKeyboardButton("🔄 Tekshirish", callback_data="check_sub")
    markup.add(btn_channel)
    markup.add(btn_check)
    
    bot.send_message(
        chat_id,
        "⚠️ Hurmatli foydalanuvchi, botimiz xizmatlaridan mukammal foydalanish uchun quyidagi rasmiy kanalimizga to'liq obuna bo'lishingiz talab etiladi!\n\nKanalga a'zo bo'lib, so'ngra pastdagi tugmani bosing:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def verify_subscription_callback(call):
    user_id = call.from_user.id
    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ Obunangiz muvaffaqiyatli tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        
        fake_message = call.message
        fake_message.from_user = call.from_user
        fake_message.text = "/start"
        start_cmd(fake_message)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)


# ==============================================================================
# 5. START VA KENGAYTIRILGAN RO'YXATDAN O'TISH QADAMLARI
# ==============================================================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = str(message.from_user.id)
    args = message.text.split()

    if message.from_user.id == ADMIN_ID and len(args) == 1:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ E'lon joylash", "📊 Foydalanuvchilar soni")
        bot.send_message(message.chat.id, "👨‍💻 Xush kelibsiz Admin! Kerakli bo'limni tanlang:", reply_markup=markup)
        return

    if not check_subscription(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    if user_id not in users_db:
        temp_data[user_id] = {'start_args': args[1] if len(args) > 1 else None}
        msg = bot.send_message(
            message.chat.id, 
            "Assalomu alaykum! Master rabotnik tizimiga xush kelibsiz.\n\nIshga joylashish va mukammal profil yaratish uchun ma'lumotlaringizni to'ldiring:\n\n1️⃣ Ism va familiyangizni to'liq kiriting:"
        )
        bot.register_next_step_handler(msg, reg_name)
        return

    if len(args) > 1 and args[1].startswith("job_"):
        job_id = args[1].replace("job_", "")
        show_job_payment(message.chat.id, job_id)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("👤 Mening profilim")
        bot.send_message(message.chat.id, "Siz allaqachon to'liq ro'yxatdan o'tgansiz! Kanalimizdagi yangi e'lonlarni kuzatib boring.", reply_markup=markup)

def reg_name(message):
    user_id = str(message.from_user.id)
    temp_data[user_id]['name'] = message.text
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_phone = types.KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)
    markup.add(btn_phone)
    msg = bot.send_message(message.chat.id, "2️⃣ Telefon raqamingizni quyidagi maxsus tugma orqali yuboring:", reply_markup=markup)
    bot.register_next_step_handler(msg, reg_phone)

def reg_phone(message):
    user_id = str(message.from_user.id)
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text
    temp_data[user_id]['phone'] = phone
    
    msg = bot.send_message(
        message.chat.id, 
        "3️⃣ Pasportingiz (yoki ID karta) rasmini sifatli holda **rasm (foto) shaklida** yuboring:", 
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, reg_passport)

def reg_passport(message):
    user_id = str(message.from_user.id)
    if message.content_type == 'photo':
        temp_data[user_id]['passport'] = message.photo[-1].file_id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("Erkak", "Ayol")
        msg = bot.send_message(message.chat.id, "4️⃣ Jinsingizni tanlang:", reply_markup=markup)
        bot.register_next_step_handler(msg, reg_gender)
    else:
        msg = bot.send_message(message.chat.id, "Iltimos, pasport rasmini aynan **foto** formatida yuboring:")
        bot.register_next_step_handler(msg, reg_passport)

def reg_gender(message):
    user_id = str(message.from_user.id)
    temp_data[user_id]['gender'] = message.text
    
    msg = bot.send_message(
        message.chat.id, 
        "5️⃣ Yoshi belgilanmaydi. O'zingizning shaxsiy 1 ta yuzingiz aniq ko'ringan rasmingizni yuboring:", 
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, reg_photo)

def reg_photo(message):
    user_id = str(message.from_user.id)
    if message.content_type == 'photo':
        temp_data[user_id]['photo'] = message.photo[-1].file_id
        
        users_db[user_id] = {
            'name': temp_data[user_id]['name'],
            'phone': temp_data[user_id]['phone'],
            'passport': temp_data[user_id]['passport'],
            'gender': temp_data[user_id]['gender'],
            'photo': temp_data[user_id]['photo']
        }
        save_data(USERS_FILE, users_db)
        
        d_args = temp_data[user_id].get('start_args')
        del temp_data[user_id]
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("👤 Mening profilim")
        bot.send_message(message.chat.id, "🎉 Tabriklaymiz! Ro'yxatdan muvaffaqiyatli o'tdingiz va barcha ma'lumotlaringiz bazada saqlandi.", reply_markup=markup)
        
        if d_args and d_args.startswith("job_"):
            show_job_payment(message.chat.id, d_args.replace("job_", ""))
    else:
        msg = bot.send_message(message.chat.id, "Iltimos, shaxsiy rasmingizni aynan **foto** formatida yuboring:")
        bot.register_next_step_handler(msg, reg_photo)


# ==============================================================================
# 6. ADMIN TOMONIDAN KANALGA E'LON JOYLASHTIRISH TIZIMI
# ==============================================================================
@bot.message_handler(func=lambda msg: msg.text == "➕ E'lon joylash" and msg.from_user.id == ADMIN_ID)
def start_post_creation(message):
    admin_post_temp[message.chat.id] = {}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Toshkent shahri", "Toshkent viloyati")
    markup.add("Farg'ona", "Andijon", "Namangan")
    markup.add("Samarqand", "Buxoro", "Xorazm")
    markup.add("Qashqadaryo", "Surxondaryo", "Navoiy")
    markup.add("Jizzax", "Sirdaryo", "Qoraqalpog'iston")

    msg = bot.send_message(message.chat.id, "📍 1/5. Viloyatni tanlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_step_region)

def process_step_region(message):
    region = message.text
    admin_post_temp[message.chat.id]["region"] = region

    tumanlar_list = TUMANLAR.get(region, [])
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    if tumanlar_list:
        for i in range(0, len(tumanlar_list), 2):
            pair = tumanlar_list[i:i+2]
            markup.add(*pair)
        msg_text = f"🏙 2/5. *{region}* bo'yicha tumanni tanlang:"
    else:
        markup = types.ReplyKeyboardRemove()
        msg_text = "🏙 2/5. Tuman yoki manzilni kiriting:"

    msg = bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_step_district)

def process_step_district(message):
    admin_post_temp[message.chat.id]["district"] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("1 ta", "2 ta", "3 ta", "4-5 ta", "Jamoa kerak")

    msg = bot.send_message(message.chat.id, "👥 3/5. Nechta ishchi kerakligini tanlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_step_workers)

def process_step_workers(message):
    admin_post_temp[message.chat.id]["workers"] = message.text

    msg = bot.send_message(message.chat.id, "💰 4/5. Ish haqqini kiriting:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_step_salary)

def process_step_salary(message):
    admin_post_temp[message.chat.id]["salary"] = message.text

    msg = bot.send_message(
        message.chat.id, 
        "📝 5/5. Batafsil ma'lumot va ish beruvchining aloqa raqamini kiriting:", 
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, process_step_final)

def process_step_final(message):
    chat_id = message.chat.id
    data = admin_post_temp.get(chat_id, {})
    details = message.text

    post_id = str(int(time.time()))[-4:]
    posts_db[post_id] = {
        "text": (
            f"📍 Hudud: {data['region']} ({data['district']})\n"
            f"👥 Kerakli ishchilar: {data['workers']}\n"
            f"💰 Ish haqqi: {data['salary']}\n"
            f"📝 Batafsil: {details}"
        ),
        "contacts": details
    }
    save_data(POSTS_FILE, posts_db)
    del admin_post_temp[chat_id]

    caption = (
        f"{posts_db[post_id]['text']}\n\n"
        f"🟢 Holat: Faol\n#{post_id}"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("📥 Ishga yozilish", url=f"https://t.me/{BOT_USERNAME}?start=job_{post_id}"))

    bot.send_message(CHANNEL_ID, caption, reply_markup=keyboard)
    bot.send_message(chat_id, f"✅ E'lon #{post_id} muvaffaqiyatli kanalga joylandi!")


# ==============================================================================
# 7. TO'LOV VA ISH BERUVCHI KONTAKTINI TAQDIM ETISH
# ==============================================================================
def show_job_payment(chat_id, job_id):
    if not check_subscription(chat_id):
        send_subscription_prompt(chat_id)
        return

    job = posts_db.get(job_id)
    if not job:
        bot.send_message(chat_id, "❌ Kechirasiz, bu e'lon topilmadi yoki o'chirilgan.")
        return

    text = (
        f"📋 **Tanlangan e'lon:**\n{job['text']}\n\n"
        f"💳 **To'lov rekvizitlari:**\n"
        f"Karta raqami: `{KARTA_RAQAMI}`\n"
        f"Karta egasi: **{KARTA_EGASI}**\n"
        f"Xizmat haqqi: **{XIZMAT_HAQQI} so'm**\n\n"
        f"Ish beruvchi kontaktini olish uchun ko'rsatilgan summani o'tkazing va **chekni rasm shaklida** yuboring!"
    )
    msg = bot.send_message(chat_id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_receipt, job_id)

def process_receipt(message, job_id):
    chat_id = message.chat.id
    if message.content_type == 'photo':
        photo_id = message.photo[-1].file_id
        
        markup = types.InlineKeyboardMarkup()
        btn_app = types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"app_{chat_id}_{job_id}")
        btn_rej = types.InlineKeyboardButton("❌ Rad etish", callback_data=f"rej_{chat_id}_{job_id}")
        markup.add(btn_app, btn_rej)
        
        user = users_db.get(str(chat_id), {})
        caption = (
            f"📥 **YANGI TO'LOV CHEKI KELDI!**\n\n"
            f"👤 **Ishchi:** {user.get('name')}\n"
            f"📞 **Telefon:** {user.get('phone')}\n"
            f"🆔 E'lon ID: `#{job_id}`"
        )
        bot.send_photo(ADMIN_ID, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
        bot.send_message(chat_id, "✅ Chekingiz adminga yuborildi! Tasdiqlangach, kontakt yuboriladi.")
    else:
        msg = bot.send_message(chat_id, "Iltimos, to'lov chekini faqatgina **rasm (foto)** ko'rinishida yuboring:")
        bot.register_next_step_handler(msg, process_receipt, job_id)


# ==============================================================================
# 8. ADMINNING TO'LOVNI TASDIQLASH YOKI RAD ETISH AMallari
# ==============================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_')))
def admin_approval(call):
    parts = call.data.split('_')
    action = parts[0]
    user_id = int(parts[1])
    job_id = parts[2]

    if action == 'app':
        job = posts_db.get(job_id, {})
        contacts = job.get('contacts', 'Ma\'lumot topilmadi')
        
        success_text = (
            f"🎉 **To'lovingiz tasdiqlandi!**\n\n"
            f"📞 **Ish beruvchi ma'lumotlari:**\n"
            f"{contacts}"
        )
        bot.send_message(user_id, success_text, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Muvaffaqiyatli tasdiqlandi!")
        try:
            bot.edit_message_caption(
                chat_id=ADMIN_ID, 
                message_id=call.message.message_id, 
                caption=call.message.caption + "\n\n✅ Holat: Tasdiqlandi", 
                reply_markup=None
            )
        except Exception:
            pass
    elif action == 'rej':
        bot.send_message(user_id, "❌ To'lov chekingiz rad etildi.")
        bot.answer_callback_query(call.id, "Rad etildi!")
        try:
            bot.edit_message_caption(
                chat_id=ADMIN_ID, 
                message_id=call.message.message_id, 
                caption=call.message.caption + "\n\n❌ Holat: Rad etildi", 
                reply_markup=None
            )
        except Exception:
            pass


# ==============================================================================
# 9. PROFIL VA STATISTIKA BO'LIMI
# ==============================================================================
@bot.message_handler(func=lambda msg: msg.text == "👤 Mening profilim")
def show_profile(message):
    user_id_str = str(message.from_user.id)
    user = users_db.get(user_id_str)
    if user:
        text = (
            f"👤 **Sizning shaxsiy profilingiz:**\n\n"
            f"**Ism va familiya:** {user.get('name')}\n"
            f"**Telefon raqam:** {user.get('phone')}\n"
            f"**Jins:** {user.get('gender')}\n\n"
            f"📸 **Pasport va shaxsiy rasmingiz bazada xavfsiz saqlanmoqda.**"
        )
        try:
            bot.send_photo(message.chat.id, user.get('photo'), caption=text, parse_mode="Markdown")
        except Exception:
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Profil topilmadi. /start buyrug'ini bosing.")

@bot.message_handler(func=lambda msg: msg.text == "📊 Foydalanuvchilar soni" and msg.from_user.id == ADMIN_ID)
def count_users(mess
