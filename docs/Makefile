# Makefile for Sphinx documentation
#

SPHINXOPTS   = 
SPHINXBUILD  = sphinx-build
BUILDDIR     = _build
PYTHON       = python
DOCKER       = docker

ALLSPHINXOPTS = -d $(BUILDDIR)/doctrees $(SPHINXOPTS) sources

clean:
	-rm -rf $(BUILDDIR)/*
image:
	$(DOCKER) build -t $(USER)/drydock-doc .
run:
	$(DOCKER) run -d -v ./:/docs $(USER)/drydock-doc
docs:
	$(SPHINXBUILD) -b dirhtml $(ALLSPHINXOPTS) $(BUILDDIR)/html
	@echo
	@echo "Build finished. The documentation pages are now in $(BUILDDIR)/html."

server: docs
	@cd $(BUILDDIR)/html; $(PYTHON) -m SimpleHTTPServer 8000