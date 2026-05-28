const state = {
  referenceData: null,
  debtors: [],
  modalMode: "create",
  deleteTargetId: null,
  claimTargetId: null,
  lawsuitTargetId: null,
  lastCreatedCourt: null,
  currentPage: 1,
  currentLanguage: "ru",
  currentCountry: "kz",
  currentUser: window.__APP_CONTEXT__?.user ?? null,
  datePicker: {
    activeInput: null,
    visibleMonth: null,
    view: "days",
  },
};

const PAGE_SIZE = 50;
const VIEW_STATE_STORAGE_KEY = "legal-department-table-view";
const LANGUAGE_STORAGE_KEY = "legal-department-language";
const COUNTRY_STORAGE_KEY = "legal-department-country";
const LANGUAGE_LOCALES = {
  ru: "ru-RU",
  pl: "pl-PL",
  en: "en-US",
  uk: "uk-UA",
  kk: "kk-KZ",
};

const COUNTRY_DISPLAY_LABELS = {
  kz: {
    ru: "KZ Казахстан",
    pl: "KZ Kazachstan",
    en: "KZ Kazakhstan",
    uk: "KZ Казахстан",
    kk: "KZ Қазақстан",
  },
  uz: {
    ru: "UZ Узбекистан",
    pl: "UZ Uzbekistan",
    en: "UZ Uzbekistan",
    uk: "UZ Узбекистан",
    kk: "UZ Өзбекстан",
  },
};

const CATEGORY_LABELS = {
  "Новый": { ru: "Новый", pl: "Nowy", en: "New", uk: "Новий", kk: "Жаңа" },
  "Готовим иск": { ru: "Готовим иск", pl: "Przygotowujemy pozew", en: "Preparing lawsuit", uk: "Готуємо позов", kk: "Талапты дайындап жатырмыз" },
  "Иск подан": { ru: "Иск подан", pl: "Pozew złożony", en: "Lawsuit filed", uk: "Позов подано", kk: "Талап берілді" },
  "Иск закрыт": { ru: "Иск закрыт", pl: "Sprawa zamknięta", en: "Lawsuit closed", uk: "Позов закрито", kk: "Талап жабылды" },
  "Оплата по претензии": { ru: "Оплата по претензии", pl: "Płatność po roszczeniu", en: "Paid after claim", uk: "Оплата за претензією", kk: "Наразылықтан кейін төлем" },
  "Клиент частично оплачивает": { ru: "Клиент частично оплачивает", pl: "Klient częściowo spłaca", en: "Client partially pays", uk: "Клієнт частково сплачує", kk: "Клиент ішінара төлеп жатыр" },
  "Ожидаем ответа по претензии": { ru: "Ожидаем ответа по претензии", pl: "Czekamy na odpowiedź na roszczenie", en: "Awaiting claim response", uk: "Очікуємо відповіді на претензію", kk: "Наразылыққа жауап күтіп отырмыз" },
  "Возврат в работу Юр. Отдела": { ru: "Возврат в работу Юр. Отдела", pl: "Zwrot do działu prawnego", en: "Returned to legal team", uk: "Повернення в роботу юрвідділу", kk: "Заң бөліміне қайта жұмысқа" },
  "Долг закрыт": { ru: "Долг закрыт", pl: "Dług zamknięty", en: "Debt closed", uk: "Борг закрито", kk: "Қарыз жабылды" },
  "Неподсудно": { ru: "Неподсудно", pl: "Brak właściwości sądu", en: "No jurisdiction", uk: "Не підсудно", kk: "Соттылыққа жатпайды" },
  "Прошел срок исковой давности": { ru: "Прошел срок исковой давности", pl: "Upłynął termin przedawnienia", en: "Limitation period expired", uk: "Сплив строк позовної давності", kk: "Талап қою мерзімі өтіп кеткен" },
  "Маленькая сумма долга": { ru: "Маленькая сумма долга", pl: "Niewielka kwota długu", en: "Small debt amount", uk: "Мала сума боргу", kk: "Қарыз сомасы аз" },
  "Закрытая компания": { ru: "Закрытая компания", pl: "Zamknięta spółka", en: "Closed company", uk: "Закрита компанія", kk: "Жабық компания" },
  "Не должник": { ru: "Не должник", pl: "Nie jest dłużnikiem", en: "Not a debtor", uk: "Не боржник", kk: "Борышкер емес" },
  "Требуется проверка решения в кабинете": { ru: "Требуется проверка решения в кабинете", pl: "Wymaga sprawdzenia decyzji w gabinecie", en: "Decision check required", uk: "Потрібна перевірка рішення в кабінеті", kk: "Кабинетте шешімді тексеру қажет" },
  "Передать на ЧСИ": { ru: "Передать на ЧСИ", pl: "Przekazać do komornika", en: "Send to bailiff", uk: "Передати приватному виконавцю", kk: "ЖСИ-ға беру" },
};

const DECISION_LABELS = {
  "Удовлетворить": { ru: "Удовлетворить", pl: "Uwzględnić", en: "Grant", uk: "Задовольнити", kk: "Қанағаттандыру" },
  "Частично": { ru: "Частично", pl: "Częściowo", en: "Partially", uk: "Частково", kk: "Ішінара" },
  "По соглашению сторон": { ru: "По соглашению сторон", pl: "Za porozumieniem stron", en: "By settlement", uk: "За згодою сторін", kk: "Тараптардың келісімі бойынша" },
  "Отказ в иске": { ru: "Отказ в иске", pl: "Oddalenie powództwa", en: "Claim denied", uk: "Відмова в позові", kk: "Талаптан бас тарту" },
  "Возврат иска": { ru: "Возврат иска", pl: "Zwrot pozwu", en: "Claim returned", uk: "Повернення позову", kk: "Талапты қайтару" },
};

const UI_STRINGS = {
  ru: {
    appTitle: "Контроль взыскания с должников",
    dept: "Юридический департамент",
    country: "KZ Казахстан",
    owner: "Owner",
    addDebtor: "Добавить должника",
    activeFilters: "Активные фильтры",
    reset: "Сброс",
    all: "Все",
    yes: "Да",
    no: "Нет",
    fromShort: "от",
    toShort: "до",
    severalComma: "несколько через запятую",
    selectedCount: "Выбрано: {count}",
    clear: "Очистить",
    today: "Сегодня",
    loading: "Загрузка данных...",
    noRecords: "Записей пока нет.",
    noResults: "По выбранным фильтрам ничего не найдено.",
    shownOf: "Показано {from}-{to} из {total}",
    back: "Назад",
    forward: "Вперед",
    removeFilter: "Убрать фильтр",
    edit: "Ред.",
    delete: "Удалить",
    pdf: "PDF",
    soon: "Скоро",
    lawsuitModuleSoon: "Модуль генерации иска будет добавлен следующим этапом",
    newRecord: "Новая запись",
    editRecord: "Редактирование записи",
    addDebtorTitle: "Добавить должника",
    debtorMainData: "Основные данные должника",
    save: "Сохранить",
    saveChanges: "Сохранить изменения",
    cancel: "Отмена",
    close: "Закрыть",
    confirm: "Подтверждение",
    confirmDeleteTitle: "Удалить запись?",
    deleteWarning: "Запись будет удалена без возможности восстановления. Если у нее есть вложенная подстрока возврата иска, она тоже удалится.",
    newCourt: "Новый суд",
    addCourt: "Добавить суд",
    claimDataConfirm: "Подтверждение данных",
    generateClaim: "Генерация претензии",
    generateLawsuit: "Генерация иска",
    generate: "Генерировать",
    lookupEnterContract: "Сначала введите номер договора.",
    lookupLoading: "Ищу клиента в CRM...",
    lookupFailed: "Не удалось получить данные из CRM.",
    lookupSuccess: "Данные из CRM подставлены в форму. Проверьте сумму долга и дату просрочки.",
    lookupConnectFailed: "Не удалось связаться с CRM.",
    saveRecordFailed: "Не удалось сохранить запись. Проверьте заполнение полей.",
    updateRecordFailed: "Не удалось обновить запись.",
    saveChangeFailed: "Не удалось сохранить изменение.",
    saveCourtFailed: "Не удалось сохранить новый суд.",
    generateClaimFailed: "Не удалось сформировать претензию.",
    generateLawsuitFailed: "Не удалось сформировать иск.",
    readClaimErrorFailed: "Не удалось прочитать ошибку генерации претензии.",
    readLawsuitErrorFailed: "Не удалось прочитать ошибку генерации иска.",
    deleteFailed: "Не удалось удалить запись.",
    fillFields: "Заполните поля: {fields}.",
    installmentEndAfterStart: "Дата окончания рассрочки должна быть позже даты начала.",
    fieldCourtName: "Название суда",
    fieldInstallmentFrom: "Рассрочка от",
    fieldInstallmentTo: "Рассрочка до",
    fieldDebtAmount: "Сумма долга",
    fieldPenaltyAmount: "Пеня",
    fieldMonthlyPayment: "Ежемесячный равный платеж",
    fieldFirstPeriodPaid: "Оплачено в 1-м периоде",
    productsAndQuantity: "Товары и количество",
    productName: "Название",
    productQuantity: "Кол-во",
    addProduct: "Добавить товар",
    account: "Аккаунт",
    profile: "Профиль",
    currentPassword: "Текущий пароль",
    newPassword: "Новый пароль",
    changePassword: "Сменить пароль",
    logout: "Выйти",
    firstLogin: "Первый вход",
    forcePasswordTitle: "Смените временный пароль",
    accessManagement: "Управление доступом",
    newLogin: "Новый логин",
    username: "Логин",
    fullName: "Имя сотрудника",
    role: "Роль",
    temporaryPassword: "Временный пароль",
    createLogin: "Создать логин",
    accountSummary: "{name} · {role}",
    authPasswordRule: "Пароль должен быть не короче 8 символов.",
    changePasswordSuccess: "Пароль успешно обновлен.",
    changePasswordFailed: "Не удалось сменить пароль.",
    createUserSuccess: "Логин создан. Сотрудник сменит пароль при первом входе.",
    createUserFailed: "Не удалось создать логин.",
    logoutFailed: "Не удалось завершить сессию.",
    usersListTitle: "Существующие логины",
    roleOwner: "owner",
    roleAdmin: "admin",
    roleLawyer: "lawyer",
    headers: ["Действие","Дата внесения","Дата контракта","Категория","ФИО клиента","№ договора","Дата последнего неисполненного платежа","Компания","Город","Суд","Претензия","Дата отправки претензии","Кол-во дней с отправки претензии","Кол-во дней долга","Сумма долга (тг)","Пеня (тг)","Сумма гос. пошлины (тг)","Общая сумма (тг)","Направлен иск","Дата отправки иска","Иск принят","Дата заседания","Есть решение","Решение","Сумма выплаты по решению (тг)","Получено (тг)","Комментарий","Номер дела","Суд по делу","Генерация претензии","Генерация иска","Удалить"],
    weekdays: ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"],
  },
  en: {
    appTitle: "Debt Recovery Control",
    dept: "Legal Department",
    country: "KZ Kazakhstan",
    owner: "Owner",
    addDebtor: "Add debtor",
    activeFilters: "Active filters",
    reset: "Reset",
    all: "All",
    yes: "Yes",
    no: "No",
    fromShort: "from",
    toShort: "to",
    severalComma: "multiple, comma separated",
    selectedCount: "Selected: {count}",
    clear: "Clear",
    today: "Today",
    loading: "Loading data...",
    noRecords: "No records yet.",
    noResults: "No records found for the selected filters.",
    shownOf: "Showing {from}-{to} of {total}",
    back: "Back",
    forward: "Next",
    removeFilter: "Remove filter",
    edit: "Edit",
    delete: "Delete",
    pdf: "PDF",
    soon: "Soon",
    lawsuitModuleSoon: "The lawsuit generation module will be added in the next phase",
    newRecord: "New record",
    editRecord: "Edit record",
    addDebtorTitle: "Add debtor",
    debtorMainData: "Debtor basic data",
    save: "Save",
    saveChanges: "Save changes",
    cancel: "Cancel",
    close: "Close",
    confirm: "Confirmation",
    confirmDeleteTitle: "Delete record?",
    deleteWarning: "The record will be deleted without recovery. If it has a nested claim-return subrow, it will be deleted too.",
    newCourt: "New court",
    addCourt: "Add court",
    claimDataConfirm: "Confirm data",
    generateClaim: "Generate claim",
    generateLawsuit: "Generate lawsuit",
    generate: "Generate",
    lookupEnterContract: "Enter the contract number first.",
    lookupLoading: "Searching CRM...",
    lookupFailed: "Failed to fetch data from CRM.",
    lookupSuccess: "CRM data has been inserted into the form. Check the debt amount and overdue date.",
    lookupConnectFailed: "Could not connect to CRM.",
    saveRecordFailed: "Failed to save the record. Check the required fields.",
    updateRecordFailed: "Failed to update the record.",
    saveChangeFailed: "Failed to save the change.",
    saveCourtFailed: "Failed to save the new court.",
    generateClaimFailed: "Failed to generate the claim.",
    generateLawsuitFailed: "Failed to generate the lawsuit.",
    readClaimErrorFailed: "Failed to read the claim generation error.",
    readLawsuitErrorFailed: "Failed to read the lawsuit generation error.",
    deleteFailed: "Failed to delete the record.",
    fillFields: "Fill in the fields: {fields}.",
    installmentEndAfterStart: "The installment end date must be later than the start date.",
    fieldCourtName: "Court name",
    fieldInstallmentFrom: "Installment from",
    fieldInstallmentTo: "Installment to",
    fieldDebtAmount: "Debt amount",
    fieldPenaltyAmount: "Penalty",
    fieldMonthlyPayment: "Monthly payment",
    fieldFirstPeriodPaid: "Paid in the 1st period",
    productsAndQuantity: "Products and quantity",
    productName: "Name",
    productQuantity: "Qty",
    addProduct: "Add product",
    headers: ["Action","Entry date","Contract date","Category","Client name","Contract no.","Last missed payment date","Company","City","Court","Claim","Claim sent date","Days since claim sent","Debt days","Debt amount (KZT)","Penalty (KZT)","State duty (KZT)","Total amount (KZT)","Lawsuit sent","Lawsuit sent date","Lawsuit accepted","Hearing date","Decision exists","Decision","Decision payout (KZT)","Received (KZT)","Comment","Case number","Case court","Claim PDF","Lawsuit PDF","Delete"],
    weekdays: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
  },
  uk: {
    appTitle: "Контроль стягнення з боржників",
    dept: "Юридичний департамент",
    country: "KZ Казахстан",
    owner: "Owner",
    addDebtor: "Додати боржника",
    activeFilters: "Активні фільтри",
    reset: "Скинути",
    all: "Усі",
    yes: "Так",
    no: "Ні",
    fromShort: "від",
    toShort: "до",
    severalComma: "кілька через кому",
    selectedCount: "Вибрано: {count}",
    clear: "Очистити",
    today: "Сьогодні",
    loading: "Завантаження даних...",
    noRecords: "Записів поки немає.",
    noResults: "За вибраними фільтрами нічого не знайдено.",
    shownOf: "Показано {from}-{to} із {total}",
    back: "Назад",
    forward: "Вперед",
    removeFilter: "Прибрати фільтр",
    edit: "Ред.",
    delete: "Видалити",
    pdf: "PDF",
    soon: "Скоро",
    lawsuitModuleSoon: "Модуль генерації позову буде додано на наступному етапі",
    newRecord: "Новий запис",
    editRecord: "Редагування запису",
    addDebtorTitle: "Додати боржника",
    debtorMainData: "Основні дані боржника",
    save: "Зберегти",
    saveChanges: "Зберегти зміни",
    cancel: "Скасувати",
    close: "Закрити",
    confirm: "Підтвердження",
    confirmDeleteTitle: "Видалити запис?",
    deleteWarning: "Запис буде видалено без можливості відновлення. Якщо є вкладений підрядок повернення позову, його теж буде видалено.",
    newCourt: "Новий суд",
    addCourt: "Додати суд",
    claimDataConfirm: "Підтвердження даних",
    generateClaim: "Генерація претензії",
    generateLawsuit: "Генерація позову",
    generate: "Згенерувати",
    lookupEnterContract: "Спочатку введіть номер договору.",
    lookupLoading: "Шукаю клієнта в CRM...",
    lookupFailed: "Не вдалося отримати дані з CRM.",
    lookupSuccess: "Дані з CRM підставлені у форму. Перевірте суму боргу та дату прострочення.",
    lookupConnectFailed: "Не вдалося зв'язатися з CRM.",
    saveRecordFailed: "Не вдалося зберегти запис. Перевірте заповнення полів.",
    updateRecordFailed: "Не вдалося оновити запис.",
    saveChangeFailed: "Не вдалося зберегти зміну.",
    saveCourtFailed: "Не вдалося зберегти новий суд.",
    generateClaimFailed: "Не вдалося сформувати претензію.",
    generateLawsuitFailed: "Не вдалося сформувати позов.",
    readClaimErrorFailed: "Не вдалося прочитати помилку генерації претензії.",
    readLawsuitErrorFailed: "Не вдалося прочитати помилку генерації позову.",
    deleteFailed: "Не вдалося видалити запис.",
    fillFields: "Заповніть поля: {fields}.",
    installmentEndAfterStart: "Дата завершення розстрочки має бути пізнішою за дату початку.",
    fieldCourtName: "Назва суду",
    fieldInstallmentFrom: "Розстрочка від",
    fieldInstallmentTo: "Розстрочка до",
    fieldDebtAmount: "Сума боргу",
    fieldPenaltyAmount: "Пеня",
    fieldMonthlyPayment: "Щомісячний рівний платіж",
    fieldFirstPeriodPaid: "Сплачено у 1-му періоді",
    productsAndQuantity: "Товари і кількість",
    productName: "Назва",
    productQuantity: "К-сть",
    addProduct: "Додати товар",
    headers: ["Дія","Дата внесення","Дата контракту","Категорія","ПІБ клієнта","№ договору","Дата останнього невиконаного платежу","Компанія","Місто","Суд","Претензія","Дата відправки претензії","К-сть днів з відправки претензії","К-сть днів боргу","Сума боргу (тг)","Пеня (тг)","Сума держмита (тг)","Загальна сума (тг)","Позов направлено","Дата відправки позову","Позов прийнято","Дата засідання","Є рішення","Рішення","Сума виплати за рішенням (тг)","Отримано (тг)","Коментар","Номер справи","Суд у справі","Генерація претензії","Генерація позову","Видалити"],
    weekdays: ["Пн","Вт","Ср","Чт","Пт","Сб","Нд"],
  },
  pl: {
    appTitle: "Kontrola windykacji dłużników",
    dept: "Dział prawny",
    country: "KZ Kazachstan",
    owner: "Owner",
    addDebtor: "Dodaj dłużnika",
    activeFilters: "Aktywne filtry",
    reset: "Resetuj",
    all: "Wszystkie",
    yes: "Tak",
    no: "Nie",
    fromShort: "od",
    toShort: "do",
    severalComma: "kilka, po przecinku",
    selectedCount: "Wybrano: {count}",
    clear: "Wyczyść",
    today: "Dziś",
    loading: "Ładowanie danych...",
    noRecords: "Brak zapisów.",
    noResults: "Brak wyników dla wybranych filtrów.",
    shownOf: "Pokazano {from}-{to} z {total}",
    back: "Wstecz",
    forward: "Dalej",
    removeFilter: "Usuń filtr",
    edit: "Edytuj",
    delete: "Usuń",
    pdf: "PDF",
    soon: "Wkrótce",
    lawsuitModuleSoon: "Moduł generowania pozwu zostanie dodany w następnym etapie",
    newRecord: "Nowy zapis",
    editRecord: "Edycja zapisu",
    addDebtorTitle: "Dodaj dłużnika",
    debtorMainData: "Podstawowe dane dłużnika",
    save: "Zapisz",
    saveChanges: "Zapisz zmiany",
    cancel: "Anuluj",
    close: "Zamknij",
    confirm: "Potwierdzenie",
    confirmDeleteTitle: "Usunąć zapis?",
    deleteWarning: "Zapis zostanie usunięty bez możliwości przywrócenia. Jeśli ma zagnieżdżony wiersz zwrotu pozwu, on też zostanie usunięty.",
    newCourt: "Nowy sąd",
    addCourt: "Dodaj sąd",
    claimDataConfirm: "Potwierdzenie danych",
    generateClaim: "Generowanie roszczenia",
    generateLawsuit: "Generowanie pozwu",
    generate: "Generuj",
    lookupEnterContract: "Najpierw wpisz numer umowy.",
    lookupLoading: "Szukam klienta w CRM...",
    lookupFailed: "Nie udało się pobrać danych z CRM.",
    lookupSuccess: "Dane z CRM zostały wstawione do formularza. Sprawdź kwotę długu i datę opóźnienia.",
    lookupConnectFailed: "Nie udało się połączyć z CRM.",
    saveRecordFailed: "Nie udało się zapisać rekordu. Sprawdź pola.",
    updateRecordFailed: "Nie udało się zaktualizować rekordu.",
    saveChangeFailed: "Nie udało się zapisać zmiany.",
    saveCourtFailed: "Nie udało się zapisać nowego sądu.",
    generateClaimFailed: "Nie udało się wygenerować roszczenia.",
    generateLawsuitFailed: "Nie udało się wygenerować pozwu.",
    readClaimErrorFailed: "Nie udało się odczytać błędu generowania roszczenia.",
    readLawsuitErrorFailed: "Nie udało się odczytać błędu generowania pozwu.",
    deleteFailed: "Nie udało się usunąć rekordu.",
    fillFields: "Wypełnij pola: {fields}.",
    installmentEndAfterStart: "Data zakończenia rat musi być późniejsza niż data rozpoczęcia.",
    fieldCourtName: "Nazwa sądu",
    fieldInstallmentFrom: "Raty od",
    fieldInstallmentTo: "Raty do",
    fieldDebtAmount: "Kwota długu",
    fieldPenaltyAmount: "Kara",
    fieldMonthlyPayment: "Równa miesięczna rata",
    fieldFirstPeriodPaid: "Zapłacono w 1. okresie",
    productsAndQuantity: "Towary i ilość",
    productName: "Nazwa",
    productQuantity: "Ilość",
    addProduct: "Dodaj towar",
    headers: ["Działanie","Data wpisu","Data umowy","Kategoria","Klient","Nr umowy","Data ostatniej zaległej płatności","Spółka","Miasto","Sąd","Roszczenie","Data wysłania roszczenia","Dni od wysłania roszczenia","Dni długu","Kwota długu (KZT)","Kara (KZT)","Opłata sądowa (KZT)","Łączna kwota (KZT)","Pozew wysłany","Data wysłania pozwu","Pozew przyjęty","Data rozprawy","Jest orzeczenie","Orzeczenie","Kwota wypłaty wg orzeczenia (KZT)","Otrzymano (KZT)","Komentarz","Numer sprawy","Sąd w sprawie","Generowanie roszczenia","Generowanie pozwu","Usuń"],
    weekdays: ["Pn","Wt","Śr","Cz","Pt","Sb","Nd"],
  },
  kk: {
    appTitle: "Борышкерлерден өндіріп алуды бақылау",
    dept: "Заң департаменті",
    country: "KZ Қазақстан",
    owner: "Owner",
    addDebtor: "Борышкер қосу",
    activeFilters: "Белсенді сүзгілер",
    reset: "Тазарту",
    all: "Барлығы",
    yes: "Иә",
    no: "Жоқ",
    fromShort: "бастап",
    toShort: "дейін",
    severalComma: "бірнешеуі үтір арқылы",
    selectedCount: "Таңдалды: {count}",
    clear: "Тазарту",
    today: "Бүгін",
    loading: "Деректер жүктелуде...",
    noRecords: "Әзірге жазбалар жоқ.",
    noResults: "Таңдалған сүзгілер бойынша ештеңе табылмады.",
    shownOf: "{from}-{to} / {total} көрсетілді",
    back: "Артқа",
    forward: "Алға",
    removeFilter: "Сүзгіні алып тастау",
    edit: "Өңд.",
    delete: "Жою",
    pdf: "PDF",
    soon: "Жақында",
    lawsuitModuleSoon: "Талап генерациясы келесі кезеңде қосылады",
    newRecord: "Жаңа жазба",
    editRecord: "Жазбаны өңдеу",
    addDebtorTitle: "Борышкер қосу",
    debtorMainData: "Борышкердің негізгі деректері",
    save: "Сақтау",
    saveChanges: "Өзгерістерді сақтау",
    cancel: "Бас тарту",
    close: "Жабу",
    confirm: "Растау",
    confirmDeleteTitle: "Жазбаны жою керек пе?",
    deleteWarning: "Жазба қалпына келтіру мүмкіндігінсіз жойылады. Егер талапты қайтару ішкі жолы болса, ол да жойылады.",
    newCourt: "Жаңа сот",
    addCourt: "Сот қосу",
    claimDataConfirm: "Деректерді растау",
    generateClaim: "Наразылықты генерациялау",
    generateLawsuit: "Талапты генерациялау",
    generate: "Генерациялау",
    lookupEnterContract: "Алдымен шарт нөмірін енгізіңіз.",
    lookupLoading: "CRM-де клиент ізделуде...",
    lookupFailed: "CRM-нен деректерді алу мүмкін болмады.",
    lookupSuccess: "CRM деректері формаға қойылды. Қарыз сомасы мен кешігу күнін тексеріңіз.",
    lookupConnectFailed: "CRM-мен байланысу мүмкін болмады.",
    saveRecordFailed: "Жазбаны сақтау мүмкін болмады. Өрістерді тексеріңіз.",
    updateRecordFailed: "Жазбаны жаңарту мүмкін болмады.",
    saveChangeFailed: "Өзгерісті сақтау мүмкін болмады.",
    saveCourtFailed: "Жаңа сотты сақтау мүмкін болмады.",
    generateClaimFailed: "Наразылықты қалыптастыру мүмкін болмады.",
    generateLawsuitFailed: "Талапты қалыптастыру мүмкін болмады.",
    readClaimErrorFailed: "Наразылық қатесін оқу мүмкін болмады.",
    readLawsuitErrorFailed: "Талап қатесін оқу мүмкін болмады.",
    deleteFailed: "Жазбаны жою мүмкін болмады.",
    fillFields: "Өрістерді толтырыңыз: {fields}.",
    installmentEndAfterStart: "Бөліп төлеудің аяқталу күні басталу күнінен кеш болуы тиіс.",
    fieldCourtName: "Сот атауы",
    fieldInstallmentFrom: "Бөліп төлеу басталуы",
    fieldInstallmentTo: "Бөліп төлеу аяқталуы",
    fieldDebtAmount: "Қарыз сомасы",
    fieldPenaltyAmount: "Өсімпұл",
    fieldMonthlyPayment: "Ай сайынғы тең төлем",
    fieldFirstPeriodPaid: "1-кезеңде төленгені",
    productsAndQuantity: "Тауарлар мен саны",
    productName: "Атауы",
    productQuantity: "Саны",
    addProduct: "Тауар қосу",
    headers: ["Әрекет","Енгізілген күні","Шарт күні","Санат","Клиенттің аты-жөні","Шарт №","Соңғы орындалмаған төлем күні","Компания","Қала","Сот","Наразылық","Наразылық жіберілген күн","Наразылықтан кейінгі күн саны","Қарыз күндері","Қарыз сомасы (тг)","Өсімпұл (тг)","Мемлекеттік баж (тг)","Жалпы сома (тг)","Талап жіберілді","Талап жіберілген күн","Талап қабылданды","Отырыс күні","Шешім бар","Шешім","Шешім бойынша төлем сомасы (тг)","Алынғаны (тг)","Түсініктеме","Іс нөмірі","Іс бойынша сот","Наразылық генерациясы","Талап генерациясы","Жою"],
    weekdays: ["Дс","Сс","Ср","Бс","Жм","Сб","Жс"],
  },
};

