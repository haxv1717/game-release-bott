"""🎮 Game Release Bot  (python-telegram-bot >= 21)"""
import html
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    MessageHandler,
    filters
)

TOKEN = "TOKEN_BOT"
ADMINS = {7409111335}
DB_FILE = "gaoo66mmp.db"
HTML = ParseMode.HTML

CUSTOM = {"🎮": "", "📅": "", "👾": "", "🕹": "", "🏞": ""}


def em(ch):
    cid = CUSTOM.get(ch)
    return f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>' if cid else ch


# ───────────────────────── Database ─────────────────────────

def db(sql, args=(), one=False):
    with closing(sqlite3.connect(DB_FILE)) as c, c:
        c.row_factory = sqlite3.Row
        cur = c.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


SEED = [
    ("GTA VI", "2026-11-19 14:00", "PS5, Xbox", "Rockstar Games", ""),
    ("Call of Duty Modern Warfer 4", "2026-10-23 00:00",
     "PS5, Xbox, PC", "Infinity Ward", ""),
    ("Gears of War: E-Day", "2026-10-06 00:00",
     "PC, Xbox", "Xbox", ""),
    ("Until Dawn 2", "2027-01-28 00:00",
     "PS5", "Ballistic Moon", ""),

    ("Stranger Than Heaven", "2027-01-15 00:00",
     "PS5, Xbox Series X/S, PC", "Ryu Ga Gotoku Studio", ""),
    ("Ananta", "2027-01-15 00:00",
     "PS5, PC, iOS, Android", "Naked Rain", ""),
    ("Metro 2039", "2027-02-04 00:00",
     "PS5, Xbox Series X/S, PC", "4A Games", ""),
    ("Tomb Raider: Legacy of Atlantis", "2027-02-12 00:00",
     "PS5, Xbox Series X/S, Switch 2, PC",
     "Crystal Dynamics / Flying Wild Hog", ""),
    ("God of War: Laufey", "2027-02-16 00:00",
     "PS5", "Santa Monica Studio", ""),
    ("Persona 4 Revival", "2027-02-18 00:00",
     "PS5, Xbox Series X/S, PC", "Atlus", ""),
    ("Fable", "2027-02-23 00:00",
     "PS5, Xbox Series X/S, PC", "Playground Games", ""),
    ("Trine 6: Together in Time", "2027-03-04 00:00",
     "PS5, Xbox Series X/S, Switch 2, Switch, PC",
     "Frozenbyte", ""),
    ("Wo Long 2: Wings of Ember", "2027-03-04 00:00",
     "PS5, Xbox Series X/S, Switch 2, PC", "Team NINJA", ""),
    ("Gundam Rogue Orbit", "2027-03-05 00:00",
     "PS5, Xbox Series X/S, PC", "Bandai Namco", ""),
    ("Road Kings", "2027-03-11 00:00",
     "PS5, Xbox Series X/S, PC", "Saber Interactive", ""),
    ("Exodus", "2027-04-07 00:00",
     "PS5, Xbox Series X/S, PC", "Archetype Entertainment", ""),
    ("Final Fantasy VII Revelation", "2027-04-08 00:00",
     "PS5, Xbox Series X/S, Switch 2, PC", "Square Enix", ""),
    ("Mariachi Legends", "2027-04-27 00:00",
     "PS5, Xbox Series X/S, Switch, PC", "Halberd Studios", ""),
]


def init_db():
    for sql in (
        "CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " title TEXT, release_date TEXT, platforms TEXT, company TEXT,"
        " image TEXT DEFAULT '', description TEXT DEFAULT '')",

        "CREATE TABLE IF NOT EXISTS users("
        "id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'en')",

        "CREATE TABLE IF NOT EXISTS groups("
        "id INTEGER PRIMARY KEY, title TEXT, lang TEXT DEFAULT 'en',"
        " active INTEGER DEFAULT 1, added_by INTEGER, added_at TEXT)",

        "CREATE TABLE IF NOT EXISTS views("
        "game_id INTEGER, user_id INTEGER,"
        "PRIMARY KEY(game_id, user_id))",

        "CREATE TABLE IF NOT EXISTS texts("
        "key TEXT, lang TEXT, value TEXT,"
        "PRIMARY KEY(key, lang))",
    ):
        db(sql)

    if not db("SELECT 1 FROM games", one=True):
        for row in SEED:
            db(
                "INSERT INTO games("
                "title,release_date,platforms,company,description"
                ") VALUES(?,?,?,?,?)",
                row
            )


