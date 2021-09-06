Contribute
==========

Generating locally the documentation
------------------------------------


.. code-block:: shell

   # Install sphinx-build and related packages
   pip install .[docs]

   # cd to the docs directory
   cd docs

   # Generate the docs
   sphinx-build -T -W --keep-going -b html -d _build/doctrees -c ./source -D language=en ./source _build/html
