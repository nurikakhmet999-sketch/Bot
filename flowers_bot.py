import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, ForeignKey, DateTime
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# ----------------- НАСТРОЙКИ -----------------
API_TOKEN = "8223265391:AAG3kmA6OIQdfSBeiNuNX3voojA3YtnCihU"   # <- вставь сюда токен
ADMIN_ID = 1128002925        # <- вставь сюда свой Telegram ID (число)

logging.basicConfig(level=logging.INFO)
Base = declarative_base()

# ----------------- БД (SQLite) -----------------
engine = create_engine("sqlite:///flowers.db", echo=False, future=True)
Session = sessionmaker(bind=engine, future=True)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    products = relationship("Product", back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    photo_id = Column(String, nullable=True)  # Telegram file_id
    category = relationship("Category", back_populates="products")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False)
    customer_id = Column(Integer, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    delivery_method = Column(String, nullable=False)
    address = Column(String, nullable=True)
    status = Column(String, default="Новый")
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)

# ----------------- FSM -----------------
class AdminStates(StatesGroup):
    waiting_category_name = State()
    waiting_product_category = State()
    waiting_product_name = State()
    waiting_product_description = State()
    waiting_product_price = State()
    waiting_product_photo = State()


class OrderStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_delivery_method = State()
    waiting_address = State()
    confirm_order = State()


# ----------------- Aiogram init -----------------
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ----------------- Кнопки -----------------
start_kb_admin = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Каталог"), KeyboardButton(text="Админ")]],
    resize_keyboard=True
)
start_kb_user = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Каталог")]],
    resize_keyboard=True
)

admin_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить категорию"), KeyboardButton(text="Удалить категорию")],
        [KeyboardButton(text="Добавить товар"), KeyboardButton(text="Удалить товар")],
        [KeyboardButton(text="Просмотр заказов")],
        [KeyboardButton(text="Каталог")],
    ],
    resize_keyboard=True
)

delivery_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Доставка"), KeyboardButton(text="Самовывоз")]],
    resize_keyboard=True
)

confirm_order_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Подтвердить заказ"), KeyboardButton(text="Отменить")]],
    resize_keyboard=True
)


# ----------------- Хелперы -----------------
async def get_categories_inline():
    with Session() as session:
        cats = session.query(Category).order_by(Category.id).all()
    if not cats:
        return None
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.name, callback_data=f"cat_{c.id}")] for c in cats])
    return kb


async def get_products_inline_by_category(cat_id: int):
    with Session() as session:
        prods = session.query(Product).filter_by(category_id=cat_id).order_by(Product.id).all()
    if not prods:
        return None
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=p.name, callback_data=f"prod_{p.id}")] for p in prods])
    return kb


# ----------------- Хендлеры: старт и каталог -----------------
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Привет, админ. Выберите режим:", reply_markup=start_kb_admin)
    else:
        await message.answer("Добро пожаловать! Вот наш каталог:", reply_markup=start_kb_user)
        kb = await get_categories_inline()
        if kb:
            await message.answer("Категории:", reply_markup=kb)
        else:
            await message.answer("Категории пока отсутствуют.")


@dp.message(F.text == "Каталог")
async def open_catalog(message: Message):
    kb = await get_categories_inline()
    if kb:
        await message.answer("Категории:", reply_markup=kb)
    else:
        await message.answer("Категории пока отсутствуют.")


# ----------------- Клиент: выбор категории -> товары -> карточка товара -----------------
@dp.callback_query(F.data.startswith("cat_"))
async def cat_selected(callback: CallbackQuery):
    await callback.answer()
    cat_id = int(callback.data.split("_", 1)[1])
    with Session() as session:
        products = session.query(Product).filter_by(category_id=cat_id).order_by(Product.id).all()
    if not products:
        await callback.message.answer("В этой категории пока нет товаров.")
        return
    # Покажем список товаров как inline-кнопки (название) — при нажатии откроется карточка
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=p.name, callback_data=f"prod_{p.id}")] for p in products])
    await callback.message.answer("Товары в категории:", reply_markup=kb)