# ───────────────────────── Texts / i18n ─────────────────────────

TEXTS = {
    "welcome": {
        "en": "👋 Welcome to <b>Game Release</b>!\n"
              "Track upcoming games with a live countdown.\n\n"
              "Send a game name to get its info.\n"
              "/games – all games\n"
              "/upcoming – nearest releases\n"
              "/search – find a game",

        "fa": "👋 به ربات <b>Game Release</b> خوش آمدید!\n"
              "زمان انتشار بازی‌ها را با شمارش معکوس دنبال کنید.\n\n"
              "اسم بازی را بفرستید تا اطلاعاتش را ببینید.\n"
              "/games – همه بازی‌ها\n"
              "/upcoming – نزدیک‌ترین بازی‌ها\n"
              "/search – جستجوی بازی",
    },

    "search": {
        "en": "🔎 Send the game name:",
        "fa": "🔎 نام بازی را بفرستید:"
    },

    "notfound": {
        "en": "😕 No game found.",
        "fa": "😕 بازی‌ای پیدا نشد."
    },

    "empty": {
        "en": "📭 No games yet.",
        "fa": "📭 هنوز بازی‌ای ثبت نشده."
    },

    "released": {
        "en": "✅ Released",
        "fa": "✅ منتشر شده"
    },
}


def txt(key, lang):
    r = db(
        "SELECT value FROM texts WHERE key=? AND lang=?",
        (key, lang),
        one=True
    )
    return r["value"] if r else TEXTS[key][lang]


LANG_KB = Kb([
    [
        Btn("🇬🇧 English", callback_data="lang:en"),
        Btn("🇮🇷 فارسی", callback_data="lang:fa")
    ]
])


def lang_of(chat, user):
    t, i = (
        ("users", user.id)
        if chat.type == ChatType.PRIVATE
        else ("groups", chat.id)
    )

    r = db(
        f"SELECT lang FROM {t} WHERE id=?",
        (i,),
        one=True
    )

    return r["lang"] if r else "en"


def prep(update):
    chat, user = update.effective_chat, update.effective_user

    if chat.type == ChatType.PRIVATE:
        db(
            "INSERT OR IGNORE INTO users(id) VALUES(?)",
            (user.id,)
        )

    return lang_of(chat, user)


# ───────────────────────── Game formatting ─────────────────────────

