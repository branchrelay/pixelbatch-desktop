"""Central Russian/English UI translations."""

from __future__ import annotations

import logging
import re
from typing import Any


# English is the canonical form. Exact source strings are intentionally kept here,
# rather than spread through language conditionals in UI classes.
RU: dict[str, str] = {
    "Generate Images": "Генерация изображений", "Remove Background": "Удаление фона",
    "Add Background": "Добавление фона", "Resize Images": "Изменение размера",
    "Convert Format": "Конвертация формата", "Rename Files": "Переименование файлов",
    "How to Use": "Как пользоваться",
    "Settings": "Настройки", "Status: Ready": "Состояние: Готово", "Status": "Состояние",
    "Ready": "Готово", "Processing": "Обработка", "Cancelling": "Отмена",
    "Completed": "Готово", "Completed with errors": "Завершено с ошибками", "Error": "Ошибка",
    "Log": "Журнал", "Start": "Запустить", "Cancel": "Отмена", "Browse": "Обзор",
    "Select": "Выбрать", "Select Files": "Выбрать файлы", "Select Folder": "Выбрать папку",
    "Input folder": "Папка изображений", "Output folder": "Папка для сохранения",
    "CSV file": "CSV-файл", "Open Settings": "Открыть настройки",
    "Batch Image Processing Desktop Tool": "Инструмент для массовой обработки изображений",
    "Experimental AI image generation from CSV through the selected provider": "Экспериментальная AI-генерация изображений из CSV через выбранного провайдера",
    "Bulk image generation from CSV through the selected provider": "Массовая генерация изображений из CSV через выбранного провайдера",
    "Batch background removal with local rembg models": "Пакетное удаление фона локальными моделями rembg",
    "Background, canvas, centering, and padding for product images": "Фон, холст, центрирование и отступы для товарных изображений",
    "Resize a folder of images with the Lanczos filter": "Изменение размеров папки изображений с фильтром Lanczos",
    "Batch conversion of PNG, JPEG, WEBP, BMP, and TIFF": "Пакетная конвертация PNG, JPEG, WEBP, BMP и TIFF",
    "CSV processing range": "Диапазон обработки CSV", "All rows": "Все строки",
    "First N rows": "Первые N строк", "Row range": "Диапазон строк",
    "Skip first rows": "Пропустить первые строки", "First N": "Первые N", "From": "С",
    "To": "По", "CSV not checked": "CSV не проверен", "Check CSV": "Проверить CSV",
    "Prompt column": "Колонка prompt", "Prompt template": "Шаблон prompt",
    "Output format": "Формат результата", "Skip existing files": "Пропускать существующие файлы",
    "Skip existing": "Пропускать существующие", "Limit maximum file size": "Ограничить размер файла",
    "Limit size": "Ограничить размер", "Maximum size": "Максимальный размер",
    "Minimum quality": "Минимальное качество", "Allow resolution reduction": "Разрешить уменьшение разрешения",
    "Model": "Модель", "Output": "Результат", "Background color": "Цвет фона",
    "Choose Color": "Выбрать цвет", "White": "Белый", "Light Gray": "Светло-серый",
    "Black": "Чёрный", "Transparent": "Прозрачный", "Background image": "Изображение фона",
    "Canvas size": "Размер холста", "Keep original size": "Сохранить исходный размер",
    "Square canvas": "Квадратный холст", "Custom size": "Свой размер", "Side": "Сторона",
    "Width": "Ширина", "Height": "Высота", "Object padding": "Отступ объекта",
    "Filename suffix": "Суффикс имени", "Crop transparent margins": "Обрезать прозрачные поля",
    "Preserve aspect ratio": "Сохранять пропорции", "Center object": "Центрировать объект",
    "Allow upscaling": "Разрешить увеличение", "Preview": "Предпросмотр",
    "Original preview": "Исходное изображение", "Result preview": "Результат",
    "Process Folder": "Обработать папку", "Size (px)": "Размер (px)", "Percent": "Процент",
    "Fit": "Поместить", "Fill": "Заполнить", "Exact": "Растянуть", "Stretch": "Растянуть",
    "Width only": "Только ширина", "Height only": "Только высота", "Percentage": "В процентах",
    "Operation": "Операция", "Quality": "Качество", "Alpha background": "Фон прозрачности",
    "Image generation provider": "Провайдер генерации изображений", "Active provider": "Провайдер",
    "API Key": "API-ключ", "Show/Hide API Key": "Показать/скрыть API-ключ",
    "Delete Saved Key": "Удалить сохранённый ключ", "Base URL": "Адрес API",
    "Timeout (seconds)": "Время ожидания (секунды)", "Retries": "Повторные попытки",
    "Theme": "Тема", "System": "Как в системе", "System Default": "Как в системе", "Light": "Светлая", "Dark": "Тёмная",
    "Interface Language": "Язык интерфейса", "Russian": "Русский", "English": "English",
    "Test Connection": "Проверить подключение", "Save Settings": "Сохранить настройки",
    "Settings file": "Файл настроек", "Open Folder": "Открыть папку", "Copy Path": "Скопировать путь",
    "Hover over the path to see the full location.": "Наведите курсор на путь, чтобы увидеть полное расположение.",
    "Settings path copied.": "Путь к настройкам скопирован.",
    "Application and image generation settings": "Параметры приложения и генерации изображений",
    "Processed": "Обработано", "Successful": "Успешно", "Errors": "Ошибки", "Skipped": "Пропущено",
    "Choose a folder with images": "Выберите папку с изображениями",
    "Choose an output folder": "Выберите папку для сохранения", "Choose CSV": "Выберите CSV",
    "CSV files": "Файлы CSV", "All files": "Все файлы", "Images": "Изображения",
    "Choose background image": "Выберите изображение фона", "API key required": "Нужен API-ключ",
    "An API key is required only to generate images. Local tools work without it.": "API-ключ требуется только для генерации изображений. Локальные инструменты работают без него.",
    "Wait for the current operation to finish or cancel it.": "Дождитесь завершения текущей операции или отмените её.",
    "Cancellation requested. The current file or API request will finish first.": "Запрошена отмена. Текущий файл или API-запрос будет завершён.",
    "The operation is still running. Cancel it and close the application?": "Операция ещё выполняется. Отменить её и закрыть приложение?",
    "Select input and output folders.": "Выберите исходную папку и папку для сохранения.",
    "Select a CSV file and an output folder.": "Выберите CSV-файл и папку для сохранения.",
    "Select a CSV file first.": "Сначала выберите CSV-файл.",
    "The selected range has no valid rows to process.": "В выбранном диапазоне нет корректных строк для обработки.",
    "Width and height must be integers.": "Ширина и высота должны быть целыми числами.",
    "Input folder contains no previewable images.": "В исходной папке нет изображений для предпросмотра.",
    "Discard unsaved provider changes?": "Отменить несохранённые изменения провайдера?",
    "Use this key for the current session only?": "Использовать этот ключ только в текущем сеансе?",
    "Settings saved locally.": "Настройки сохранены локально.", "Settings saved": "Настройки сохранены",
    "Model must not be empty": "Поле модели не должно быть пустым",
    "Base URL must use HTTPS": "Адрес API должен использовать HTTPS",
    "Timeout and retries must be integers": "Время ожидания и число попыток должны быть целыми числами",
    "Quick Start": "Быстрый старт", "If something does not work": "Если что-то не работает",
    "Where are completed files?": "Где искать готовые файлы?", "Original files are not deleted": "Исходные файлы не удаляются",
    "Configured": "Настроен", "Not configured": "Не настроен",
    "No image generation provider is selected.": "Не выбран провайдер генерации изображений.",
    "The selected provider requires an API key to generate images.": "Для генерации изображений нужен API-ключ выбранного провайдера.",
    "Set a model in Settings before generating images.": "Перед генерацией укажите модель в настройках.",
    "How to Use PixelBatch": "Как пользоваться PixelBatch",
    "About PixelBatch": "О программе PixelBatch",
    "PixelBatch is a desktop tool for batch image processing: background removal, resizing, format conversion, background and padding setup, mass renaming, and e-commerce image preparation.": "PixelBatch — десктопное приложение для массовой пакетной обработки изображений: удаления фона, изменения размера, конвертации форматов, настройки фона и отступов, массового переименования и подготовки изображений для e-commerce.",
    "Version: 0.1.0-alpha. This project is currently in alpha development. Features and interfaces may change.": "Версия: 0.1.0-alpha. Проект находится на стадии alpha-разработки. Функции и интерфейсы могут измениться.",
    "Choose a tool from the menu on the left and follow a few simple steps.": "Выберите нужный инструмент слева и выполните несколько простых шагов.",
    "Choose a tool from the menu on the left.\nSelect images or a CSV file.\nChoose where to save the result.\nSet the required options.\nClick “Start”.\nWait for the completion message.": "Выберите инструмент в меню слева.\nВыберите изображения или CSV-файл.\nУкажите папку, куда сохранить результат.\nНастройте нужные параметры.\nНажмите «Запустить».\nДождитесь сообщения о завершении.",
    "You do not need an API key to remove backgrounds, add backgrounds, resize images, convert formats, or rename files. An API key is required only for experimental image generation.": "Для удаления фона, добавления фона, изменения размера, конвертации и переименования файлов API-ключ не нужен. API-ключ требуется только для экспериментальной генерации изображений.",
    "1. Generate Images": "1. Генерация изображений",
    "This experimental tool creates new images with artificial intelligence.": "Этот экспериментальный раздел создаёт новые изображения с помощью искусственного интеллекта.",
    "Open “Generate Images”.\nSelect a CSV file or enter an image description.\nSelect the rows to process.\nChoose an output folder.\nCheck the selected model.\nClick “Start”.": "Откройте «Генерация изображений».\nВыберите CSV-файл или введите описание изображения.\nВыберите строки, которые нужно обработать.\nУкажите папку для сохранения.\nПроверьте выбранную модель.\nНажмите «Запустить».",
    "Experimental API feature: this tool requires a provider API key. Add it in Settings. Local batch image tools work without an API key.": "Экспериментальная API-функция: для этого инструмента нужен API-ключ провайдера. Его можно добавить в «Настройках». Локальные инструменты пакетной обработки изображений работают без API-ключа.",
    "2. Remove Background": "2. Удаление фона",
    "This tool removes the background and leaves the object on a transparent background.": "Этот раздел удаляет фон у изображения и оставляет объект на прозрачном фоне.",
    "Open “Remove Background”.\nClick “Select Folder”.\nChoose a folder with one or more images.\nChoose an output folder.\nClick “Start”.\nCompleted images will appear in the selected folder.": "Откройте «Удаление фона».\nНажмите «Выбрать папку».\nВыберите папку с одним или несколькими изображениями.\nУкажите папку для сохранения.\nНажмите «Запустить».\nГотовые изображения появятся в выбранной папке.",
    "On first use, the app may download the background removal model once. Processing then runs on your computer.": "При первом запуске программа может один раз загрузить модель удаления фона. После загрузки обработка работает на компьютере.",
    "3. Add Background": "3. Добавление фона", "This tool adds a solid, white, transparent, or image background.": "Этот раздел добавляет цветной, белый, прозрачный фон или изображение.",
    "Open “Add Background”.\nChoose the images folder.\nChoose a background color, transparency, or an image.\nSet the canvas size and padding if needed.\nChoose an output folder.\nClick “Start”.": "Откройте «Добавление фона».\nВыберите папку с изображениями.\nВыберите цвет, прозрачность или изображение для фона.\nПри необходимости укажите размер холста и отступы.\nУкажите папку для сохранения.\nНажмите «Запустить».",
    "A HEX code is a color code. For example, white is #FFFFFF.": "HEX-код — это код цвета. Например, белый цвет: #FFFFFF.",
    "4. Resize Images": "4. Изменение размера", "This tool changes image width and height.": "Этот раздел меняет ширину и высоту изображений.",
    "Open “Resize Images”.\nChoose the images folder.\nEnter width and height.\nKeep “Preserve aspect ratio” enabled to avoid stretching.\nChoose an output folder.\nClick “Start”.": "Откройте «Изменение размера».\nВыберите папку с изображениями.\nУкажите ширину и высоту.\nОставьте включённым «Сохранять пропорции», чтобы изображение не растягивалось.\nУкажите папку для сохранения.\nНажмите «Запустить».",
    "Fit: the whole image fits inside the size. Fill: the image fills the size and edges may be cropped. Stretch: the image stretches to the exact size.": "Поместить: изображение полностью помещается в размер. Заполнить: изображение заполняет размер, края могут быть обрезаны. Растянуть: изображение растягивается точно до указанного размера.",
    "5. Convert Format": "5. Конвертация формата", "This tool saves images in another format.": "Этот раздел сохраняет изображения в другом формате.",
    "Open “Convert Format”.\nChoose the images folder.\nChoose a new format.\nSet quality when available.\nChoose an output folder.\nClick “Start”.": "Откройте «Конвертация формата».\nВыберите папку с изображениями.\nВыберите новый формат.\nУкажите качество, если этот параметр доступен.\nУкажите папку для сохранения.\nНажмите «Запустить».",
    "PNG supports transparency. JPEG is good for photos but not transparency. WEBP usually makes smaller files. BMP can be large. TIFF is suitable for high-quality printing and editing.": "PNG поддерживает прозрачность. JPEG подходит для фотографий, но не поддерживает прозрачность. WEBP обычно создаёт небольшие файлы. BMP может быть большим. TIFF подходит для качественной печати и обработки.",
    "6. Rename Files": "6. Переименование файлов",
    "This tool changes many filenames at once.\n\nOpen “Rename Files”.\nSelect files or a folder.\nChoose how names should change.\nReview the preview.\nChoose whether to create copies or rename originals.\nClick “Start”.": "Этот инструмент изменяет много имён файлов за один раз.\n\nОткройте «Переименование файлов».\nВыберите файлы или папку.\nНастройте, как должны измениться названия.\nПроверьте предпросмотр.\nВыберите режим создания копий или переименования оригиналов.\nНажмите «Запустить».",
    "If you are not sure, choose the copy mode. In this mode the source files stay unchanged.": "Если вы не уверены, выберите режим создания копий. В этом режиме исходные файлы остаются без изменений.",
    "6. Settings": "6. Настройки", "7. Settings": "7. Настройки",
    "Choose the language, theme, provider, model, and access settings here.": "Здесь можно выбрать язык, тему, провайдера, модель и параметры доступа.",
    "Provider is the service that creates images. Model is the selected AI model. API Key is its private access code. Base URL normally does not need changing. Timeout is how long the app waits. Retries control temporary request repeats.": "Провайдер — сервис, который создаёт изображения. Модель — выбранная модель искусственного интеллекта. API-ключ — её код доступа. Адрес API обычно не нужно менять. Время ожидания задаёт, сколько программа ждёт ответ. Повторные попытки задают число повторов при временной ошибке.",
    "Check that files and an output folder are selected. Make sure a file is not open in another app and that the disk has free space. For generation, check the API key. Read the message at the bottom. If needed, click “Cancel” and restart the app.": "Проверьте, выбраны ли файлы и папка для сохранения. Убедитесь, что файл не открыт другой программой и на диске есть свободное место. Для генерации проверьте API-ключ. Посмотрите сообщение внизу окна. При необходимости нажмите «Отмена» и перезапустите приложение.",
    "Completed files are saved in the folder shown in “Output folder”.": "Готовые файлы сохраняются в папку, указанную в поле «Папка для сохранения».",
    "The app creates new files and does not delete the originals.": "Приложение создаёт новые файлы и не удаляет оригиналы.",
    "Best for": "Для", "Speed": "Скорость", "Memory": "Память", "high": "высокая",
    "low/medium": "низкая/средняя", "Portraits": "Портреты", "Objects": "Объекты",
    "People": "Люди", "Clothing": "Одежда", "Illustrations": "Иллюстрации",
    "Precise masks": "Точные маски", "Large images": "Крупные изображения",
    "Hidden objects": "Скрытые объекты", "Experimental": "Экспериментально",
    "Medium": "Средняя", "Fast": "Быстрая", "Very fast": "Очень быстрая", "Slow": "Медленная",
    "High-quality hair and human contours.": "Высокое качество волос и контуров человека.",
    "Accurate general model for products and complex objects.": "Точная универсальная модель для товаров и сложных объектов.",
    "Lightweight BiRefNet for batch processing.": "Облегчённая BiRefNet для массовой обработки.",
    "Reliable general model and a good default choice.": "Надёжная универсальная модель, хороший базовый выбор.",
    "Full-body human segmentation.": "Сегментация человека в полный рост.",
    "Clothing segmentation in photos of people.": "Сегментация одежды на фотографиях людей.",
    "Compact model: faster but less precise on details.": "Компактная модель: быстрее, но менее точна на деталях.",
    "Compact general model with small weights.": "Компактная универсальная модель с небольшим размером весов.",
    "General model with clean edges.": "Универсальная модель с аккуратными краями.",
    "Optimized for anime and illustrated characters.": "Оптимизирована для аниме и рисованных персонажей.",
    "Modern general model for objects and people.": "Современная универсальная модель для предметов и людей.",
    "Detailed object segmentation with precise boundaries.": "Дихотомическая сегментация объектов с детальными границами.",
    "Salient object detection for high-resolution images.": "Выделение заметных объектов высокого разрешения.",
    "Model for objects that blend into the background.": "Модель для объектов, сливающихся с фоном.",
    "Heavy general model trained on a large dataset.": "Тяжёлая универсальная модель, обученная на большом наборе данных.",
    "Heavy general model; results depend on the scene.": "Тяжёлая универсальная модель; результат зависит от сцены.",
    "Delete the saved key for {provider}?": "Удалить сохранённый ключ для {provider}?",
    "Saved key deleted": "Сохранённый ключ удалён",
    "API key is session-only and will not be saved": "API-ключ действует только в этом сеансе и не будет сохранён",
    "Could not save settings:": "Не удалось сохранить настройки:",
    "Operation cancelled; ": "Операция отменена; ", "Completed; ": "Завершено; ",
    "The key is stored in Windows Credential Manager and is not written to settings.json.": "Ключ хранится в Диспетчере учётных данных Windows и не записывается в settings.json.",
    "Windows Credential Manager is unavailable. The key is used only until the app closes and is not written to settings.json.": "Диспетчер учётных данных Windows недоступен. Ключ используется только до закрытия приложения и не записывается в settings.json.",
    "An API key is needed only for experimental image generation. Background removal, background addition, resize, conversion, and renaming work locally without a key.": "API-ключ нужен только для экспериментальной генерации изображений. Удаление фона, добавление фона, изменение размера, конвертация и переименование работают локально без ключа.",
    "Only the active provider receives its key. No telemetry is collected.": "Только активный провайдер получает свой ключ. Телеметрия не собирается.",
    "Total data rows": "Всего строк данных", "Selected rows": "Выбрано строк",
    "Rows to process": "Строки для обработки", "Invalid rows": "Некорректные строки",
    "Folder not found": "Папка не найдена", "Unknown rembg model": "Неизвестная модель rembg",
    "This tool changes the names of many files at once.": "Этот инструмент изменяет названия многих файлов за один раз.",
    "Source files": "Исходные файлы", "No files selected": "Файлы не выбраны",
    "Clear List": "Очистить список", "Include subfolders": "Включать вложенные папки",
    "Extension filter": "Фильтр расширений", "Custom extensions": "Пользовательские расширения",
    "Custom extensions": "Пользовательские расширения", "All files": "Все файлы",
    "Rename operations": "Операции переименования", "Add prefix": "Добавить в начало",
    "Add suffix": "Добавить в конец названия", "Remove text": "Удалить из названия",
    "Case-sensitive": "Учитывать регистр", "First occurrence only": "Только первое вхождение",
    "Find and replace": "Найти и заменить", "Replace with": "Заменить на", "Replace all": "Заменить все",
    "Case": "Регистр", "None": "Без изменений", "Lowercase": "Нижний регистр",
    "Uppercase": "Верхний регистр", "Title Case": "Каждое слово с заглавной",
    "Normalize spaces and separators": "Нормализовать пробелы и разделители",
    "Lowercase extension": "Расширение в нижний регистр", "Sequential numbering": "Последовательная нумерация",
    "Enable numbering": "Включить нумерацию", "Base name": "Основа имени",
    "Start number": "Начальный номер", "Step": "Шаг", "Padding": "Разрядность",
    "Output mode": "Режим результата", "Mode": "Режим",
    "Create renamed copies": "Создать переименованные копии",
    "Rename original files": "Переименовать оригиналы", "Refresh Preview": "Обновить предпросмотр",
    "Preview": "Предпросмотр", "Old name": "Старое имя", "New name": "Новое имя",
    "OK": "Готово", "Files": "Файлы", "files found": "файлов найдено", "files selected": "файлов выбрано",
    "Preview shows first 300 files.": "Предпросмотр показывает первые 300 файлов.",
    "The source files will not be changed. Renamed copies will be saved to the selected folder.": "Исходные файлы останутся без изменений. Переименованные копии будут сохранены в выбранную папку.",
    "The original files will be renamed in the source folder.\n\nCheck the preview carefully before continuing. After renaming, the previous file names will no longer be used.": "Названия оригинальных файлов будут изменены в исходной папке.\n\nПеред продолжением внимательно проверьте предпросмотр. После переименования старые названия больше не будут использоваться.",
    "I checked the new names and understand that the original files will be renamed": "Я проверил новые названия и понимаю, что оригинальные файлы будут переименованы",
    "Choose a different folder to create copies.": "Для создания копий выберите другую папку.",
    "Select files or a folder first.": "Сначала выберите файлы или папку.",
    "Fix conflicts before starting.": "Исправьте конфликты перед запуском.",
    "Confirm that original files can be renamed.": "Подтвердите, что оригинальные файлы можно переименовать.",
    "Numbering values must be integers": "Значения нумерации должны быть целыми числами",
    "Numbering step must not be negative": "Шаг нумерации не должен быть отрицательным",
    "New filename is empty": "Новое имя файла пустое",
    "New filename contains invalid characters": "Новое имя файла содержит недопустимые символы",
    "New filename ends with a space or dot": "Новое имя файла заканчивается пробелом или точкой",
    "New filename has an empty name": "Новое имя файла не содержит названия",
    "New filename uses a reserved Windows name": "Новое имя использует зарезервированное имя Windows",
    "New filename is too long": "Новое имя файла слишком длинное",
    "Filename is unchanged": "Имя файла не изменилось",
    "Destination already exists": "Файл назначения уже существует",
    "Duplicate destination name": "Повторяющееся имя назначения",
    "The selected folder contains no supported images": "В выбранной папке нет поддерживаемых изображений",
    "rembg is not installed. Run": "rembg не установлен. Выполните",
    "Loading model": "Загрузка модели", "On first use, rembg may download its files": "При первом запуске rembg может загрузить файлы модели",
    "Processing": "Обработка", "Invalid background color": "Некорректный цвет фона",
    "Invalid HEX color. Use #RRGGBB, for example #FFFFFF": "Некорректный HEX-цвет. Используйте #RRGGBB, например #FFFFFF",
    "CSV range values must be integers": "Значения диапазона CSV должны быть целыми числами",
    "Select a valid conversion direction": "Выберите допустимое направление конвертации",
    "Quality must be between 20 and 95": "Качество должно быть от 20 до 95",
    "The folder contains no files for": "В папке нет файлов для операции",
    "Percentage must be between 0 and 1000": "Процент должен быть от 0 до 1000",
    "Width must be positive": "Ширина должна быть больше нуля", "Height must be positive": "Высота должна быть больше нуля",
    "Width and height must be from 1 to 20000 pixels": "Ширина и высота должны быть от 1 до 20000 пикселей",
    "Unknown resize mode": "Неизвестный режим изменения размера", "Unknown canvas mode": "Неизвестный режим холста",
    "Canvas dimensions must be at least 16 px": "Размеры холста должны быть не меньше 16 px",
    "Canvas is too large; maximum is 12000 px per side and 80 megapixels": "Холст слишком большой: не более 12000 px на сторону и 80 мегапикселей",
    "Padding cannot be negative": "Отступ не может быть отрицательным", "Padding percentage must be less than 50%": "Отступ должен быть меньше 50%",
    "Padding unit must be px or %": "Единица отступа должна быть px или %", "The image is fully transparent": "Изображение полностью прозрачное",
    "Padding leaves no usable canvas area": "После отступов на холсте не осталось полезной области",
    "Background image could not be opened": "Не удалось открыть изображение фона",
    "Background removal output must be PNG or WEBP to preserve transparency": "Для сохранения прозрачности результат удаления фона должен быть PNG или WEBP",
    "JPG/JPEG cannot store a transparent background; choose PNG or WEBP": "JPG/JPEG не поддерживает прозрачный фон; выберите PNG или WEBP",
    "Input folder not found": "Исходная папка не найдена", "The input folder contains no PNG, JPG or WEBP images": "В исходной папке нет изображений PNG, JPG или WEBP",
    "Maximum file size must be greater than zero": "Максимальный размер файла должен быть больше нуля",
    "File-size unit must be KB or MB": "Единица размера файла должна быть KB или MB",
    "Unsupported output format": "Неподдерживаемый формат результата", "max_bytes must be greater than zero": "Максимальный размер должен быть больше нуля",
    "Minimum quality must be between 20 and 95": "Минимальное качество должно быть от 20 до 95",
    "Operation cancelled": "Операция отменена",
}


