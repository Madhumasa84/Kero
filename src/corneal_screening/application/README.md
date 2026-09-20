# KERASCAN Local Streamlit Interface

This folder contains the Week 1 offline interface for submitting an original
JPEG or PNG image and anonymous capture metadata to the existing local API.

The interface does not perform image analysis, disease prediction, diagnosis
or referral decisions. It displays the structured mock result returned by the
shared API.

## Requirements

- Python 3.11
- The project core and development dependencies
- The optional `ui` dependency group

## Installation

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
python -m pip install -e ".[ui]" --no-deps