(function () {
    const STORAGE_KEYS = {
        theme: "tp-theme",
        language: "tp-language",
    };

    const FALLBACK_LANGUAGE = "uk";
    const FALLBACK_THEME = "light";

    const translations = {
        uk: {
            "brand.title": "Турнірна платформа",
            "brand.subtitle": "Турніри, команди, повідомлення, сертифікати та результати в одному просторі.",
            "nav.home": "Головна",
            "nav.messages": "Повідомлення",
            "nav.certificates": "Сертифікати",
            "nav.archive": "Архів",
            "nav.management": "Керування",
            "nav.management.title": "Адмінські розділи",
            "nav.users": "Користувачі",
            "nav.create_user": "Створити користувача",
            "nav.active_tournaments": "Активні турніри",
            "nav.inactive_tournaments": "Неактивні турніри",
            "nav.create_tournament": "Створити турнір",
            "nav.teams": "Команди",
            "nav.registrations": "Заявки",
            "nav.submissions": "Роботи",
            "nav.announcements": "Оголошення",
            "nav.admin_certificates": "Сертифікати",
            "nav.profile": "Профіль",
            "nav.my_team": "Моя команда",
            "nav.jury": "Журі",
            "nav.my_tournaments": "Мої турніри",
            "nav.logout": "Вийти",
            "nav.login": "Увійти",
            "nav.register": "Зареєструватися",
            "theme.label": "Тема",
            "theme.light": "Світла",
            "theme.dark": "Темна",
            "lang.label": "Мова",
            "lang.uk": "UA",
            "lang.en": "EN",
            "auth.home": "На головну",
            "login.title": "Вхід",
            "login.subtitle": "Увійдіть у свій акаунт, щоб працювати з турнірами, командами та оцінюванням.",
            "login.username": "Логін",
            "login.password": "Пароль",
            "login.submit": "Увійти",
            "login.no_account": "Ще не маєте акаунта?",
            "login.register_link": "Зареєструватися",
            "login.unblock_prefix": "Розблокування через:",
            "login.unblocked": "Блокування завершилося. Можна спробувати ще раз.",
            "register.title": "Реєстрація",
            "register.subtitle": "Створіть акаунт учасника, щоб подавати заявки на турніри.",
            "register.notice": "Після реєстрації ми надішлемо лист із посиланням для підтвердження електронної пошти. Увійти на сайт можна буде після переходу за цим посиланням.",
            "register.username": "Логін",
            "register.email": "Електронна пошта",
            "register.password": "Пароль",
            "register.password_confirm": "Підтвердження пароля",
            "register.submit": "Зареєструватися",
            "register.has_account": "Уже є акаунт?",
            "register.login_link": "Увійти",
            "home.hero.kicker": "Публічний доступ",
            "home.hero.title": "Турніри, заявки, результати та сповіщення без зайвих переходів.",
            "home.hero.text": "На цій сторінці ви можете побачити: активні, майбутні та завершені турніри, новини платформи, повідомлення від системи та підсумковий лідерборд.",
            "home.stat.total": "Усього опублікованих турнірів",
            "home.stat.open": "Турніри з відкритою реєстрацією",
            "home.stat.finished": "Завершені події з підсумками",
            "messages.hero.kicker": "Центр повідомлень",
            "messages.hero.title": "Повідомлення платформи",
            "messages.hero.text": "Тут зібрані особисті статуси команди, загальні оголошення та турнірні події: старт реєстрації, старт завдань, дедлайни, завершення оцінювання й системні оновлення.",
            "messages.filters.title": "Фільтри повідомлень",
            "messages.filters.note": "Перемикай між особистими, загальними та турнірними повідомленнями без перезавантаження сторінки.",
            "messages.filter.all": "Усі",
            "messages.filter.personal": "Особисті",
            "messages.filter.general": "Загальні",
            "messages.filter.tournament": "Турнірні",
            "messages.filter.empty": "За цим фільтром повідомлень поки немає.",
            "messages.empty": "Поки що для вас немає повідомлень.",
            "profile.hero.kicker": "Особистий кабінет",
            "profile.hero.title": "Профіль користувача",
            "profile.hero.text": "Тут зібрано вашу базову інформацію, команди, турніри, сертифікати та останні оголошення платформи.",
            "create_team.title.create": "Створити команду",
            "create_team.title.edit": "Редагувати команду",
            "create_team.note": "Заповніть базові дані команди та вкажіть один зручний спосіб зв'язку з контактною особою (капітаном).",
            "team.hero.back": "Назад",
        },
        en: {
            "brand.title": "Tournament Platform",
            "brand.subtitle": "Tournaments, teams, messages, certificates, and results in one place.",
            "nav.home": "Home",
            "nav.messages": "Messages",
            "nav.certificates": "Certificates",
            "nav.archive": "Archive",
            "nav.management": "Manage",
            "nav.management.title": "Admin sections",
            "nav.users": "Users",
            "nav.create_user": "Create user",
            "nav.active_tournaments": "Active tournaments",
            "nav.inactive_tournaments": "Inactive tournaments",
            "nav.create_tournament": "Create tournament",
            "nav.teams": "Teams",
            "nav.registrations": "Registrations",
            "nav.submissions": "Submissions",
            "nav.announcements": "Announcements",
            "nav.admin_certificates": "Certificates",
            "nav.profile": "Profile",
            "nav.my_team": "My team",
            "nav.jury": "Jury",
            "nav.my_tournaments": "My tournaments",
            "nav.logout": "Log out",
            "nav.login": "Log in",
            "nav.register": "Sign up",
            "theme.label": "Theme",
            "theme.light": "Light",
            "theme.dark": "Dark",
            "lang.label": "Language",
            "lang.uk": "UA",
            "lang.en": "EN",
            "auth.home": "Home",
            "login.title": "Log in",
            "login.subtitle": "Sign in to work with tournaments, teams, and evaluations.",
            "login.username": "Username",
            "login.password": "Password",
            "login.submit": "Log in",
            "login.no_account": "Don't have an account yet?",
            "login.register_link": "Sign up",
            "login.unblock_prefix": "Unlocked in:",
            "login.unblocked": "The lock has ended. You can try again now.",
            "register.title": "Sign up",
            "register.subtitle": "Create a participant account to register for tournaments.",
            "register.notice": "After registration, we will send you an email confirmation link. You will be able to sign in after following that link.",
            "register.username": "Username",
            "register.email": "Email",
            "register.password": "Password",
            "register.password_confirm": "Confirm password",
            "register.submit": "Sign up",
            "register.has_account": "Already have an account?",
            "register.login_link": "Log in",
            "home.hero.kicker": "Public access",
            "home.hero.title": "Tournaments, registrations, results, and notifications without extra clicks.",
            "home.hero.text": "On this page you can see active, upcoming, and finished tournaments, platform news, system notifications, and the final leaderboard.",
            "home.stat.total": "Published tournaments",
            "home.stat.open": "Tournaments with open registration",
            "home.stat.finished": "Finished events with results",
            "messages.hero.kicker": "Message center",
            "messages.hero.title": "Platform messages",
            "messages.hero.text": "Here you can find personal team statuses, general announcements, and tournament events: registration start, task launch, deadlines, evaluation completion, and system updates.",
            "messages.filters.title": "Message filters",
            "messages.filters.note": "Switch between personal, general, and tournament messages without reloading the page.",
            "messages.filter.all": "All",
            "messages.filter.personal": "Personal",
            "messages.filter.general": "General",
            "messages.filter.tournament": "Tournament",
            "messages.filter.empty": "There are no messages for this filter yet.",
            "messages.empty": "There are no messages for you yet.",
            "profile.hero.kicker": "Personal space",
            "profile.hero.title": "User profile",
            "profile.hero.text": "This page contains your basic info, teams, tournaments, certificates, and the latest platform announcements.",
            "create_team.title.create": "Create team",
            "create_team.title.edit": "Edit team",
            "create_team.note": "Fill in the basic team information and choose one preferred way to contact the team contact person (captain).",
            "team.hero.back": "Back",
        },
    };

    function getStoredPreference(key, fallbackValue) {
        try {
            return localStorage.getItem(key) || fallbackValue;
        } catch (error) {
            return fallbackValue;
        }
    }

    function setStoredPreference(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            return;
        }
    }

    function getTranslation(language, key) {
        const languageTable = translations[language] || translations[FALLBACK_LANGUAGE];
        return languageTable[key] || (translations[FALLBACK_LANGUAGE] || {})[key] || key;
    }

    function applyTheme(theme) {
        const resolvedTheme = theme === "dark" ? "dark" : FALLBACK_THEME;
        document.documentElement.dataset.theme = resolvedTheme;
        setStoredPreference(STORAGE_KEYS.theme, resolvedTheme);
        document.querySelectorAll("[data-theme-option]").forEach(function (button) {
            button.classList.toggle("is-active", button.dataset.themeOption === resolvedTheme);
            button.setAttribute("aria-pressed", button.dataset.themeOption === resolvedTheme ? "true" : "false");
        });
    }

    function applyLanguage(language) {
        const resolvedLanguage = language === "en" ? "en" : FALLBACK_LANGUAGE;
        document.documentElement.lang = resolvedLanguage;
        setStoredPreference(STORAGE_KEYS.language, resolvedLanguage);

        document.querySelectorAll("[data-i18n]").forEach(function (element) {
            element.textContent = getTranslation(resolvedLanguage, element.dataset.i18n);
        });
        document.querySelectorAll("[data-i18n-placeholder]").forEach(function (element) {
            element.setAttribute("placeholder", getTranslation(resolvedLanguage, element.dataset.i18nPlaceholder));
        });
        document.querySelectorAll("[data-i18n-title]").forEach(function (element) {
            element.setAttribute("title", getTranslation(resolvedLanguage, element.dataset.i18nTitle));
        });
        document.querySelectorAll("[data-language-option]").forEach(function (button) {
            button.classList.toggle("is-active", button.dataset.languageOption === resolvedLanguage);
            button.setAttribute("aria-pressed", button.dataset.languageOption === resolvedLanguage ? "true" : "false");
        });
    }

    function bindPreferenceButtons() {
        document.querySelectorAll("[data-theme-option]").forEach(function (button) {
            button.addEventListener("click", function () {
                applyTheme(button.dataset.themeOption);
            });
        });
        document.querySelectorAll("[data-language-option]").forEach(function (button) {
            button.addEventListener("click", function () {
                applyLanguage(button.dataset.languageOption);
            });
        });
    }

    window.TournamentUIPreferences = {
        getTranslation: function (key) {
            return getTranslation(getStoredPreference(STORAGE_KEYS.language, FALLBACK_LANGUAGE), key);
        },
        getTheme: function () {
            return getStoredPreference(STORAGE_KEYS.theme, FALLBACK_THEME);
        },
        getLanguage: function () {
            return getStoredPreference(STORAGE_KEYS.language, FALLBACK_LANGUAGE);
        },
        applyTheme: applyTheme,
        applyLanguage: applyLanguage,
    };

    document.addEventListener("DOMContentLoaded", function () {
        bindPreferenceButtons();
        applyTheme(getStoredPreference(STORAGE_KEYS.theme, FALLBACK_THEME));
        applyLanguage(getStoredPreference(STORAGE_KEYS.language, FALLBACK_LANGUAGE));
    });
}());