function getFilterLabel(key) {
  const headers = getLocalizedHeaders();
  const labels = {
    entry_date: headers[1],
    contract_date: headers[2],
    category: headers[3],
    client_name: headers[4],
    contract_number: headers[5],
    last_missed_payment_date: headers[6],
    company: headers[7],
    city: headers[8],
    court: headers[9],
    claim_sent: headers[10],
    claim_sent_date: headers[11],
    claim_sent_days: headers[12],
    debt_days: headers[13],
    debt_amount: headers[14],
    penalty_amount: headers[15],
    state_duty_amount: headers[16],
    total_amount: headers[17],
    lawsuit_sent: headers[18],
    lawsuit_sent_date: headers[19],
    lawsuit_accepted: headers[20],
    hearing_date: headers[21],
    decision_exists: headers[22],
    decision: headers[23],
    decision_payout: headers[24],
    received_amount: headers[25],
    comment: headers[26],
    case_number: headers[27],
    case_court: headers[28],
  };
  return labels[key] ?? FILTER_LABELS[key] ?? key;
}

function getFilterPlaceholder(column) {
  const headers = getLocalizedHeaders();
  const placeholders = {
    category: headers[3],
    client_name: headers[4],
    contract_number: headers[5],
    company: headers[7],
    city: headers[8],
    court: headers[9],
    decision: headers[23],
    comment: headers[26],
    case_number: headers[27],
    case_court: headers[28],
  };
  return placeholders[column.key] ?? column.placeholder ?? t("all");
}

function getLocalizedHeaders() {
  const headers = [...t("headers")];
  if (state.currentCountry !== "uz") {
    return headers;
  }
  return headers.map((header) => header.replaceAll("(тг)", "(сум)").replaceAll("(KZT)", "(UZS)"));
}

function extraLabel(key) {
  const labels = {
    contractNo: {
      ru: "№ договора",
      en: "Contract no.",
      uk: "№ договору",
      pl: "Nr umowy",
      kk: "Шарт №",
    },
    mobilePhone: {
      ru: "Мобильный телефон",
      en: "Mobile phone",
      uk: "Мобільний телефон",
      pl: "Telefon komórkowy",
      kk: "Ұялы телефон",
    },
    homePhone: {
      ru: "Домашний телефон",
      en: "Home phone",
      uk: "Домашній телефон",
      pl: "Telefon domowy",
      kk: "Үй телефоны",
    },
    clientAddress: {
      ru: "Адрес клиента",
      en: "Client address",
      uk: "Адреса клієнта",
      pl: "Adres klienta",
      kk: "Клиент мекенжайы",
    },
    phone: {
      ru: "Телефон",
      en: "Phone",
      uk: "Телефон",
      pl: "Telefon",
      kk: "Телефон",
    },
    name: {
      ru: "Название",
      en: "Name",
      uk: "Назва",
      pl: "Nazwa",
      kk: "Атауы",
    },
    region: {
      ru: "Область",
      en: "Region",
      uk: "Область",
      pl: "Region",
      kk: "Облыс",
    },
  };

  return labels[key]?.[state.currentLanguage] ?? labels[key]?.ru ?? key;
}

const CATEGORY_STYLES = {
  "Новый": { bg: "#FFFFE0", text: "#111111" },
  "Готовим иск": { bg: "#FFDAB9", text: "#111111" },
  "Иск подан": { bg: "#808000", text: "#111111" },
  "Иск закрыт": { bg: "#006400", text: "#111111" },
  "Оплата по претензии": { bg: "#98FB98", text: "#111111" },
  "Клиент частично оплачивает": { bg: "#4169E1", text: "#ffffff" },
  "Ожидаем ответа по претензии": { bg: "#DAA520", text: "#111111" },
  "Возврат в работу Юр. Отдела": { bg: "#FFFF00", text: "#111111" },
  "Долг закрыт": { bg: "#7FFF00", text: "#111111" },
  "Неподсудно": { bg: "#808080", text: "#111111" },
  "Прошел срок исковой давности": { bg: "#808080", text: "#111111" },
  "Маленькая сумма долга": { bg: "#808080", text: "#111111" },
  "Закрытая компания": { bg: "#808080", text: "#111111" },
  "Не должник": { bg: "#808080", text: "#111111" },
  "Требуется проверка решения в кабинете": { bg: "#7B68EE", text: "#ffffff" },
  "Передать на ЧСИ": { bg: "#FA8072", text: "#111111" },
};

const DECISION_STYLES = {
  "Удовлетворить": { bg: "#0b5d1e", text: "#ffffff" },
  "Частично": { bg: "#cfeec9", text: "#111111" },
  "По соглашению сторон": { bg: "#87ceeb", text: "#111111" },
  "Отказ в иске": { bg: "#6b0f1a", text: "#ffffff" },
  "Возврат иска": { bg: "#ffe066", text: "#111111" },
};

const tbody = document.getElementById("debtors-tbody");
const modalBackdrop = document.getElementById("debtor-modal-backdrop");
const deleteModalBackdrop = document.getElementById("delete-modal-backdrop");
const courtModalBackdrop = document.getElementById("court-modal-backdrop");
const claimModalBackdrop = document.getElementById("claim-modal-backdrop");
const lawsuitModalBackdrop = document.getElementById("lawsuit-modal-backdrop");
const accountModalBackdrop = document.getElementById("account-modal-backdrop");
const forcePasswordModalBackdrop = document.getElementById("force-password-modal-backdrop");
const openModalButton = document.getElementById("open-create-modal");
const topbarActions = document.querySelector(".topbar-actions");
const countrySelect = document.getElementById("country-select");
const ownerButton = document.getElementById("owner-button");
const languageSelect = document.getElementById("language-select");
const closeModalButton = document.getElementById("close-debtor-modal");
const cancelModalButton = document.getElementById("cancel-debtor-modal");
const lookupContractButton = document.getElementById("lookup-contract-button");
const openCourtModalButton = document.getElementById("open-court-modal");
const closeCourtModalButton = document.getElementById("close-court-modal");
const cancelCourtModalButton = document.getElementById("cancel-court-modal");
const debtorForm = document.getElementById("debtor-form");
const courtForm = document.getElementById("court-form");
const modalTitle = document.getElementById("debtor-modal-title");
const modalEyebrow = document.getElementById("debtor-modal-eyebrow");
const submitButton = document.getElementById("debtor-submit-button");
const companySelect = document.getElementById("company-select");
const citySelect = document.getElementById("city-select");
const courtSelect = document.getElementById("court-select");
const crmLookupStatus = document.getElementById("crm-lookup-status");
const courtModalCitySelect = document.getElementById("court-city-select");
const courtModalRegionSelect = document.getElementById("court-region-select");
const closeDeleteModalButton = document.getElementById("close-delete-modal");
const cancelDeleteModalButton = document.getElementById("cancel-delete-modal");
const confirmDeleteButton = document.getElementById("confirm-delete-button");
const deleteModalText = document.getElementById("delete-modal-text");
const closeClaimModalButton = document.getElementById("close-claim-modal");
const cancelClaimModalButton = document.getElementById("cancel-claim-modal");
const claimConfirmForm = document.getElementById("claim-confirm-form");
const closeLawsuitModalButton = document.getElementById("close-lawsuit-modal");
const cancelLawsuitModalButton = document.getElementById("cancel-lawsuit-modal");
const lawsuitConfirmForm = document.getElementById("lawsuit-confirm-form");
const claimProductsList = document.getElementById("claim-products-list");
const lawsuitProductsList = document.getElementById("lawsuit-products-list");
const claimAddProductButton = document.getElementById("claim-add-product");
const lawsuitAddProductButton = document.getElementById("lawsuit-add-product");
const closeAccountModalButton = document.getElementById("close-account-modal");
const changePasswordForm = document.getElementById("change-password-form");
const forcePasswordForm = document.getElementById("force-password-form");
const createUserForm = document.getElementById("create-user-form");
const logoutButton = document.getElementById("logout-button");
const accountSummary = document.getElementById("account-summary");
const userManagementBlock = document.getElementById("user-management-block");
const usersList = document.getElementById("users-list");
const changePasswordStatus = document.getElementById("change-password-status");
const forcePasswordStatus = document.getElementById("force-password-status");
const createUserStatus = document.getElementById("create-user-status");
const activeFiltersBlock = document.getElementById("active-filters");
const activeFiltersList = document.getElementById("active-filters-list");
const thead = document.getElementById("debtors-thead");
const paginationBar = document.getElementById("pagination-bar");
const paginationSummary = document.getElementById("pagination-summary");
const paginationControls = document.getElementById("pagination-controls");
const datePickerPopover = document.getElementById("date-picker-popover");
const datePickerGrid = document.getElementById("date-picker-grid");
const datePickerWeekdays = datePickerPopover?.querySelector(".date-picker-weekdays");
const datePickerTitleMonth = datePickerPopover?.querySelector(".date-picker-title-month");
const datePickerTitleYear = datePickerPopover?.querySelector(".date-picker-title-year");

function t(key, params = {}) {
  let value = UI_STRINGS[state.currentLanguage]?.[key] ?? UI_STRINGS.ru[key] ?? key;
  Object.entries(params).forEach(([paramKey, paramValue]) => {
    value = value.replaceAll(`{${paramKey}}`, String(paramValue));
  });
  return value;
}

function currentLocale() {
  return LANGUAGE_LOCALES[state.currentLanguage] ?? LANGUAGE_LOCALES.ru;
}

function currentUserDisplayName() {
  if (!state.currentUser) {
    return t("owner");
  }
  return state.currentUser.full_name || state.currentUser.username || t("owner");
}

function currentUserRoleLabel() {
  if (!state.currentUser?.role) {
    return "";
  }
  return t(
    state.currentUser.role === "owner"
      ? "roleOwner"
      : state.currentUser.role === "admin"
        ? "roleAdmin"
        : "roleLawyer",
  );
}

