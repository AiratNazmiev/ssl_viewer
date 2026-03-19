import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "ssl-viewer"
author = "Your Name"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "alabaster"
html_static_path = ["_static"]

autosummary_generate = True

autodoc_mock_imports = ["streamlit", "pydeck", "zmq"]

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": False,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = True
