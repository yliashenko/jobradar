# Корінь проєкту на sys.path, щоб `import jobradar` бачив пакет без встановлення
# (ADR-0006: рантайм — пакет jobradar/, але не пакуємо через pip; «скопіюй теку
# й біжи» лишається чинним і на NAS, і в тестах). Дублює pyproject
# [tool.pytest] pythonpath — свідомо, щоб тести йшли і поза pytest.
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest

from jobradar import clock, paths


@pytest.fixture(autouse=True)
def _isolated_env():
    """Кожен тест стартує й завершується з чистими HOME і годинником (#1, #2).

    Тест ізолює дані через `paths.use_home(tmp)`, а час — через `clock.freeze(dt)`;
    ця фікстура гарантує, що жоден перекрив не протече в наступний тест (інакше
    вказівник на видалену тимчасову теку чи заморожений час впали б у сусіда)."""
    paths.use_home(None)
    clock.unfreeze()
    yield
    paths.use_home(None)
    clock.unfreeze()
