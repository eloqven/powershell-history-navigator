# Contributing to PowerShell History Navigator

Thank you for your interest in contributing to **PowerShell History Navigator**! We welcome bug reports, feature requests, documentation improvements, and code contributions.

---

## 🛠️ Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/powershell-history-navigator.git
   cd powershell-history-navigator
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pytest flake8 black
   ```

4. **Run the tests:**
   ```bash
   pytest
   ```

---

## 📝 Code Style & Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) style conventions.
- Maintain type hints where applicable.
- When adding new features or modifying the syntax validator (`is_dud_command`), please add corresponding unit tests in `tests/`.

---

## 🚀 Submitting a Pull Request

1. Create a feature branch (`git checkout -b feat/my-new-feature`).
2. Commit your changes with clear, descriptive commit messages.
3. Push to your branch (`git push origin feat/my-new-feature`).
4. Open a Pull Request against the `main` branch with the provided PR template.
