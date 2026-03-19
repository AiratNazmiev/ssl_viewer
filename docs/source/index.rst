SSL Viewer documentation
========================

SSL Viewer is a Streamlit-based application for visualizing planar-array sound
source localization telemetry on a 3D map. It subscribes to live ZeroMQ
telemetry, interprets azimuth and elevation in the array coordinate system, and
renders the estimated target direction as a ray anchored at the array position.

The project is organized into small modules for telemetry handling, receiver
logic, geometry, layer construction, session management, and app rendering.
This documentation covers installation, usage, geometry conventions, and the
Python API.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   usage
   geometry
   api