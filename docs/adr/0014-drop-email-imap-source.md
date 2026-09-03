# ADR-0014: прибрано email/IMAP-джерело; DOU RSS + Djinni RSS — єдині джерела

Дата: 2026-09-03
Статус: ухвалено (переглядає інваріант «Boards are not scraped … arrive as email alerts» з CLAUDE.md §4 і ADR-0009)

## Контекст
Радар мав три канали збору: DOU RSS, Djinni RSS і **email-алерти Djinni/LinkedIn
через IMAP** (`core/collectors/email_alerts.py`, `sources.imap.*` у config.json).
Email був способом дістати LinkedIn (борд, який не скрапиться) і додатковим
потоком Djinni — модель BYOA («принеси власні алерти»), описана в
`docs/PRODUCT.md §6` як стратегічний стовп майбутнього продукту.

На практиці email-інтеграції в роботі немає й не планується. Вона тягла за собою
непропорційну ціну для персонального інструмента: обовʼязкові `imap.user/password`
у config.json (через що навіть `run --dry-run` на свіжому клоні падав), окремий
парсер листів як найкрихкіший вузол (розмітка листів змінюється частіше за RSS),
IMAP-гілка в `check`, і Gmail app-password + окремий label/фільтр в онбордингу.
Djinni й так покритий офіційним RSS; втрачається лише LinkedIn.

## Рішення
- **Видалено email/IMAP повністю.** Прибрано `core/collectors/email_alerts.py`,
  imap-джерело в `sources.py`, ре-експорти в `engine.py`, IMAP-перевірку в
  `cli.check`, imap-валідацію в `config.py`, секцію `sources.imap` у
  `config.example.json`, а також email-фікстури й тести (`test_collectors`).
- **Джерела тепер лише два: DOU RSS і Djinni RSS.** LinkedIn більше не джерело.
- **Інваріант CLAUDE.md §4 переписано:** «Boards are not scraped. DOU and Djinni
  are read from their official RSS only; there is no email/IMAP integration.»
  Заборона скрейпінгу бордів лишається; додано заборону повертати email-джерело.
- **SCO-4 (стеля 6 для вакансій без опису) узагальнено:** формулювання більше не
  привʼязане до LinkedIn — правило діє для будь-якої вакансії без опису. Логіка
  скорера не змінюється.
- **Вимогу ING-3 (email over IMAP) виведено з обігу** — ID не переуживаний.
- **`docs/PRODUCT.md`:** BYOA/inbound-email лишається як **гіпотеза
  vision-треку** (заморожено ADR-0003), з явним банером, що це не наявна фіча;
  рядок «є зараз» виправлено на «DOU RSS + Djinni RSS».

## Наслідки
- Простіший онбординг: `cp config.example.json config.json` і `run` працюють без
  налаштування пошти; лишаються машинні налаштування (фіди, scorer) + Settings.
- Втрачаємо LinkedIn як канал; UA-пул спирається на DOU+Djinni (ризик концентрації
  джерел зафіксовано в PRODUCT.md §6 — тепер без email-фолбека).
- Крихкий парсер листів більше не супроводжується; heartbeat лишається сторожем
  тиші, але тепер «тиша» вказує на RSS-фіди, а не на поштовий фільтр.
- `make check` зелений; кількість джерельних колекторів — два.
