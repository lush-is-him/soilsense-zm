"""SoilSense ZM decision logic (spec 2.1).

Pure services with no FastAPI or database imports; backend/ wraps them in
endpoints. Agronomy values come from rules/*.yaml, never from this package.
"""
