# ssl-viewer

Streamlit SSL viewer for planar-array telemetry.

## Run

```bash
streamlit run main.py
```

## Package layout

- `ssl_viewer/telemetry.py` – telemetry schema
- `ssl_viewer/receiver.py` – ZeroMQ subscriber polling
- `ssl_viewer/geometry.py` – coordinate and projection helpers
- `ssl_viewer/layers.py` – PyDeck layer builders
- `ssl_viewer/session.py` – Streamlit session / receiver lifecycle
- `ssl_viewer/app.py` – Streamlit UI assembly
- `main.py` – thin entry point