@dp.callback_query(F.data.startswith("prod_"))
async def prod_selected(callback: CallbackQuery):
    await callback.answer()
    prod_id = int(callback.data.split("_", 1)[1])
    with Session() as session:
        p = session.get(Product, prod_id)
    if not p:
        await callback.message.answer("Товар не найден.")
        return
    text = f"<b>{p.name}</b>\n\n{(p.description or '')}\n\nЦена: {p.price} ₽"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заказать", callback_data=f"order_{p.id}")],
        [InlineKeyboardButton(text="Назад к категории", callback_data=f"back_cat_{p.category_id}")]
    ])
    if p.photo_id:
        await bot.send_photo(callback.from_user.id, p.photo_id, caption=text, parse_mode="HTML", reply_markup=kb)
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("back_cat_"))
async def back_to_cat(callback: CallbackQuery):
    await callback.answer()
    cat_id = int(callback.data.split("_", 2)[2])
    # показать товары этой категории
    with Session() as session:
        products = session.query(Product).filter_by(category_id=cat_id).order_by(Product.id).all()
    if not products:
        await callback.message.answer("В этой категории пока нет товаров.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=p.name, callback_data=f"prod_{p.id}")] for p in products])
    await callback.message.answer("Товары в категории:", reply_markup=kb)


# ----------------- Оформление заказа -----------------
@dp.callback_query(F.data.startswith("order_"))
async def order_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    prod_id = int(callback.data.split("_", 1)[1])
    await state.update_data(product_id=prod_id)
    await bot.send_message(callback.from_user.id, "Введите ваше имя:")
    await state.set_state(OrderStates.waiting_name)


@dp.message(OrderStates.waiting_name)
async def order_name(message: Message, state: FSMContext):
    await state.update_data(customer_name=message.text.strip())
    await message.answer("Введите телефон (пример: +77001234567):")
    await state.set_state(OrderStates.waiting_phone)


@dp.message(OrderStates.waiting_phone)
async def order_phone(message: Message, state: FSMContext):
    await state.update_data(customer_phone=message.text.strip())
    await message.answer("Выберите способ получения:", reply_markup=delivery_kb)
    await state.set_state(OrderStates.waiting_delivery_method)


@dp.message(OrderStates.waiting_delivery_method)
async def order_delivery(message: Message, state: FSMContext):
    method = message.text
    if method not in ("Доставка", "Самовывоз"):
        await message.answer("Пожалуйста, используйте кнопки клавиатуры.")
        return
    await state.update_data(delivery_method=method)
    if method == "Доставка":
        await message.answer("Введите адрес доставки:")
        await state.set_state(OrderStates.waiting_address)
    else:
        await state.update_data(address=None)
        await confirm_order_show(message.chat.id, state)


@dp.message(OrderStates.waiting_address)
async def order_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await confirm_order_show(message.chat.id, state)


async def confirm_order_show(chat_id: int, state: FSMContext):
    data = await state.get_data()
    with Session() as session:
        product = session.get(Product, data["product_id"])
    if not product:
        await bot.send_message(chat_id, "Товар не найден, отмена.")
        await state.clear()
        return
    txt = (
        f"Вы заказываете:\n\n<b>{product.name}</b>\nЦена: {product.price} ₽\n\n"
        f"Имя: {data.get('customer_name')}\nТелефон: {data.get('customer_phone')}\n"
        f"Способ: {data.get('delivery_method')}\n"
    )
    if data.get('delivery_method') == "Доставка":
        txt += f"Адрес: {data.get('address')}\n"
    await bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=confirm_order_kb)
    await state.set_state(OrderStates.confirm_order)


