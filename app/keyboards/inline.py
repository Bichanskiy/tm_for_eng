from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database.enums import TaskStatus


def get_tasks_keyboard(tasks: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Клавиатура для списка задач"""
    builder = InlineKeyboardBuilder()

    for task in tasks:
        builder.button(
            text=f"📝 {task.title[:30]}",
            callback_data=f"task_{task.id}"
        )

    builder.adjust(1)

    # Кнопки пагинации
    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"page_{page - 1}"
        ))
    if page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"page_{page + 1}"
        ))

    if pagination_buttons:
        builder.row(*pagination_buttons)

    return builder.as_markup()


def get_task_detail_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для конкретной задачи"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Сделано",
        callback_data=f"done_{task_id}"
    )
    builder.button(
        text="🔄 В работе",
        callback_data=f"progress_{task_id}"
    )
    builder.button(
        text="✏️ Изменить",
        callback_data=f"edit_{task_id}"
    )
    builder.button(
        text="🗑️ Удалить",
        callback_data=f"delete_{task_id}"
    )
    builder.button(
        text="📋 К списку",
        callback_data="back_to_list"
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_edit_task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для редактирования задачи"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="📝 Название",
        callback_data=f"edit_title_{task_id}"
    )
    builder.button(
        text="📄 Описание",
        callback_data=f"edit_desc_{task_id}"
    )
    builder.button(
        text="📅 Срок",
        callback_data=f"edit_due_{task_id}"
    )
    builder.button(
        text="🔢 Приоритет",
        callback_data=f"edit_priority_{task_id}"
    )
    builder.button(
        text="🔙 Назад",
        callback_data=f"task_{task_id}"
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора статуса"""
    builder = InlineKeyboardBuilder()

    for status in TaskStatus:
        builder.button(
            text=str(status).replace('_', ' ').title(),
            callback_data=f"status_{status.value}"
        )

    builder.adjust(1)
    return builder.as_markup()


def get_confirmation_keyboard(task_id: int, action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Да",
        callback_data=f"confirm_{action}_{task_id}"
    )
    builder.button(
        text="❌ Нет",
        callback_data=f"task_{task_id}"
    )

    builder.adjust(2)
    return builder.as_markup()