/* =========================================================
   MAPSCRAPER — FRONTEND ENGINE
========================================================= */

document.addEventListener("DOMContentLoaded", () => {


    /* =====================================================
       ELEMENTS
    ====================================================== */

    const form =
        document.getElementById("scrapeForm");

    const queryInput =
        document.getElementById("searchQuery");

    const limitInput =
        document.getElementById("resultLimit");

    const startButton =
        document.getElementById("startButton");

    const stopButton =
        document.getElementById("stopButton");

    const downloadButton =
        document.getElementById("downloadButton");

    const resultsTitle =
        document.getElementById("resultsTitle");

    const progressStatus =
        document.getElementById("progressStatus");

    const progressMessage =
        document.getElementById("progressMessage");

    const progressCount =
        document.getElementById("progressCount");

    const progressBar =
        document.getElementById("progressBar");

    const progressPercentage =
        document.getElementById("progressPercentage");

    const progressDetails =
        document.getElementById("progressDetails");

    const progressIcon =
        document.getElementById("progressIcon");

    const resultsBody =
        document.getElementById("resultsBody");

    const tableCount =
        document.getElementById("tableCount");

    const footerStatus =
        document.getElementById("footerStatus");

    const heroResults =
        document.getElementById("heroResults");

    const toast =
        document.getElementById("toast");

    const toastTitle =
        document.getElementById("toastTitle");

    const toastMessage =
        document.getElementById("toastMessage");


    let currentJobId = null;

    let pollingTimer = null;

    stopButton.addEventListener("click", stopScraping);


    /* =====================================================
       MOUSE LIGHT
    ====================================================== */

    const mouseLight =
        document.getElementById("mouseLight");

    document.addEventListener(
        "mousemove",
        (event) => {

            mouseLight.style.left =
                `${event.clientX}px`;

            mouseLight.style.top =
                `${event.clientY}px`;

        }
    );


    /* =====================================================
       QUICK SEARCH BUTTONS
    ====================================================== */

    document
        .querySelectorAll(".quick-btn")
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    queryInput.value =
                        button.dataset.query;

                    queryInput.focus();

                    queryInput.dispatchEvent(
                        new Event("input")
                    );

                }
            );

        });


    /* =====================================================
       FORM SUBMIT
    ====================================================== */

    form.addEventListener(
        "submit",
        async (event) => {

            event.preventDefault();

            const searchQuery =
                queryInput.value.trim();

            const limit =
                limitInput.value;


            if (!searchQuery) {

                showToast(
                    "Search required",
                    "Enter a Google Maps search query."
                );

                queryInput.focus();

                return;
            }


            stopPolling();

            setRunningState();


            resultsTitle.textContent =
                `Scraping: ${searchQuery}`;


            clearResults();


            try {

                const response =
                    await fetch(
                        "/api/scrape",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({
                                search_query:
                                    searchQuery,

                                limit:
                                    limit
                            })
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.error ||
                        "Could not start scraper."
                    );

                }


                currentJobId =
                    data.job_id;

                stopButton.disabled = false;


                showToast(
                    "Scraper started",
                    "Chrome is preparing your Google Maps search."
                );


                startPolling();


            }

            catch (error) {

                setIdleState();

                showToast(
                    "Error",
                    error.message
                );

            }

        }
    );


    /* =====================================================
       POLLING
    ====================================================== */

    function startPolling() {

        if (!currentJobId)
            return;


        pollJob();


        pollingTimer =
            setInterval(
                pollJob,
                1500
            );

    }


    function stopPolling() {

        if (pollingTimer) {

            clearInterval(
                pollingTimer
            );

            pollingTimer = null;

        }

    }


    async function pollJob() {

        if (!currentJobId)
            return;


        try {

            const response =
                await fetch(
                    `/api/jobs/${currentJobId}`
                );


            const job =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    job.error ||
                    "Unable to read scraper status."
                );

            }


            updateProgress(job);


            if (job.status === "completed") {

                stopPolling();

                setCompletedState(job);

            }


            if (job.status === "failed") {

                stopPolling();

                setFailedState(job);

            }

            if (job.status === "cancelled") {
                stopPolling();
                setCancelledState(job);
            }

        }

        catch (error) {

            console.error(
                "Polling error:",
                error
            );

        }

    }


    async function stopScraping() {
        if (!currentJobId || stopButton.disabled) return;

        stopButton.disabled = true;
        stopButton.textContent = "Stopping...";

        try {
            const response = await fetch(
                `/api/jobs/${currentJobId}/stop`,
                { method: "POST" }
            );
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Could not stop scraper.");

            progressStatus.textContent = "Stopping";
            progressMessage.textContent = "Waiting for the current browser action to finish...";
            showToast("Stopping scraper", "The current browser step will finish first.");
        } catch (error) {
            stopButton.disabled = false;
            stopButton.textContent = "Stop Scraping";
            showToast("Could not stop", error.message);
        }
    }


    /* =====================================================
       UPDATE PROGRESS
    ====================================================== */

    function updateProgress(job) {

        const current =
            Number(job.current || 0);

        const total =
            Number(job.total || 0);


        progressStatus.textContent =
            capitalize(job.status || "running");


        progressMessage.textContent =
            job.message ||
            "Working...";


        progressCount.textContent =
            current;


        if (total > 0) {

            const percentage =
                Math.min(
                    100,
                    Math.round(
                        (current / total) * 100
                    )
                );


            progressBar.style.width =
                `${percentage}%`;


            progressPercentage.textContent =
                `${percentage}% complete`;


            progressDetails.textContent =
                `${current} of ${total} businesses`;

        }

        else {

            progressBar.style.width =
                "20%";


            progressPercentage.textContent =
                "Collecting";


            progressDetails.textContent =
                "Searching Google Maps...";

        }


        if (
            job.status === "running" ||
            job.status === "queued"
        ) {

            progressIcon.classList.add(
                "running"
            );

            document
                .querySelector(".progress-card")
                .classList.add("running");

        }


        if (
            job.results &&
            job.results.length
        ) {

            renderResults(
                job.results
            );

        }

    }


    /* =====================================================
       COMPLETED
    ====================================================== */

    function setCompletedState(job) {

        progressStatus.textContent =
            "Completed";


        progressMessage.textContent =
            job.message ||
            "Scraping completed successfully.";


        progressIcon.classList.remove(
            "running"
        );


        document
            .querySelector(".progress-card")
            .classList.remove(
                "running"
            );


        progressBar.style.width =
            "100%";


        progressPercentage.textContent =
            "100% complete";


        progressDetails.textContent =
            `${job.current || 0} businesses collected`;


        progressIcon.innerHTML =
            "✓";


        progressCount.textContent =
            job.current || 0;


        downloadButton.disabled =
            false;


        downloadButton.onclick =
            () => {

                window.location.href =
                    `/api/jobs/${currentJobId}/download`;

            };


        footerStatus.textContent =
            "Scraping completed";


        heroResults.textContent =
            job.current || 0;


        setIdleButton();


        showToast(
            "Scraping complete",
            `${job.current || 0} businesses collected successfully.`
        );

    }


    /* =====================================================
       FAILED
    ====================================================== */

    function setFailedState(job) {

        progressStatus.textContent =
            "Scraper failed";


        progressMessage.textContent =
            job.error ||
            "Something went wrong.";


        progressIcon.classList.remove(
            "running"
        );


        document
            .querySelector(".progress-card")
            .classList.remove(
                "running"
            );


        progressIcon.innerHTML =
            "×";


        progressIcon.style.color =
            "#ff7070";


        progressPercentage.textContent =
            "Failed";


        progressDetails.textContent =
            "Check the VS Code terminal for details.";


        footerStatus.textContent =
            "Scraping failed";


        setIdleButton();


        showToast(
            "Scraper error",
            job.error ||
            "The scraper failed."
        );

    }


    /* =====================================================
       RENDER RESULTS
    ====================================================== */

    function renderResults(results) {

        if (!results || !results.length)
            return;


        resultsBody.innerHTML =
            "";


        results
            .slice()
            .reverse()
            .forEach(
                (item, index) => {

                    const row =
                        document.createElement(
                            "tr"
                        );


                    const name =
                        item["Business Name"] ||
                        "—";


                    const category =
                        item["Category"] ||
                        "—";


                    const rating =
                        item["Rating"] ||
                        "—";


                    const phone =
                        item["Phone"] ||
                        "—";


                    const address =
                        item["Address"] ||
                        "—";


                    const website =
                        item["Website"] ||
                        "";


                    row.innerHTML = `

                        <td>
                            <span class="business-name">
                                ${escapeHTML(name)}
                            </span>
                        </td>

                        <td>
                            ${escapeHTML(category)}
                        </td>

                        <td>
                            <span class="rating">
                                ${escapeHTML(rating)}
                            </span>
                        </td>

                        <td>
                            ${escapeHTML(phone)}
                        </td>

                        <td>
                            ${escapeHTML(address)}
                        </td>

                        <td>

                            ${
                                website
                                ?
                                `
                                <a
                                    class="website-link"
                                    href="${escapeAttribute(website)}"
                                    target="_blank"
                                    rel="noopener"
                                >
                                    Visit ↗
                                </a>
                                `
                                :
                                "—"
                            }

                        </td>

                    `;


                    row.style.animationDelay =
                        `${index * 0.025}s`;


                    resultsBody.appendChild(
                        row
                    );

                }
            );


        tableCount.textContent =
            `${results.length} records`;


        footerStatus.textContent =
            `${results.length} businesses displayed`;

    }


    /* =====================================================
       CLEAR RESULTS
    ====================================================== */

    function clearResults() {

        resultsBody.innerHTML = `

            <tr class="empty-row">

                <td colspan="6">

                    <div class="empty-state">

                        <div class="empty-icon">
                            ◌
                        </div>

                        <h3>
                            Starting scraper
                        </h3>

                        <p>
                            Google Maps data will appear here.
                        </p>

                    </div>

                </td>

            </tr>

        `;


        tableCount.textContent =
            "0 records";


        downloadButton.disabled =
            true;


        progressBar.style.width =
            "0%";


        progressCount.textContent =
            "0";


        progressIcon.innerHTML =
            "✦";


        progressIcon.style.color =
            "";


        footerStatus.textContent =
            "Scraping in progress";

    }


    /* =====================================================
       RUNNING STATE
    ====================================================== */

    function setRunningState() {

        startButton.disabled =
            true;

        stopButton.disabled = true;
        stopButton.textContent = "Stop Scraping";

        startButton.classList.add(
            "loading"
        );


        startButton.querySelector(
            ".button-text"
        ).textContent =
            "Scraping...";


        progressIcon.classList.add(
            "running"
        );


        document
            .querySelector(".progress-card")
            .classList.add(
                "running"
            );


        progressStatus.textContent =
            "Queued";


        progressMessage.textContent =
            "Starting scraper...";


        progressCount.textContent =
            "0";


        progressPercentage.textContent =
            "Starting";


        progressDetails.textContent =
            "Chrome will open automatically.";

    }


    /* =====================================================
       IDLE BUTTON
    ====================================================== */

    function setIdleButton() {

        startButton.disabled =
            false;

        startButton.classList.remove(
            "loading"
        );


        startButton.querySelector(
            ".button-text"
        ).textContent =
            "Start Scraping";

        stopButton.disabled = true;
        stopButton.textContent = "Stop Scraping";

    }


    function setCancelledState(job) {
        progressStatus.textContent = "Stopped";
        progressMessage.textContent = job.message || "Scraping stopped by user.";
        progressIcon.classList.remove("running");
        progressIcon.innerHTML = "Ⅱ";
        progressIcon.style.color = "#ff9292";
        document.querySelector(".progress-card").classList.remove("running");
        progressPercentage.textContent = "Stopped";
        progressDetails.textContent = `${job.current || 0} businesses collected`;
        footerStatus.textContent = "Scraping stopped";
        heroResults.textContent = job.current || 0;
        setIdleButton();
        showToast("Scraping stopped", `${job.current || 0} businesses collected.`);
    }


    function setIdleState() {

        setIdleButton();

        progressStatus.textContent =
            "Ready";

        progressMessage.textContent =
            "Enter a search query to begin.";

        progressIcon.classList.remove(
            "running"
        );

        document
            .querySelector(".progress-card")
            .classList.remove(
                "running"
            );

    }


    /* =====================================================
       TOAST
    ====================================================== */

    let toastTimer;


    function showToast(
        title,
        message
    ) {

        toastTitle.textContent =
            title;

        toastMessage.textContent =
            message;


        toast.classList.add(
            "show"
        );


        clearTimeout(
            toastTimer
        );


        toastTimer =
            setTimeout(
                () => {

                    toast.classList.remove(
                        "show"
                    );

                },
                4000
            );

    }


    /* =====================================================
       HTML ESCAPING
    ====================================================== */

    function escapeHTML(value) {

        return String(value)
            .replace(
                /&/g,
                "&amp;"
            )
            .replace(
                /</g,
                "&lt;"
            )
            .replace(
                />/g,
                "&gt;"
            )
            .replace(
                /"/g,
                "&quot;"
            )
            .replace(
                /'/g,
                "&#039;"
            );

    }


    function escapeAttribute(value) {

        return String(value)
            .replace(
                /"/g,
                "&quot;"
            )
            .replace(
                /</g,
                "&lt;"
            )
            .replace(
                />/g,
                "&gt;"
            );

    }


    /* =====================================================
       CAPITALIZE
    ====================================================== */

    function capitalize(value) {

        if (!value)
            return "";

        return (
            value.charAt(0).toUpperCase() +
            value.slice(1)
        );

    }


});