@dp.message(OrderStates.confirm_order)
async def order_finalize(message: Message, state: FSMContext):
    if message.text == "Подтвердить заказ":
        data = await state.get_data()
        with Session() as session:
            new_order = Order(
                product_id=data["product_id"],
                customer_id=message.from_user.id,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                delivery_method=data["delivery_method"],
                address=data.get("address"),
                status="Новый",
                created_at=datetime.utcnow()
            )
            session.add(new_order)
            session.commit()
            order_id = new_order.id
        # уведомим админа
        await bot.send_message(
            ADMIN_ID,
            f"📦 Новый заказ #{order_id}\nКлиент: {new_order.customer_name} ({new_order.customer_phone})\n"
            f"Товар ID: {new_order.product_id}\nСпособ: {new_order.delivery_method}\nАдрес: {new_order.address or '-'}"
        )
        await message.answer("Спасибо! Ваш заказ сохранён ✅", reply_markup=start_kb_user)
        await state.clear()
    elif message.text == "Отменить":
        await message.answer("Заказ отменён.", reply_markup=start_kb_user)
        await state.clear()
    else:
        await message.answer("Пожалуйста, используйте кнопки: Подтвердить заказ или Отменить.")


# ----------------- Админ: меню -----------------
@dp.message(F.text == "Админ")
async def admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет доступа.")
        return
    await message.answer("Панель администратора:", reply_markup=admin_menu_kb)


# ---- Добавить категорию ----
@dp.message(F.text == "Добавить категорию")
async def admin_add_category_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите имя новой категории:")
    await state.set_state(AdminStates.waiting_category_name)


@dp.message(AdminStates.waiting_category_name)
async def admin_add_category_save(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым.")
        return
    with Session() as session:
        # проверим уникальность
        exists = session.query(Category).filter_by(name=name).first()
        if exists:
            await message.answer("Категория с таким именем уже есть.")
            await state.clear()
            return
        session.add(Category(name=name))
        session.commit()
    await message.answer(f"Категория '{name}' добавлена ✅", reply_markup=admin_menu_kb)
    await state.clear()


# ---- Удалить категорию ----
@dp.message(F.text == "Удалить категорию")
async def admin_delete_category_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    with Session() as session:
        cats = session.query(Category).order_by(Category.id).all()
    if not cats:
        await message.answer("Категорий пока нет.", reply_markup=admin_menu_kb)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.name, callback_data=f"delcat_{c.id}")] for c in cats])
    await message.answer("Выберите категорию для удаления (все продукты в ней будут удалены):", reply_markup=kb)


@dp.callback_query(F.data.startswith("delcat_"))
async def admin_delete_category_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    cat_id = int(callback.data.split("_", 1)[1])
    with Session() as session:
        c = session.get(Category, cat_id)
        if not c:
            await callback.message.answer("Категория не найдена.")
            return
        name = c.name
        session.delete(c)  # cascade удалит продукты
        session.commit()
    await callback.message.answer(f"Категория '{name}' удалена вместе с товарами ✅", reply_markup=admin_menu_kb)


# ---- Добавить товар (выбор категории -> имя -> описание -> цена -> фото) ----
@dp.message(F.text == "Добавить товар")
async def admin_add_product_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    with Session() as session:
        cats = session.query(Category).order_by(Category.id).all()
    if not cats:
        await message.answer("Сначала добавьте категорию.", reply_markup=admin_menu_kb)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.name, callback_data=f"addcat_{c.id}")] for c in cats])
    await message.answer("Выберите категорию для нового товара:", reply_markup=kb)


