import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_USERNAME = "Tigermate23"
SHOP_NAME = "LUXENT PRIME"
BKASH_NUMBER = os.environ.get("BKASH_NUMBER", "01XXXXXXXXX")
CRYPTO_ADDRESS = os.environ.get("CRYPTO_ADDRESS", "YOUR_USDT_TRC20_ADDRESS")

# ─── DATA FILES ────────────────────────────────────────────
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

# ─── CONVERSATION STATES ──────────────────────────────────
ADD_NAME, ADD_DESC, ADD_PRICE, ADD_STOCK = range(4)
DEPOSIT_AMOUNT, DEPOSIT_METHOD, DEPOSIT_PROOF = range(10, 13)

# ─── DATA HELPERS ─────────────────────────────────────────
def load_json(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_products():
    return load_json(PRODUCTS_FILE)

def get_orders():
    return load_json(ORDERS_FILE)

def get_users():
    return load_json(USERS_FILE)

def ensure_user(user_id, username):
    users = get_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"username": username, "balance": 0.0, "orders": []}
        save_json(USERS_FILE, users)
    return users[uid]

def is_admin(username):
    return username == ADMIN_USERNAME

# ─── KEYBOARDS ────────────────────────────────────────────
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛍️ Shop"), KeyboardButton("💰 Deposit")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🔔 Referral")],
        [KeyboardButton("✨ Clear Chat"), KeyboardButton("🆘 Support")],
        [KeyboardButton("🏠 Home")],
    ], resize_keyboard=True)

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("🗑️ Delete Product", callback_data="admin_delete")],
        [InlineKeyboardButton("📦 All Orders", callback_data="admin_orders")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("✅ Approve Deposit", callback_data="admin_approve")],
    ])

# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or user.first_name)

    text = (
        f"👋 *Welcome to {SHOP_NAME}!*\n\n"
        f"We offer premium digital products at the best prices.\n"
        f"Fast, secure, and fully automated delivery. ⚡\n\n"
        f"🛍️ *Shop* — Browse & buy products\n"
        f"💰 *Deposit* — Add funds to your wallet\n"
        f"👤 *Profile* — Balance, orders & settings\n"
        f"🔔 *Referral* — Invite friends & earn rewards\n"
        f"✨ *Clear Chat* — Clean up the conversation\n"
        f"🆘 *Support* — Get help\n\n"
        f"Choose an option below to get started! 👇"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

# ─── SHOP ─────────────────────────────────────────────────
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_products()
    if not products:
        await update.message.reply_text("😔 No products available right now. Check back soon!")
        return

    text = f"🛍️ *{SHOP_NAME} — Products*\n\n"
    buttons = []
    for pid, p in products.items():
        stock_icon = "✅" if int(p.get("stock", 0)) > 0 else "❌"
        text += f"{stock_icon} *{p['name']}*\n💵 ${p['price']} | 📦 Stock: {p['stock']}\n_{p['desc']}_\n\n"
        if int(p.get("stock", 0)) > 0:
            buttons.append([InlineKeyboardButton(f"🛒 Buy {p['name']} — ${p['price']}", callback_data=f"buy_{pid}")])

    if not buttons:
        text += "⚠️ All products are currently out of stock."

    await update.message.reply_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

# ─── BUY PRODUCT ──────────────────────────────────────────
async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.replace("buy_", "")
    products = get_products()
    user = query.from_user
    users = get_users()
    uid = str(user.id)
    ensure_user(user.id, user.username)

    if pid not in products:
        await query.edit_message_text("❌ Product not found.")
        return

    p = products[pid]
    price = float(p["price"])
    balance = float(users[uid]["balance"])

    if int(p["stock"]) <= 0:
        await query.edit_message_text("❌ This product is out of stock.")
        return

    if balance < price:
        await query.edit_message_text(
            f"❌ *Insufficient Balance!*\n\n"
            f"💵 Product Price: ${price}\n"
            f"💰 Your Balance: ${balance:.2f}\n\n"
            f"Please deposit funds first using 💰 *Deposit*.",
            parse_mode="Markdown"
        )
        return

    # Deduct balance
    users[uid]["balance"] = round(balance - price, 2)

    # Save order
    orders = get_orders()
    order_id = f"ORD{len(orders)+1:04d}"
    orders[order_id] = {
        "user_id": uid,
        "username": user.username,
        "product": p["name"],
        "price": price,
        "status": "completed"
    }
    products[pid]["stock"] = int(p["stock"]) - 1
    users[uid]["orders"].append(order_id)

    save_json(USERS_FILE, users)
    save_json(ORDERS_FILE, orders)
    save_json(PRODUCTS_FILE, products)

    await query.edit_message_text(
        f"✅ *Order Successful!*\n\n"
        f"📦 Product: *{p['name']}*\n"
        f"💵 Price: ${price}\n"
        f"🆔 Order ID: `{order_id}`\n"
        f"💰 Remaining Balance: ${users[uid]['balance']:.2f}\n\n"
        f"Thank you for shopping at *{SHOP_NAME}*! 🎉",
        parse_mode="Markdown"
    )

# ─── DEPOSIT ──────────────────────────────────────────────
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 bKash", callback_data="dep_bkash")],
        [InlineKeyboardButton("₿ Crypto (USDT TRC20)", callback_data="dep_crypto")],
    ])
    await update.message.reply_text(
        f"💰 *Deposit Funds*\n\nChoose your payment method:",
        parse_mode="Markdown", reply_markup=buttons
    )