function setInlineStatus(target, message, kind = "error") {
  if (!target) {
    return;
  }
  if (!message) {
    target.textContent = "";
    target.classList.add("hidden");
    target.classList.remove("is-loading", "is-success", "is-error", "status-success", "status-error");
    return;
  }
  target.textContent = message;
  target.classList.remove("hidden", "is-loading", "is-success", "is-error", "status-success", "status-error");
  if (kind === "loading") {
    target.classList.add("is-loading");
  } else if (kind === "success") {
    target.classList.add("is-success", "status-success");
  } else {
    target.classList.add("is-error", "status-error");
  }
}

function translateCategory(value) {
  return CATEGORY_LABELS[value]?.[state.currentLanguage] ?? value;
}

function translateDecision(value) {
  return DECISION_LABELS[value]?.[state.currentLanguage] ?? value;
}

const FILTER_COLUMNS = [
  { key: "actions", type: "reset" },
  { key: "entry_date", type: "date-range" },
  { key: "contract_date", type: "date-range" },
  { key: "category", type: "multi-select", optionsSource: "categories", placeholder: "Категории" },
  { key: "client_name", type: "text", placeholder: "ФИО" },
  { key: "contract_number", type: "text", placeholder: "№ договора" },
  { key: "last_missed_payment_date", type: "date-range" },
  { key: "company", type: "multi-select", optionsSource: "companies", placeholder: "Компании" },
  { key: "city", type: "token-suggest", suggestionsId: "filter-cities-list", placeholder: "Города" },
  { key: "court", type: "token-suggest", suggestionsId: "filter-courts-list", placeholder: "Суды" },
  { key: "claim_sent", type: "boolean" },
  { key: "claim_sent_date", type: "date-range" },
  { key: "claim_sent_days", type: "number-range" },
  { key: "debt_days", type: "number-range" },
  { key: "debt_amount", type: "number-range" },
  { key: "penalty_amount", type: "number-range" },
  { key: "state_duty_amount", type: "number-range" },
  { key: "total_amount", type: "number-range" },
  { key: "lawsuit_sent", type: "boolean" },
  { key: "lawsuit_sent_date", type: "date-range" },
  { key: "lawsuit_accepted", type: "boolean" },
  { key: "hearing_date", type: "date-range" },
  { key: "decision_exists", type: "boolean" },
  { key: "decision", type: "multi-select", optionsSource: "decisions", placeholder: "Решения", includeEmptyOption: true },
  { key: "decision_payout", type: "number-range" },
  { key: "received_amount", type: "number-range" },
  { key: "comment", type: "text", placeholder: "Комментарий" },
  { key: "case_number", type: "text", placeholder: "Номер дела" },
  { key: "case_court", type: "token-suggest", suggestionsId: "filter-courts-list", placeholder: "Суд по делу" },
  { key: "claim_document", type: "empty" },
  { key: "lawsuit_document", type: "empty" },
  { key: "delete", type: "empty" },
];

const FILTER_LABELS = {
  entry_date: "Дата внесения",
  contract_date: "Дата контракта",
  category: "Категория",
  client_name: "ФИО клиента",
  contract_number: "№ договора",
  last_missed_payment_date: "Дата последнего неисполненного платежа",
  company: "Компания",
  city: "Город",
  court: "Суд",
  claim_sent: "Претензия",
  claim_sent_date: "Дата отправки претензии",
  claim_sent_days: "Кол-во дней с отправки претензии",
  debt_days: "Кол-во дней долга",
  debt_amount: "Сумма долга",
  penalty_amount: "Пеня",
  state_duty_amount: "Сумма гос. пошлины",
  total_amount: "Общая сумма",
  lawsuit_sent: "Направлен иск",
  lawsuit_sent_date: "Дата отправки иска",
  lawsuit_accepted: "Иск принят",
  hearing_date: "Дата заседания",
  decision_exists: "Есть решение",
  decision: "Решение",
  decision_payout: "Сумма выплаты по решению",
  received_amount: "Получено",
  comment: "Комментарий",
  case_number: "Номер дела",
  case_court: "Суд по делу",
};

function ensureLanguageControls() {
  if (!topbarActions) {
    return;
  }

  if (!document.getElementById("country-select")) {
    const select = document.createElement("select");
    select.className = "ghost-button language-select";
    select.id = "country-select";
    select.setAttribute("aria-label", "Country");
    [["kz", "KZ Казахстан"], ["uz", "UZ Узбекистан"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
    const language = document.getElementById("language-select");
    const owner = ownerButton ?? topbarActions.querySelector("button.ghost-button:last-of-type");
    if (language) {
      topbarActions.insertBefore(select, language);
    } else if (owner) {
      topbarActions.insertBefore(select, owner);
    } else {
      topbarActions.appendChild(select);
    }
  }

  if (!document.getElementById("language-select")) {
    const select = document.createElement("select");
    select.className = "ghost-button language-select";
    select.id = "language-select";
    select.setAttribute("aria-label", "Language");
    [["ru", "RU"], ["pl", "PL"], ["en", "EN"], ["uk", "UK"], ["kk", "KZ"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
    const owner = ownerButton ?? topbarActions.querySelector("button.ghost-button:last-of-type");
    if (owner) {
      topbarActions.insertBefore(select, owner);
    } else {
      topbarActions.appendChild(select);
    }
  }

  if (!document.getElementById("owner-button")) {
    const button = topbarActions.querySelector("button.ghost-button:last-of-type");
    if (button) {
      button.id = "owner-button";
    }
  }
}

function renderCurrentUserButton() {
  const button = document.getElementById("owner-button");
  if (!button) {
    return;
  }
  button.textContent = currentUserDisplayName();
}

function renderAccountSummary() {
  if (!accountSummary) {
    return;
  }
  if (!state.currentUser) {
    accountSummary.replaceChildren();
    return;
  }
  const roleLabel = currentUserRoleLabel();
  accountSummary.innerHTML = `
    <div class="account-summary-line">${state.currentUser.full_name || ""}</div>
    <div class="account-summary-line">${state.currentUser.username || ""}</div>
    <div class="account-summary-line">${roleLabel}</div>
  `;
}

function openAccountModal() {
  renderAccountSummary();
  if (userManagementBlock) {
    userManagementBlock.classList.toggle("hidden", state.currentUser?.role !== "owner");
  }
  if (state.currentUser?.role === "owner") {
    loadUsers();
  }
  accountModalBackdrop?.classList.remove("hidden");
}

function closeAccountModal() {
  accountModalBackdrop?.classList.add("hidden");
  setInlineStatus(changePasswordStatus, "");
  setInlineStatus(createUserStatus, "");
  changePasswordForm?.reset();
  createUserForm?.reset();
}

function openForcePasswordModal() {
  forcePasswordModalBackdrop?.classList.remove("hidden");
}

function closeForcePasswordModal() {
  forcePasswordModalBackdrop?.classList.add("hidden");
  setInlineStatus(forcePasswordStatus, "");
  forcePasswordForm?.reset();
}

function mapAuthError(detail, fallbackMessage) {
  switch (detail) {
    case "INVALID_CURRENT_PASSWORD":
      return "Текущий пароль введен неверно.";
    case "PASSWORD_TOO_SHORT":
      return t("authPasswordRule");
    case "USERNAME_ALREADY_EXISTS":
      return "Такой логин уже существует.";
    case "INVALID_ROLE":
      return "Выбрана неверная роль.";
    case "AUTH_REQUIRED":
      return "Сессия истекла. Войдите снова.";
    default:
      return fallbackMessage;
  }
}

async function loadUsers() {
  if (!usersList || state.currentUser?.role !== "owner") {
    return;
  }
  usersList.innerHTML = "";
  try {
    const response = await fetch("/api/users", { credentials: "same-origin" });
    if (!response.ok) {
      return;
    }
    const users = await response.json();
    usersList.innerHTML = users
      .map(
        (user) => `
          <article class="user-card">
            <div class="user-card-title">${escapeHtml(user.full_name || user.username)}</div>
            <div class="user-card-meta">${escapeHtml(user.username)} · ${escapeHtml(user.role)}</div>
            <div class="user-card-meta">${user.must_change_password ? "Требуется смена пароля" : "Пароль активирован"}</div>
          </article>
        `,
      )
      .join("");
  } catch (error) {
    console.error(error);
  }
}

async function handleChangePasswordSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const currentPassword = form.current_password.value;
  const newPassword = form.new_password.value;
  if (!currentPassword || !newPassword) {
    setInlineStatus(changePasswordStatus, "Заполните оба поля.");
    return;
  }
  if (newPassword.length < 8) {
    setInlineStatus(changePasswordStatus, t("authPasswordRule"));
    return;
  }

  try {
    const response = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setInlineStatus(changePasswordStatus, mapAuthError(payload.detail, t("changePasswordFailed")));
      return;
    }
    const payload = await response.json();
    state.currentUser = payload.user;
    renderCurrentUserButton();
    renderAccountSummary();
    setInlineStatus(changePasswordStatus, t("changePasswordSuccess"), "success");
    setTimeout(() => {
      closeAccountModal();
    }, 500);
  } catch (error) {
    console.error(error);
    setInlineStatus(changePasswordStatus, t("changePasswordFailed"));
  }
}

async function handleForcePasswordSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const currentPassword = form.current_password.value;
  const newPassword = form.new_password.value;
  if (!currentPassword || !newPassword) {
    setInlineStatus(forcePasswordStatus, "Заполните оба поля.");
    return;
  }
  if (newPassword.length < 8) {
    setInlineStatus(forcePasswordStatus, t("authPasswordRule"));
    return;
  }

  try {
    const response = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setInlineStatus(forcePasswordStatus, mapAuthError(payload.detail, t("changePasswordFailed")));
      return;
    }
    const payload = await response.json();
    state.currentUser = payload.user;
    renderCurrentUserButton();
    closeForcePasswordModal();
    await initAppData();
  } catch (error) {
    console.error(error);
    setInlineStatus(forcePasswordStatus, t("changePasswordFailed"));
  }
}

async function handleCreateUserSubmit(event) {
  event.preventDefault();
  if (state.currentUser?.role !== "owner") {
    return;
  }
  const form = event.currentTarget;
  const payload = {
    username: form.username.value.trim(),
    full_name: form.full_name.value.trim(),
    role: form.role.value,
    temporary_password: form.temporary_password.value,
  };
  if (!payload.username || !payload.full_name || !payload.temporary_password) {
    setInlineStatus(createUserStatus, "Заполните все поля.");
    return;
  }
  if (payload.temporary_password.length < 8) {
    setInlineStatus(createUserStatus, t("authPasswordRule"));
    return;
  }
  try {
    const response = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      setInlineStatus(createUserStatus, mapAuthError(errorPayload.detail, t("createUserFailed")));
      return;
    }
    form.reset();
    setInlineStatus(createUserStatus, t("createUserSuccess"), "success");
    await loadUsers();
  } catch (error) {
    console.error(error);
    setInlineStatus(createUserStatus, t("createUserFailed"));
  }
}

async function handleLogout() {
  try {
    const response = await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
    if (!response.ok) {
      alert(t("logoutFailed"));
      return;
    }
    window.location.href = "/";
  } catch (error) {
    console.error(error);
    alert(t("logoutFailed"));
  }
}

async function initAppData() {
  await loadReferenceData();
  initFilters();
  restoreViewState();
  await loadDebtors();
}

document.addEventListener("DOMContentLoaded", async () => {
  ensureLanguageControls();
  state.currentLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY) || "ru";
  state.currentCountry = window.localStorage.getItem(COUNTRY_STORAGE_KEY) || "kz";
  document.getElementById("country-select").value = state.currentCountry;
  document.getElementById("language-select").value = state.currentLanguage;
  if (closeLawsuitModalButton) {
    closeLawsuitModalButton.innerHTML = "&times;";
  }
  bindEvents();
  applyStaticTranslations();
  renderCurrentUserButton();
  if (state.currentUser?.must_change_password) {
    openForcePasswordModal();
    return;
  }
  await initAppData();
});

function bindEvents() {
  document.getElementById("country-select")?.addEventListener("change", handleCountryChange);
  document.getElementById("language-select")?.addEventListener("change", handleLanguageChange);
  ownerButton?.addEventListener("click", openAccountModal);
  openModalButton.addEventListener("click", openCreateModal);
  closeModalButton.addEventListener("click", closeModal);
  cancelModalButton.addEventListener("click", closeModal);
  modalBackdrop.addEventListener("click", (event) => {
    if (event.target === modalBackdrop) {
      closeModal();
    }
  });

  closeDeleteModalButton.addEventListener("click", closeDeleteModal);
  cancelDeleteModalButton.addEventListener("click", closeDeleteModal);
  confirmDeleteButton.addEventListener("click", confirmDelete);
  deleteModalBackdrop.addEventListener("click", (event) => {
    if (event.target === deleteModalBackdrop) {
      closeDeleteModal();
    }
  });

  closeClaimModalButton.addEventListener("click", closeClaimModal);
  cancelClaimModalButton.addEventListener("click", closeClaimModal);
  claimConfirmForm.addEventListener("submit", handleClaimConfirmSubmit);
  claimAddProductButton?.addEventListener("click", () => appendDocumentProductRow(claimProductsList));
  claimModalBackdrop.addEventListener("click", (event) => {
    if (event.target === claimModalBackdrop) {
      closeClaimModal();
    }
  });
  claimProductsList?.addEventListener("click", (event) => {
    const removeButton = event.target.closest(".product-remove-button");
    if (!removeButton) {
      return;
    }
    removeButton.closest(".product-editor-row")?.remove();
    if (!claimProductsList.querySelector(".product-editor-row")) {
      appendDocumentProductRow(claimProductsList);
    }
  });

  closeLawsuitModalButton.addEventListener("click", closeLawsuitModal);
  cancelLawsuitModalButton.addEventListener("click", closeLawsuitModal);
  lawsuitConfirmForm.addEventListener("submit", handleLawsuitConfirmSubmit);
  lawsuitAddProductButton?.addEventListener("click", () => appendDocumentProductRow(lawsuitProductsList));
  lawsuitConfirmForm.debt_amount.addEventListener("input", recalculateLawsuitStateDuty);
  lawsuitConfirmForm.penalty_amount.addEventListener("input", recalculateLawsuitStateDuty);
  hideAutoCalculatedLawsuitFields();
  lawsuitModalBackdrop.addEventListener("click", (event) => {
    if (event.target === lawsuitModalBackdrop) {
      closeLawsuitModal();
    }
  });
  lawsuitProductsList?.addEventListener("click", (event) => {
    const removeButton = event.target.closest(".product-remove-button");
    if (!removeButton) {
      return;
    }
    removeButton.closest(".product-editor-row")?.remove();
    if (!lawsuitProductsList.querySelector(".product-editor-row")) {
      appendDocumentProductRow(lawsuitProductsList);
    }
  });

  openCourtModalButton.addEventListener("click", openCourtModal);
  lookupContractButton.addEventListener("click", handleContractLookup);
  closeCourtModalButton.addEventListener("click", closeCourtModal);
  cancelCourtModalButton.addEventListener("click", closeCourtModal);
  courtForm.addEventListener("submit", handleCourtSubmit);
  courtModalBackdrop.addEventListener("click", (event) => {
    if (event.target === courtModalBackdrop) {
      closeCourtModal();
    }
  });

  courtSelect.addEventListener("change", handleModalCourtChange);
  courtModalRegionSelect.addEventListener("change", handleCourtModalRegionChange);
  courtModalCitySelect.addEventListener("change", handleCourtModalCityChange);

  debtorForm.addEventListener("submit", handleModalSubmit);
  debtorForm.contract_number.addEventListener("input", handleContractNumberInput);
  tbody.addEventListener("click", handleTableClick);
  tbody.addEventListener("change", handleTableChange);
  tbody.addEventListener("blur", handleTableBlur, true);
  thead.addEventListener("input", handleFilterInteraction);
  thead.addEventListener("change", handleFilterInteraction);
  thead.addEventListener("click", handleFilterClick);
  thead.addEventListener("toggle", handleFilterToggle, true);
  activeFiltersList?.addEventListener("click", handleActiveFilterClick);
  paginationControls?.addEventListener("click", handlePaginationClick);
  document.addEventListener("click", handleDateClick);
  document.addEventListener("mousedown", handleDateMouseDown);
  document.addEventListener("focusin", handleDateFocusIn);
  document.addEventListener("input", handleDateInput);
  document.addEventListener("keydown", handleDateKeydown);
  document.addEventListener("blur", handleDateBlur, true);
  document.addEventListener("click", handleGlobalFilterClick);
  document.addEventListener("keydown", handleGlobalFilterKeydown);
  closeAccountModalButton?.addEventListener("click", closeAccountModal);
  accountModalBackdrop?.addEventListener("click", (event) => {
    if (event.target === accountModalBackdrop) {
      closeAccountModal();
    }
  });
  changePasswordForm?.addEventListener("submit", handleChangePasswordSubmit);
  forcePasswordForm?.addEventListener("submit", handleForcePasswordSubmit);
  createUserForm?.addEventListener("submit", handleCreateUserSubmit);
  logoutButton?.addEventListener("click", handleLogout);
}

function handleLanguageChange(event) {
  state.currentLanguage = event.target.value || "ru";
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, state.currentLanguage);
  applyStaticTranslations();
  const filtersSnapshot = collectFilterControlState();
  initFilters();
  applyFilterControlState(filtersSnapshot);
  updateAllFilterSummaries();
  renderDebtors();
}

async function handleCountryChange(event) {
  state.currentCountry = event.target.value || "kz";
  window.localStorage.setItem(COUNTRY_STORAGE_KEY, state.currentCountry);
  state.currentPage = 1;
  state.lastCreatedCourt = null;
  applyStaticTranslations();
  await loadReferenceData();
  initFilters();
  restoreViewState();
  await loadDebtors();
}

function getCountryDisplayName(countryCode = state.currentCountry, language = state.currentLanguage) {
  const labels = COUNTRY_DISPLAY_LABELS[countryCode] || COUNTRY_DISPLAY_LABELS.kz;
  return labels[language] || labels.ru;
}

function getViewStateStorageKey() {
  return `${VIEW_STATE_STORAGE_KEY}-${state.currentCountry}`;
}

