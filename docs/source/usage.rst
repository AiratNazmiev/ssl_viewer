Usage
=====

Run the application
-------------------

From the project root:

.. code-block:: bash

   streamlit run main.py

What the application does
-------------------------

The application subscribes to telemetry over ZeroMQ and visualizes a target
ray on a 3D map.

Default endpoint
----------------

.. code-block:: text

   tcp://127.0.0.1:5555

Sidebar controls
----------------

The sidebar configures:

- anchor latitude / longitude
- array +x heading
- refresh interval
- microphone body radius / height
- ray length
- basemap visibility
- live telemetry connection settings

Connection settings
-------------------

Connection updates are applied through the sidebar form button.

Expected telemetry payload
--------------------------

The viewer expects a JSON object with:

- ``az_deg``
- ``el_deg``
- ``confidence``
- ``target_id``
- ``ts_ns``
- ``version``
