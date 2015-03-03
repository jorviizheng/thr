default: all

all:
	python setup.py build

install: all
	python setup.py install

clean:
	rm -f *.pyc
	cd tests && rm -f *.pyc
	cd thr && rm -f *.pyc
	cd tests && rm -Rf htmlcov 
	cd docs && make clean
	rm -f .coverage tests/.coverage
	rm -f MANIFEST
	rm -Rf build
	rm -Rf dist
	rm -Rf thr.egg-info
	rm -Rf thr/__pycache__
	rm -Rf tests/__pycache__
	rm -f tests/conf.py
	rm -f tests/auth.txt

sdist: clean
	python setup.py sdist

doc:
	cd docs && make html

test:
	flake8 --exclude=docs/*,examples/* .
	cd tests && nosetests

coveralls:
	cd tests && nosetests --with-coverage --cover-package=thr && ../.coveralls.sh

upload:
	python setup.py sdist register upload

coverage:
	cd tests && coverage run `which nosetests` && coverage html --include='*/thr/thr/*' --omit='test_*'

release: test coverage clean upload clean 
