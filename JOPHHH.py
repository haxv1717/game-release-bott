"""🎮 Game Release Bot  (python-telegram-bot >= 21)"""
import html
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

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

# ⚠️ توکن رباتت را بین دو کوتیشن بنویس. این فایل را روی GitHub نگذار!
TOKEN = "BOT_TUKEN"
ADMINS = {7409111335}
DB_FILE = "gaoo66mmp.db"
HTML = ParseMode.HTML

# ───────────────────── Premium emoji (managed from admin panel) ─────────────────────

_EMO = {}
_EMO_RE = None
_TAG_RE = re.compile(r"(<tg-emoji[^>]*>.*?</tg-emoji>)", re.S)


def _norm(ch):
    return ch.replace("\ufe0f", "").strip()


def load_emojis():
    global _EMO, _EMO_RE

    _EMO = {
        r["ch"]: r["cid"]
        for r in db("SELECT ch,cid FROM emojis")
    }

    _EMO_RE = (
        re.compile(
            "("
            + "|".join(
                re.escape(k)
                for k in sorted(_EMO, key=len, reverse=True)
            )
            + ")\ufe0f?"
        )
        if _EMO else None
    )


def fx(s):
    """Replace mapped emojis with premium <tg-emoji> tags (HTML only)."""
    if not _EMO_RE:
        return s

    def sub(m):
        return (
            f'<tg-emoji emoji-id="{_EMO[m.group(1)]}">'
            f'{m.group(1)}</tg-emoji>'
        )

    return "".join(
        part if i % 2 else _EMO_RE.sub(sub, part)
        for i, part in enumerate(_TAG_RE.split(s))
    )


