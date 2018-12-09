.PHONY: clean all sdist

all:
	@ echo "Run 'make clean' to clean up this directory"

sdist: clean
	python setup.py sdist
	mv -f dist/*.tar.gz .

clean:
	rm -f MANIFEST
	rm -vfr build
	rm -vfr dist
	rm -vfr __pycache__
	rm -f *.pyc *.pyo
	rm -f *~
