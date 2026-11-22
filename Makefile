.PHONY: all test
# One command reproduces every reported number:  make all   (or: python run_all.py)
all:
	python run_all.py
test:
	python -m pytest -q