class I18nManager:
    supported = {"ru", "en"}

    def __init__(self, language: str = "ru") -> None:
        self.language = language if language in self.supported else "en"
        self._reverse = {value: key for key, value in RU.items()}

    def set_language(self, language: str) -> None:
        if language not in self.supported:
            raise ValueError(f"Unsupported language: {language}")
        self.language = language

    def canonical(self, text: str) -> str:
        return self._reverse.get(text, text)

    def t(self, text: str, **kwargs: Any) -> str:
        canonical = self.canonical(text)
        if self.language == "ru":
            value = RU.get(canonical)
            if value is None:
                value = canonical
                for source in sorted(RU, key=len, reverse=True):
                    if source in value:
                        value = value.replace(source, RU[source])
        else:
            value = canonical
            for translated in sorted(self._reverse, key=len, reverse=True):
                if translated in value:
                    value = value.replace(translated, self._reverse[translated])
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            logging.getLogger(__name__).debug("Invalid translation template: %s", canonical)
            return value

    def localize_message(self, message: str) -> str:
        """Translate known UI/log phrases while preserving filenames and technical names."""
        exact = self.t(message)
        if exact != message:
            return exact
        pairs = {
            "saved as": "сохранён как", "output already exists": "результат уже существует",
            "generation started": "генерация начата", "canvas processing started": "обработка холста начата",
            "resize started": "изменение размера начато", "saved through": "сохранено через",
            "copied as": "скопирован как", "renamed to": "переименован в",
            "filename is unchanged": "имя файла не изменилось", "rename failed": "переименование не удалось",
            "Rename preview has conflicts": "В предпросмотре переименования есть конфликты",
            "Saved:": "Сохранено:", "Error": "Ошибка", "CSV row": "строка CSV",
        }
        if self.language == "ru":
            for source, target in pairs.items():
                message = re.sub(re.escape(source), target, message, flags=re.IGNORECASE)
        else:
            for source, target in pairs.items():
                message = re.sub(re.escape(target), source, message, flags=re.IGNORECASE)
        return message
