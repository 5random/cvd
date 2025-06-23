install:
        pip install -e .


test:
	pytest


lint:
        pre-commit run --all-files

update-requirements:
        python scripts/update_requirements.py

