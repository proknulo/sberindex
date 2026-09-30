PY=.venv/bin/python

.PHONY: setup data run landing report all

setup:
	python3 -m venv .venv && $(PY) -m pip install -r requirements.txt && $(PY) -m pip install -e .

data:            ## скачать данные СберИндекса, справочник МО и выгрузку БДПМО Росстата
	$(PY) scripts/get_data.py
	$(PY) scripts/download_rosstat.py

run:             ## весь аналитический пайплайн (≈10 мин на ноутбуке)
	$(PY) -m sbx.pipeline --config configs/default.yaml

landing:         ## данные для интерактивного лендинга
	$(PY) -m sbx.landing --config configs/default.yaml

report:          ## рисунки для методологического отчёта
	$(PY) -m sbx.figures --config configs/default.yaml

all: data run report landing
