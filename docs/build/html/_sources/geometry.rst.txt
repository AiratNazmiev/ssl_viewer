Geometry and conventions
========================

Telemetry convention
--------------------

The viewer uses planar-array telemetry:

- ``az_deg`` is azimuth in the local x-y plane
- azimuth is measured counter-clockwise from local ``+x``
- ``el_deg`` is elevation above the local x-y plane toward local ``+z``

Local axes
----------

The viewer assumes:

- ``+x`` = in-plane reference axis shown by the arrow
- ``+y`` = in-plane axis 90 degrees counter-clockwise from ``+x``
- ``+z`` = array normal / up

Local ray model
---------------

The local ray is computed as:

.. math::

   x = \cos(el)\cos(az)

.. math::

   y = \cos(el)\sin(az)

.. math::

   z = \sin(el)

World placement
---------------

The UI heading defines the world heading of local ``+x``.

The local ``+y`` axis is derived as 90 degrees counter-clockwise from local
``+x``.

The local ``+z`` axis is treated as world up.

Interpretation
--------------

- ``az = 0°, el = 0°`` points along the arrow
- ``az = 90°, el = 0°`` points 90 degrees counter-clockwise from the arrow in the ground plane
- ``el = 90°`` points straight up

Map rendering
-------------

The blue arrow shows local ``+x`` only.

The rendered ray starts at the microphone anchor position and extends in the
telemetry direction.