function applyStaticTranslations() {
  document.documentElement.lang = state.currentLanguage;
  document.title = t("appTitle");
  document.querySelector(".brand-block .eyebrow").textContent = t("dept");
  document.querySelector(".brand-block h1").textContent = t("appTitle");
  const countrySelectElement = document.getElementById("country-select");
  if (countrySelectElement) {
    Array.from(countrySelectElement.options).forEach((option) => {
      option.textContent = getCountryDisplayName(option.value, state.currentLanguage);
    });
    countrySelectElement.value = state.currentCountry;
  }
  renderCurrentUserButton();
  openModalButton.textContent = t("addDebtor");
  activeFiltersBlock?.querySelector(".active-filters-label")?.replaceChildren(document.createTextNode(t("activeFilters")));

  const headerCells = thead?.querySelectorAll(".header-row th") ?? [];
  const headerTexts = getLocalizedHeaders();
  headerCells.forEach((cell, index) => {
    if (headerTexts[index]) {
      cell.textContent = headerTexts[index];
    }
  });

  const modalHeader = document.querySelector("#debtor-modal-backdrop .modal-header .eyebrow");
  if (modalHeader && state.modalMode === "create") {
    modalHeader.textContent = t("newRecord");
  }
  if (modalTitle && state.modalMode === "create") {
    modalTitle.textContent = t("addDebtorTitle");
  }
  if (submitButton && state.modalMode === "create") {
    submitButton.textContent = t("save");
  }
  cancelModalButton.textContent = t("cancel");
  closeModalButton.setAttribute("aria-label", t("close"));

  setModalLabel(debtorForm, "contract_number", extraLabel("contractNo"));
  setModalLabel(debtorForm, "client_name", headerTexts[4]);
  setModalLabel(debtorForm, "company", headerTexts[7]);
  setModalLabel(debtorForm, "city", headerTexts[8]);
  setModalLabel(debtorForm, "mobile_phone", extraLabel("mobilePhone"));
  setModalLabel(debtorForm, "home_phone", extraLabel("homePhone"));
  setModalLabel(debtorForm, "address", extraLabel("clientAddress"));
  setModalLabel(debtorForm, "court", headerTexts[9]);
  setModalLabel(debtorForm, "last_missed_payment_date", headerTexts[6]);
  setModalLabel(debtorForm, "debt_amount", headerTexts[14]);
  lookupContractButton.textContent = "CRM";

  document.querySelector("#delete-modal-backdrop .modal-header .eyebrow").textContent = t("confirm");
  document.getElementById("delete-modal-title").textContent = t("confirmDeleteTitle");
  deleteModalText.textContent = t("deleteWarning");
  cancelDeleteModalButton.textContent = t("cancel");
  confirmDeleteButton.textContent = t("delete");
  closeDeleteModalButton.setAttribute("aria-label", t("close"));

  document.querySelector("#court-modal-backdrop .modal-header .eyebrow").textContent = t("newCourt");
  document.getElementById("court-modal-title").textContent = t("addCourt");
  setModalLabel(courtForm, "name", extraLabel("name"));
  setModalLabel(courtForm, "city", headerTexts[8]);
  setModalLabel(courtForm, "region", extraLabel("region"));
  cancelCourtModalButton.textContent = t("cancel");
  document.getElementById("save-court-button").textContent = t("save");
  closeCourtModalButton.setAttribute("aria-label", t("close"));

  document.querySelector("#claim-modal-backdrop .modal-header .eyebrow").textContent = t("claimDataConfirm");
  document.getElementById("claim-modal-title").textContent = t("generateClaim");
  setModalLabel(claimConfirmForm, "client_name", headerTexts[4]);
  setModalLabel(claimConfirmForm, "client_phone", extraLabel("phone"));
  setModalLabel(claimConfirmForm, "client_address", extraLabel("clientAddress"));
  setModalLabel(claimConfirmForm, "company_name", headerTexts[7]);
  setModalLabel(claimConfirmForm, "contract_number", extraLabel("contractNo"));
  setModalLabel(claimConfirmForm, "debt_amount", headerTexts[14]);
  document.getElementById("claim-products-title").textContent = t("productsAndQuantity");
  document.getElementById("claim-product-name-label").textContent = t("productName");
  document.getElementById("claim-product-qty-label").textContent = t("productQuantity");
  claimAddProductButton.textContent = "+";
  claimAddProductButton.setAttribute("aria-label", t("addProduct"));
  cancelClaimModalButton.textContent = t("cancel");
  document.getElementById("confirm-claim-button").textContent = t("generate");
  closeClaimModalButton.setAttribute("aria-label", t("close"));

  document.querySelector("#lawsuit-modal-backdrop .modal-header .eyebrow").textContent = t("claimDataConfirm");
  document.getElementById("lawsuit-modal-title").textContent = t("generateLawsuit");
  setModalLabel(lawsuitConfirmForm, "client_name", headerTexts[4]);
  setModalLabel(lawsuitConfirmForm, "company_name", headerTexts[7]);
  setModalLabel(lawsuitConfirmForm, "contract_number", extraLabel("contractNo"));
  setModalLabel(lawsuitConfirmForm, "contract_date", headerTexts[2]);
  setModalLabel(lawsuitConfirmForm, "court_name", t("fieldCourtName"));
  setModalLabel(lawsuitConfirmForm, "debt_amount", t("fieldDebtAmount"));
  setModalLabel(lawsuitConfirmForm, "penalty_amount", t("fieldPenaltyAmount"));
  setModalLabel(lawsuitConfirmForm, "state_duty_amount", headerTexts[16]);
  setModalLabel(lawsuitConfirmForm, "installment_from", t("fieldInstallmentFrom"));
  setModalLabel(lawsuitConfirmForm, "installment_to", t("fieldInstallmentTo"));
  setModalLabel(lawsuitConfirmForm, "monthly_payment_amount", t("fieldMonthlyPayment"));
  setModalLabel(lawsuitConfirmForm, "first_period_paid_amount", t("fieldFirstPeriodPaid"));
  document.getElementById("lawsuit-products-title").textContent = t("productsAndQuantity");
  document.getElementById("lawsuit-product-name-label").textContent = t("productName");
  document.getElementById("lawsuit-product-qty-label").textContent = t("productQuantity");
  lawsuitAddProductButton.textContent = "+";
  lawsuitAddProductButton.setAttribute("aria-label", t("addProduct"));
  cancelLawsuitModalButton.textContent = t("cancel");
  document.getElementById("confirm-lawsuit-button").textContent = t("generate");
  closeLawsuitModalButton.setAttribute("aria-label", t("close"));
  document.getElementById("account-modal-eyebrow").textContent = t("account");
  document.getElementById("account-modal-title").textContent = t("profile");
  document.getElementById("change-password-current-label").textContent = t("currentPassword");
  document.getElementById("change-password-new-label").textContent = t("newPassword");
  document.getElementById("change-password-submit").textContent = t("changePassword");
  document.getElementById("logout-button").textContent = t("logout");
  document.getElementById("user-management-eyebrow").textContent = t("accessManagement");
  document.getElementById("user-management-title").textContent = t("newLogin");
  document.getElementById("create-user-username-label").textContent = t("username");
  document.getElementById("create-user-full-name-label").textContent = t("fullName");
  document.getElementById("create-user-role-label").textContent = t("role");
  document.getElementById("create-user-temp-password-label").textContent = t("temporaryPassword");
  document.getElementById("create-user-submit").textContent = t("createLogin");
  document.getElementById("force-password-modal-eyebrow").textContent = t("firstLogin");
  document.getElementById("force-password-modal-title").textContent = t("forcePasswordTitle");
  document.getElementById("force-password-current-label").textContent = t("currentPassword");
  document.getElementById("force-password-new-label").textContent = t("newPassword");
  document.getElementById("force-password-submit").textContent = t("save");
  renderAccountSummary();

  const weekdayNodes = datePickerPopover?.querySelectorAll(".date-picker-weekdays span") ?? [];
  weekdayNodes.forEach((node, index) => {
    node.textContent = t("weekdays")[index];
  });
  datePickerPopover?.querySelector('[data-date-action="clear"]')?.replaceChildren(document.createTextNode(t("clear")));
  datePickerPopover?.querySelector('[data-date-action="today"]')?.replaceChildren(document.createTextNode(t("today")));
}

function setModalLabel(form, fieldName, text) {
  const control = form?.elements?.namedItem(fieldName);
  if (!control) {
    return;
  }
  const label = control.closest("label");
  const actionLabel = label?.querySelector(".field-label-with-action");
  const span = actionLabel?.querySelector(":scope > span:first-child") ?? label?.querySelector("span");
  if (span) {
    span.textContent = text;
  }
}

function setCrmLookupStatus(message, type = "info") {
  crmLookupStatus.textContent = message;
  crmLookupStatus.classList.remove("hidden", "is-error", "is-success", "is-loading");
  if (type === "error") {
    crmLookupStatus.classList.add("is-error");
  } else if (type === "success") {
    crmLookupStatus.classList.add("is-success");
  } else if (type === "loading") {
    crmLookupStatus.classList.add("is-loading");
  }
}

function clearCrmLookupStatus() {
  crmLookupStatus.textContent = "";
  crmLookupStatus.classList.add("hidden");
  crmLookupStatus.classList.remove("is-error", "is-success", "is-loading");
}

function clearCrmPrefillFields() {
  debtorForm.client_name.value = "";
  debtorForm.company.value = "";
  debtorForm.city.value = "";
  debtorForm.mobile_phone.value = "";
  debtorForm.home_phone.value = "";
  debtorForm.address.value = "";
  debtorForm.contract_total_amount.value = "";
  debtorForm.contract_advance_amount.value = "";
  if (!debtorForm.court.value) {
    renderModalCourts("", null);
  }
}

function handleContractNumberInput() {
  clearCrmLookupStatus();
  clearCrmPrefillFields();
}

function applyCrmPrefill(prefill) {
  debtorForm.client_name.value = prefill.client_name || "";
  debtorForm.company.value = prefill.company || "";
  debtorForm.city.value = prefill.city || "";
  debtorForm.mobile_phone.value = prefill.mobile_phone || "";
  debtorForm.home_phone.value = prefill.home_phone || "";
  debtorForm.address.value = prefill.address || "";
  debtorForm.debt_amount.value = Number(prefill.debt_amount || 0);
  debtorForm.contract_total_amount.value =
    prefill.contract_total_amount === null || prefill.contract_total_amount === undefined
      ? ""
      : Number(prefill.contract_total_amount);
  debtorForm.contract_advance_amount.value =
    prefill.contract_advance_amount === null || prefill.contract_advance_amount === undefined
      ? ""
      : Number(prefill.contract_advance_amount);
  const preservedCourt =
    state.referenceData?.courtCityMap?.[debtorForm.court.value] === (prefill.city || "")
      ? debtorForm.court.value
      : "";
  renderModalCourts(prefill.city || "", preservedCourt);
}

async function handleContractLookup() {
  const contractNumber = debtorForm.contract_number.value.trim();
  if (!contractNumber) {
    setCrmLookupStatus(t("lookupEnterContract"), "error");
    debtorForm.contract_number.focus();
    return;
  }

  lookupContractButton.disabled = true;
  setCrmLookupStatus(t("lookupLoading"), "loading");

  try {
    const response = await fetch(
      `/api/crm/debtor-prefill?contract_number=${encodeURIComponent(contractNumber)}&country=${encodeURIComponent(state.currentCountry)}`
    );
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      setCrmLookupStatus(payload?.detail || t("lookupFailed"), "error");
      return;
    }

    applyCrmPrefill(payload);
    setCrmLookupStatus(t("lookupSuccess"), "success");
  } catch (error) {
    console.error("CRM lookup failed", error);
    setCrmLookupStatus(t("lookupConnectFailed"), "error");
  } finally {
    lookupContractButton.disabled = false;
  }
}

async function handleModalSubmit(event) {
  event.preventDefault();

  const payload = {
    country: state.currentCountry,
    client_name: debtorForm.client_name.value.trim(),
    contract_number: debtorForm.contract_number.value.trim(),
    company: debtorForm.company.value.trim(),
    city: debtorForm.city.value.trim(),
    court: debtorForm.court.value,
    last_missed_payment_date: getDateInputIsoValue(debtorForm.last_missed_payment_date),
    debt_amount: Number(debtorForm.debt_amount.value),
    mobile_phone: debtorForm.mobile_phone.value.trim() || null,
    home_phone: debtorForm.home_phone.value.trim() || null,
    address: debtorForm.address.value.trim() || null,
    contract_total_amount:
      debtorForm.contract_total_amount.value === ""
        ? null
        : Number(debtorForm.contract_total_amount.value),
    contract_advance_amount:
      debtorForm.contract_advance_amount.value === ""
        ? null
        : Number(debtorForm.contract_advance_amount.value),
  };

  let response;
  if (state.modalMode === "create") {
    response = await fetch("/api/debtors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } else {
    response = await fetch(`/api/debtors/${debtorForm.debtor_id.value}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  if (!response.ok) {
    alert(state.modalMode === "create" ? t("saveRecordFailed") : t("updateRecordFailed"));
    return;
  }

  if (state.modalMode === "create") {
    const debtor = await response.json();
    state.debtors.unshift(debtor);
    renderDebtors(true);
  } else {
    await loadDebtors();
  }

  closeModal();
}

async function loadReferenceData() {
  const response = await fetch(`/api/reference-data?country=${encodeURIComponent(state.currentCountry)}`);
  if (response.status === 401) {
    window.location.href = "/";
    return;
  }
  if (response.status === 403) {
    const payload = await response.json().catch(() => ({}));
    if (payload.detail === "PASSWORD_CHANGE_REQUIRED") {
      openForcePasswordModal();
      return;
    }
  }
  state.referenceData = await response.json();

  populateModalCities(debtorForm.city?.value || null, debtorForm.court?.value || null);
  renderModalCourts(citySelect.value, debtorForm.court?.value || null);
  populateCourtModalRegions(courtModalRegionSelect.value || null);
  populateCourtModalCities(courtModalRegionSelect.value || null, courtModalCitySelect.value || null);
  if (thead.querySelector(".filter-row")) {
    ensureFilterSupportMarkup();
  }
}

async function loadDebtors() {
  const response = await fetch(`/api/debtors?country=${encodeURIComponent(state.currentCountry)}`);
  if (response.status === 401) {
    window.location.href = "/";
    return;
  }
  if (response.status === 403) {
    const payload = await response.json().catch(() => ({}));
    if (payload.detail === "PASSWORD_CHANGE_REQUIRED") {
      openForcePasswordModal();
      return;
    }
  }
  state.debtors = await response.json();
  renderDebtors();
}

function initFilters() {
  ensureFilterSupportMarkup();
  thead.querySelector(".filter-row")?.remove();
  thead.insertAdjacentHTML("afterbegin", renderFiltersRow());
  localizeFilterControls();
  updateAllFilterSummaries();
}

function localizeFilterControls() {
  const filterRow = thead.querySelector(".filter-row");
  if (!filterRow) {
    return;
  }

  const resetButton = filterRow.querySelector("[data-filter-reset]");
  if (resetButton) {
    resetButton.textContent = t("reset");
  }

  FILTER_COLUMNS.forEach((column) => {
    if (column.type === "empty" || column.type === "reset") {
      return;
    }
    if (column.type === "boolean") {
      const select = filterRow.querySelector(`[data-filter-key="${column.key}"]`);
      if (select?.options?.length >= 3) {
        select.options[0].textContent = t("all");
        select.options[1].textContent = t("yes");
        select.options[2].textContent = t("no");
      }
      return;
    }
    if (column.type === "text") {
      const input = filterRow.querySelector(`[data-filter-key="${column.key}"]`);
      if (input) {
        input.placeholder = getFilterPlaceholder(column);
      }
      return;
    }
    if (column.type === "token-suggest") {
      const input = filterRow.querySelector(`[data-filter-key="${column.key}"]`);
      if (input) {
        input.placeholder = t("severalComma");
      }
      return;
    }
    if (column.type === "number-range") {
      const fromInput = filterRow.querySelector(`[data-filter-key="${column.key}"][data-bound="from"]`);
      const toInput = filterRow.querySelector(`[data-filter-key="${column.key}"][data-bound="to"]`);
      if (fromInput) {
        fromInput.placeholder = t("fromShort");
      }
      if (toInput) {
        toInput.placeholder = t("toShort");
      }
      return;
    }
    if (column.type === "multi-select") {
      const summary = filterRow.querySelector(`[data-filter-summary="${column.key}"]`);
      if (summary && !summary.dataset.userChosen) {
        summary.textContent = getFilterPlaceholder(column);
      }
      const clearButton = filterRow.querySelector(`[data-filter-clear-group="${column.key}"]`);
      if (clearButton) {
        clearButton.textContent = t("clear");
      }
      filterRow.querySelectorAll(`input[type="checkbox"][data-filter-key="${column.key}"]`).forEach((checkbox) => {
        const label = checkbox.closest("label")?.querySelector("span");
        if (label) {
          label.textContent = checkbox.value === "__" ? "-" : translateFilterOption(column.key, checkbox.value);
        }
      });
    }
  });
}

function localizeRenderedTable() {
  tbody.querySelectorAll(".edit-row-button").forEach((button) => {
    button.textContent = t("edit");
  });
  tbody.querySelectorAll(".delete-row-button").forEach((button) => {
    button.textContent = t("delete");
  });
  tbody.querySelectorAll(".lawsuit-document-button").forEach((button) => {
    button.textContent = t("pdf");
  });
  tbody.querySelectorAll(".claim-document-button").forEach((button) => {
    button.textContent = t("pdf");
  });
  tbody.querySelectorAll('select[data-inline-field="category"] option').forEach((option) => {
    option.textContent = translateCategory(option.value);
  });
  tbody.querySelectorAll('select[data-inline-field="decision"] option').forEach((option) => {
    option.textContent = option.value ? translateDecision(option.value) : "—";
  });
  tbody.querySelectorAll(
    'select[data-inline-field="claim_sent"] option, select[data-inline-field="lawsuit_sent"] option, select[data-inline-field="lawsuit_accepted"] option, select[data-inline-field="decision_exists"] option',
  ).forEach((option) => {
    option.textContent = option.value === "true" ? t("yes") : t("no");
  });
}

function translateFilterOption(key, value) {
  if (key === "category") {
    return translateCategory(value);
  }
  if (key === "decision") {
    return translateDecision(value);
  }
  return value;
}

function renderFiltersRow() {
  const cells = FILTER_COLUMNS.map((column) => renderFilterCell(column)).join("");
  return `<tr class="filter-row">${cells}</tr>`;
}

function renderFilterCell(column) {
  if (column.type === "reset") {
    return `
      <th class="filter-header-cell filter-header-cell-reset">
        <button class="secondary-button compact-button filter-reset-button" type="button" data-filter-reset="true">
          Сброс
        </button>
      </th>
    `;
  }

  if (column.type === "empty") {
    return '<th class="filter-header-cell filter-header-cell-empty"></th>';
  }

  if (column.type === "date-range") {
    return `
      <th class="filter-header-cell">
        <div class="filter-range">
          <input class="filter-control filter-control-date date-input" data-date-input="true" data-filter-key="${column.key}" data-bound="from" type="text" placeholder="дд.мм.гггг" autocomplete="off" />
          <input class="filter-control filter-control-date date-input" data-date-input="true" data-filter-key="${column.key}" data-bound="to" type="text" placeholder="дд.мм.гггг" autocomplete="off" />
        </div>
      </th>
    `;
  }

  if (column.type === "number-range") {
    return `
      <th class="filter-header-cell">
        <div class="filter-range">
          <input class="filter-control filter-control-number" data-filter-key="${column.key}" data-bound="from" type="number" step="0.01" placeholder="от" />
          <input class="filter-control filter-control-number" data-filter-key="${column.key}" data-bound="to" type="number" step="0.01" placeholder="до" />
        </div>
      </th>
    `;
  }

  if (column.type === "boolean") {
    return `
      <th class="filter-header-cell">
        <select class="filter-control filter-control-select" data-filter-key="${column.key}">
          <option value="">Все</option>
          <option value="true">Да</option>
          <option value="false">Нет</option>
        </select>
      </th>
    `;
  }

  if (column.type === "text") {
    return `
      <th class="filter-header-cell">
        <input
          class="filter-control filter-control-text"
          data-filter-key="${column.key}"
          type="text"
          placeholder="${escapeHtmlAttribute(column.placeholder ?? "Поиск")}"
        />
      </th>
    `;
  }

  if (column.type === "token-suggest") {
    return `
      <th class="filter-header-cell">
        <input
          class="filter-control filter-control-text"
          data-filter-key="${column.key}"
          type="text"
          list="${column.suggestionsId}"
          placeholder="несколько через запятую"
        />
      </th>
    `;
  }

  if (column.type === "multi-select") {
    const options = getFilterOptions(column);
    return `
      <th class="filter-header-cell">
        <details class="filter-multi" data-filter-group="${column.key}">
          <summary class="filter-control filter-multi-summary" data-filter-summary="${column.key}">
            ${escapeHtml(column.placeholder ?? "Все")}
          </summary>
          <div class="filter-multi-popover">
            <button
              class="ghost-button filter-mini-button"
              type="button"
              data-filter-clear-group="${column.key}"
            >
              Очистить
            </button>
            <div class="filter-multi-options">
              ${options
                .map(
                  (option) => `
                    <label class="filter-option">
                      <input type="checkbox" data-filter-key="${column.key}" value="${escapeHtmlAttribute(option)}" />
                      <span>${escapeHtml(option === "__" ? "-" : option)}</span>
                    </label>
                  `,
                )
                .join("")}
            </div>
          </div>
        </details>
      </th>
    `;
  }

  return '<th class="filter-header-cell"></th>';
}

function ensureFilterSupportMarkup() {
  document.getElementById("filter-support-markup")?.remove();
  const cities = state.referenceData?.cities ?? [];
  const courts = collectCourtOptions();

  const markup = `
    <div id="filter-support-markup" hidden>
      <datalist id="filter-cities-list">
        ${cities.map((city) => `<option value="${escapeHtmlAttribute(city)}"></option>`).join("")}
      </datalist>
      <datalist id="filter-courts-list">
        ${courts.map((court) => `<option value="${escapeHtmlAttribute(court)}"></option>`).join("")}
      </datalist>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", markup);
}

function collectCourtOptions() {
  const allCourts = Object.values(state.referenceData?.courtsByCity ?? {}).flat();
  return [...new Set(allCourts)].sort((left, right) => left.localeCompare(right, "ru"));
}

function getFilterOptions(source) {
  if (typeof source === "string") {
    return state.referenceData?.[source] ?? [];
  }
  if (!source?.optionsSource) {
    return [];
  }

  const baseOptions = [...(state.referenceData?.[source.optionsSource] ?? [])];
  if (source.includeEmptyOption) {
    return ["__", ...baseOptions];
  }
  return baseOptions;
}

function populateSelect(element, values, { includeBlank = false, selectedValue = null } = {}) {
  element.innerHTML = "";

  if (includeBlank) {
    const blankOption = document.createElement("option");
    blankOption.value = "";
    blankOption.textContent = "—";
    element.appendChild(blankOption);
  }

  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    if (selectedValue !== null && value === selectedValue) {
      option.selected = true;
    }
    element.appendChild(option);
  }
}

function sortStrings(values) {
  return [...values].sort((left, right) => left.localeCompare(right, "ru"));
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))];
}