@dp.callback_query(F.data.startswith("addcat_"))
async def admin_add_product_choose_cat(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    cat_id = int(callback.data.split("_", 1)[1])
    await state.update_data(category_id=cat_id)
    await bot.send_message(callback.from_user.id, "Введите название товара:")
    await state.set_state(AdminStates.waiting_product_name)


@dp.message(AdminStates.waiting_product_name)
async def admin_add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите описание товара:")
    await state.set_state(AdminStates.waiting_product_description)


@dp.message(AdminStates.waiting_product_description)
async def admin_add_product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("Введите цену (например 499.99):")
    await state.set_state(AdminStates.waiting_product_price)


@dp.message(AdminStates.waiting_product_price)
async def admin_add_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("Некорректная цена. Введите число, например 199.50")
        return
    await state.update_data(price=price)
    await message.answer("Отправьте фото товара (или напишите /skip для добавления без фото):")
    await state.set_state(AdminStates.waiting_product_photo)


@dp.message(AdminStates.waiting_product_photo)
async def admin_add_product_photo(message: Message, state: FSMContext):
    # allow /skip
    if message.photo:
        photo_id = message.photo[-1].file_id
    else:
        if message.text and message.text.strip().lower() == "/skip":
            photo_id = None
        else:
            await message.answer("Пожалуйста, отправьте фото или напишите /skip.")
            return

    data = await state.get_data()
    with Session() as session:
        prod = Product(
            category_id=data["category_id"],
            name=data["name"],
            description=data.get("description", ""),
            price=data["price"],
            photo_id=photo_id
        )
        session.add(prod)
        session.commit()
    await message.answer(f"Товар '{data['name']}' добавлен ✅", reply_markup=admin_menu_kb)
    await state.clear()


# ---- Удалить товар ----
@dp.message(F.text == "Удалить товар")
async def admin_delete_product_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    with Session() as session:
        prods = session.query(Product).order_by(Product.id).all()
    if not prods:
        await message.answer("Нет товаров для удаления.", reply_markup=admin_menu_kb)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=p.name, callback_data=f"delprod_{p.id}")] for p in prods])
    await message.answer("Выберите товар для удаления:", reply_markup=kb)


@dp.callback_query(F.data.startswith("delprod_"))
async def admin_delete_product_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    prod_id = int(callback.data.split("_", 1)[1])
    with Session() as session:
        p = session.get(Product, prod_id)
        if not p:
            await callback.message.answer("Товар не найден.")
            return
        name = p.name
        session.delete(p)
        session.commit()
    await callback.message.answer(f"Товар '{name}' удалён ✅", reply_markup=admin_menu_kb)


# ---- Просмотр заказов (и подтверждение/отмена) ----
@dp.message(F.text == "Просмотр заказов")
async def admin_view_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    with Session() as session:
        orders = session.query(Order).order_by(Order.created_at.desc()).all()
    if not orders:
        await message.answer("Нет заказов.", reply_markup=admin_menu_kb)
        return
    for o in orders:
        with Session() as s:
            prod = s.get(Product, o.product_id)
        txt = (
            f"Заказ #{o.id}\n"
            f"Товар: {prod.name if prod else 'Удалён'} (ID:{o.product_id})\n"
            f"Клиент: {o.customer_name} ({o.customer_phone})\n"
            f"Способ: {o.delivery_method}\n"
            f"Адрес: {o.address or '-'}\n"
            f"Статус: {o.status}\n"
            f"Дата: {o.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data=f"order_accept_{o.id}"),
             InlineKeyboardButton(text="Отменить", callback_data=f"order_reject_{o.id}")]
        ])
        await message.answer(txt, reply_markup=kb)


@dp.callback_query(F.data.startswith("order_accept_"))
async def admin_accept_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    order_id = int(callback.data.split("_", 2)[2])
    with Session() as session:
        o = session.get(Order, order_id)
        if not o:
            await callback.message.answer("Заказ не найден.")
            return
        o.status = "Подтверждён"
        session.commit()
    await callback.message.answer(f"Заказ #{order_id} подтверждён ✅", reply_markup=admin_menu_kb)


@dp.callback_query(F.data.startswith("order_reject_"))
async def admin_reject_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    order_id = int(callback.data.split("_", 2)[2])
    with Session() as session:
        o = session.get(Order, order_id)
        if not o:
            await callback.message.answer("Заказ не найден.")
            return
        o.status = "Отменён"
        session.commit()
    await callback.message.answer(f"Заказ #{order_id} отменён ❌", reply_markup=admin_menu_kb)


# ----------------- Запуск -----------------
async def main():
    logging.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())