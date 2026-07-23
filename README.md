🤖 Telegram Web Automation Bot (⁠tg-playwright-bot⁠)
Docker Build
Playwright
Python
License
A high-performance Telegram bot that spins up an isolated, headless Chromium browser environment on demand using Playwright. It navigates to target URLs, handles client-side rendering, performs browser interactions (scrolling, waiting, clicking), captures full-page screenshots, and delivers extracted data directly back to your Telegram chat.
✨ Features
￼ 🌐 Isolated Browser Environments: Spawns asynchronous Chromium contexts per job to isolate browsing sessions.
￼ 📸 High-Res Screenshots: Captures full-page screenshots even on complex single-page applications (SPAs).
￼ ⚡ Smart Dynamic Waiting: Uses network idle checks to ensure heavy JavaScript loads completely before taking snapshots.
￼ 🐳 Dockerized Architecture: Built on top of official Microsoft Playwright images to eliminate missing OS font/X11 library bugs.
￼ ⚙️ Automated CI/CD: Built-in GitHub Actions workflow to auto-build and publish Docker images to GitHub Container Registry (GHCR).
🛠️ Tech Stack
￼ Language: Python 3.10+
￼ Bot Framework: ⁠python-telegram-bot⁠
￼ Browser Engine: ⁠playwright⁠ (Chromium)
￼ Containerization: Docker & Docker Compose
￼ CI/CD: GitHub Actions
🤖 Telegram Bot Commands
Command
Arguments
Description
Example
/start
None
Displays welcome message and basic usage guidelines.
/start
/check
<URL>
Launches browser, navigates to target URL, scrolls, and returns screenshot + title.
/check https://github.com

🚀 Getting Started
Prerequisites
Make sure you have the following installed:
1. Git
2. Docker Desktop (Recommended)
3. A Telegram Bot Token from @BotFather
Quickstart with Docker (Recommended)
Local Development Setup (Without Docker)
<details>
<summary><b>Click here for local Python instructions</b></summary>
If you prefer to run the script natively on your machine for debugging or development:
</details>
🔄 Automated CI/CD Deployment
This repository includes a pre-configured GitHub Actions workflow in ⁠.github/workflows/docker-publish.yml⁠.
Whenever you push to the ⁠main⁠ branch, GitHub Actions will build the Docker container and push it to the GitHub Container Registry (GHCR).
Pulling the pre-built image on your VPS:
📂 Project Structure
🛡️ License
Distributed under the MIT License. See ⁠LICENSE⁠ for more information.