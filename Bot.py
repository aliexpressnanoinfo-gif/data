import json
import telebot
from flask import Flask, request
import threading
from telebot import types
from aliexpress_api import AliexpressApi, models
import re
import os
from urllib.parse import urlparse, parse_qs
import urllib.parse
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the bot with the token
TELEGRAM_TOKEN_BOT = os.getenv('TELEGRAM_BOT_TOKEN')
ALIEXPRESS_API_PUBLIC = os.getenv('ALIEXPRESS_API_PUBLIC')
ALIEXPRESS_API_SECRET = os.getenv('ALIEXPRESS_API_SECRET')
ALIEXPRESS_TRACKING_ID = os.getenv('ALIEXPRESS_TRACKING_ID', 'default')

# Check if required environment variables are set
if not TELEGRAM_TOKEN_BOT:
    print("❌ Error: TELEGRAM_BOT_TOKEN environment variable is not set!")
    print("Please set the environment variable or create a .env file with your bot token.")
    exit(1)

if not ALIEXPRESS_API_PUBLIC or not ALIEXPRESS_API_SECRET:
    print("❌ Error: ALIEXPRESS_API_PUBLIC and ALIEXPRESS_API_SECRET environment variables are not set!")
    print("Please set the environment variables or create a .env file with your API credentials.")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN_BOT)

# Initialize Aliexpress API
try:
    aliexpress = AliexpressApi(
        ALIEXPRESS_API_PUBLIC,
        ALIEXPRESS_API_SECRET,
        models.Language.AR,
        models.Currency.USD,
        ALIEXPRESS_TRACKING_ID
    )
    print("AliExpress API initialized successfully.")
except Exception as e:
    print(f"Error initializing AliExpress API: {e}")

# Define keyboards
keyboardStart = types.InlineKeyboardMarkup(row_width=1)
btn1 = types.InlineKeyboardButton("⭐️ صفحة مراجعة وجمع النقاط يوميا ⭐️", url="https://s.click.aliexpress.com/e/_DdwUZVd")
btn2 = types.InlineKeyboardButton("⭐️تخفيض العملات على منتجات السلة 🛒⭐️", callback_data='click')
btn3 = types.InlineKeyboardButton("❤️ اشترك في القناة للمزيد من العروض ❤️", url="https://t.me/ShopAliExpressMaroc")
btn4 = types.InlineKeyboardButton("🎬 شاهد كيفية عمل البوت 🎬", url="https://t.me/ShopAliExpressMaroc/9")
btn5 = types.InlineKeyboardButton("💰 حمل تطبيق Aliexpress عبر… على مكافأة 5 دولار 💰", url="https://a.aliexpress.com/_mtV0j3q")
keyboardStart.add(btn1, btn2, btn3, btn4)

keyboard = types.InlineKeyboardMarkup(row_width=1)
btn1 = types.InlineKeyboardButton("⭐️ صفحة مراجعة وجمع النقاط يوميا ⭐️", url="https://s.click.aliexpress.com/e/_DdwUZVd")
btn2 = types.InlineKeyboardButton("⭐️تخفيض العملات على منتجات السلة 🛒⭐️", callback_data='click')
btn3 = types.InlineKeyboardButton("❤️ اشترك في القناة للمزيد من العروض ❤️", url="https://t.me/ShopAliExpressMaroc")
keyboard.add(btn1, btn2, btn3)

keyboard_games = types.InlineKeyboardMarkup(row_width=1)
btn1 = types.InlineKeyboardButton("⭐️ صفحة مراجعة وجمع النقاط يوميا ⭐️", url="https://s.click.aliexpress.com/e/_DdwUZVd")
btn2 = types.InlineKeyboardButton("⭐️ لعبة Merge boss ⭐️", url="https://s.click.aliexpress.com/e/_DlCyg5Z")
btn3 = types.InlineKeyboardButton("⭐️ لعبة Fantastic Farm ⭐️", url="https://s.click.aliexpress.com/e/_DBBkt9V")
btn4 = types.InlineKeyboardButton("⭐️ لعبة قلب الاوراق Flip ⭐️", url="https://s.click.aliexpress.com/e/_DdcXZ2r")
btn5 = types.InlineKeyboardButton("⭐️ لعبة GoGo Match ⭐️", url="https://s.click.aliexpress.com/e/_DDs7W5D")
keyboard_games.add(btn1, btn2, btn3, btn4, btn5)

