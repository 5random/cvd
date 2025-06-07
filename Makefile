install:
	pip install -r requirements.txt
	pip install -e .


test:
	pytest


lint:
	pre-commit run --all-files

