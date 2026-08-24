# Badge Generator

Badge Generator is a web application for generating badges from document inputs.

The application consists of a React frontend and a FastAPI backend. The backend processes document information, validates the extracted details, and generates the final badge using the appropriate badge renderer.

## Architecture

```text
React Frontend
      |
      | REST API
      v
FastAPI Backend
      |
      +-- Document Processing
      |
      +-- Information Extraction
      |
      +-- Validation Service
      |
      +-- Badge Generation Service
      |
      +-- Badge Renderers
             |
             +-- Circle Renderer
             |
             +-- Diamond Renderer
```

### Frontend

The frontend is built with React and provides the user interface for:

- Uploading the input document
- Providing or selecting badge information
- Previewing the generated badge
- Interacting with the FastAPI backend

Frontend directory:

```text
badge-generator_Frontend/
```

### Backend

The backend is built with Python and FastAPI.

It contains the services responsible for:

- Processing PDF documents
- Extracting badge information
- Cleaning extracted text
- Validating badge details
- Generating badges
- Rendering circle and diamond badge designs

Backend directory:

```text
badge-generator_Backend/
```

## Project Structure

```text
badge_generator/
|
|-- README.md
|
|-- badge-generator_Backend/
|   |-- api.py
|   |-- config.py
|   |-- main.py
|   |-- requirements.txt
|   |
|   |-- input/
|   |
|   |-- models/
|   |
|   |-- services/
|   |   |-- badge/
|   |   |   |-- renderers/
|   |   |   `-- templates/
|   |   |
|   |   `-- doc_info/
|   |
|   `-- utils/
|
`-- badge-generator_Frontend/
    |-- public/
    |-- src/
    |-- package.json
    |-- package-lock.json
    `-- vite.config.js
```

## Prerequisites

Before running the application, make sure the following are installed:

- Python - 3.13.14
- Node.js and npm
- Git

## Installation

Clone the repository and open the project directory before setting up the backend and frontend.

---

## Backend Setup

Navigate to the backend directory.

### Using PowerShell

```powershell
cd .\badge-generator_Backend
```

Create a Python virtual environment:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the required Python packages:

```powershell
pip install -r requirements.txt
```

### Using Command Prompt (CMD)

```cmd
cd badge-generator_Backend
```

Create a Python virtual environment:

```cmd
python -m venv .venv
```

Activate the virtual environment:

```cmd
.venv\Scripts\activate.bat
```

Install the required Python packages:

```cmd
pip install -r requirements.txt
```

---

## Frontend Setup

Open another terminal from the project root and navigate to the frontend directory.

### Using PowerShell

```powershell
cd .\badge-generator_Frontend
```

Install the frontend dependencies:

```powershell
npm install
```

Start the frontend development server:

```powershell
npm run dev
```

### Using Command Prompt (CMD)

```cmd
cd badge-generator_Frontend
```

Install the frontend dependencies:

```cmd
npm install
```

Start the frontend development server:

```cmd
npm run dev
```

After starting the frontend, open the local URL displayed in the terminal.

## Technology Stack

### Frontend

- React
- JavaScript
- Vite

### Backend

- Python
- FastAPI
- Pydantic
- Pillow

### Development

- Git
- GitHub
- VS Code
- Postman

## Git

The repository contains both the frontend and backend under a single Git repository.

```text
badge_generator/
|
|-- badge-generator_Backend/
|-- badge-generator_Frontend/
`-- README.md
```

Virtual environments, dependency folders, generated output, and cache files should remain excluded through the project's `.gitignore` files.