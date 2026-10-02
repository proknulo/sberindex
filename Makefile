# Обёртка над run.py для тех, у кого есть make (macOS, Linux). В Windows используйте python run.py <шаг>.
PY ?= python3

.PHONY: setup data run robustness intracity report landing test serve all

setup:       ## виртуальное окружение и зависимости
	$(PY) run.py setup

data:        ## данные СберИндекса, справочник МО и выгрузка БДПМО Росстата
	$(PY) run.py data

run:         ## аналитический пайплайн (≈10 мин)
	$(PY) run.py pipeline

robustness:  ## проверки надёжности
	$(PY) run.py robustness

intracity:   ## внутригородской анализ Москвы и Санкт-Петербурга
	$(PY) run.py intracity

report:      ## рисунки для отчёта
	$(PY) run.py figures

landing:     ## данные для интерактивного лендинга
	$(PY) run.py landing

test:        ## тесты индексов качества
	$(PY) run.py test

serve:       ## открыть лендинг на http://localhost:8000
	$(PY) run.py serve

all:         ## всё по порядку
	$(PY) run.py all