async def deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "dep_bkash":
        text = (
            f"📱 *bKash Deposit*\n\n"
            f"1️⃣ Send money to: `{BKASH_NUMBER}`\n"
            f"2️⃣ Use *Send Money* option\n"
            f"3️⃣ After payment, send screenshot + amount to @{ADMIN_USERNAME}\n\n"
            f"⏱️ Your balance will be updated within 30 minutes."
        )
    else:
        text = (
            f"₿ *Crypto Deposit (USDT TRC20)*\n\n"
            f"Send USDT to:\n`{CRYPTO_ADDRESS}`\n\n"
            f"After sending, contact @{ADMIN_USERNAME} with:\n"
            f"• Transaction Hash (TXID)\n"
            f"• Amount sent\n\n"
            f"⏱️ Confirmed within 1-10 minutes."
        )

    await query.edit_message_text(text, parse_mode="Markdown")

# ─── PROFILE ──────────────────────────────────────────────
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = get_users()
    uid = str(user.id)
    ensure_user(user.id, user.username)
    u = users[uid]

    text = (
        f"👤 *Your Profile*\n\n"
        f"🆔 User ID: `{user.id}`\n"
        f"👤 Username: @{user.username}\n"
        f"💰 Balance: *${float(u['balance']):.2f}*\n"
        f"📦 Total Orders: *{len(u['orders'])}*\n\n"
        f"Use 💰 *Deposit* to add funds."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── SUPPORT ──────────────────────────────────────────────
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆘 *Support*\n\n"
        f"For help, contact our admin directly:\n"
        f"👤 @{ADMIN_USERNAME}\n\n"
        f"⏱️ Response time: within 1 hour.",
        parse_mode="Markdown"
    )

# ─── CLEAR CHAT ───────────────────────────────────────────
async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Chat cleared! Type /start to begin again.",
        reply_markup=main_menu_keyboard()
    )

# ─── REFERRAL ─────────────────────────────────────────────
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"
    await update.message.reply_text(
        f"🔔 *Referral Program*\n\n"
        f"Share your link and earn rewards!\n\n"
        f"🔗 Your Link:\n`{link}`\n\n"
        f"💰 Earn $1 for every friend who joins & deposits!",
        parse_mode="Markdown"
    )

# ─── HOME ─────────────────────────────────────────────────
async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ══════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.username):
        await update.message.reply_text("❌ Access denied.")
        return
    await update.message.reply_text(
        f"🔐 *ADMIN PANEL — {SHOP_NAME}*\n\nChoose an action:",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )

# ─── ADD PRODUCT (Conversation) ───────────────────────────
async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.username):
        await query.edit_message_text("❌ Access denied.")
        return ConversationHandler.END
    await query.edit_message_text("➕ *Add New Product*\n\nStep 1/4: Send the *product name*:", parse_mode="Markdown")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"] = {"name": update.message.text}
    await update.message.reply_text("Step 2/4: Send the *description*:", parse_mode="Markdown")
    return ADD_DESC

async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["desc"] = update.message.text
    await update.message.reply_text("Step 3/4: Send the *price* (e.g. 5.99):", parse_mode="Markdown")
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data["new_product"]["price"] = price
        await update.message.reply_text("Step 4/4: Send the *stock quantity*:", parse_mode="Markdown")
        return ADD_STOCK
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Send a number like 5.99:")
        return ADD_PRICE

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        products = get_products()
        pid = f"P{len(products)+1:03d}"
        context.user_data["new_product"]["stock"] = stock
        products[pid] = context.user_data["new_product"]
        save_json(PRODUCTS_FILE, products)
        p = products[pid]
        await update.message.reply_text(
            f"✅ *Product Added!*\n\n"
            f"🆔 ID: `{pid}`\n"
            f"📦 Name: {p['name']}\n"
            f"💵 Price: ${p['price']}\n"
            f"📊 Stock: {p['stock']}\n",
            parse_mode="Markdown",
            reply_markup=admin_menu_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Send stock quantity:")
        return ADD_STOCK

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─── DELETE PRODUCT ───────────────────────────────────────
async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.username):
        return
    products = get_products()
    if not products:
        await query.edit_message_text("No products to delete.")
        return
    buttons = [[InlineKeyboardButton(f"🗑️ {p['name']}", callback_data=f"del_{pid}")] for pid, p in products.items()]
    await query.edit_message_text("Select product to delete:", reply_markup=InlineKeyboardMarkup(buttons))

async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.replace("del_", "")
    products = get_products()
    if pid in products:
        name = products[pid]["name"]
        del products[pid]
        save_json(PRODUCTS_FILE, products)
        await query.edit_message_text(f"✅ *{name}* deleted successfully!", parse_mode="Markdown")
    else:
        await query.edit_message_text("❌ Product not found.")

# ─── ADMIN ORDERS ─────────────────────────────────────────
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    orders = get_orders()
    if not orders:
        await query.edit_message_text("📦 No orders yet.")
        return
    text = "📦 *All Orders:*\n\n"
    for oid, o in list(orders.items())[-10:]:
        text += f"🆔 `{oid}` | @{o.get('username','?')} | {o['product']} | ${o['price']}\n"
    await query.edit_message_text(text, parse_mode="Markdown")

# ─── ADMIN USERS ──────────────────────────────────────────
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = get_users()
    text = f"👥 *Total Users: {len(users)}*\n\n"
    for uid, u in list(users.items())[-10:]:
        text += f"👤 @{u.get('username','?')} | 💰 ${float(u['balance']):.2f} | 📦 {len(u['orders'])} orders\n"
    await query.edit_message_text(text, parse_mode="Markdown")

# ─── MANUAL BALANCE ADD (Admin) ───────────────────────────
async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.username):
        await update.message.reply_text("❌ Access denied.")
        return
    try:
        # /addbalance @username 10.00
        _, target, amount = update.message.text.split()
        target = target.replace("@", "")
        amount = float(amount)
        users = get_users()
        for uid, u in users.items():
            if u.get("username") == target:
                users[uid]["balance"] = round(float(u["balance"]) + amount, 2)
                save_json(USERS_FILE, users)
                await update.message.reply_text(f"✅ Added ${amount} to @{target}. New balance: ${users[uid]['balance']}")
                return
        await update.message.reply_text(f"❌ User @{target} not found.")
    except:
        await update.message.reply_text("Usage: /addbalance @username 10.00")

# ─── MESSAGE HANDLER ──────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🛍️ Shop":
        await shop(update, context)
    elif text == "💰 Deposit":
        await deposit(update, context)
    elif text == "👤 Profile":
        await profile(update, context)
    elif text == "🔔 Referral":
        await referral(update, context)
    elif text == "✨ Clear Chat":
        await clear_chat(update, context)
    elif text == "🆘 Support":
        await support(update, context)
    elif text == "🏠 Home":
        await home(update, context)

# ─── MAIN ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Add product conversation
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(admin_orders, pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(delete_confirm, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(deposit_callback, pattern="^dep_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"🚀 {SHOP_NAME} Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
