install:
        pip install -e .


test:
	pytest


lint:
	pre-commit run --all-files

