# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pandas as pd

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ БОТА ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATA_FILE = "mood_data.csv"
USERS_FILE = "users.csv"

# Определяем состояния для диалога
SELECT_PROFESSION = 0
QUESTION_1, QUESTION_2, QUESTION_3, QUESTION_4, QUESTION_5 = range(1, 6)

# --- СПИСОК ПРОФЕССИЙ И КЛАВИАТУРА ---
PROFESSIONS = [
    ["Заместитель директора", "Начальник отдела"],
    ["Врач", "Медсестра"],
    ["Работник кухни", "Работник АХО"],
    ["Специалист по соц. работе"],
    ["Педагог (психолог)", "Педагог (логопед)"],
    ["Педагог (дефектолог)", "Педагог (ПДО)"],
    ["Педагог (организатор)", "Педагог (АФК)"],
    ["Педагог (муз. рук.)", "Воспитатель"],
    ["Помощник воспитателя", "Младший воспитатель"],
    ["Кадровый работник", "Бухгалтер/Экономист"],
    ["Специалист АУП", "Водитель"]
]
PROFESSION_MARKUP = ReplyKeyboardMarkup(PROFESSIONS, one_time_keyboard=True, resize_keyboard=True)
FLAT_PROFESSIONS = [prof for sublist in PROFESSIONS for prof in sublist]


# --- БЛОК С ВОПРОСАМИ И ОТВЕТАМИ ---
QUIZZES = {
    "morning": {
        "intro": "Доброе утро! ✨ Мне очень важно знать, как ты себя чувствуешь. Давай пройдем быстрый опрос, чтобы настроиться на продуктивный день.",
        "questions": [
            "Как ты оцениваешь качество своего сна?",
            "С каким настроением ты начинаешь рабочий день?",
            "Насколько ясны твои задачи на сегодня?",
            "Чувствуешь ли ты в себе энергию для выполнения задач?",
            "Насколько ты оптимистично смотришь на сегодняшний день?",
        ],
    },
    "day": {
        "intro": "Привет! Как проходит твой день? ☕️ Давай сделаем короткую паузу и проверим твой настрой. Это займет всего минуту.",
        "questions": [
            "Насколько ты сейчас загружен работой?",
            "Чувствуешь ли ты поддержку со стороны коллег?",
            "Насколько успешно получается справляться с задачами?",
            "Как ты оцениваешь свой текущий уровень стресса?",
            "Хватает ли тебе времени на короткие перерывы?",
        ],
    },
    "evening": {
        "intro": "Добрый вечер! Рабочий день подходит к концу. 🌅 Поделись, пожалуйста, своими впечатлениями. Твои ответы помогут нам стать лучше.",
        "questions": [
            "Насколько продуктивным был твой сегодняшний день?",
            "Доволен ли ты результатами своей работы сегодня?",
            "Остались ли у тебя силы на вечерние дела и хобби?",
            "Были ли сегодня моменты, которые тебя расстроили или вызвали негатив?",
            "Что ты чувствуешь по поводу завтрашнего рабочего дня?",
        ],
    },
}

ANSWERS = {
    "Плохо/Нет": 1,
    "Нормально/Частично": 2,
    "Отлично/Да": 3,
}
REPLY_KEYBOARD = [list(ANSWERS.keys())]
MARKUP = ReplyKeyboardMarkup(REPLY_KEYBOARD, one_time_keyboard=True)

# --- ОБНОВЛЕННЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ---

def get_users_df():
    """Загружает DataFrame с пользователями или создает новый."""
    if not os.path.exists(USERS_FILE):
        return pd.DataFrame(columns=["user_id", "profession"])
    return pd.read_csv(USERS_FILE)

def save_user(user_id, profession):
    """Сохраняет нового пользователя с его профессией."""
    df = get_users_df()
    if user_id not in df["user_id"].values:
        new_user = pd.DataFrame([{"user_id": user_id, "profession": profession}])
        df = pd.concat([df, new_user], ignore_index=True)
        df.to_csv(USERS_FILE, index=False)
        logger.info(f"Новый пользователь {user_id} с профессией '{profession}' сохранен.")

def get_all_users():
    """Возвращает список ID всех зарегистрированных пользователей."""
    df = get_users_df()
    return df["user_id"].tolist()

def get_user_info(user_id):
    """Возвращает информацию о пользователе (включая профессию)."""
    df = get_users_df()
    user_data = df[df["user_id"] == user_id]
    if not user_data.empty:
        return user_data.iloc[0]
    return None

def save_answer(user_id, quiz_type, question_index, answer, score):
    """Сохраняет ответ, добавляя профессию пользователя."""
    user_info = get_user_info(user_id)
    profession = user_info['profession'] if user_info is not None else "Unknown"

    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=["timestamp", "user_id", "profession", "quiz_type", "question", "answer", "score"])
        df.to_csv(DATA_FILE, index=False)
    
    question_text = QUIZZES[quiz_type]['questions'][question_index]
    new_data = pd.DataFrame([{
        "timestamp": datetime.now(),
        "user_id": user_id,
        "profession": profession,
        "quiz_type": quiz_type,
        "question": question_text,
        "answer": answer,
        "score": score
    }])
    
    df_data = pd.read_csv(DATA_FILE)
    df_data = pd.concat([df_data, new_data], ignore_index=True)
    df_data.to_csv(DATA_FILE, index=False)

