====================================
Metrics
====================================

This benchmark uses three different metrics:

- Pearson's correlation coefficient;
- Mean absolute error (MAE); and
- Fraction correct.

The metrics are not mutually exclusive but each has a separate focus. Pearson's R indicates the level of correlation
between experimental and predicted values but ignores the average errors in cases. The MAE reports this error which
is important when using a DDG protocol protein design. Finally, the fraction correct measures how likely we are to correctly
predict hotspots or neutral mutations.

For certain applications, the user may be more interested in one or two of the metrics above however the combination of
all three metrics reports how useful a DDG protocol is in general.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pearson's correlation coefficient (R)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

todo:

~~~~~~~~~~~~~~~~~~~~~~~~~
Mean absolute error (MAE)
~~~~~~~~~~~~~~~~~~~~~~~~~

todo:

~~~~~~~~~~~~~~~~
Fraction correct
~~~~~~~~~~~~~~~~

todo:

================
Running analysis
================

~~~~~~~~~~~~~~
Required tools
~~~~~~~~~~~~~~

The analysis scripts require the `R software suite <http://www.r-project.org>`_. The scripts have been tested using R
versions 2.12.1 and 3.1.1. They also require the following Python libraries:
 - numpy
 - scipy


~~~~~~~~~~~~~
Main analysis
~~~~~~~~~~~~~

The main analysis is performed by a Python script which invokes R. The input to the script should be a JSON or a commas-/tabs-
separated file (CSV/TSV).

If the JSON format is used, the object should be a list of associative arrays/dicts each of which has both an Experimental and a
Predicted field with floating-point values *e.g.*:

::

  [{'Experimental': 0.8, 'ID': '71689', 'Predicted': 2.14764},
   {'Experimental': 2.6, 'ID': '71692', 'Predicted': 3.88848},
   ...
   {'Experimental': 1.4, 'ID': '76748', 'Predicted': 4.9911}]

The ID field above is unnecessary; any fields besides the required two fields will be ignored.

If the CSV/TSV format is used, all non-empty file lines not containing data should be preceded with a '#' character. The
first two columns will be used for the Experimental and Predicted values respectively *e.g.*:

::

  #Experimental,Predicted,ID,RecordID
  0.800000,2.147640,71689,332
  2.600000,3.888480,71692,333
  ...
  1.400000,4.991100,76748,944

The analysis script prints out statistics on the input dataset, including the metrics above, and creates a scatterplot. By
default, this scatterplot will be named scatterplot.png but the --output argument can be used to specify the filename and
PNG or PDF format *e.g.*:

::

  cd analysis
  python analyze.py ../output/sample/kellogg_r57471.txt # produces scatterplot.png
  python analyze.py ../output/sample/kellogg_r57471.txt --output myplot.pdf # produces myplot.pdf