function populateModalCities(selectedCity = null, selectedCourt = null) {
  const mappedCity = selectedCourt ? state.referenceData?.courtCityMap?.[selectedCourt] : null;
  citySelect.value = selectedCity ?? mappedCity ?? "";
}

function renderModalCourts(city, selectedCourt = null) {
  const cityCourts = state.referenceData?.courtsByCity?.[city] ?? [];
  const courts = sortStrings(uniqueValues([...cityCourts, selectedCourt]));
  populateSelect(courtSelect, courts, {
    includeBlank: true,
    selectedValue: selectedCourt ?? "",
  });
}

function populateCourtModalRegions(selectedRegion = null) {
  const options = state.referenceData?.regions ?? [];
  populateSelect(courtModalRegionSelect, options, {
    selectedValue: selectedRegion ?? options[0] ?? null,
  });
}

function populateCourtModalCities(region, selectedCity = null) {
  const regionCities = region
    ? state.referenceData?.citiesByRegion?.[region] ?? []
    : state.referenceData?.cities ?? [];
  const options = sortStrings(uniqueValues([...(regionCities ?? []), selectedCity]));
  populateSelect(courtModalCitySelect, options, {
    selectedValue: selectedCity ?? options[0] ?? null,
  });
}

function handleModalCourtChange() {
  const selectedCourt = courtSelect.value;
  const mappedCity = state.referenceData?.courtCityMap?.[selectedCourt];
  if (!mappedCity) {
    return;
  }

  populateModalCities(mappedCity, selectedCourt);
  citySelect.value = mappedCity;
  renderModalCourts(mappedCity, selectedCourt);
}

function handleCourtModalRegionChange() {
  populateCourtModalCities(courtModalRegionSelect.value);
}

function handleCourtModalCityChange() {
  const selectedCity = courtModalCitySelect.value;
  const mappedRegion = state.referenceData?.cityRegionMap?.[selectedCity];
  if (mappedRegion) {
    populateCourtModalRegions(mappedRegion);
    courtModalRegionSelect.value = mappedRegion;
    populateCourtModalCities(mappedRegion, selectedCity);
  }
}