# --- ОБНОВЛЕННЫЕ ФУНКЦИИ БОТА ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает команду /start. Начинает регистрацию для новых пользователей."""
    user = update.effective_user
    user_info = get_user_info(user.id)
    
    if user_info is not None:
        await update.message.reply_html(
            f"С возвращением, {user.mention_html()}! Я уже знаю, что твоя должность - {user_info['profession']}. Просто дождись следующего опроса.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END
    else:
        await update.message.reply_html(
            f"Привет, {user.mention_html()}!\n\nЯ бот для отслеживания настроения команды. "
            "Чтобы начать, пожалуйста, выбери свою должность из списка ниже.",
            reply_markup=PROFESSION_MARKUP,
        )
        return SELECT_PROFESSION

async def select_profession(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет выбранную профессию и завершает регистрацию."""
    user = update.effective_user
    profession = update.message.text
    
    if profession not in FLAT_PROFESSIONS:
        await update.message.reply_text(
            "Пожалуйста, выбери должность с помощью кнопок.",
            reply_markup=PROFESSION_MARKUP,
        )
        return SELECT_PROFESSION

    save_user(user.id, profession)
    await update.message.reply_text(
        f"Отлично! Я записал, что твоя должность - {profession}. "
        "Теперь ты будешь получать опросы по расписанию. Спасибо!",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def force_start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает квиз по команде /quiz, если пользователь зарегистрирован."""
    user = update.effective_user
    user_info = get_user_info(user.id)
    
    if user_info is None:
        await update.message.reply_text(
            "Я тебя еще не знаю. Пожалуйста, сначала зарегистрируйся с помощью команды /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    current_hour = datetime.now().hour
    if 6 <= current_hour < 12:
        quiz_type = "morning"
    elif 12 <= current_hour < 17:
        quiz_type = "day"
    else:
        quiz_type = "evening"
    
    context.user_data["quiz_type"] = quiz_type
    context.user_data["current_question"] = 0
    
    await update.message.reply_text(
        QUIZZES[quiz_type]["intro"],
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        QUIZZES[quiz_type]["questions"][0],
        reply_markup=MARKUP,
    )
    return QUESTION_1

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text
    if answer not in ANSWERS:
        await update.message.reply_text("Пожалуйста, выберите ответ с помощью кнопок.", reply_markup=MARKUP)
        return context.user_data["current_question"] + 1

    user_id = update.effective_user.id
    quiz_type = context.user_data["quiz_type"]
    question_index = context.user_data["current_question"]
    score = ANSWERS[answer]
    
    save_answer(user_id, quiz_type, question_index, answer, score)

    question_index += 1
    context.user_data["current_question"] = question_index

    if question_index < len(QUIZZES[quiz_type]["questions"]):
        await update.message.reply_text(
            QUIZZES[quiz_type]["questions"][question_index],
            reply_markup=MARKUP,
        )
        return question_index + 1 
    else:
        await update.message.reply_text(
            "Спасибо за твои ответы! Хорошего дня! 😊",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает любой диалог."""
    await update.message.reply_text(
        "Действие отменено.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def send_quiz(bot: Bot):
    """Функция планировщика для отправки уведомлений о квизе."""
    user_ids = get_all_users()
    logger.info(f"Плановая рассылка квиза для {len(user_ids)} пользователей.")
    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"Время пройти опрос! Нажмите /quiz чтобы начать."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

async def post_init(application: Application) -> None:
    """Запускает планировщик после инициализации приложения."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_quiz, 'cron', day_of_week='mon-fri', hour=10, minute=0, args=[application.bot])
    scheduler.add_job(send_quiz, 'cron', day_of_week='mon-fri', hour=14, minute=0, args=[application.bot])
    scheduler.add_job(send_quiz, 'cron', day_of_week='mon-fri', hour=18, minute=0, args=[application.bot])
    scheduler.start()


# --- НОВАЯ ГЛАВНАЯ ФУНКЦИЯ ДЛЯ РАБОТЫ ЧЕРЕЗ WEBHOOK ---
def main() -> None:
    """Основная функция запуска бота в режиме Webhook."""
    if not TELEGRAM_TOKEN:
        logger.error("Токен не найден! Убедитесь, что вы добавили его в переменные окружения.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Добавляем все обработчики
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={ SELECT_PROFESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_profession)], },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    quiz_handler = ConversationHandler(
        entry_points=[CommandHandler("quiz", force_start_quiz)],
        states={
            QUESTION_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
            QUESTION_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
            QUESTION_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
            QUESTION_4: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
            QUESTION_5: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(registration_handler)
    application.add_handler(quiz_handler)

    # --- НАСТРОЙКА WEBHOOK ---
    # Render предоставляет URL в переменной окружения RENDER_EXTERNAL_URL
    # и порт в переменной PORT
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
    PORT = int(os.environ.get("PORT", "8443")) # Порт, который слушает Render

    if not WEBHOOK_URL:
        logger.error("Не удалось найти RENDER_EXTERNAL_URL. Запускаемся в режиме Polling для локальной разработки.")
        application.run_polling()
        return

    logger.info(f"Устанавливаем webhook на {WEBHOOK_URL}...")
    
    # Запускаем бота
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        secret_token="A_SECRET_TOKEN_TO_PREVENT_UNAUTHORIZED_ACCESS", # Дополнительная безопасность
        webhook_url=WEBHOOK_URL
    )
    logger.info(f"Бот запущен и слушает порт {PORT}")


if __name__ == "__main__":
    main()

