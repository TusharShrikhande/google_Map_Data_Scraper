from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_from_directory

from scraper import ScrapeCancelled, run_scraper


app = Flask(__name__)

# ---------------------------------------------------------
# FOLDERS
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(EXPORT_DIR, exist_ok=True)


# ---------------------------------------------------------
# JOB STORAGE
# ---------------------------------------------------------

jobs = {}
job_cancel_events = {}
jobs_lock = threading.Lock()


# ---------------------------------------------------------
# UPDATE JOB
# ---------------------------------------------------------

def update_job(
    job_id,
    status=None,
    message=None,
    current=None,
    total=None,
    results=None,
    filename=None,
    error=None,
):
    with jobs_lock:
        job = jobs.get(job_id)

        if not job:
            return

        if status is not None:
            job["status"] = status

        if message is not None:
            job["message"] = message

        if current is not None:
            job["current"] = current

        if total is not None:
            job["total"] = total

        if results is not None:
            job["results"] = results

        if filename is not None:
            job["filename"] = filename

        if error is not None:
            job["error"] = error


# ---------------------------------------------------------
# BACKGROUND SCRAPER
# ---------------------------------------------------------

def background_scrape(job_id, search_query, max_results, cancel_event):

    try:

        if cancel_event.is_set():
            raise ScrapeCancelled("Scraping stopped by user.")

        update_job(
            job_id,
            status="running",
            message="Preparing scraper...",
            current=0,
            total=max_results if isinstance(max_results, int) else 0,
        )

        def progress_callback(message, current=0, total=0, results=None):

            if cancel_event.is_set():
                return

            update_job(
                job_id,
                status="running",
                message=message,
                current=current,
                total=total,
                results=results,
            )

        result = run_scraper(
            search_query=search_query,
            max_results=max_results,
            progress_callback=progress_callback,
            export_dir=EXPORT_DIR,
            cancel_event=cancel_event,
        )

        with jobs_lock:
            job = jobs.get(job_id)
            if job and job["status"] in ("running", "cancelling"):
                cancelled = cancel_event.is_set()
                job.update({
                    "status": "cancelled" if cancelled else "completed",
                    "message": "Scraping stopped by user." if cancelled else f"Completed successfully. Found {result['count']} businesses.",
                    "current": result["count"],
                    "total": result["count"],
                    "results": result["results"],
                    "filename": result["filename"] if not cancelled else None,
                })

    except ScrapeCancelled:

        update_job(
            job_id,
            status="cancelled",
            message="Scraping stopped by user.",
        )

    except Exception as e:

        print("\n")
        print("=" * 70)
        print("SCRAPER ERROR")
        print("=" * 70)
        print(str(e))
        print("=" * 70)
        print("\n")

        with jobs_lock:
            cancelled = cancel_event.is_set()

        update_job(
            job_id,
            status="cancelled" if cancelled else "failed",
            message="Scraping stopped by user." if cancelled else "Scraper failed.",
            error=str(e),
        )
    finally:
        with jobs_lock:
            job_cancel_events.pop(job_id, None)


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------
# START SCRAPING
# ---------------------------------------------------------

@app.route("/api/scrape", methods=["POST"])
def start_scrape():

    data = request.get_json(silent=True) or {}

    search_query = str(data.get("search_query", "")).strip()
    limit = data.get("limit", 500)

    # -----------------------------------------
    # VALIDATE SEARCH
    # -----------------------------------------

    if not search_query:

        return jsonify({
            "error": "Please enter a search query."
        }), 400

    # -----------------------------------------
    # VALIDATE LIMIT
    # -----------------------------------------

    if isinstance(limit, str):

        limit = limit.strip().lower()

        if limit == "all":
            max_results = "all"

        else:

            try:
                max_results = int(limit)
            except ValueError:

                return jsonify({
                    "error": "Invalid result limit."
                }), 400

    else:

        try:
            max_results = int(limit)

        except (TypeError, ValueError):

            return jsonify({
                "error": "Invalid result limit."
            }), 400

    if max_results != "all" and max_results <= 0:

        return jsonify({
            "error": "Result limit must be greater than zero."
        }), 400

    # -----------------------------------------
    # CREATE JOB
    # -----------------------------------------

    job_id = str(uuid.uuid4())

    with jobs_lock:

        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "message": "Queued",
            "search_query": search_query,
            "current": 0,
            "total": 0 if max_results == "all" else max_results,
            "results": [],
            "filename": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
        }
        cancel_event = threading.Event()
        job_cancel_events[job_id] = cancel_event

    # -----------------------------------------
    # START BACKGROUND THREAD
    # -----------------------------------------

    thread = threading.Thread(
        target=background_scrape,
        args=(job_id, search_query, max_results, cancel_event),
        daemon=True,
    )

    thread.start()

    return jsonify({
        "job_id": job_id,
        "status": "queued",
    })


@app.route("/api/jobs/<job_id>/stop", methods=["POST"])
def stop_scrape(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found."}), 404

        if job["status"] not in ("queued", "running"):
            return jsonify(job), 409

        job["status"] = "cancelling"
        job["message"] = "Stopping scraper..."
        cancel_event = job_cancel_events.get(job_id)
        if cancel_event:
            cancel_event.set()

    return jsonify({"job_id": job_id, "status": "cancelling"})


# ---------------------------------------------------------
# JOB STATUS
# ---------------------------------------------------------

@app.route("/api/jobs/<job_id>", methods=["GET"])
def job_status(job_id):

    with jobs_lock:

        job = jobs.get(job_id)

        if not job:

            return jsonify({
                "error": "Job not found."
            }), 404

        return jsonify(job)


# ---------------------------------------------------------
# DOWNLOAD CSV
# ---------------------------------------------------------

@app.route("/api/jobs/<job_id>/download", methods=["GET"])
def download_csv(job_id):

    with jobs_lock:

        job = jobs.get(job_id)

        if not job:

            return jsonify({
                "error": "Job not found."
            }), 404

        filename = job.get("filename")

    if not filename:

        return jsonify({
            "error": "CSV is not ready yet."
        }), 404

    filepath = os.path.join(EXPORT_DIR, filename)

    if not os.path.exists(filepath):

        return jsonify({
            "error": "CSV file not found."
        }), 404

    return send_from_directory(
        EXPORT_DIR,
        filename,
        as_attachment=True,
    )


# ---------------------------------------------------------
# RUN SERVER
# ---------------------------------------------------------

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("MAPSCRAPER SERVER")
    print("=" * 60)
    print()
    print("Open:")
    print("http://127.0.0.1:5000")
    print()
    print("Press CTRL+C to stop.")
    print("=" * 60)
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True,
    )
