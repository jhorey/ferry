:title: Ferry Upgrade Installation
:description: Upgrading Ferry on your local machine
:keywords: ferry, installation, upgrade

.. _upgrade:

Updating Ferry
==============

We are trying to make upgrading Ferry a breeze. Assuming that you already have a 
working Ferry installation, the first thing you'll want to do is stop any
running Ferry instances:

.. code-block:: bash

    $ sudo ferry quit

Now let's upgrade the Python packages.

.. code-block:: bash

    $ sudo pip install -U ferry

Finally, we'll need to update the Ferry images. 

.. code-block:: bash

    $ sudo ferry install -u

We're constantly trying to improve the process, so if anything goes wrong, don't
hesitate to file an issue on `GitHub <https://github.com/opencore/ferry/>`_ or 
leave a message on the `Ferry Google Group<https://groups.google.com/d/forum/ferry-user/>`_. 