def em(ch):
    return fx(ch)


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

        "CREATE TABLE IF NOT EXISTS settings("
        "key TEXT PRIMARY KEY, value TEXT)",

        "CREATE TABLE IF NOT EXISTS admins("
        "id INTEGER PRIMARY KEY, added_at TEXT)",

        "CREATE TABLE IF NOT EXISTS emojis("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ch TEXT UNIQUE, cid TEXT)",
    ):
        db(sql)

    for col in ("joined_at", "last_seen"):
        try:
            db(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    load_emojis()

    if not db("SELECT 1 FROM games", one=True):
        for row in SEED:
            db(
                "INSERT INTO games("
                "title,release_date,platforms,company,description"
                ") VALUES(?,?,?,?,?)",
                row
            )


# ───────────────────────── Settings / admins / colors / support ─────────────────────────

def now_s():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def get_set(key, default=None):
    r = db(
        "SELECT value FROM settings WHERE key=?",
        (key,),
        one=True
    )
    return r["value"] if r else default


def put_set(key, value):
    if value is None:
        db("DELETE FROM settings WHERE key=?", (key,))
    else:
        db(
            "INSERT OR REPLACE INTO settings VALUES(?,?)",
            (key, value)
        )


def is_owner(uid):
    return uid in ADMINS


def is_admin(uid):
    return uid in ADMINS or bool(
        db("SELECT 1 FROM admins WHERE id=?", (uid,), one=True)
    )


# (code, emoji, name)
COLORS = (
    ("primary", "🔵", "آبی"),
    ("success", "🟢", "سبز"),
    ("danger", "🔴", "قرمز"),
    ("none", "⚪", "بدون رنگ"),
)

# (key, label, default color)
COLOR_GROUPS = (
    ("lang_en", "🇬🇧 دکمه انگلیسی", "primary"),
    ("lang_fa", "🇮🇷 دکمه فارسی", "success"),
    ("nav", "⬅️➡️ قبلی / بعدی", "primary"),
    ("support", "💬 دکمه پشتیبانی", "success"),
    ("p_add", "➕ پنل: افزودن", "success"),
    ("p_edit", "✏️ پنل: ویرایش", "primary"),
    ("p_del", "🗑 پنل: حذف", "danger"),
    ("p_other", "⚙️ پنل: بقیه دکمه‌ها", "primary"),
)

DEFAULT_COLOR = {k: d for k, _, d in COLOR_GROUPS}


def color_name(code):
    return next(
        (f"{e} {n}" for c, e, n in COLORS if c == code),
        "⚪ بدون رنگ"
    )


def sty(group):
    v = get_set("color:" + group, DEFAULT_COLOR[group])
    return v if v in ("primary", "success", "danger") else None


def B(text, group, **kw):
    """Inline button whose color is controlled from the admin panel."""
    return Btn(text, style=sty(group), **kw)


def parse_support(raw):
    s = re.sub(
        r"^(https?://)?(t\.me/|telegram\.me/)",
        "",
        raw.strip()
    ).lstrip("@")

    return s if re.fullmatch(r"\+?[A-Za-z0-9_\-]{4,64}", s) else None


def support_btn(lang):
    u = get_set("support")

    if not u:
        return None

    return B(
        txt("support_btn", lang),
        "support",
        url=f"https://t.me/{u}"
    )


# ───────────────────────── Texts / i18n ─────────────────────────

TEXTS = {
    "welcome": {
        "en": "👋 Welcome to <b>Game Release</b>!\n"
              "Track upcoming games with a live countdown.\n\n"
              "Send a game name to get its info.\n"
              "/games – all games\n"
              "/upcoming – nearest releases\n"
              "/search – find a game\n"
              "/support – contact support",

        "fa": "👋 به ربات <b>Game Release</b> خوش آمدید!\n"
              "زمان انتشار بازی‌ها را با شمارش معکوس دنبال کنید.\n\n"
              "اسم بازی را بفرستید تا اطلاعاتش را ببینید.\n"
              "/games – همه بازی‌ها\n"
              "/upcoming – نزدیک‌ترین بازی‌ها\n"
              "/search – جستجوی بازی\n"
              "/support – ارتباط با پشتیبانی",
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

    "support": {
        "en": "💬 Need help? Contact our support team:",
        "fa": "💬 به کمک نیاز دارید؟ با پشتیبانی در تماس باشید:"
    },

    "support_btn": {
        "en": "💬 Support",
        "fa": "💬 پشتیبانی"
    },

    "support_none": {
        "en": "Support is not available right now.",
        "fa": "در حال حاضر پشتیبانی تنظیم نشده است."
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


def txth(key, lang):
    """txt() with premium emojis applied (for HTML messages)."""
    return fx(txt(key, lang))


def lang_kb(lang="en"):
    rows = [[
        B("🇬🇧 English", "lang_en", callback_data="lang:en"),
        B("🇮🇷 فارسی", "lang_fa", callback_data="lang:fa"),
    ]]

    sb = support_btn(lang)

    if sb:
        rows.append([sb])

    return Kb(rows)


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
            "INSERT OR IGNORE INTO users(id,joined_at) VALUES(?,?)",
            (user.id, now_s())
        )

        db(
            "UPDATE users SET last_seen=? WHERE id=?",
            (now_s(), user.id)
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
        return await msg.reply_html(
            txth(empty_key, lang)
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
            B(
                "⬅️ قبلی",
                "nav",
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
            B(
                "➡️ بعدی",
                "nav",
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
        txth("welcome", lang),
        reply_markup=lang_kb(lang)
    )


async def support_cmd(update: Update, ctx):
    lang = prep(update)
    sb = support_btn(lang)

    if not sb:
        return await update.effective_message.reply_html(
            txth("support_none", lang)
        )

    await update.effective_message.reply_html(
        txth("support", lang),
        reply_markup=Kb([[sb]])
    )


async def set_lang(update: Update, ctx):
    q = update.callback_query

    chat = q.message.chat
    lang = q.data.split(":")[1]

    if chat.type == ChatType.PRIVATE:
        db(
            "INSERT INTO users(id,lang,joined_at) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET lang=excluded.lang",
            (q.from_user.id, lang, now_s())
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
            txth("welcome", lang),
            parse_mode=HTML,
            reply_markup=lang_kb(lang)
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

    await update.effective_message.reply_html(
        txth("search", lang)
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
            txth("welcome", lang),
            parse_mode=HTML,
            reply_markup=lang_kb(lang)
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

def panel_kb(uid):
    rows = [
        [B("➕ افزودن بازی", "p_add", callback_data="a:add")],
        [
            B("✏️ ویرایش بازی", "p_edit", callback_data="a:edit"),
            B("🗑 حذف بازی", "p_del", callback_data="a:del"),
        ],
        [
            B("📊 آمار", "p_other", callback_data="a:stats"),
            B("📝 متن‌های ربات", "p_other", callback_data="a:texts"),
        ],
        [
            B("💬 پشتیبانی", "p_other", callback_data="a:sup"),
            B("🎨 رنگ دکمه‌ها", "p_other", callback_data="a:col"),
        ],
        [B("💎 ایموجی پرمیوم", "p_other", callback_data="a:emo")],
    ]

    if is_owner(uid):
        rows[-1].append(
            B("👮 ادمین‌ها", "p_other", callback_data="a:adm")
        )

    return Kb(rows)


def colors_kb():
    rows = [
        [
            B(
                f"{label} — {color_name(get_set('color:' + key, d))}",
                key,
                callback_data=f"a:cg:{key}"
            )
        ]
        for key, label, d in COLOR_GROUPS
    ]

    rows.append([Btn("🔙 بازگشت", callback_data="a:home")])

    return Kb(rows)


COLORS_TEXT = (
    "🎨 <b>رنگ دکمه‌ها</b>\n"
    "روی هر دکمه بزنید تا رنگش را عوض کنید.\n"
    "رنگ‌ها فقط در نسخه‌های جدید تلگرام دیده می‌شوند."
)


def admins_text():
    rows = db("SELECT id FROM admins ORDER BY added_at")

    return (
        "👮 <b>ادمین‌ها</b>\n\n"
        "👑 مالک: "
        + "، ".join(f"<code>{i}</code>" for i in sorted(ADMINS))
        + "\n\n"
        + (
            "\n".join(f"• <code>{r['id']}</code>" for r in rows)
            or "ادمین دیگری ثبت نشده."
        )
    )


def admins_kb():
    rows = [
        [
            Btn(
                f"🗑 حذف {r['id']}",
                callback_data=f"a:admdel:{r['id']}",
                style="danger"
            )
        ]
        for r in db("SELECT id FROM admins ORDER BY added_at")
    ]

    rows.append(
        [B("➕ افزودن ادمین", "p_add", callback_data="a:admadd")]
    )
    rows.append([Btn("🔙 بازگشت", callback_data="a:home")])

    return Kb(rows)


def emo_text():
    rows = db("SELECT ch,cid FROM emojis ORDER BY id")

    return (
        "💎 <b>ایموجی پرمیوم</b>\n"
        f"تعداد: {len(rows)}\n\n"
        + (
            "\n".join(
                f"{fx(r['ch'])} ← <code>{r['cid']}</code>"
                for r in rows
            )
            or "هنوز ایموجی‌ای اضافه نشده."
        )
    )


def emo_kb():
    rows = [
        [
            Btn(
                f"🗑 {r['ch']}",
                callback_data=f"a:emodel:{r['id']}",
                style="danger"
            )
        ]
        for r in db("SELECT id,ch FROM emojis ORDER BY id")
    ]

    rows.append(
        [B("➕ افزودن ایموجی", "p_add", callback_data="a:emoadd")]
    )
    rows.append([Btn("🔙 بازگشت", callback_data="a:home")])

    return Kb(rows)


EMO_HELP = (
    "💎 <b>افزودن ایموجی پرمیوم</b>\n\n"
    "۱) یک ایموجی معمولی و کنارش یک ایموجی پرمیوم بفرستید "
    "(مثال: 🎮 و بعد ایموجی پرمیوم). از این به بعد هر 🎮 در ربات "
    "با ایموجی پرمیوم نمایش داده می‌شود.\n\n"
    "۲) فقط یک ایموجی پرمیوم بفرستید تا جای ایموجی هم‌شکلش بنشیند.\n\n"
    "۳) یا ایموجی و ID عددی را بفرستید: "
    "<code>🎮 5368324170671202286</code>\n\n"
    "فرستادن ایموجی پرمیوم نیاز به اکانت پرمیوم دارد. "
    "نمایش آن برای کاربران هم فقط وقتی کار می‌کند که صاحب ربات "
    "پرمیوم باشد یا ربات یوزرنیم Fragment داشته باشد.\n"
    "لغو: /cancel"
)

SPARK = "▁▂▃▄▅▆▇█"


def spark(vals):
    mx = max(vals) or 1

    return "".join(
        SPARK[min(7, int(v / mx * 7))] if v else "▁"
        for v in vals
    )


def stats_text():
    one = lambda sql, a=(): db(sql, a, one=True)[0]

    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%d %H:%M"
    ago = lambda d: (now - timedelta(days=d)).strftime(fmt)
    today = now.strftime("%Y-%m-%d") + " 00:00"
    nowm = now.strftime(fmt)

    users = one("SELECT COUNT(*) FROM users")
    en = one("SELECT COUNT(*) FROM users WHERE lang='en'")
    fa = one("SELECT COUNT(*) FROM users WHERE lang='fa'")

    new = lambda since: one(
        "SELECT COUNT(*) FROM users WHERE joined_at>=?", (since,)
    )
    act = lambda since: one(
        "SELECT COUNT(*) FROM users WHERE last_seen>=?", (since,)
    )

    days = [
        (now - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(6, -1, -1)
    ]
    series = [
        one(
            "SELECT COUNT(*) FROM users WHERE joined_at LIKE ?",
            (d + "%",)
        )
        for d in days
    ]

    g_total = one("SELECT COUNT(*) FROM groups")
    g_act = one("SELECT COUNT(*) FROM groups WHERE active=1")
    g_new = one(
        "SELECT COUNT(*) FROM groups WHERE added_at>=?",
        ((now - timedelta(days=7)).strftime("%Y-%m-%d"),)
    )

    games_n = one("SELECT COUNT(*) FROM games")
    up = one("SELECT COUNT(*) FROM games WHERE release_date>=?", (nowm,))
    nxt = db(
        "SELECT title,release_date FROM games "
        "WHERE release_date>=? ORDER BY release_date LIMIT 1",
        (nowm,),
        one=True
    )

    v_total = one("SELECT COUNT(*) FROM views")
    v_users = one("SELECT COUNT(DISTINCT user_id) FROM views")
    top = db(
        "SELECT g.title, COUNT(v.user_id) n FROM games g "
        "LEFT JOIN views v ON v.game_id=g.id "
        "GROUP BY g.id ORDER BY n DESC, g.title LIMIT 5"
    )
    zero = one(
        "SELECT COUNT(*) FROM games g WHERE NOT EXISTS "
        "(SELECT 1 FROM views v WHERE v.game_id=g.id)"
    )

    last_groups = db(
        "SELECT * FROM groups ORDER BY added_at DESC LIMIT 5"
    )

    out = (
        "📊 <b>آمار ربات</b>\n\n"
        "👥 <b>کاربران</b>\n"
        f"• کل: {users}  (🇬🇧 {en} / 🇮🇷 {fa})\n"
        f"• جدید امروز: {new(today)}\n"
        f"• ۷ روز اخیر: {new(ago(7))}\n"
        f"• ۳۰ روز اخیر: {new(ago(30))}\n"
        f"• فعال ۲۴ ساعت: {act(ago(1))}\n"
        f"• فعال ۷ روز: {act(ago(7))}\n"
        f"• روند ورود ۷ روز: <code>{spark(series)}</code> "
        f"({'، '.join(map(str, series))})\n\n"
        "🏘 <b>گروه‌ها</b>\n"
        f"• فعال: {g_act} از {g_total}\n"
        f"• جدید ۷ روز اخیر: {g_new}\n\n"
        "🎮 <b>بازی‌ها</b>\n"
        f"• کل: {games_n}  |  در راه: {up}  |  منتشرشده: {games_n - up}\n"
    )

    if nxt:
        out += (
            f"• نزدیک‌ترین: {html.escape(nxt['title'])} — "
            f"{nxt['release_date'][:10]}\n"
        )

    out += (
        "\n👁 <b>بازدید</b>\n"
        f"• کل: {v_total}  |  بینندگان یکتا: {v_users}\n"
        f"• بدون بازدید: {zero} بازی\n"
        "🏆 پربازدیدترین‌ها:\n"
        + (
            "\n".join(
                f"{i}. {html.escape(r['title'])} — {r['n']}"
                for i, r in enumerate(top, 1)
            )
            or "-"
        )
    )

    if last_groups:
        out += "\n\n🆕 <b>آخرین گروه‌ها</b>\n" + "\n".join(
            f"{'✅' if r['active'] else '❌'} "
            f"{html.escape(r['title'] or '?')} — {r['added_at']}"
            for r in last_groups
        )

    return fx(out)


async def admin(update: Update, ctx):
    if (
        is_admin(update.effective_user.id)
        and update.effective_chat.type == ChatType.PRIVATE
    ):
        await update.message.reply_text(
            "⚙️ پنل مدیریت",
            reply_markup=panel_kb(update.effective_user.id)
        )


async def admin_cb(update: Update, ctx):
    q = update.callback_query

    if not is_admin(q.from_user.id):
        return await q.answer(
            "⛔",
            show_alert=True
        )

    await q.answer()

    _, act, *a = q.data.split(":")

    ud = ctx.user_data
    send = q.message.reply_text
    uid = q.from_user.id

    async def edit(text, kb=None):
        try:
            await q.edit_message_text(
                text,
                parse_mode=HTML,
                reply_markup=kb
            )
        except BadRequest:
            pass

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

    elif act in ("stats", "statsr"):
        kb = Kb([[
            B("🔄 به‌روزرسانی", "p_other", callback_data="a:statsr")
        ]])

        if act == "stats":
            await q.message.reply_html(stats_text(), reply_markup=kb)
        else:
            await edit(stats_text(), kb)

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

    elif act == "home":
        await edit("⚙️ پنل مدیریت", panel_kb(uid))

    # ── support
    elif act == "sup":
        cur = get_set("support")
        ud["job"] = {"kind": "support"}

        await q.message.reply_html(
            "💬 <b>تنظیم پشتیبانی</b>\n"
            "فعلی: "
            + (f"t.me/{html.escape(cur)}" if cur else "تنظیم نشده")
            + "\n\nآیدی یا لینک پشتیبانی را بفرستید "
            "(مثال: <code>@username</code> یا <code>t.me/username</code>).\n"
            "برای حذف: <code>-</code>\n"
            "لغو: /cancel"
        )

    # ── button colors
    elif act == "col":
        await edit(COLORS_TEXT, colors_kb())

    elif act == "cg" and a and a[0] in DEFAULT_COLOR:
        label = next(l for k, l, _ in COLOR_GROUPS if k == a[0])

        rows = [
            [
                Btn(
                    f"{e} {n}",
                    callback_data=f"a:cs:{a[0]}:{c}",
                    style=None if c == "none" else c
                )
            ]
            for c, e, n in COLORS
        ]

        rows.append([Btn("🔙 بازگشت", callback_data="a:col")])

        await edit(f"🎨 رنگ «{label}» را انتخاب کنید:", Kb(rows))

    elif (
        act == "cs"
        and len(a) == 2
        and a[0] in DEFAULT_COLOR
        and a[1] in {c for c, _, _ in COLORS}
    ):
        put_set("color:" + a[0], a[1])
        await edit(COLORS_TEXT + "\n\n✅ ذخیره شد.", colors_kb())

    # ── admins (owner only)
    elif act in ("adm", "admadd", "admdel"):
        if not is_owner(uid):
            return await send("⛔ فقط مالک ربات")

        if act == "adm":
            await edit(admins_text(), admins_kb())

        elif act == "admadd":
            ud["job"] = {"kind": "admin_add"}

            await q.message.reply_html(
                "👮 آیدی عددی ادمین جدید را بفرستید، "
                "یا یک پیام از او را فوروارد کنید.\n"
                "لغو: /cancel"
            )

        elif a and a[0].isdigit():
            db("DELETE FROM admins WHERE id=?", (int(a[0]),))
            await edit(admins_text(), admins_kb())

    # ── premium emoji
    elif act == "emo":
        await edit(emo_text(), emo_kb())

    elif act == "emoadd":
        ud["job"] = {"kind": "emoji"}
        await q.message.reply_html(EMO_HELP)

    elif act == "emodel" and a and a[0].isdigit():
        db("DELETE FROM emojis WHERE id=?", (int(a[0]),))
        load_emojis()
        await edit(emo_text(), emo_kb())


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

    if job["kind"] == "support":
        if not m.text:
            return

        v = m.text.strip()

        if v == "-":
            put_set("support", None)
            msg = "🗑 پشتیبانی حذف شد."
        else:
            p = parse_support(v)

            if not p:
                return await m.reply_text(
                    "❌ آیدی نامعتبر. مثال: @username"
                )

            put_set("support", p)
            msg = f"✅ پشتیبانی تنظیم شد: t.me/{p}"

        ctx.user_data.pop("job")
        return await m.reply_text(msg)

    if job["kind"] == "admin_add":
        if not is_owner(m.from_user.id):
            ctx.user_data.pop("job")
            return

        new_id = None
        su = getattr(
            getattr(m, "forward_origin", None),
            "sender_user",
            None
        )

        if su:
            new_id = su.id
        elif m.text and m.text.strip().isdigit():
            new_id = int(m.text.strip())

        if not new_id:
            return await m.reply_text(
                "❌ آیدی عددی بفرستید یا یک پیام از او فوروارد کنید."
            )

        db(
            "INSERT OR IGNORE INTO admins VALUES(?,?)",
            (new_id, now_s())
        )

        ctx.user_data.pop("job")

        return await m.reply_text(f"✅ {new_id} ادمین شد.")

    if job["kind"] == "emoji":
        if not m.text:
            return

        ents = [
            e for e in (m.entities or ())
            if e.type == "custom_emoji"
        ]

        pairs = []

        if ents:
            plain = m.text

            for e in ents:
                plain = plain.replace(m.parse_entity(e), "", 1)

            plain = _norm(plain)

            if plain and (len(ents) > 1 or len(plain) > 8):
                return await m.reply_text(
                    "❌ در هر پیام فقط یک ایموجی معمولی + یک پرمیوم."
                )

            for e in ents:
                pairs.append((
                    plain or _norm(m.parse_entity(e)),
                    e.custom_emoji_id
                ))
        else:
            mt = re.fullmatch(
                r"\s*(\S{1,8})\s+(\d{10,25})\s*",
                m.text
            )

            if mt:
                pairs.append((_norm(mt.group(1)), mt.group(2)))

        pairs = [(c, i) for c, i in pairs if c]

        if not pairs:
            return await m.reply_text(
                "❌ ایموجی پرمیوم یا «ایموجی + ID» بفرستید."
            )

        for ch, cid in pairs:
            db(
                "INSERT INTO emojis(ch,cid) VALUES(?,?) "
                "ON CONFLICT(ch) DO UPDATE SET cid=excluded.cid",
                (ch, cid)
            )

        load_emojis()
        ctx.user_data.pop("job")

        return await m.reply_html(
            "✅ ذخیره شد: " + " ".join(fx(c) for c, _ in pairs)
        )

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

    if is_admin(update.effective_user.id):
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
        ("support", support_cmd),
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