function renderDebtors(resetPage = false) {
  if (resetPage) {
    state.currentPage = 1;
  }

  const filters = readFilters();
  updateActiveFilters(filters);

  if (!state.debtors.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="32">${t("noRecords")}</td></tr>`;
    renderPaginationMeta(0, 0, 0, 0);
    saveViewState();
    return;
  }
  const roots = state.debtors.filter((debtor) => !debtor.parent_debtor_id);
  const childrenByParent = new Map(
    state.debtors
      .filter((debtor) => debtor.parent_debtor_id)
      .map((debtor) => [debtor.parent_debtor_id, debtor]),
  );

  const visibleRoots = roots.filter((debtor) => {
    const child = childrenByParent.get(debtor.id);
    return branchMatchesFilters(debtor, child, filters);
  });

  if (!visibleRoots.length) {
    const emptyMessage = hasActiveFilters(filters) ? t("noResults") : t("noRecords");
    tbody.innerHTML = `<tr class="empty-row"><td colspan="32">${emptyMessage}</td></tr>`;
    renderPaginationMeta(0, 0, 0, 0);
    saveViewState();
    return;
  }

  const totalItems = visibleRoots.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
  state.currentPage = Math.min(Math.max(1, state.currentPage), totalPages);
  const startIndex = (state.currentPage - 1) * PAGE_SIZE;
  const pagedRoots = visibleRoots.slice(startIndex, startIndex + PAGE_SIZE);

  tbody.innerHTML = pagedRoots
    .map((debtor) => {
      const child = childrenByParent.get(debtor.id);
      return child ? renderNestedPair(debtor, child) : renderSingleRow(debtor);
    })
    .join("");

  localizeRenderedTable();
  renderPaginationMeta(totalItems, totalPages, startIndex, pagedRoots.length);
  saveViewState();
}

function handleFilterInteraction(event) {
  if (!event.target.closest(".filter-row")) {
    return;
  }

  if (event.target.matches('input[type="checkbox"][data-filter-key]')) {
    updateFilterSummary(event.target.dataset.filterKey);
  }

  renderDebtors(true);
}

function handleFilterClick(event) {
  const resetButton = event.target.closest("[data-filter-reset]");
  if (resetButton) {
    clearFilters();
    return;
  }

  const clearGroupButton = event.target.closest("[data-filter-clear-group]");
  if (clearGroupButton) {
    const key = clearGroupButton.dataset.filterClearGroup;
    clearMultiFilterGroup(key);
    renderDebtors(true);
  }
}

function handleFilterToggle(event) {
  const details = event.target;
  if (!(details instanceof HTMLDetailsElement) || !details.matches(".filter-multi")) {
    return;
  }

  const hostCell = details.closest("th");
  if (details.open) {
    closeAllFilterDropdowns(details);
    hostCell?.classList.add("filter-open");
  } else {
    hostCell?.classList.remove("filter-open");
  }
}

function handleGlobalFilterClick(event) {
  if (event.target.closest(".filter-multi")) {
    return;
  }
  closeAllFilterDropdowns();
}

function handleGlobalFilterKeydown(event) {
  if (event.key !== "Escape") {
    return;
  }
  closeAllFilterDropdowns();
}

function handleActiveFilterClick(event) {
  const removeButton = event.target.closest("[data-active-filter-remove]");
  if (!removeButton) {
    return;
  }

  removeActiveFilter(removeButton.dataset);
  renderDebtors(true);
}

function clearFilters() {
  const row = thead.querySelector(".filter-row");
  if (!row) {
    return;
  }

  row.querySelectorAll('input[type="text"], input[type="date"], input[type="number"]').forEach((input) => {
    input.value = "";
  });
  row.querySelectorAll("select").forEach((select) => {
    select.value = "";
  });
  row.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = false;
  });
  row.querySelectorAll("details").forEach((details) => {
    details.open = false;
  });

  updateAllFilterSummaries();
  renderDebtors(true);
}

function clearMultiFilterGroup(key) {
  const details = thead.querySelector(`[data-filter-group="${key}"]`);
  details?.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = false;
  });
  details?.removeAttribute("open");
  details?.closest("th")?.classList.remove("filter-open");
  updateFilterSummary(key);
}

function handlePaginationClick(event) {
  const button = event.target.closest("[data-page]");
  if (!button || button.disabled) {
    return;
  }

  const nextPage = Number(button.dataset.page);
  if (!Number.isFinite(nextPage) || nextPage === state.currentPage) {
    return;
  }

  state.currentPage = nextPage;
  renderDebtors();
}

function renderPaginationMeta(totalItems, totalPages, startIndex, pageLength) {
  if (!paginationBar || !paginationSummary || !paginationControls) {
    return;
  }

  if (!totalItems) {
    paginationBar.classList.add("hidden");
    paginationSummary.textContent = "";
    paginationControls.innerHTML = "";
    return;
  }

  const from = startIndex + 1;
  const to = startIndex + pageLength;
  paginationBar.classList.remove("hidden");
  paginationSummary.textContent = t("shownOf", { from, to, total: totalItems });
  paginationControls.innerHTML = buildPaginationButtons(totalPages);
}

function buildPaginationButtons(totalPages) {
  if (totalPages <= 1) {
    return `
      <button class="secondary-button compact-button pagination-button is-active" type="button" disabled>
        1
      </button>
    `;
  }

  const pages = new Set([1, totalPages, state.currentPage - 1, state.currentPage, state.currentPage + 1]);
  const visiblePages = [...pages]
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((left, right) => left - right);

  const fragments = [
    `
      <button
        class="secondary-button compact-button pagination-button ${state.currentPage === 1 ? "is-disabled" : ""}"
        type="button"
        data-page="${Math.max(1, state.currentPage - 1)}"
        ${state.currentPage === 1 ? "disabled" : ""}
      >
        ${t("back")}
      </button>
    `,
  ];

  let previousPage = 0;
  visiblePages.forEach((page) => {
    if (page - previousPage > 1) {
      fragments.push('<span class="pagination-ellipsis">…</span>');
    }

    fragments.push(`
      <button
        class="secondary-button compact-button pagination-button ${page === state.currentPage ? "is-active" : ""}"
        type="button"
        data-page="${page}"
      >
        ${page}
      </button>
    `);
    previousPage = page;
  });

  fragments.push(`
    <button
      class="secondary-button compact-button pagination-button ${state.currentPage === totalPages ? "is-disabled" : ""}"
      type="button"
      data-page="${Math.min(totalPages, state.currentPage + 1)}"
      ${state.currentPage === totalPages ? "disabled" : ""}
    >
      ${t("forward")}
    </button>
  `);

  return fragments.join("");
}

function saveViewState() {
  try {
    const payload = {
      currentPage: state.currentPage,
      filters: collectFilterControlState(),
    };
    window.localStorage.setItem(getViewStateStorageKey(), JSON.stringify(payload));
  } catch (error) {
    console.warn("Не удалось сохранить состояние таблицы.", error);
  }
}

function restoreViewState() {
  try {
    const raw = window.localStorage.getItem(getViewStateStorageKey());
    if (!raw) {
      return;
    }

    const parsed = JSON.parse(raw);
    if (Number.isFinite(Number(parsed?.currentPage))) {
      state.currentPage = Math.max(1, Number(parsed.currentPage));
    }
    applyFilterControlState(parsed?.filters ?? {});
    updateAllFilterSummaries();
  } catch (error) {
    console.warn("Не удалось восстановить состояние таблицы.", error);
  }
}

function collectFilterControlState() {
  const snapshot = {};

  FILTER_COLUMNS.forEach((column) => {
    if (column.type === "reset" || column.type === "empty") {
      return;
    }

    if (column.type === "date-range" || column.type === "number-range") {
      const fromInput = thead.querySelector(`[data-filter-key="${column.key}"][data-bound="from"]`);
      const toInput = thead.querySelector(`[data-filter-key="${column.key}"][data-bound="to"]`);
      snapshot[column.key] = {
        from: fromInput?.value ?? "",
        to: toInput?.value ?? "",
      };
      return;
    }

    if (column.type === "multi-select") {
      snapshot[column.key] = [...thead.querySelectorAll(`input[type="checkbox"][data-filter-key="${column.key}"]:checked`)]
        .map((checkbox) => checkbox.value);
      return;
    }

    const control = thead.querySelector(`[data-filter-key="${column.key}"]`);
    snapshot[column.key] = control?.value ?? "";
  });

  return snapshot;
}

function applyFilterControlState(snapshot) {
  FILTER_COLUMNS.forEach((column) => {
    if (column.type === "reset" || column.type === "empty") {
      return;
    }

    const savedValue = snapshot?.[column.key];

    if (column.type === "date-range" || column.type === "number-range") {
      const fromInput = thead.querySelector(`[data-filter-key="${column.key}"][data-bound="from"]`);
      const toInput = thead.querySelector(`[data-filter-key="${column.key}"][data-bound="to"]`);
      if (fromInput) {
        fromInput.value = savedValue?.from ?? "";
      }
      if (toInput) {
        toInput.value = savedValue?.to ?? "";
      }
      return;
    }

    if (column.type === "multi-select") {
      const selectedValues = Array.isArray(savedValue) ? new Set(savedValue) : new Set();
      thead.querySelectorAll(`input[type="checkbox"][data-filter-key="${column.key}"]`).forEach((checkbox) => {
        checkbox.checked = selectedValues.has(checkbox.value);
      });
      return;
    }

    const control = thead.querySelector(`[data-filter-key="${column.key}"]`);
    if (control) {
      control.value = typeof savedValue === "string" ? savedValue : "";
    }
  });
}

function closeAllFilterDropdowns(exceptDetails = null) {
  thead.querySelectorAll(".filter-multi").forEach((details) => {
    if (details === exceptDetails) {
      return;
    }
    details.open = false;
    details.closest("th")?.classList.remove("filter-open");
  });
}

function updateAllFilterSummaries() {
  thead.querySelectorAll("[data-filter-group]").forEach((details) => {
    updateFilterSummary(details.dataset.filterGroup);
  });
}

function updateActiveFilters(filters) {
  if (!activeFiltersBlock || !activeFiltersList) {
    return;
  }

  const chips = buildActiveFilterChips(filters);
  if (!chips.length) {
    activeFiltersList.innerHTML = "";
    activeFiltersBlock.classList.add("hidden");
    return;
  }

  activeFiltersList.innerHTML = chips.join("");
  activeFiltersBlock.classList.remove("hidden");
}

function buildActiveFilterChips(filters) {
  const chips = [];

  for (const [key, value] of Object.entries(filters)) {
    const label = getFilterLabel(key);
    const column = FILTER_COLUMNS.find((item) => item.key === key);

    if (Array.isArray(value)) {
      value.forEach((item) => {
        chips.push(
          renderActiveFilterChip({
            label,
            value: item === "__" ? "-" : translateFilterOption(key, item),
            key,
            mode: column?.type === "token-suggest" ? "token" : "array",
            item,
          }),
        );
      });
      continue;
    }

    if (value && typeof value === "object") {
      if (value.from !== null) {
        chips.push(
          renderActiveFilterChip({
            label,
            value: `${t("fromShort")} ${formatFilterValue(key, value.from)}`,
            key,
            mode: "range",
            bound: "from",
          }),
        );
      }
      if (value.to !== null) {
        chips.push(
          renderActiveFilterChip({
            label,
            value: `${t("toShort")} ${formatFilterValue(key, value.to)}`,
            key,
            mode: "range",
            bound: "to",
          }),
        );
      }
      continue;
    }

    if (typeof value === "boolean") {
      chips.push(
        renderActiveFilterChip({
          label,
          value: value ? t("yes") : t("no"),
          key,
          mode: "single",
        }),
      );
      continue;
    }

    if (typeof value === "string" && value !== "") {
      chips.push(
        renderActiveFilterChip({
          label,
          value,
          key,
          mode: "single",
        }),
      );
    }
  }

  return chips;
}

function renderActiveFilterChip({ label, value, key, mode, item = "", bound = "" }) {
  return `
    <button
      class="active-filter-chip"
      type="button"
      data-active-filter-remove="true"
      data-filter-key="${escapeHtmlAttribute(key)}"
      data-filter-mode="${escapeHtmlAttribute(mode)}"
      data-filter-item="${escapeHtmlAttribute(item)}"
      data-filter-bound="${escapeHtmlAttribute(bound)}"
      title="${escapeHtmlAttribute(t("removeFilter"))}"
    >
      <span class="active-filter-chip-text">${escapeHtml(label)}: ${escapeHtml(String(value))}</span>
      <span class="active-filter-chip-close" aria-hidden="true">×</span>
    </button>
  `;
}

function formatFilterValue(key, value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  const column = FILTER_COLUMNS.find((item) => item.key === key);
  if (column?.type === "date-range") {
    return formatDisplayDate(value) ?? String(value);
  }
  if (column?.type === "number-range") {
    return formatMoney(value);
  }
  return String(value);
}

function removeActiveFilter({ filterKey, filterMode, filterItem, filterBound }) {
  if (!filterKey) {
    return;
  }

  if (filterMode === "range") {
    const input = thead.querySelector(`[data-filter-key="${filterKey}"][data-bound="${filterBound}"]`);
    if (input) {
      input.value = "";
    }
    return;
  }

  if (filterMode === "array") {
    const checkbox = thead.querySelector(
      `input[type="checkbox"][data-filter-key="${filterKey}"][value="${cssEscape(filterItem)}"]`,
    );
    if (checkbox) {
      checkbox.checked = false;
      updateFilterSummary(filterKey);
    }
    return;
  }

  if (filterMode === "token") {
    const control = thead.querySelector(`[data-filter-key="${filterKey}"]`);
    if (control) {
      const nextValue = String(control.value ?? "")
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item && item.toLowerCase() !== String(filterItem).toLowerCase())
        .join(", ");
      control.value = nextValue;
    }
    return;
  }

  const control = thead.querySelector(`[data-filter-key="${filterKey}"]`);
  if (!control) {
    return;
  }

  control.value = "";
}

function updateFilterSummary(key) {
  const summary = thead.querySelector(`[data-filter-summary="${key}"]`);
  const group = thead.querySelector(`[data-filter-group="${key}"]`);
  if (!summary || !group) {
    return;
  }

  const checked = [...group.querySelectorAll('input[type="checkbox"]:checked')].map((checkbox) => checkbox.value);
  if (!checked.length) {
    const column = FILTER_COLUMNS.find((item) => item.key === key);
    summary.textContent = getFilterPlaceholder(column ?? { key });
    return;
  }

  if (checked.length === 1) {
    summary.textContent = checked[0] === "__" ? "-" : translateFilterOption(key, checked[0]);
    return;
  }

  summary.textContent = t("selectedCount", { count: checked.length });
}

function renderSingleRow(debtor) {
  return `
    <tr data-row-id="${debtor.id}" class="main-row">
      ${renderActionCell(debtor)}
      ${renderSharedStartCells(debtor)}
      ${renderCategoryCell(debtor)}
      ${renderSharedIdentityCells(debtor)}
      ${renderClaimCells(debtor)}
      ${renderSharedFinancialCells(debtor)}
      ${renderLawsuitAndDecisionCells(debtor)}
      ${renderCaseCells(debtor)}
      ${renderSharedCaseCourtCell(debtor)}
      ${renderDocumentCells(debtor)}
      ${renderDeleteCell(debtor)}
    </tr>
  `;
}

function renderNestedPair(parent, child) {
  return `
    <tr data-row-id="${parent.id}" class="main-row parent-branch">
      ${renderActionCell(parent)}
      ${renderSharedStartCells(parent, true)}
      ${renderCategoryCell(parent)}
      ${renderSharedIdentityCells(parent, true)}
      ${renderClaimCells(parent)}
      ${renderSharedFinancialCells(parent, true)}
      ${renderLawsuitAndDecisionCells(parent)}
      ${renderCaseCells(parent)}
      ${renderSharedCaseCourtCell(parent, true)}
      ${renderDocumentCells(parent)}
      ${renderDeleteCell(parent, true)}
    </tr>
    <tr data-row-id="${child.id}" class="child-row">
      <td class="indent-cell sticky-col sticky-action-col"></td>
      ${renderCategoryCell(child)}
      ${renderClaimCells(child)}
      ${renderLawsuitAndDecisionCells(child, { isChild: true })}
      ${renderCaseCells(child)}
      ${renderDocumentCells(child)}
    </tr>
  `;
}

function renderActionCell(debtor, isRowSpan = false) {
  const rowSpan = isRowSpan ? ' rowspan="2"' : "";
  return `
    <td class="action-cell sticky-col sticky-action-col"${rowSpan}>
      <button class="secondary-button compact-button edit-row-button" type="button" data-id="${debtor.id}">
        Ред.
      </button>
    </td>
  `;
}

function renderDeleteCell(debtor, isRowSpan = false) {
  const rowSpan = isRowSpan ? ' rowspan="2"' : "";
  const extraClass = isRowSpan ? " branch-shared-cell" : "";
  return `
    <td class="delete-cell${extraClass}"${rowSpan}>
      <button class="danger-button compact-button delete-row-button" type="button" data-id="${debtor.id}">
        Удалить
      </button>
    </td>
  `;
}

function renderSharedStartCells(debtor, isRowSpan = false, sharedStyle = "") {
  const rowSpan = isRowSpan ? ' rowspan="2"' : "";
  const extraClass = isRowSpan ? " branch-shared-cell" : "";
  return `
    <td${rowSpan} class="sticky-col sticky-entry-col${extraClass}"${sharedStyle}>${escapeHtml(debtor.entry_date)}</td>
    <td${rowSpan} class="sticky-col sticky-contract-col${extraClass}"${sharedStyle}>${renderPlain(debtor.contract_date)}</td>
  `;
}

function renderCategoryCell(debtor) {
  return `<td class="sticky-col sticky-category-col">${renderCategorySelect(debtor)}</td>`;
}

function renderSharedIdentityCells(debtor, isRowSpan = false, sharedStyle = "") {
  const rowSpan = isRowSpan ? ' rowspan="2"' : "";
  const branchClass = isRowSpan ? " branch-shared-cell" : "";
  return `
    <td${rowSpan} class="shared-text client-cell${branchClass}"${sharedStyle}>${escapeHtml(debtor.client_name)}</td>
    <td${rowSpan}${isRowSpan ? ' class="branch-shared-cell"' : ""}${sharedStyle}>${escapeHtml(debtor.contract_number)}</td>
    <td${rowSpan}${isRowSpan ? ' class="branch-shared-cell"' : ""}${sharedStyle}>${renderPlain(debtor.last_missed_payment_date)}</td>
    <td${rowSpan} class="shared-text${branchClass}"${sharedStyle}>${escapeHtml(debtor.company)}</td>
    <td${rowSpan} class="city-cell${branchClass}"${sharedStyle}>${escapeHtml(debtor.city)}</td>
    <td${rowSpan} class="shared-text${branchClass}"${sharedStyle}>${escapeHtml(debtor.court)}</td>
  `;
}

function renderClaimCells(debtor) {
  return `
    <td>${renderBooleanSelect(debtor, "claim_sent")}</td>
    <td>${renderDateInput(debtor, "claim_sent_date", debtor.claim_sent_date_iso)}</td>
    <td>${renderClaimDays(debtor.claim_sent_days)}</td>
  `;
}

function renderSharedFinancialCells(debtor, isRowSpan = false, sharedStyle = "") {
  const rowSpan = isRowSpan ? ' rowspan="2"' : "";
  const extraClass = isRowSpan ? ' class="branch-shared-cell"' : "";
  return `
    <td${rowSpan}${extraClass}${sharedStyle}>${renderPlain(debtor.debt_days)}</td>
    <td${rowSpan}${extraClass}${sharedStyle}>${formatMoney(debtor.debt_amount)}</td>
    <td${rowSpan}${extraClass}${sharedStyle}>${formatMoney(debtor.penalty_amount)}</td>
    <td${rowSpan}${extraClass}${sharedStyle}>${formatMoney(debtor.state_duty_amount)}</td>
    <td${rowSpan}${extraClass}${sharedStyle}>${formatMoney(debtor.total_amount)}</td>
  `;
}

function renderLawsuitAndDecisionCells(debtor, { isChild = false } = {}) {
  return `
    <td>${renderBooleanSelect(debtor, "lawsuit_sent")}</td>
    <td>${renderDateInput(debtor, "lawsuit_sent_date", debtor.lawsuit_sent_date_iso)}</td>
    <td>${renderBooleanSelect(debtor, "lawsuit_accepted")}</td>
    <td>${renderDateInput(
      debtor,
      "hearing_date",
      debtor.hearing_date_iso,
      !debtor.lawsuit_accepted,
    )}</td>
    <td class="${debtor.is_hearing_overdue_without_decision ? "decision-alert" : ""}">
      ${renderBooleanSelect(debtor, "decision_exists")}
    </td>
    <td class="decision-cell">${renderDecisionSelect(debtor, { isChild })}</td>
    <td>${renderNumberInput(debtor, "decision_payout", debtor.decision_payout, !debtor.decision_exists)}</td>
  `;
}

function renderCaseCells(debtor) {
  return `
    <td>${renderNumberInput(debtor, "received_amount", debtor.received_amount)}</td>
    <td class="cell-comment">${renderTextarea(debtor, "comment")}</td>
    <td>${renderTextInput(debtor, "case_number")}</td>
  `;
}

function renderSharedCaseCourtCell(debtor, isRowSpan = false, sharedStyle = "") {
  const rowSpan = isRowSpan ? ' rowspan="2"' : "";
  const branchClass = isRowSpan ? " branch-shared-cell" : "";
  return `<td${rowSpan} class="shared-text${branchClass}"${sharedStyle}>${escapeHtml(debtor.case_court)}</td>`;
}

function renderDocumentCells(debtor) {
  return `
    <td class="document-cell">
      <button class="secondary-button compact-button document-button claim-document-button" type="button" data-id="${debtor.id}">
        PDF
      </button>
    </td>
    <td class="document-cell">
      <button
        class="secondary-button compact-button document-button document-button-disabled"
        type="button"
        disabled
        title="Модуль генерации иска будет добавлен следующим этапом"
      >
        Скоро
      </button>
    </td>
  `;
}

function renderCategorySelect(debtor) {
  const style = buildCategorySelectStyle(debtor.category);
  const options = debtor.category_options
    .map(
      (category) =>
        `<option value="${escapeHtmlAttribute(category)}" ${
          debtor.category === category ? "selected" : ""
        }>${escapeHtml(category)}</option>`,
    )
    .join("");

  return `
    <select
      class="cell-editor cell-select cell-category"
      data-inline-field="category"
      data-id="${debtor.id}"
      ${style}
    >
      ${options}
    </select>
  `;
}

function renderDecisionSelect(debtor, { isChild = false } = {}) {
  const blank = '<option value="">—</option>';
  const decisions = isChild
    ? state.referenceData.decisions.filter((decision) => decision !== "Возврат иска")
    : state.referenceData.decisions;
  const style = buildDecisionSelectStyle(debtor.decision);

  const options = decisions
    .map(
      (decision) =>
        `<option value="${escapeHtmlAttribute(decision)}" ${
          debtor.decision === decision ? "selected" : ""
        }>${escapeHtml(decision)}</option>`,
    )
    .join("");

  return `
    <select
      class="cell-editor cell-select cell-decision"
      data-inline-field="decision"
      data-id="${debtor.id}"
      ${!debtor.decision_exists ? "disabled" : ""}
      ${style}
    >
      ${blank}${options}
    </select>
  `;
}

function renderBooleanSelect(debtor, field) {
  const isPositive = Boolean(debtor[field]);
  const yesSelected = isPositive ? "selected" : "";
  const noSelected = !isPositive ? "selected" : "";
  const toneClass = isPositive ? "cell-bool-yes" : "cell-bool-no";
  const yesDisabled = isYesOptionDisabled(debtor, field) ? "disabled" : "";

  return `
    <select
      class="cell-editor cell-select ${toneClass}"
      data-inline-field="${field}"
      data-id="${debtor.id}"
    >
      <option value="true" ${yesSelected} ${yesDisabled}>Да</option>
      <option value="false" ${noSelected}>Нет</option>
    </select>
  `;
}

function renderDateInput(debtor, field, value, disabled = false) {
  return `
    <input
      class="cell-editor cell-date date-input"
      data-date-input="true"
      data-inline-field="${field}"
      data-id="${debtor.id}"
      type="text"
      value="${escapeHtmlAttribute(formatDisplayDate(value) ?? "")}"
      placeholder="дд.мм.гггг"
      autocomplete="off"
      ${disabled ? "disabled" : ""}
    />
  `;
}

function renderNumberInput(debtor, field, value, disabled = false) {
  return `
    <input
      class="cell-editor cell-number"
      data-inline-field="${field}"
      data-id="${debtor.id}"
      type="number"
      min="0"
      step="0.01"
      value="${Number(value || 0)}"
      ${disabled ? "disabled" : ""}
    />
  `;
}

function renderTextInput(debtor, field) {
  return `
    <input
      class="cell-editor cell-text"
      data-inline-field="${field}"
      data-id="${debtor.id}"
      type="text"
      value="${escapeHtmlAttribute(debtor[field] ?? "")}"
    />
  `;
}

function renderTextarea(debtor, field) {
  return `
    <textarea
      class="cell-editor cell-textarea"
      data-inline-field="${field}"
      data-id="${debtor.id}"
      rows="3"
    >${escapeHtml(debtor[field] ?? "")}</textarea>
  `;
}

function handleTableClick(event) {
  const claimButton = event.target.closest(".claim-document-button");
  if (claimButton) {
    openClaimModal(Number(claimButton.dataset.id));
    return;
  }

  const editButton = event.target.closest(".edit-row-button");
  if (editButton) {
    openEditModal(Number(editButton.dataset.id));
    return;
  }

  const deleteButton = event.target.closest(".delete-row-button");
  if (deleteButton) {
    openDeleteModal(Number(deleteButton.dataset.id));
  }
}

function handleTableChange(event) {
  const element = event.target;
  if (!element.matches("[data-inline-field]")) {
    return;
  }

  if (element.matches("select")) {
    commitInlineField(element);
  }
}

function handleTableBlur(event) {
  const element = event.target;
  if (!element.matches("[data-inline-field]")) {
    return;
  }

  if (element.matches('input[type="number"], input[type="text"], textarea')) {
    commitInlineField(element);
  }
}

async function commitInlineField(element) {
  if (element.disabled) {
    return;
  }

  const debtorId = Number(element.dataset.id);
  const field = element.dataset.inlineField;
  const payload = { [field]: getInlineValue(element, field) };

  element.disabled = true;
  const response = await fetch(`/api/debtors/${debtorId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    alert(t("saveChangeFailed"));
    element.disabled = false;
    await loadDebtors();
    return;
  }

  await loadDebtors();
}

function getInlineValue(element, field) {
  if (element.matches("select")) {
    if (["claim_sent", "lawsuit_sent", "lawsuit_accepted", "decision_exists"].includes(field)) {
      return element.value === "true";
    }
    return element.value || null;
  }

  if (element.matches(".date-input")) {
    return getDateInputIsoValue(element);
  }

  if (element.matches('input[type="number"]')) {
    return element.value === "" ? 0 : Number(element.value);
  }

  return element.value.trim() || null;
}

function openCreateModal() {
  state.modalMode = "create";
  modalEyebrow.textContent = t("newRecord");
  modalTitle.textContent = t("addDebtorTitle");
  submitButton.textContent = t("save");
  debtorForm.reset();
  debtorForm.debtor_id.value = "";

  debtorForm.contract_total_amount.value = "";
  debtorForm.contract_advance_amount.value = "";
  clearCrmLookupStatus();
  populateModalCities();
  renderModalCourts("", null);

  modalBackdrop.classList.remove("hidden");
}

function openEditModal(debtorId) {
  const debtor = state.debtors.find((item) => item.id === debtorId);
  if (!debtor) {
    return;
  }

  state.modalMode = "edit";
  modalEyebrow.textContent = t("editRecord");
  modalTitle.textContent = t("debtorMainData");
  submitButton.textContent = t("saveChanges");

  debtorForm.debtor_id.value = debtor.id;
  debtorForm.client_name.value = debtor.client_name;
  debtorForm.contract_number.value = debtor.contract_number;
  debtorForm.company.value = debtor.company ?? "";
  debtorForm.city.value = debtor.city ?? "";
  debtorForm.mobile_phone.value = debtor.mobile_phone ?? "";
  debtorForm.home_phone.value = debtor.home_phone ?? "";
  debtorForm.address.value = debtor.address ?? "";
  debtorForm.contract_total_amount.value =
    debtor.contract_total_amount === null || debtor.contract_total_amount === undefined
      ? ""
      : Number(debtor.contract_total_amount);
  debtorForm.contract_advance_amount.value =
    debtor.contract_advance_amount === null || debtor.contract_advance_amount === undefined
      ? ""
      : Number(debtor.contract_advance_amount);
  debtorForm.last_missed_payment_date.value = formatDisplayDate(debtor.last_missed_payment_date_iso) ?? "";
  debtorForm.debt_amount.value = Number(debtor.debt_amount);
  clearCrmLookupStatus();
  populateModalCities(debtor.city, debtor.court);
  renderModalCourts(debtor.city, debtor.court);

  modalBackdrop.classList.remove("hidden");
}

function openDeleteModal(debtorId) {
  state.deleteTargetId = debtorId;
  deleteModalText.textContent =
    "Запись будет удалена без возможности восстановления. Если у нее есть вложенная подстрока возврата иска, она тоже удалится.";
  deleteModalBackdrop.classList.remove("hidden");
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
}

function closeDeleteModal() {
  state.deleteTargetId = null;
  deleteModalBackdrop.classList.add("hidden");
}

function openCourtModal() {
  courtForm.reset();

  const preselectedCourt = courtSelect.value || state.lastCreatedCourt?.name || null;
  const preselectedCity =
    citySelect.value ||
    state.lastCreatedCourt?.city ||
    state.referenceData?.courtCityMap?.[preselectedCourt] ||
    null;
  const preselectedRegion =
    state.lastCreatedCourt?.region ||
    state.referenceData?.cityRegionMap?.[preselectedCity] ||
    state.referenceData?.courtRegionMap?.[preselectedCourt] ||
    state.referenceData?.regions?.[0] ||
    null;

  populateCourtModalRegions(preselectedRegion);
  populateCourtModalCities(courtModalRegionSelect.value, preselectedCity);
  if (preselectedCity) {
    courtModalCitySelect.value = preselectedCity;
  }

  courtModalBackdrop.classList.remove("hidden");
}

function closeCourtModal() {
  courtModalBackdrop.classList.add("hidden");
}

async function handleCourtSubmit(event) {
  event.preventDefault();

  const payload = {
    country: state.currentCountry,
    name: courtForm.name.value.trim(),
    city: courtModalCitySelect.value,
    region: courtModalRegionSelect.value,
  };

  const response = await fetch("/api/courts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    alert(error?.detail || t("saveCourtFailed"));
    return;
  }

  state.lastCreatedCourt = await response.json();
  await loadReferenceData();
  populateModalCities(state.lastCreatedCourt.city, state.lastCreatedCourt.name);
  citySelect.value = state.lastCreatedCourt.city;
  renderModalCourts(state.lastCreatedCourt.city, state.lastCreatedCourt.name);
  closeCourtModal();
}

function formatClaimModalPhones(mobilePhone, homePhone) {
  const phones = [mobilePhone, homePhone]
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter((value) => value && value !== "—");
  return phones.length ? Array.from(new Set(phones)).join(", ") : "—";
}

function normalizeDocumentProducts(products) {
  const normalized = (products || [])
    .map((item) => {
      const name = typeof item?.name === "string" ? item.name.trim() : "";
      const quantity = Math.max(1, Number.parseInt(item?.quantity ?? 1, 10) || 1);
      if (!name) {
        return null;
      }
      return { name, quantity };
    })
    .filter(Boolean);
  return normalized.length ? normalized : [{ name: "Товар по договору", quantity: 1 }];
}

function createProductRowElement(product = { name: "", quantity: 1 }) {
  const row = document.createElement("div");
  row.className = "product-editor-row";
  row.innerHTML = `
    <input type="text" class="product-name-input" value="${escapeHtml(product.name || "")}" />
    <input type="number" class="product-quantity-input" min="1" step="1" value="${Number(product.quantity || 1)}" />
    <button class="secondary-button product-remove-button" type="button" aria-label="${escapeHtml(t("delete"))}">×</button>
  `;
  return row;
}

function setDocumentProducts(listElement, products) {
  if (!listElement) {
    return;
  }
  listElement.innerHTML = "";
  normalizeDocumentProducts(products).forEach((product) => {
    listElement.appendChild(createProductRowElement(product));
  });
}

function appendDocumentProductRow(listElement, product = { name: "", quantity: 1 }) {
  if (!listElement) {
    return;
  }
  listElement.appendChild(createProductRowElement(product));
}

function readDocumentProducts(listElement) {
  if (!listElement) {
    return [];
  }
  const rows = Array.from(listElement.querySelectorAll(".product-editor-row"));
  return rows
    .map((row) => {
      const name = row.querySelector(".product-name-input")?.value?.trim() || "";
      const quantityRaw = row.querySelector(".product-quantity-input")?.value;
      const quantity = Math.max(1, Number.parseInt(quantityRaw || "1", 10) || 1);
      if (!name) {
        return null;
      }
      return { name, quantity };
    })
    .filter(Boolean);
}

async function hydrateClaimModalFromCrm(debtor) {
  const contractNumber = (debtor?.contract_number || "").trim();
  if (!contractNumber || state.claimTargetId !== debtor.id) {
    return;
  }

  try {
    const response = await fetch(
      `/api/crm/debtor-prefill?contract_number=${encodeURIComponent(contractNumber)}&country=${encodeURIComponent(state.currentCountry)}`
    );
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || state.claimTargetId !== debtor.id) {
      return;
    }

    claimConfirmForm.client_name.value = payload.client_name || claimConfirmForm.client_name.value;
    claimConfirmForm.client_phone.value = formatClaimModalPhones(
      payload.mobile_phone,
      payload.home_phone
    );
    claimConfirmForm.client_address.value = payload.address || claimConfirmForm.client_address.value;
    claimConfirmForm.company_name.value = payload.company || claimConfirmForm.company_name.value;
    if (state.currentCountry === "uz") {
      claimConfirmForm.debt_amount.value = Number(payload.debt_amount || 0);
    }
    setDocumentProducts(claimProductsList, payload.products || []);
  } catch (error) {
    console.warn("Claim CRM lookup failed", error);
  }
}

