Ferry documentation
=====================

Overview
--------

The source for all documentation is under ``sources/`` in the form of .rst files. 
These files use [reStructuredText](http://docutils.sourceforge.net/rst.html) formatting
with [Sphinx](http://sphinx-doc.org/) extensions for structure, cross-linking, and
indexing. 

Getting Started
---------------

To edit and compile the docs you'll need to have Docker installed. Then
it's just a matter of creating the documentation image and starting the server. 

### Installation

The preferred way of generating the documentation is using ``docker``. First, 
you'll want to create the image:

```bash
make image

This will create an image called $USER/ferry-doc. Next you'll want to generate
the documentation and start the HTML server. 

```bash
docker run -d -v ./:/docs $USER/ferry-doc
# Or equivalently
make run

You should be able to access the documentation under ``_build/html``, or by
visiting ``http://localhost:8000``. 
