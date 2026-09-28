# Google Maps Data Scraper

A local web application for searching Google Maps business listings and exporting the results to CSV. The Flask interface starts a scrape in the background, shows progress, lets you stop a running job, and provides a download when it finishes.

## Features

- Search Google Maps with a business type, place, or a combination (for example, `beauty salons in Pune`).
- Set a result limit or choose `all` to continue until the scraper reaches the end of the available listings.
- View live progress and scraped business details in the browser.
- Stop a running scrape and download the completed CSV.
- Save CSV exports in the local `exports/` directory.

The CSV includes business name, category, phone, address, website, location, rating, review count, hours/status, and Google Maps URL when those details are available.

## Requirements

- Python 3.10 or newer
- Google Chrome
- Python packages listed in [`requirement.text`](requirement.text)

Selenium starts Chrome through Selenium's built-in driver management. The first run may need an internet connection to obtain a compatible browser driver.

## Setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/TusharShrikhande/google_Map_Data_Scraper.git
cd google_Map_Data_Scraper
```

Create and activate a virtual environment (recommended), then install dependencies:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

Install the packages:

```bash
python -m pip install -r requirement.text
```

## Run

Start the local server:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser. Enter a search query and a positive result limit, or select `all`, then start the scrape. Keep the server running while the job is in progress. Completed CSV files are written to `exports/` and can also be downloaded from the results page.

Press `Ctrl+C` in the terminal to stop the server.

## API

The Flask server also exposes these JSON endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/scrape` | Start a job with JSON such as `{"search_query":"beauty salons in Pune","limit":100}`. Use `"all"` for the limit to scrape all available results. |
| `GET` | `/api/jobs/<job_id>` | Read job status and progress. |
| `POST` | `/api/jobs/<job_id>/stop` | Request cancellation of a queued or running job. |
| `GET` | `/api/jobs/<job_id>/download` | Download the completed CSV. |

## Project files

- `app.py` — Flask web server and job/status/download API.
- `scraper.py` — Selenium-based Google Maps collection and CSV export.
- `templates/index.html` — Web interface.
- `static/` — Interface styles and JavaScript.
- `exports/` — Existing and newly generated CSV files.
- `requirement.text` — Python dependency list.

## Notes

- Scraping requires a working Chrome installation and may take time depending on the requested number of results.
- Google Maps can change its page structure, which may affect extraction.
- Use the scraper responsibly and follow applicable laws and the relevant service terms.