# Define function to get exchange rate from USD to SAR (Saudi Riyal)
def get_usd_to_sar_rate():
    try:
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
        data = response.json()
        return data['rates'].get('SAR')
    except Exception as e:
        print(f"Error fetching exchange rate: {e}")
        return None

# Define function to resolve redirect chain and get final URL
def resolve_full_redirect_chain(link):
    """Resolve all redirects to get the final URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/58.0.3029.110 Safari/537.36'
    }
    try:
        session_req = requests.Session()
        response = session_req.get(link, allow_redirects=True, timeout=10, headers=headers)
        final_url = response.url
        print(f"🔗 Resolved URL: {link} -> {final_url}")
        
        if "star.aliexpress.com" in final_url:
            # Extract redirectUrl parameter
            parsed_url = urlparse(final_url)
            params = parse_qs(parsed_url.query)
            if 'redirectUrl' in params:
                redirect_url = params['redirectUrl'][0]
                print(f"🔗 Found redirectUrl: {redirect_url}")
                return redirect_url
        
        if "aliexpress.com/item" in final_url:
            return final_url
        elif "p/coin-index" in final_url:
            # If final URL goes to coin-index, resolve its redirectUrl
            parsed_url = urlparse(final_url)
            params = parse_qs(parsed_url.query)
            if 'redirectUrl' in params:
                redirect_url = params['redirectUrl'][0]
                print(f"🔗 Found redirectUrl in coin-index: {redirect_url}")
                return redirect_url
        
        return final_url
    except Exception as e:
        print(f"❌ Error resolving redirect chain: {e}")
        return None

# Define function to extract product ID from AliExpress link
def extract_product_id(link):
    try:
        # Try extracting product ID for standard URLs (e.g., /item/1234567890.html)
        match = re.search(r'/item/(\d+)\.html', link)
        if match:
            return match.group(1)
        
        # Try extracting product ID from query parameters (e.g., ?productId=1234567890)
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        if 'productId' in query_params:
            return query_params['productId'][0]
        
        print("❌ Could not extract product ID from link.")
        return None
    except Exception as e:
        print(f"❌ Error extracting product ID: {e}")
        return None

def generate_coin_affiliate_link(product_id, resolved_link):
    try:
        coin_index_url = (
            f'https://star.aliexpress.com/share/share.htm?platform=AE'
            f'&businessType=ProductDetail&redirectUrl={resolved_link}?sourceType=620'
            f'&aff_fcid=34fabe5cf18745ab97c90d014e8a80cf-1734973621910-01431-UneMJZVf'
            f'&tt=CPS_NORMAL&aff_fsk=UneMJZVf&aff_platform=default&sk=UneMJZVf'
            f'&aff_trace_key=34fabe5cf18745ab97c90d014e8a80cf-1734973621910-01431-UneMJZVf'
            f'&terminal_id=62cf3423af9c4ab4850b626d4215da6f'
        )
        affiliate_link = aliexpress.get_affiliate_links(coin_index_url)
        return affiliate_link[0].promotion_link
    except Exception as e:
        print(f"❌ Error generating coin affiliate link for product {product_id}: {e}")
        return None

def generate_bundle_affiliate_link(product_id, resolved_link):
    try:
        bundle_url = (
            f'https://star.aliexpress.com/share/share.htm?platform=AE'
            f'&businessType=ProductDetail&redirectUrl={resolved_link}?sourceType=560'
            f'&aff_fcid=8709097a28d844489c4a3f7de6192b4f-1734973687070-08567-UneMNwjD'
            f'&tt=CPS_NORMAL&aff_fsk=UneMNwjD&aff_platform=default&sk=UneMNwjD'
            f'&aff_trace_key=8709097a28d844489c4a3f7de6192b4f-1734973687070-08567-UneMNwjD'
            f'&terminal_id=62cf3423af9c4ab4850b626d4215da6f'
        )
        affiliate_link = aliexpress.get_affiliate_links(bundle_url)
        return affiliate_link[0].promotion_link
    except Exception as e:
        print(f"❌ Error generating bundle affiliate link for product {product_id}: {e}")
        return None

# ====== /shopcart handlers & some helpers موجودة في ملفك الأصلي، تركتها كما هي ======
# (كل شيء قبل get_affiliate_links من نسختك الأصلية يبقى كما هو، فقط عدلت الأجزاء المتعلقة بالأسعار والرسالة.)

# ... هنا باقي دوالك مثل get_affiliate_shopcart_link و resolve_full_redirect_chain و extract_link الخ

# للتبسيط أكمل مباشرة إلى get_affiliate_links حسب نسختك الأصلية مع التعديلات:

def extract_link(text):
    link_pattern = r'https?://\S+|www\.\S+'
    links = re.findall(link_pattern, text)
    if links:
        print(f"Extracted link: {links[0]}")
        return links[0]
    return None

def get_affiliate_links(message, message_id, link):
    try:
        # Resolve the full redirect chain first
        resolved_link = resolve_full_redirect_chain(link)
        if not resolved_link:
            bot.delete_message(message.chat.id, message_id)
            bot.send_message(message.chat.id, "❌ ما قدرت أفتح الرابط بالكامل، تأكد من رابط المنتج وجرب مرة ثانية.")
            return

        # Extract product ID from the resolved link
        product_id = extract_product_id(resolved_link)
        if not product_id:
            bot.delete_message(message.chat.id, message_id)
            bot.send_message(message.chat.id, "❌ ما قدرت أطلع رقم المنتج من الرابط.")
            return

        # Generate other affiliate links using traditional method
        super_links = aliexpress.get_affiliate_links(
            f'https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl={resolved_link}?sourceType=562&aff_fcid='
        )
        super_links = super_links[0].promotion_link

        limit_links = aliexpress.get_affiliate_links(
            f'https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl={resolved_link}?sourceType=561&aff_fcid='
        )
        limit_links = limit_links[0].promotion_link

        # coin & bundle
        coin_affiliate_link = generate_coin_affiliate_link(product_id, resolved_link)
        bundle_affiliate_link = generate_bundle_affiliate_link(product_id, resolved_link)

        try:
            # Get product details using the product ID
            product_details = aliexpress.get_products_details([
                product_id
            ], fields=["target_sale_price", "product_title", "product_main_image_url"])
            
            if product_details and len(product_details) > 0:
                print(f"Product details object: {json.dumps(product_details[0].__dict__, indent=2, ensure_ascii=False)}")
                price_pro = float(product_details[0].target_sale_price)
                title_link = product_details[0].product_title
                img_link = product_details[0].product_main_image_url
                
                # Convert price to SAR (Saudi Riyal)
                exchange_rate = get_usd_to_sar_rate()
                if exchange_rate:
                    price_pro_sar = price_pro * exchange_rate
                else:
                    price_pro_sar = price_pro  # fallback to USD if exchange rate not available
                
                print(f"Product details: {title_link}, {price_pro}, {img_link}")
                bot.delete_message(message.chat.id, message_id)
                
                # Build the message with all affiliate links (Arabic + English, for Saudi buyers)
                message_text = (
                    "🛒 <b>هذا منتجك</b> 🔥\n"
                    f"<b>{title_link}</b> 🛍\n\n"
                    "💵 <b>Price / السعر التقريبي:</b>\n"
                    f"{price_pro:.2f} USD (Dollar)\n"
                    f"{price_pro_sar:.2f} SAR (ريال سعودي)\n\n"
                    "📊 <b>اختر العرض اللي يناسبك / Choose your best offer 👇</b>\n\n"
                )

                # Add coin-index affiliate link for 620 channel if available
                if coin_affiliate_link:
                    message_text += (
                        "💰 <b>عرض العملات (أرخص سعر عند الدفع)</b>\n"
                        f"<a href=\"{coin_affiliate_link}\">اضغط هنا / Click here</a>\n\n"
                    )

                # Add bundle affiliate link for 560 channel if available
                if bundle_affiliate_link:
                    message_text += (
                        "📦 <b>عرض الحزمة (عروض متنوعة)</b>\n"
                        f"<a href=\"{bundle_affiliate_link}\">اضغط هنا / Click here</a>\n\n"
                    )

                # Always add super and limited offers
                message_text += (
                    "💎 <b>عرض السوبر</b>\n"
                    f"<a href=\"{super_links}\">اضغط هنا / Click here</a>\n\n"
                    "🔥 <b>عرض محدود</b>\n"
                    f"<a href=\"{limit_links}\">اضغط هنا / Click here</a>\n\n"
                    "──────────────\n"
                    "<b>EN:</b> Best AliExpress offers for this product.\n"
                    "Choose any link above to get the best price.\n\n"
                    "#AliExpressSaverBot ✅"
                )

                bot.send_photo(
                    message.chat.id,
                    img_link,
                    caption=message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                # Fallback if product details couldn't be fetched
                bot.delete_message(message.chat.id, message_id)
                
                message_text = "قارن بين الأسعار واشتري 🔥 \n"
                if coin_affiliate_link:
                    message_text += "💰 عرض العملات (السعر النهائي عند الدفع) : \n" + coin_affiliate_link + "\n"
                if bundle_affiliate_link:
                    message_text += "📦 عرض الحزمة (عروض متنوعة) : \n" + bundle_affiliate_link + "\n"
                message_text += (
                    f"💎 عرض السوبر : \n{super_links}\n"
                    f"🔥 عرض محدود : \n{limit_links}\n\n"
                    "#AliExpressSaverBot ✅"
                )
                bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
        except Exception as e:
            print(f"Error in get_affiliate_links inner try: {e}")
            bot.delete_message(message.chat.id, message_id)
            message_text = "قارن بين الأسعار واشتري 🔥 \n"
            if coin_affiliate_link:
                message_text += "💰 عرض العملات (السعر النهائي عند الدفع) : \n" + coin_affiliate_link + "\n"
            if bundle_affiliate_link:
                message_text += "📦 عرض الحزمة (عروض متنوعة) : \n" + bundle_affiliate_link + "\n"
            message_text += (
                f"💎 عرض السوبر : \n{super_links}\n"
                f"🔥 عرض محدود : \n{limit_links}\n\n"
                "#AliExpressSaverBot ✅"
            )
            bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
    except Exception as e:
        print(f"Error in get_affiliate_links: {e}")
        bot.delete_message(message.chat.id, message_id)
        bot.send_message(message.chat.id, "❌ صار خطأ أثناء معالجة الرابط، جرب مرة ثانية لاحقًا.")

@bot.message_handler(commands=['start'])
def welcome_user(message):
    print("Handling /start command")
    bot.send_message(
        message.chat.id,
        "هلا فيك 👋 \n"
        "أنا بوت خصومات AliExpress للمشترين 👑\n\n"
        "ارسل رابط أي منتج من AliExpress وأنا أجيب لك أفضل العروض والأسعار المتاحة 🛒🔥\n\n"
        "تقدر بعد تستفيد من ألعاب وتجميع نقاط يومية 💰\n\n"
        "اختر من الأزرار بالأسفل 👇",
        reply_markup=keyboardStart
    )

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    try:
        print(f"Message received: {message.text}")
        link = extract_link(message.text)
        sent_message = bot.send_message(message.chat.id, '⏳ جاري فحص رابط المنتج، ثواني بس ...')
        message_id = sent_message.message_id
        if link and "aliexpress.com" in link and not ("p/shoppingcart" in message.text.lower()):
            if "availableProductShopcartIds".lower() in message.text.lower():
                get_affiliate_shopcart_link(link, message)
                return
            get_affiliate_links(message, message_id, link)
        else:
            bot.delete_message(message.chat.id, message_id)
            bot.send_message(
                message.chat.id,
                "الرابط غير صحيح ! تأكد من رابط المنتج أو اعد المحاولة.\n"
                " قم بإرسال <b> الرابط فقط</b> بدون عنوان المنتج",
                parse_mode='HTML'
            )
    except Exception as e:
        print(f"Error in echo_all: {e}")
        bot.send_message(message.chat.id, "❌ صار خطأ غير متوقع. جرب مرة ثانية لاحقًا.")

# Flask + webhook / polling (كما هو في ملفك الأصلي)
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return 'OK', 200

if __name__ == '__main__':
    webhook_url = os.getenv('WEBHOOK_URL')
    if webhook_url:
        print("🚀 Starting bot in webhook mode (production)...")
        try:
            bot.remove_webhook()
            bot.set_webhook(url=webhook_url)
            print(f"✅ Webhook set to: {webhook_url}")
        except Exception as e:
            print(f"❌ Error setting webhook: {e}")
    else:
        # Development mode: Use polling
        print("🚀 Starting bot in polling mode (development)...")
        try:
            bot.remove_webhook()
            print("✅ Removed existing webhooks")
            print("🔄 Bot is running... Press Ctrl+C to stop.")
            bot.infinity_polling(none_stop=True, timeout=10, long_polling_timeout=5)
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user.")
        except Exception as e:
            print(f"❌ Error in polling mode: {e}")