async function hydrateLawsuitModalFromCrm(debtor) {
  const contractNumber = (debtor?.contract_number || "").trim();
  if (!contractNumber || state.lawsuitTargetId !== debtor.id) {
    return;
  }

  try {
    const response = await fetch(
      `/api/crm/debtor-prefill?contract_number=${encodeURIComponent(contractNumber)}&country=${encodeURIComponent(state.currentCountry)}`
    );
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || state.lawsuitTargetId !== debtor.id) {
      return;
    }
    if (state.currentCountry === "uz") {
      lawsuitConfirmForm.debt_amount.value = Number(payload.debt_amount || 0);
      lawsuitConfirmForm.penalty_amount.value = calculateUzLawsuitPenaltyAmount(
        Number(payload.debt_amount || 0),
        Number(lawsuitConfirmForm.dataset.overdueDays || 0),
      );
      recalculateLawsuitStateDuty();
    }
    setDocumentProducts(lawsuitProductsList, payload.products || []);
  } catch (error) {
    console.warn("Lawsuit CRM lookup failed", error);
  }
}

async function openClaimModal(debtorId) {
  const debtor = state.debtors.find((item) => item.id === debtorId);
  if (!debtor) {
    return;
  }

  state.claimTargetId = debtorId;
  claimConfirmForm.debtor_id.value = debtorId;
  claimConfirmForm.client_name.value = debtor.client_name ?? "";
  claimConfirmForm.client_phone.value = formatClaimModalPhones(
    debtor.mobile_phone,
    debtor.home_phone
  );
  claimConfirmForm.client_address.value = debtor.address ?? "";
  claimConfirmForm.company_name.value = debtor.company ?? "";
  claimConfirmForm.contract_number.value = debtor.contract_number ?? "";
  claimConfirmForm.debt_amount.value = Number(debtor.debt_amount || 0);
  setDocumentProducts(claimProductsList, [{ name: "Товар по договору", quantity: 1 }]);
  claimModalBackdrop.classList.remove("hidden");
  await hydrateClaimModalFromCrm(debtor);
}

function closeClaimModal() {
  state.claimTargetId = null;
  claimConfirmForm.reset();
  if (claimProductsList) {
    claimProductsList.innerHTML = "";
  }
  claimModalBackdrop.classList.add("hidden");
}

async function handleClaimConfirmSubmit(event) {
  event.preventDefault();
  if (state.claimTargetId === null) {
    return;
  }

  const payload = {
    debt_amount_override:
      claimConfirmForm.debt_amount.value === "" ? 0 : Number(claimConfirmForm.debt_amount.value),
    product_overrides: readDocumentProducts(claimProductsList),
  };

  const previewWindow = window.open("", "_blank");

  const response = await fetch(`/api/debtors/${state.claimTargetId}/claim-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    if (previewWindow) {
      previewWindow.close();
    }
    let message = t("generateClaimFailed");
    try {
      const data = await response.json();
      if (data?.detail) {
        message = data.detail;
      }
    } catch (error) {
      console.warn(t("readClaimErrorFailed"), error);
    }
    alert(message);
    return;
  }

  const blob = await response.blob();
  const fileUrl = window.URL.createObjectURL(blob);
  if (previewWindow) {
    previewWindow.location.href = fileUrl;
  } else {
    window.open(fileUrl, "_blank", "noopener");
  }
  window.setTimeout(() => window.URL.revokeObjectURL(fileUrl), 60_000);
  closeClaimModal();
}

function renderDocumentCells(debtor) {
  return `
    <td class="document-cell">
      <button class="secondary-button compact-button document-button claim-document-button" type="button" data-id="${debtor.id}">
        PDF
      </button>
    </td>
    <td class="document-cell">
      <button class="secondary-button compact-button document-button lawsuit-document-button" type="button" data-id="${debtor.id}">
        PDF
      </button>
    </td>
  `;
}

function handleTableClick(event) {
  const claimButton = event.target.closest(".claim-document-button");
  if (claimButton) {
    openClaimModal(Number(claimButton.dataset.id));
    return;
  }

  const lawsuitButton = event.target.closest(".lawsuit-document-button");
  if (lawsuitButton) {
    openLawsuitModal(Number(lawsuitButton.dataset.id));
    return;
  }

  const editButton = event.target.closest(".edit-row-button");
  if (editButton) {
    openEditModal(Number(editButton.dataset.id));
    return;
  }

  const deleteButton = event.target.closest(".delete-row-button");
  if (deleteButton) {
    openDeleteModal(Number(deleteButton.dataset.id));
  }
}

function openLawsuitModal(debtorId) {
  const debtor = state.debtors.find((item) => item.id === debtorId);
  if (!debtor) {
    return;
  }

  state.lawsuitTargetId = debtorId;
  lawsuitConfirmForm.debtor_id.value = debtorId;
  lawsuitConfirmForm.client_name.value = debtor.client_name ?? "";
  lawsuitConfirmForm.company_name.value = debtor.company ?? "";
  lawsuitConfirmForm.contract_number.value = debtor.contract_number ?? "";
  lawsuitConfirmForm.contract_date.value = formatDisplayDate(debtor.contract_date_iso) ?? debtor.contract_date ?? "";
  lawsuitConfirmForm.court_name.value = debtor.case_court || debtor.court || "";
  lawsuitConfirmForm.debt_amount.value = Number(debtor.debt_amount || 0);
  lawsuitConfirmForm.dataset.overdueDays = String(Number(debtor.debt_days || 0));
  lawsuitConfirmForm.penalty_amount.value =
    state.currentCountry === "uz"
      ? calculateUzLawsuitPenaltyAmount(Number(debtor.debt_amount || 0), Number(debtor.debt_days || 0))
      : Number(debtor.penalty_amount || 0);
  lawsuitConfirmForm.state_duty_amount.value = calculateLawsuitStateDutyAmount(
    Number(debtor.debt_amount || 0),
    Number(lawsuitConfirmForm.penalty_amount.value || 0),
  );
  setDateInputValue(lawsuitConfirmForm.installment_from, debtor.lawsuit_installment_from || "");
  setDateInputValue(lawsuitConfirmForm.installment_to, debtor.lawsuit_installment_to || "");
  lawsuitConfirmForm.first_period_paid_amount.value = Number(debtor.lawsuit_first_period_paid_amount || 0);
  setDocumentProducts(lawsuitProductsList, [{ name: "Товар по договору", quantity: 1 }]);

  const totalAmount = Number(debtor.contract_total_amount || 0);
  const advanceAmount = Number(debtor.contract_advance_amount || 0);
  const balanceAmount = Math.max(totalAmount - advanceAmount, 0);
  lawsuitConfirmForm.monthly_payment_amount.value =
    debtor.lawsuit_monthly_payment_amount
      ? Number(debtor.lawsuit_monthly_payment_amount)
      : balanceAmount > 0
        ? roundToTwo(balanceAmount / 12)
        : "";

  lawsuitModalBackdrop.classList.remove("hidden");
  hydrateLawsuitModalFromCrm(debtor);
}

function recalculateLawsuitStateDuty() {
  if (!lawsuitConfirmForm) {
    return;
  }
  const debtAmount = Number(lawsuitConfirmForm.debt_amount.value || 0);
  const penaltyAmount =
    state.currentCountry === "uz"
      ? calculateUzLawsuitPenaltyAmount(debtAmount, Number(lawsuitConfirmForm.dataset.overdueDays || 0))
      : Number(lawsuitConfirmForm.penalty_amount.value || 0);
  if (state.currentCountry === "uz") {
    lawsuitConfirmForm.penalty_amount.value = penaltyAmount;
  }
  lawsuitConfirmForm.state_duty_amount.value = calculateLawsuitStateDutyAmount(debtAmount, penaltyAmount);
}

function hideAutoCalculatedLawsuitFields() {
  if (!lawsuitConfirmForm) {
    return;
  }

  const penaltyLabel = lawsuitConfirmForm.penalty_amount?.closest("label");
  const stateDutyLabel = lawsuitConfirmForm.state_duty_amount?.closest("label");

  if (penaltyLabel) {
    penaltyLabel.classList.add("hidden");
  }
  if (stateDutyLabel) {
    stateDutyLabel.classList.add("hidden");
  }

  if (lawsuitConfirmForm.penalty_amount) {
    lawsuitConfirmForm.penalty_amount.required = false;
    lawsuitConfirmForm.penalty_amount.type = "hidden";
  }
  if (lawsuitConfirmForm.state_duty_amount) {
    lawsuitConfirmForm.state_duty_amount.required = false;
    lawsuitConfirmForm.state_duty_amount.type = "hidden";
  }
}

function calculateLawsuitStateDutyAmount(debtAmount, penaltyAmount) {
  const claimPrice = roundToTwo((Number(debtAmount || 0) + Number(penaltyAmount || 0)));
  if (state.currentCountry === "uz") {
    return Math.max(roundToTwo(claimPrice * 0.04), 412000);
  }
  return roundToTwo(claimPrice * 0.03);
}

function calculateUzLawsuitPenaltyAmount(debtAmount, overdueDays) {
  return roundToTwo(Number(debtAmount || 0) * Number(overdueDays || 0) * 0.001);
}

function validateLawsuitForm() {
  const missingFields = [];
  const courtName = lawsuitConfirmForm.court_name.value.trim();
  const installmentFrom = getDateInputIsoValue(lawsuitConfirmForm.installment_from);
  const installmentTo = getDateInputIsoValue(lawsuitConfirmForm.installment_to);
  const debtAmount = Number(lawsuitConfirmForm.debt_amount.value || 0);
  const penaltyAmount =
    state.currentCountry === "uz"
      ? calculateUzLawsuitPenaltyAmount(debtAmount, Number(lawsuitConfirmForm.dataset.overdueDays || 0))
      : Number(lawsuitConfirmForm.penalty_amount.value || 0);
  const monthlyPaymentAmount = Number(lawsuitConfirmForm.monthly_payment_amount.value || 0);
  const firstPeriodPaidAmount = Number(lawsuitConfirmForm.first_period_paid_amount.value || 0);
  const debtor = state.debtors.find((item) => item.id === state.lawsuitTargetId);
  const fallbackInstallmentFrom = debtor?.contract_date_iso || new Date().toISOString().slice(0, 10);
  const fallbackInstallmentTo = debtor?.claim_sent_date_iso || fallbackInstallmentFrom;

  if (!courtName) {
    missingFields.push(t("fieldCourtName"));
  }
  if (state.currentCountry !== "uz" && !installmentFrom) {
    missingFields.push(t("fieldInstallmentFrom"));
  }
  if (state.currentCountry !== "uz" && !installmentTo) {
    missingFields.push(t("fieldInstallmentTo"));
  }
  if (!(debtAmount >= 0)) {
    missingFields.push(t("fieldDebtAmount"));
  }
  if (state.currentCountry !== "uz" && !(monthlyPaymentAmount > 0)) {
    missingFields.push(t("fieldMonthlyPayment"));
  }
  if (state.currentCountry !== "uz" && !(firstPeriodPaidAmount >= 0)) {
    missingFields.push(t("fieldFirstPeriodPaid"));
  }
  if (state.currentCountry !== "uz" && installmentFrom && installmentTo && installmentTo <= installmentFrom) {
    alert(t("installmentEndAfterStart"));
    return null;
  }
  if (missingFields.length) {
    alert(t("fillFields", { fields: missingFields.join(", ") }));
    return null;
  }

  return {
    court_name: courtName,
    debt_amount: debtAmount,
    penalty_amount: penaltyAmount,
    state_duty_amount: Number(lawsuitConfirmForm.state_duty_amount.value || 0),
    installment_from: state.currentCountry === "uz" ? fallbackInstallmentFrom : installmentFrom,
    installment_to: state.currentCountry === "uz" ? fallbackInstallmentTo : installmentTo,
    monthly_payment_amount: state.currentCountry === "uz" ? 1 : monthlyPaymentAmount,
    first_period_paid_amount: state.currentCountry === "uz" ? 0 : firstPeriodPaidAmount,
    product_overrides: readDocumentProducts(lawsuitProductsList),
  };
}

function closeLawsuitModal() {
  state.lawsuitTargetId = null;
  lawsuitConfirmForm.reset();
  if (lawsuitProductsList) {
    lawsuitProductsList.innerHTML = "";
  }
  lawsuitModalBackdrop.classList.add("hidden");
}

async function handleLawsuitConfirmSubmit(event) {
  event.preventDefault();
  if (state.lawsuitTargetId === null) {
    return;
  }

  const payload = validateLawsuitForm();
  if (!payload) {
    return;
  }

  const previewWindow = window.open("", "_blank");
  const response = await fetch(`/api/debtors/${state.lawsuitTargetId}/lawsuit-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    if (previewWindow) {
      previewWindow.close();
    }
    let message = t("generateLawsuitFailed");
    try {
      const data = await response.json();
      if (data?.detail) {
        message = data.detail;
      }
    } catch (error) {
      console.warn(t("readLawsuitErrorFailed"), error);
    }
    alert(message);
    return;
  }

  const blob = await response.blob();
  const fileUrl = window.URL.createObjectURL(blob);
  if (previewWindow) {
    previewWindow.location.href = fileUrl;
  } else {
    window.open(fileUrl, "_blank", "noopener");
  }
  window.setTimeout(() => window.URL.revokeObjectURL(fileUrl), 60_000);
  closeLawsuitModal();
}

