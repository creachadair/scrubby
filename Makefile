.PHONY: clean all sdist

all:
	@ echo "Run 'make clean' to clean up this directory"

sdist: clean
	python setup.py sdist
	mv -f dist/*.tar.gz .

format:
	@ echo "Formatting Python source files ..."
	find . -type f -name '*.py' -print0 | \
		xargs -0 yapf --style=pep8 -i

clean:
	rm -f MANIFEST
	rm -vfr build
	rm -vfr dist
	rm -vfr __pycache__
	rm -f *.pyc *.pyo
	rm -f *~