def parse_date(s):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(
                s.strip(), fmt
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def countdown(date_str, lang):
    left = int(
        (
            parse_date(date_str)
            - datetime.now(timezone.utc)
        ).total_seconds()
    )

    if left <= 0:
        return txt("released", lang)

    d, r = divmod(left, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)

    return f"{d}D {h:02}H {m:02}M {s:02}S"


def card(g, lang, full=False):
    e = html.escape

    out = (
        f"{em('🎮')} <b>{e(g['title'])}</b>\n"
        f"{em('💭')} "
        f"{parse_date(g['release_date']):%d %b %Y}\n"
        f"{em('👾')} {e(g['company'])}\n"
        f"{em('🕹')} {e(g['platforms'])}\n"
        f"{em('🏞')} {countdown(g['release_date'], lang)}"
    )

    if full and g["description"]:
        out += f"\n\n{e(g['description'][:500])}"

    return out


async def show(update, games, lang, photos=False, empty_key="empty"):
    msg, uid = (
        update.effective_message,
        update.effective_user.id
    )

    if not games:
        return await msg.reply_text(
            txt(empty_key, lang)
        )

    for g in games:
        db(
            "INSERT OR IGNORE INTO views VALUES(?,?)",
            (g["id"], uid)
        )

    if photos:
        for g in games:
            if g["image"]:
                await msg.reply_photo(
                    g["image"],
                    caption=card(g, lang, True),
                    parse_mode=HTML
                )
            else:
                await msg.reply_html(
                    card(g, lang, True)
                )
    else:
        for i in range(0, len(games), 10):
            await msg.reply_html(
                "\n\n".join(
                    card(g, lang)
                    for g in games[i:i + 10]
                )
            )


# ───────────────────────── PAGINATION ─────────────────────────

PAGE_SIZE = 3


async def show_games_page(update, page=0, edit=False):
    lang = prep(update)

    all_games = db(
        "SELECT * FROM games ORDER BY release_date"
    )

    total_pages = max(
        1,
        (len(all_games) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    page = max(
        0,
        min(page, total_pages - 1)
    )

    start = page * PAGE_SIZE
    page_games = all_games[
        start:start + PAGE_SIZE
    ]

    if not page_games:
        text = txt("empty", lang)
    else:
        text = "\n\n".join(
            card(g, lang)
            for g in page_games
        )

    buttons = []

    if page > 0:
        buttons.append(
            Btn(
                "⬅️ قبلی",
                callback_data=f"games:{page - 1}"
            )
        )

    buttons.append(
        Btn(
            f"📄 {page + 1}/{total_pages}",
            callback_data="games:current"
        )
    )

    if page < total_pages - 1:
        buttons.append(
            Btn(
                "➡️ بعدی",
                callback_data=f"games:{page + 1}"
            )
        )

    keyboard = Kb([buttons])

    if edit:
        try:
            await update.callback_query.edit_message_text(
                text,
                parse_mode=HTML,
                reply_markup=keyboard
            )
        except BadRequest:
            pass
    else:
        await update.effective_message.reply_html(
            text,
            reply_markup=keyboard
        )


async def games_page_cb(update: Update, ctx):
    q = update.callback_query

    if q.data == "games:current":
        return await q.answer()

    try:
        page = int(q.data.split(":")[1])
    except (ValueError, IndexError):
        return await q.answer()

    await q.answer()

    await show_games_page(
        update,
        page,
        edit=True
    )


# ───────────────────────── User commands ─────────────────────────

async def start(update: Update, ctx):
    lang = prep(update)

    await update.effective_message.reply_html(
        txt("welcome", lang),
        reply_markup=LANG_KB
    )


async def set_lang(update: Update, ctx):
    q = update.callback_query

    chat = q.message.chat
    lang = q.data.split(":")[1]

    if chat.type == ChatType.PRIVATE:
        db(
            "INSERT INTO users(id,lang) VALUES(?,?) "
            "ON CONFLICT(id) DO UPDATE SET lang=excluded.lang",
            (q.from_user.id, lang)
        )

    else:
        if (
            await chat.get_member(q.from_user.id)
        ).status not in ("administrator", "creator"):
            return await q.answer(
                "⛔ Admins only / فقط ادمین‌ها",
                show_alert=True
            )

        db(
            "UPDATE groups SET lang=? WHERE id=?",
            (lang, chat.id)
        )

    await q.answer()

    try:
        await q.edit_message_text(
            txt("welcome", lang),
            parse_mode=HTML,
            reply_markup=LANG_KB
        )
    except BadRequest:
        pass


async def games(update: Update, ctx):
    await show_games_page(update, 0)


async def upcoming(update: Update, ctx):
    lang = prep(update)

    now = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M")

    rows = db(
        "SELECT * FROM games "
        "WHERE release_date>=? "
        "ORDER BY release_date LIMIT 5",
        (now,)
    )

    await show(
        update,
        rows,
        lang,
        photos=True
    )


async def do_search(update, term, lang, silent=False):
    term = term.strip()

    if silent and len(term) < 3:
        return

    rows = db(
        "SELECT * FROM games "
        "WHERE title LIKE ? "
        "ORDER BY release_date",
        (f"%{term}%",)
    )

    if rows or not silent:
        await show(
            update,
            rows,
            lang,
            photos=True,
            empty_key="notfound"
        )


async def search(update: Update, ctx):
    lang = prep(update)

    if ctx.args:
        return await do_search(
            update,
            " ".join(ctx.args),
            lang
        )

    await update.effective_message.reply_text(
        txt("search", lang)
    )


# ───────────────────────── Groups tracking ─────────────────────────

async def on_group(update: Update, ctx):
    ev = update.my_chat_member

    chat = ev.chat
    status = ev.new_chat_member.status

    if chat.type == ChatType.PRIVATE:
        return

    if status in ("member", "administrator"):
        db(
            "INSERT INTO groups("
            "id,title,added_by,added_at"
            ") VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "active=1,title=excluded.title",
            (
                chat.id,
                chat.title,
                ev.from_user.id,
                datetime.now().strftime(
                    "%Y-%m-%d"
                )
            )
        )

        lang = lang_of(
            chat,
            ev.from_user
        )

        await ctx.bot.send_message(
            chat.id,
            txt("welcome", lang),
            parse_mode=HTML,
            reply_markup=LANG_KB
        )

    elif status in ("left", "kicked"):
        db(
            "UPDATE groups SET active=0 WHERE id=?",
            (chat.id,)
        )


# ───────────────────────── Admin panel ─────────────────────────

FIELDS = [
    "title",
    "release_date",
    "platforms",
    "company",
    "description",
    "image"
]

PROMPTS = {
    "title": "🎮 نام بازی؟",

    "release_date":
        "📅 تاریخ انتشار (UTC)\n"
        "مثال: 2027-05-26 یا 2027-05-26 18:30",

    "platforms":
        "🕹 پلتفرم‌ها؟ مثال: PC, PS5, Xbox",

    "company":
        "⛩ شرکت سازنده؟",

    "description":
        "📝 توضیحات؟",

    "image":
        "🖼 عکس کاور را بفرستید (برای رد کردن: -)",
}

PANEL = Kb([
    [
        Btn(
            "➕ افزودن بازی",
            callback_data="a:add"
        )
    ],
    [
        Btn(
            "✏️ ویرایش بازی",
            callback_data="a:edit"
        ),
        Btn(
            "🗑 حذف بازی",
            callback_data="a:del"
        )
    ],
    [
        Btn(
            "📊 آمار",
            callback_data="a:stats"
        ),
        Btn(
            "📝 متن‌های ربات",
            callback_data="a:texts"
        )
    ],
])


async def admin(update: Update, ctx):
    if (
        update.effective_user.id in ADMINS
        and update.effective_chat.type == ChatType.PRIVATE
    ):
        await update.message.reply_text(
            "⚙️ پنل مدیریت",
            reply_markup=PANEL
        )


def stats_text():
    n = lambda sql: db(
        sql,
        one=True
    )[0]

    out = (
        f"👥 کاربران: "
        f"{n('SELECT COUNT(*) FROM users')}\n"
        f"🏘 گروه‌ها: "
        f"{n('SELECT COUNT(*) FROM groups WHERE active=1')} فعال / "
        f"{n('SELECT COUNT(*) FROM groups')} کل\n\n"
        f"👁 بازدید هر بازی:\n"
    )

    out += "\n".join(
        f"• {html.escape(r['title'])}: {r['n']}"
        for r in db(
            "SELECT g.title, COUNT(v.user_id) n "
            "FROM games g "
            "LEFT JOIN views v ON v.game_id=g.id "
            "GROUP BY g.id ORDER BY n DESC"
        )
    ) or "-"

    out += (
        "\n\n🏘 آخرین گروه‌ها:\n"
        + "\n".join(
            f"{'✅' if r['active'] else '❌'} "
            f"{html.escape(r['title'] or '?')} — "
            f"{r['added_at']}"
            for r in db(
                "SELECT * FROM groups "
                "ORDER BY added_at DESC LIMIT 10"
            )
        )
    )

    return out


async def admin_cb(update: Update, ctx):
    q = update.callback_query

    if q.from_user.id not in ADMINS:
        return await q.answer(
            "⛔",
            show_alert=True
        )

    await q.answer()

    _, act, *a = q.data.split(":")

    ud = ctx.user_data
    send = q.message.reply_text

    pick = lambda pre: Kb([
        [
            Btn(
                g["title"],
                callback_data=f"a:{pre}:{g['id']}"
            )
        ]
        for g in db(
            "SELECT id,title FROM games ORDER BY title"
        )
    ])

    if act == "add":
        ud["job"] = {
            "kind": "add",
            "field": FIELDS[0],
            "data": {}
        }

        await send(
            PROMPTS[FIELDS[0]]
        )

    elif act in ("edit", "del"):
        await send(
            "🎮 بازی را انتخاب کنید:",
            reply_markup=pick(
                "pick" if act == "edit" else "rm"
            )
        )

    elif act == "pick":
        await send(
            "کدام بخش ویرایش شود؟",
            reply_markup=Kb([
                [
                    Btn(
                        f"{PROMPTS[f].split()[0]} {f}",
                        callback_data=f"a:f:{a[0]}:{f}"
                    )
                ]
                for f in FIELDS
            ])
        )

    elif act == "f" and a[1] in FIELDS:
        ud["job"] = {
            "kind": "edit",
            "id": int(a[0]),
            "field": a[1]
        }

        await send(
            PROMPTS[a[1]]
        )

    elif act == "rm":
        db(
            "DELETE FROM games WHERE id=?",
            (a[0],)
        )

        db(
            "DELETE FROM views WHERE game_id=?",
            (a[0],)
        )

        await send("🗑 حذف شد.")

    elif act == "stats":
        await q.message.reply_html(
            stats_text()
        )

    elif act == "texts":
        await send(
            "📝 کدام متن؟",
            reply_markup=Kb([
                [
                    Btn(
                        f"{k} [{l}]",
                        callback_data=f"a:t:{k}:{l}"
                    )
                    for l in ("en", "fa")
                ]
                for k in TEXTS
            ])
        )

    elif act == "t":
        ud["job"] = {
            "kind": "text",
            "key": a[0],
            "lang": a[1]
        }

        await q.message.reply_html(
            f"متن فعلی:\n"
            f"<code>{html.escape(txt(a[0], a[1]))}</code>\n\n"
            "متن جدید را بفرستید "
            "(بولد و فرمت‌های تلگرام حفظ می‌شود)."
        )


def read_field(m, field):
    if field == "image":
        if m.photo:
            return m.photo[-1].file_id, None

        return (
            ("", None)
            if (m.text or "").strip() == "-"
            else (None, "❌ عکس بفرستید یا - بزنید")
        )

    if not m.text:
        return None, "❌ متن بفرستید"

    if field == "release_date":
        d = parse_date(m.text)

        return (
            (d.strftime("%Y-%m-%d %H:%M"), None)
            if d
            else (None, "❌ فرمت تاریخ نادرست است")
        )

    return m.text.strip(), None


async def admin_input(update: Update, ctx):
    m = update.message
    job = ctx.user_data["job"]

    if job["kind"] == "text":
        if not m.text:
            return

        db(
            "INSERT OR REPLACE INTO texts VALUES(?,?,?)",
            (
                job["key"],
                job["lang"],
                m.text_html
            )
        )

        ctx.user_data.pop("job")

        return await m.reply_text(
            "✅ ذخیره شد."
        )

    field = job["field"]

    val, err = read_field(
        m,
        field
    )

    if err:
        return await m.reply_text(err)

    if job["kind"] == "edit":
        db(
            f"UPDATE games SET {field}=? WHERE id=?",
            (val, job["id"])
        )

        ctx.user_data.pop("job")

        return await m.reply_text(
            "✅ ویرایش شد."
        )

    job["data"][field] = val

    i = FIELDS.index(field) + 1

    if i < len(FIELDS):
        job["field"] = FIELDS[i]

        return await m.reply_text(
            PROMPTS[FIELDS[i]]
        )

    db(
        "INSERT INTO games("
        "title,release_date,platforms,company,description,image"
        ") VALUES(?,?,?,?,?,?)",
        tuple(
            job["data"][f]
            for f in FIELDS
        )
    )

    ctx.user_data.pop("job")

    await m.reply_text(
        "✅ بازی اضافه شد."
    )


async def cancel(update: Update, ctx):
    ctx.user_data.clear()

    await update.message.reply_text(
        "❎ Cancelled"
    )


# ───────────────────────── Message router ─────────────────────────

async def on_message(update: Update, ctx):
    m = update.message
    ud = ctx.user_data

    if update.effective_user.id in ADMINS:
        if "job" in ud:
            return await admin_input(
                update,
                ctx
            )

        ids = [
            e.custom_emoji_id
            for e in m.entities
            if e.type == "custom_emoji"
        ]

        if ids:
            return await m.reply_text(
                "\n".join(ids)
            )

    if m.text:
        private = (
            update.effective_chat.type
            == ChatType.PRIVATE
        )

        await do_search(
            update,
            m.text,
            prep(update),
            silent=not private
        )


# ───────────────────────── Main ─────────────────────────

def main():
    init_db()

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    for name, fn in (
        ("start", start),
        ("games", games),
        ("upcoming", upcoming),
        ("search", search),
        ("admin", admin),
        ("cancel", cancel),
    ):
        app.add_handler(
            CommandHandler(name, fn)
        )

    # Language buttons
    app.add_handler(
        CallbackQueryHandler(
            set_lang,
            pattern=r"^lang:"
        )
    )

    # Games pagination
    app.add_handler(
        CallbackQueryHandler(
            games_page_cb,
            pattern=r"^games:"
        )
    )

    # Admin panel
    app.add_handler(
        CallbackQueryHandler(
            admin_cb,
            pattern=r"^a:"
        )
    )

    # Group tracking
    app.add_handler(
        ChatMemberHandler(
            on_group,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    # Text messages
    app.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO,
            on_message
        )
    )

    print("🎮 Game Release Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()