async function confirmDelete() {
  if (state.deleteTargetId === null) {
    return;
  }

  const response = await fetch(`/api/debtors/${state.deleteTargetId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    alert(t("deleteFailed"));
    return;
  }

  closeDeleteModal();
  await loadDebtors();
}

function readFilters() {
  return {
    entry_date: readRangeFilter("entry_date"),
    contract_date: readRangeFilter("contract_date"),
    category: readMultiFilter("category"),
    client_name: readTextFilter("client_name"),
    contract_number: readTextFilter("contract_number"),
    last_missed_payment_date: readRangeFilter("last_missed_payment_date"),
    company: readMultiFilter("company"),
    city: readTokenFilter("city"),
    court: readTokenFilter("court"),
    claim_sent: readBooleanFilter("claim_sent"),
    claim_sent_date: readRangeFilter("claim_sent_date"),
    claim_sent_days: readRangeFilter("claim_sent_days", "number"),
    debt_days: readRangeFilter("debt_days", "number"),
    debt_amount: readRangeFilter("debt_amount", "number"),
    penalty_amount: readRangeFilter("penalty_amount", "number"),
    state_duty_amount: readRangeFilter("state_duty_amount", "number"),
    total_amount: readRangeFilter("total_amount", "number"),
    lawsuit_sent: readBooleanFilter("lawsuit_sent"),
    lawsuit_sent_date: readRangeFilter("lawsuit_sent_date"),
    lawsuit_accepted: readBooleanFilter("lawsuit_accepted"),
    hearing_date: readRangeFilter("hearing_date"),
    decision_exists: readBooleanFilter("decision_exists"),
    decision: readMultiFilter("decision"),
    decision_payout: readRangeFilter("decision_payout", "number"),
    received_amount: readRangeFilter("received_amount", "number"),
    comment: readTextFilter("comment"),
    case_number: readTextFilter("case_number"),
    case_court: readTokenFilter("case_court"),
  };
}

function readRangeFilter(key, valueType = "date") {
  const fromInput = thead.querySelector(`[data-filter-key="${key}"][data-bound="from"]`);
  const toInput = thead.querySelector(`[data-filter-key="${key}"][data-bound="to"]`);
  if (!fromInput || !toInput) {
    return { from: null, to: null };
  }

  if (valueType === "number") {
    return {
      from: fromInput.value === "" ? null : Number(fromInput.value),
      to: toInput.value === "" ? null : Number(toInput.value),
    };
  }

  return {
    from: parseDisplayDateValue(fromInput.value),
    to: parseDisplayDateValue(toInput.value),
  };
}

function readTextFilter(key) {
  return thead.querySelector(`[data-filter-key="${key}"]`)?.value.trim() ?? "";
}

function readBooleanFilter(key) {
  const value = thead.querySelector(`[data-filter-key="${key}"]`)?.value ?? "";
  return value === "" ? null : value === "true";
}

function readMultiFilter(key) {
  return [...thead.querySelectorAll(`input[type="checkbox"][data-filter-key="${key}"]:checked`)].map(
    (checkbox) => checkbox.value,
  );
}

function readTokenFilter(key) {
  const rawValue = thead.querySelector(`[data-filter-key="${key}"]`)?.value ?? "";
  return rawValue
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
}

function branchMatchesFilters(parent, child, filters) {
  if (!hasActiveFilters(filters)) {
    return true;
  }

  if (matchesDebtorFilters(parent, filters)) {
    return true;
  }

  return Boolean(child && matchesDebtorFilters(child, filters));
}

function matchesDebtorFilters(debtor, filters) {
  return (
    matchesDateRange(debtor.entry_date_iso, filters.entry_date) &&
    matchesDateRange(toIsoDateString(debtor.contract_date), filters.contract_date) &&
    matchesMultiValue(debtor.category, filters.category) &&
    matchesWordParts(debtor.client_name, filters.client_name) &&
    matchesSubstring(debtor.contract_number, filters.contract_number) &&
    matchesDateRange(debtor.last_missed_payment_date_iso, filters.last_missed_payment_date) &&
    matchesMultiValue(debtor.company, filters.company) &&
    matchesTokenList(debtor.city, filters.city) &&
    matchesTokenList(debtor.court, filters.court) &&
    matchesBooleanValue(debtor.claim_sent, filters.claim_sent) &&
    matchesDateRange(debtor.claim_sent_date_iso, filters.claim_sent_date) &&
    matchesNumberRange(debtor.claim_sent_days, filters.claim_sent_days) &&
    matchesNumberRange(debtor.debt_days, filters.debt_days) &&
    matchesNumberRange(debtor.debt_amount, filters.debt_amount) &&
    matchesNumberRange(debtor.penalty_amount, filters.penalty_amount) &&
    matchesNumberRange(debtor.state_duty_amount, filters.state_duty_amount) &&
    matchesNumberRange(debtor.total_amount, filters.total_amount) &&
    matchesBooleanValue(debtor.lawsuit_sent, filters.lawsuit_sent) &&
    matchesDateRange(debtor.lawsuit_sent_date_iso, filters.lawsuit_sent_date) &&
    matchesBooleanValue(debtor.lawsuit_accepted, filters.lawsuit_accepted) &&
    matchesDateRange(debtor.hearing_date_iso, filters.hearing_date) &&
    matchesBooleanValue(debtor.decision_exists, filters.decision_exists) &&
    matchesMultiValue(debtor.decision, filters.decision) &&
    matchesNumberRange(debtor.decision_payout, filters.decision_payout) &&
    matchesNumberRange(debtor.received_amount, filters.received_amount) &&
    matchesSubstring(debtor.comment, filters.comment) &&
    matchesSubstring(debtor.case_number, filters.case_number) &&
    matchesTokenList(debtor.case_court, filters.case_court)
  );
}

function hasActiveFilters(filters) {
  return Object.values(filters).some((value) => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    if (value && typeof value === "object") {
      return value.from !== null || value.to !== null;
    }
    return value !== null && value !== "";
  });
}

function matchesDateRange(value, range) {
  if (!range.from && !range.to) {
    return true;
  }
  if (!value) {
    return false;
  }
  if (range.from && value < range.from) {
    return false;
  }
  if (range.to && value > range.to) {
    return false;
  }
  return true;
}

function matchesNumberRange(value, range) {
  if (range.from === null && range.to === null) {
    return true;
  }
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return false;
  }

  const numericValue = Number(value);
  if (range.from !== null && numericValue < range.from) {
    return false;
  }
  if (range.to !== null && numericValue > range.to) {
    return false;
  }
  return true;
}

function matchesBooleanValue(value, expected) {
  if (expected === null) {
    return true;
  }
  return Boolean(value) === expected;
}

function matchesMultiValue(value, selectedValues) {
  if (!selectedValues.length) {
    return true;
  }
  const normalizedValue = value ?? "";
  if (selectedValues.includes("__") && normalizedValue === "") {
    return true;
  }
  return selectedValues.includes(normalizedValue);
}

function matchesSubstring(value, query) {
  if (!query) {
    return true;
  }
  return String(value ?? "").toLowerCase().includes(query.toLowerCase());
}

function matchesWordParts(value, query) {
  if (!query) {
    return true;
  }
  const normalizedValue = String(value ?? "").toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((token) => normalizedValue.includes(token));
}

function matchesTokenList(value, tokens) {
  if (!tokens.length) {
    return true;
  }
  const normalizedValue = String(value ?? "").toLowerCase();
  return tokens.some((token) => normalizedValue.includes(token));
}

function toIsoDateString(value) {
  if (!value) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }

  const match = String(value).match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!match) {
    return null;
  }

  const [, day, month, year] = match;
  return `${year}-${month}-${day}`;
}

function handleDateClick(event) {
  if (event.target.closest("#date-picker-popover")) {
    return;
  }

  const input = event.target.closest(".date-input");
  if (input && !input.disabled) {
    openDatePicker(input);
    return;
  }

  if (!event.target.closest("#date-picker-popover")) {
    closeDatePicker();
  }
}

function handleDateMouseDown(event) {
  if (processDatePickerTarget(event.target)) {
    event.preventDefault();
  }
}

function processDatePickerTarget(target) {
  const navButton = target.closest("[data-date-nav]");
  if (navButton) {
    if (navButton.dataset.dateNav === "month-select") {
      state.datePicker.view = "months";
      renderDatePicker();
      return true;
    }
    if (navButton.dataset.dateNav === "year-select") {
      state.datePicker.view = "years";
      renderDatePicker();
      return true;
    }
    shiftDatePickerMonth(Number(navButton.dataset.dateNav));
    return true;
  }

  const actionButton = target.closest("[data-date-action]");
  if (actionButton) {
    handleDatePickerAction(actionButton.dataset.dateAction);
    return true;
  }

  const dayButton = target.closest("[data-date-value]");
  if (dayButton) {
    applyDatePickerValue(dayButton.dataset.dateValue);
    return true;
  }

  const monthButton = target.closest("[data-date-month]");
  if (monthButton) {
    selectDatePickerMonth(Number(monthButton.dataset.dateMonth));
    return true;
  }

  const yearButton = target.closest("[data-date-year]");
  if (yearButton) {
    selectDatePickerYear(Number(yearButton.dataset.dateYear));
    return true;
  }

  return false;
}

function handleDateFocusIn(event) {
  const input = event.target.closest(".date-input");
  if (!input || input.disabled) {
    return;
  }
  openDatePicker(input);
}

function handleDateBlur(event) {
  const input = event.target.closest(".date-input");
  if (!input) {
    return;
  }
  normalizeDateInput(input);
}

function handleDateInput(event) {
  const input = event.target.closest(".date-input");
  if (!input || input.disabled) {
    return;
  }
  applyDateInputMask(input);
}

function handleDateKeydown(event) {
  const activeInput = event.target.closest(".date-input");
  if (event.key === "Escape") {
    closeDatePicker();
    return;
  }

  if (!activeInput) {
    return;
  }

  if (event.key === "Enter") {
    normalizeDateInput(activeInput);
    if (activeInput.dataset.inlineField) {
      activeInput.blur();
    }
  }
}

function openDatePicker(input) {
  if (!datePickerPopover || input.disabled) {
    return;
  }

  state.datePicker.activeInput = input;
  state.datePicker.visibleMonth = getInitialVisibleMonth(input.value);
  state.datePicker.view = "days";
  positionDatePicker(input);
  renderDatePicker();
  datePickerPopover.classList.remove("hidden");
}

function closeDatePicker() {
  state.datePicker.activeInput = null;
  state.datePicker.visibleMonth = null;
  state.datePicker.view = "days";
  datePickerPopover?.classList.add("hidden");
}

function positionDatePicker(input) {
  const inputRect = input.getBoundingClientRect();
  const scrollY = window.scrollY || document.documentElement.scrollTop;
  const scrollX = window.scrollX || document.documentElement.scrollLeft;
  datePickerPopover.style.top = `${inputRect.bottom + scrollY + 8}px`;
  datePickerPopover.style.left = `${inputRect.left + scrollX}px`;
}

function renderDatePicker() {
  if (!state.datePicker.visibleMonth || !datePickerGrid || !datePickerTitleMonth || !datePickerTitleYear) {
    return;
  }

  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  datePickerTitleMonth.textContent = formatMonthLabel(baseDate);
  datePickerTitleYear.textContent = String(baseDate.getFullYear());
  datePickerGrid.dataset.view = state.datePicker.view;
  if (datePickerWeekdays) {
    datePickerWeekdays.hidden = state.datePicker.view !== "days";
  }

  if (state.datePicker.view === "months") {
    renderDatePickerMonths(baseDate);
    return;
  }

  if (state.datePicker.view === "years") {
    renderDatePickerYears(baseDate);
    return;
  }

  const selectedIso = parseDisplayDateValue(state.datePicker.activeInput?.value ?? "");
  const todayIso = toIsoDateFromDate(new Date());
  const gridDays = buildCalendarDays(baseDate);

  datePickerGrid.innerHTML = gridDays
    .map((item) => {
      const classes = ["date-picker-day"];
      if (!item.currentMonth) {
        classes.push("is-outside");
      }
      if (item.iso === selectedIso) {
        classes.push("is-selected");
      }
      if (item.iso === todayIso) {
        classes.push("is-today");
      }
      return `
        <button
          class="${classes.join(" ")}"
          type="button"
          data-date-value="${item.iso}"
        >
          ${item.day}
        </button>
      `;
    })
    .join("");
}

function shiftDatePickerMonth(offset) {
  if (!state.datePicker.visibleMonth) {
    return;
  }
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  if (state.datePicker.view === "years") {
    baseDate.setFullYear(baseDate.getFullYear() + offset * 12);
  } else if (state.datePicker.view === "months") {
    baseDate.setFullYear(baseDate.getFullYear() + offset);
  } else {
    baseDate.setMonth(baseDate.getMonth() + offset);
  }
  state.datePicker.visibleMonth = `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, "0")}`;
  renderDatePicker();
}

function handleDatePickerAction(action) {
  if (!state.datePicker.activeInput) {
    return;
  }

  if (action === "today") {
    applyDatePickerValue(toIsoDateFromDate(new Date()));
    return;
  }

  if (action === "clear") {
    state.datePicker.activeInput.value = "";
    if (state.datePicker.activeInput.dataset.inlineField) {
      commitInlineField(state.datePicker.activeInput);
    } else if (state.datePicker.activeInput.dataset.filterKey) {
      renderDebtors(true);
    }
    closeDatePicker();
  }
}

function applyDatePickerValue(isoValue) {
  const input = state.datePicker.activeInput;
  if (!input) {
    return;
  }

  input.value = formatDisplayDate(isoValue) ?? "";
  if (input.dataset.inlineField) {
    commitInlineField(input);
  } else if (input.dataset.filterKey) {
    renderDebtors(true);
  }
  closeDatePicker();
}

function setDateInputValue(input, isoValue) {
  if (!input) {
    return;
  }
  input.value = formatDisplayDate(isoValue) ?? "";
}

function applyDateInputMask(input) {
  const rawValue = String(input.value ?? "");
  const digits = rawValue.replace(/\D/g, "").slice(0, 8);
  const selectionStart = input.selectionStart ?? rawValue.length;
  const digitsBeforeCaret = rawValue.slice(0, selectionStart).replace(/\D/g, "").length;

  let masked = "";
  if (digits.length <= 2) {
    masked = digits;
  } else if (digits.length <= 4) {
    masked = `${digits.slice(0, 2)}.${digits.slice(2)}`;
  } else {
    masked = `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
  }

  input.value = masked;

  let caret = masked.length;
  if (document.activeElement === input) {
    let digitCount = 0;
    caret = 0;
    while (caret < masked.length && digitCount < digitsBeforeCaret) {
      if (/\d/.test(masked[caret])) {
        digitCount += 1;
      }
      caret += 1;
    }
    input.setSelectionRange(caret, caret);
  }
}

function normalizeDateInput(input) {
  applyDateInputMask(input);
  const isoValue = parseDisplayDateValue(input.value);
  input.value = formatDisplayDate(isoValue) ?? input.value.trim();
}

function getDateInputIsoValue(input) {
  return parseDisplayDateValue(input.value);
}

function getInitialVisibleMonth(value) {
  const isoValue = parseDisplayDateValue(value);
  if (isoValue) {
    return isoValue.slice(0, 7);
  }
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
}

function formatDisplayDate(isoValue) {
  if (!isoValue) {
    return null;
  }
  const match = String(isoValue).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const [, year, month, day] = match;
  return `${day}.${month}.${year}`;
}

function parseDisplayDateValue(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return text;
  }

  if (/^\d{8}$/.test(text)) {
    const normalizedDigits = text;
    return parseDisplayDateValue(
      `${normalizedDigits.slice(0, 2)}.${normalizedDigits.slice(2, 4)}.${normalizedDigits.slice(4)}`
    );
  }

  const normalized = text.replaceAll("/", ".").replaceAll("-", ".");
  const match = normalized.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!match) {
    return null;
  }

  const [, dayRaw, monthRaw, yearRaw] = match;
  const day = Number(dayRaw);
  const month = Number(monthRaw);
  const year = Number(yearRaw);
  const dateValue = new Date(year, month - 1, day, 12);

  if (
    dateValue.getFullYear() !== year ||
    dateValue.getMonth() !== month - 1 ||
    dateValue.getDate() !== day
  ) {
    return null;
  }

  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function buildCalendarDays(baseDate) {
  const year = baseDate.getFullYear();
  const month = baseDate.getMonth();
  const firstOfMonth = new Date(year, month, 1, 12);
  const startOffset = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - startOffset, 12);

  return Array.from({ length: 42 }, (_, index) => {
    const itemDate = new Date(gridStart);
    itemDate.setDate(gridStart.getDate() + index);
    return {
      day: itemDate.getDate(),
      iso: toIsoDateFromDate(itemDate),
      currentMonth: itemDate.getMonth() === month,
    };
  });
}

function renderDatePickerMonths(baseDate) {
  const selectedMonth = baseDate.getMonth();
  const monthNames = Array.from({ length: 12 }, (_, monthIndex) =>
    new Intl.DateTimeFormat(currentLocale(), { month: "short" }).format(new Date(2026, monthIndex, 1, 12)),
  );

  datePickerGrid.innerHTML = monthNames
    .map((monthName, monthIndex) => {
      const classes = ["date-picker-day", "date-picker-choice"];
      if (monthIndex === selectedMonth) {
        classes.push("is-selected");
      }
      return `
        <button
          class="${classes.join(" ")}"
          type="button"
          data-date-month="${monthIndex}"
        >
          ${capitalizeMonthLabel(monthName)}
        </button>
      `;
    })
    .join("");
}

function renderDatePickerYears(baseDate) {
  const currentYear = baseDate.getFullYear();
  const startYear = currentYear - 5;
  const years = Array.from({ length: 12 }, (_, index) => startYear + index);

  datePickerGrid.innerHTML = years
    .map((year) => {
      const classes = ["date-picker-day", "date-picker-choice"];
      if (year === currentYear) {
        classes.push("is-selected");
      }
      return `
        <button
          class="${classes.join(" ")}"
          type="button"
          data-date-year="${year}"
        >
          ${year}
        </button>
      `;
    })
    .join("");
}

function selectDatePickerMonth(monthIndex) {
  if (!state.datePicker.visibleMonth) {
    return;
  }
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  baseDate.setMonth(monthIndex);
  state.datePicker.visibleMonth = `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, "0")}`;
  state.datePicker.view = "days";
  renderDatePicker();
}

function selectDatePickerYear(year) {
  if (!state.datePicker.visibleMonth) {
    return;
  }
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  baseDate.setFullYear(year);
  state.datePicker.visibleMonth = `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, "0")}`;
  state.datePicker.view = "days";
  renderDatePicker();
}

function formatMonthLabel(date) {
  return capitalizeMonthLabel(
    new Intl.DateTimeFormat(currentLocale(), {
      month: "long",
    }).format(date),
  );
}

function capitalizeMonthLabel(value) {
  const text = String(value ?? "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function toIsoDateFromDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function isYesOptionDisabled(debtor, field) {
  if (field === "lawsuit_sent") {
    return !debtor.claim_sent;
  }
  if (field === "lawsuit_accepted") {
    return !debtor.claim_sent || !debtor.lawsuit_sent;
  }
  if (field === "decision_exists") {
    return !debtor.claim_sent || !debtor.lawsuit_sent || !debtor.lawsuit_accepted;
  }
  return false;
}

function renderClaimDays(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  const className = value > 10 ? "tag tag-no" : "tag tag-warning";
  return `<span class="${className}">${escapeHtml(String(value))}</span>`;
}

function renderPlain(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return escapeHtml(String(value));
}

function formatMoney(value) {
  return new Intl.NumberFormat(currentLocale(), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function roundToTwo(value) {
  return Math.round(Number(value || 0) * 100) / 100;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeHtmlAttribute(value) {
  return escapeHtml(value);
}

function cssEscape(value) {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(String(value));
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function buildCategorySelectStyle(category) {
  const palette = CATEGORY_STYLES[category];
  return buildGlassSelectStyle(palette);
}

function buildDecisionSelectStyle(decision) {
  const palette = DECISION_STYLES[decision];
  if (!palette) {
    return "";
  }
  return buildGlassSelectStyle(palette);
}

function buildGlassSelectStyle(palette) {
  if (!palette) {
    return "";
  }

  const rgb = hexToRgb(palette.bg);
  if (!rgb) {
    return "";
  }

  const [red, green, blue] = rgb;
  const borderColor = `rgba(${red}, ${green}, ${blue}, 0.5)`;
  const shadowGlow = `rgba(${red}, ${green}, ${blue}, 0.26)`;
  const topLayer = `rgba(${red}, ${green}, ${blue}, 0.4)`;
  const bottomLayer = `rgba(${red}, ${green}, ${blue}, 0.24)`;

  return `style="background:linear-gradient(180deg, ${topLayer} 0%, ${bottomLayer} 100%);color:#ffffff;border-color:${borderColor};box-shadow:inset 0 1px 0 rgba(255,255,255,0.18), 0 10px 24px -18px ${shadowGlow};text-shadow:0 1px 1px rgba(0,0,0,0.35);font-weight:700;"`;
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  if (normalized.length !== 6) {
    return null;
  }

  const value = Number.parseInt(normalized, 16);
  if (Number.isNaN(value)) {
    return null;
  }

  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

