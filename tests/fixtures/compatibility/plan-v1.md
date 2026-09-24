## SLICE: A
brief: implement the first contract
files: src/a.py
acceptance_test_path: tests/test_a.py
deps:

## SLICE: B
brief: consume the first contract
files: src/b.py
acceptance_test_path: tests/test_b.py
deps: A
