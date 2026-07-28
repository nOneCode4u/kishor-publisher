# Kishor Publisher - README & Funding Design Document

## Goal
Overhaul `README.md`, `.github/FUNDING.yml`, and create `GITHUB_SETTINGS.md` for `https://github.com/nOneCode4u/kishor-publisher`, bringing it to the same visual quality, badging standard, and donation integration as `mixplorer-google-drive`, `bypass-shortlinks`, and `nOneCode4u`.

---

## Scope & Target Files
1. **`README.md`** (Overhaul existing file)
2. **`.github/FUNDING.yml`** (Update existing file)
3. **`GITHUB_SETTINGS.md`** (New helper reference for repository description, website, and topics)

---

## Detailed Components

### 1. `README.md`
- **Header**:
  - Main Title: `# Kishor Publisher (किशोर पब्लिशर)`
  - Subtitle blockquote describing automated Telegram publisher for Balbharati's Kishor monthly magazine.
- **Top Badge Bar** (`style=for-the-badge`):
  - `Daily Checker` workflow status
  - `Telegram Bot` workflow status
  - `Uploader` workflow status
  - `Python 3.10+` badge
  - `MIT License` badge
  - `Ko-fi Support` badge
- **Quick Specs Grid**:
  - Source: `ebalbharati Archives`
  - Platform: `Telegram Channel & Bot`
  - Protocol: `Pyrogram MTProto (Up to 2 GB)`
  - Automation: `GitHub Actions + cron-job.org`
  - Ads: `100% Free / Zero Ads`
- **Table of Contents**: Linked navigation.
- **Architecture & Flow**:
  - Mermaid diagram showing `checker.py` -> `pending_queue.json` -> `cron-job.org` -> `uploader.py` -> Telegram Channel.
  - Workflows table.
- **Key Features**:
  - Scraper & Archival issue detection.
  - 1-hour staggered upload scheduling (IST).
  - PyMuPDF HD cover thumbnail generation.
  - Pyrogram MTProto engine for handling large files.
  - Interactive bot command suite (`/status`, `/queue`, `/last`, `/history`, `/pause`, `/resume`, `/help`).
  - Robust error handling with smart `/resume`.
- **Repository Structure**: Annotated file tree.
- **Setup & Configuration**:
  - GitHub Secrets table.
  - External service setup (`cron-job.org`).
- **Bot Commands Table**.
- **☕ Support / Donation Section**:
  - Warm message matching `nOneCode4u` repos.
  - Ko-fi badge (`[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/none123)`)
  - Official Ko-fi SVG button (`[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/none123)`)
- **License**: MIT.

### 2. `.github/FUNDING.yml`
```yaml
ko_fi: none123
custom: ["https://ko-fi.com/none123"]
```

### 3. `GITHUB_SETTINGS.md`
- **Repo Description**: `Automated daily scraper & Telegram publisher for Kishor (किशोर) monthly magazine archive. Features 1-hour staggered queue, MTProto 2 GB uploads, PyMuPDF thumbnails, and interactive bot management.`
- **Website URL**: `https://kishor.ebalbharati.in/Archives/`
- **Topics**: `telegram-bot`, `telegram-uploader`, `kishor-magazine`, `marathi-books`, `ebalbharati`, `python`, `pyrogram`, `github-actions`, `automation`, `cron-job`, `pdf-downloader`, `scraper`

---

## Spec Verification
- All links are valid.
- Badges use standard shields.io SVG formats matching `mixplorer-google-drive` & `bypass-shortlinks`.
- Donation links point to `https://ko-fi.com/none123`.
