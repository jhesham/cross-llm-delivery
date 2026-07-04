## SLICE: T1
brief: Implement greet(name) in src/demo/greet.py returning "hello, <name>".
files: src/demo/greet.py, tests/test_greet.py
acceptance_test_path: tests/test_greet.py
deps:

## SLICE: T2
brief: Implement shout(name) in src/demo/shout.py returning greet(name).upper().
files: src/demo/shout.py
acceptance_test_path: tests/test_shout.py
deps: T1

## SLICE: T3
brief: Implement farewell(name) in src/demo/farewell.py returning "bye, <name>".
files: src/demo/farewell.py
acceptance_test_path: tests/test_farewell.py
deps:
