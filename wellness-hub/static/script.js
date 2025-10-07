document.addEventListener("DOMContentLoaded", function () {

  // ------------------------------
  // 1️⃣ GLOBAL MODAL FUNCTIONS
  // ------------------------------
  const modal = document.getElementById("actionModal");
  const modalTitle = modal ? document.getElementById("modalTitle") : null;
  const modalBody = modal ? document.getElementById("modalBody") : null;

  window.showModal = function (title, body) {
    if (modal && modalTitle && modalBody) {
      modalTitle.textContent = title;
      modalBody.innerHTML = body;
      modal.style.display = "flex";
    }
  };

  window.closeModal = function () {
    if (modal) modal.style.display = "none";
  };

  window.showJournalEntry = function(title, date, content) {
    const decodedContent = content.replace(/&quot;/g, '"')
                                  .replace(/&#39;/g, "'")
                                  .replace(/&lt;/g, '<')
                                  .replace(/&gt;/g, '>')
                                  .replace(/&amp;/g, '&');
                                  
    const modalHTML = `
    
        <p style="white-space: pre-wrap; font-size: 1em; color: var(--text-color);">${decodedContent}</p>
    `;
    
      window.showModal(title, modalHTML);
    };

  window.addEventListener("click", (event) => {
    if (event.target === modal) modal.style.display = "none";
  });

  // ------------------------------
  // 2️⃣ GLOBAL FORM VALIDATION
  // ------------------------------
  window.validateRegisterForm = function (event) {
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");

    if (!emailInput || !passwordInput) return true;

    const email = emailInput.value;
    const password = passwordInput.value;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    let errors = [];

    if (!emailRegex.test(email)) errors.push("Invalid email format.");
    if (password.length < 6)
      errors.push("Passkey must be at least 6 characters.");

    if (errors.length > 0) {
      event.preventDefault();
      alert("Registration Errors:\n" + errors.join("\n"));
      return false;
    }
    return true;
  };

  // ------------------------------
  // 3️⃣ DASHBOARD PAGE LOGIC
  // ------------------------------
  
  if (document.body.classList.contains("page-dashboard")) {
    console.log("Dashboard logic active ✅");

    const stressSlider = document.getElementById("stress_level");
    const stressValueDisplay = document.getElementById("stress_value");
    const chartCtx = document.getElementById("stressChart");
    const checkinModule = document.querySelector(".checkin-module");
    const qText = document.getElementById("question-text");
    const btnYes = document.getElementById("answer-yes");
    const btnNo = document.getElementById("answer-no");
    const sleepInputGroup = document.getElementById("sleep-input");
    const sleepInput = document.getElementById("sleep_hours");
    const submitBtn = document.getElementById("submit-checkin");
    const progressBar = document.getElementById("progress-bar");

    const chatInput = document.getElementById("chat-input");
    const chatSendBtn = document.getElementById("send-chat");
    let currentQIndex = 0;
    let answers = {};

    // --- Stress Level Slider ---
    if (stressSlider && stressValueDisplay) {
      stressValueDisplay.textContent = stressSlider.value;
      stressSlider.addEventListener("input", function () {
        stressValueDisplay.textContent = this.value;
      });
    }

    // --- Interactive Check-in ---
    function updateProgress() {
      const totalQuestions = INTERACTIVE_QUESTIONS?.length + 1 || 1;
      const progress = (currentQIndex / totalQuestions) * 100;
      if (progressBar) progressBar.style.width = `${progress}%`;
    }

    function loadQuestion() {
      if (!qText || !btnYes || !btnNo || !sleepInputGroup || !checkinModule)
        return;

      btnYes.classList.remove("hidden");
      btnNo.classList.remove("hidden");
      sleepInputGroup.classList.add("hidden");
      checkinModule.classList.remove("finished");
      const answerButtonsContainer = document.querySelector('.answer-buttons');

      if (currentQIndex < INTERACTIVE_QUESTIONS.length) {
        if (answerButtonsContainer) {
            answerButtonsContainer.classList.remove('hidden');
        }
        qText.textContent = INTERACTIVE_QUESTIONS[currentQIndex].q;
        btnYes.onclick = () => handleAnswer("yes");
        btnNo.onclick = () => handleAnswer("no");
      } else if (currentQIndex === INTERACTIVE_QUESTIONS.length) {
        qText.textContent =
          "STATUS LOGGED: Daily analysis complete. Access the Peer-AI console for immediate support.";
        btnYes.classList.add("hidden");
        btnNo.classList.add("hidden");
        sleepInputGroup.classList.remove("hidden");
        checkinModule.classList.add("finished");
      } else {
        qText.textContent =
          "STATUS LOGGED: Daily analysis complete. Access the Peer-AI console for immediate support.";
        if (answerButtonsContainer) {
            answerButtonsContainer.classList.add('hidden'); 
        }
        btnYes.classList.add("hidden");
        btnNo.classList.add("hidden");
        sleepInputGroup.classList.add("hidden");
        if (progressBar) progressBar.style.width = "100%";
      }
      updateProgress();
    }

    function handleAnswer(answer) {
      answers[currentQIndex] = answer;
      currentQIndex++;
      loadQuestion();
    }

    function updateDashboardStats(data) {
      const stressDisplay = document.querySelector(".status-indicator span");
      const indicator = document.querySelector(".status-indicator");
      const moodDisplay = document.getElementById("display-mood");
      const recDisplay = document.getElementById("display-recommendation");

      if (stressDisplay && indicator && moodDisplay && recDisplay) {
        stressDisplay.textContent = `${data.stress_level}/5`;
        indicator.className = `status-indicator stress-level-${data.stress_level}`;
        moodDisplay.textContent = data.mood.toUpperCase();
        moodDisplay.className = `mood-${data.mood}`;
        recDisplay.innerHTML = data.ai_recommendation;
      }
    }

    function handleSubmit() {
      const sleepHours = parseFloat(sleepInput.value);
      if (isNaN(sleepHours) || sleepHours < 0 || sleepHours > 15) {
        alert("SYSTEM WARNING: Invalid sleep hour value.");
        return;
      }

      const submissionData = { answers: answers, sleep_hours: sleepHours };
      submitBtn.disabled = true;
      submitBtn.textContent = "ANALYZING...";

      fetch(submitUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(submissionData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            window.showModal('STATUS REPORT', 'Survey submitted successfully! Your data has been analyzed.');
            updateDashboardStats(data);
            currentQIndex++; 
            loadQuestion();
          } else {
            alert("ERROR: Submission failed: " + data.message);
          }
          submitBtn.disabled = false;
          submitBtn.textContent = "ANALYZE & SUBMIT";
        })
        .catch((error) => {
          console.error("Submission Error:", error);
          alert("ERROR: System connection anomaly. Check console.");
          submitBtn.disabled = false;
          submitBtn.textContent = "ANALYZE & SUBMIT";
        });
    }

    if (checkinModule && btnYes && btnNo && submitBtn) {
      btnYes.addEventListener("click", () => handleAnswer("yes"));
      btnNo.addEventListener("click", () => handleAnswer("no"));
      submitBtn.addEventListener("click", handleSubmit);
      loadQuestion();
    }

    // --- Chart.js Initialization ---
    if (
      chartCtx &&
      typeof Chart !== "undefined" &&
      typeof chartLabels !== "undefined" &&
      typeof chartData !== "undefined"
    ) {
      new Chart(chartCtx, {
        type: "line",
        data: {
          labels: chartLabels,
          datasets: [
            {
              label: "Stress Index (1=Low, 10=High)",
              data: chartData,
              borderColor: "#30b0ff",
              backgroundColor: "rgba(48, 176, 255, 0.2)",
              pointRadius: 6,
              pointHitRadius: 10,
              pointBackgroundColor: function (context) {
                const value = context.dataset.data[context.dataIndex];
                if (value === null) return "#444";
                if (value >= 8) return "#ff3050";
                if (value <= 5) return "#33ff88";
                return "#ffb300";
              },
              borderWidth: 2,
              tension: 0.4,
              fill: true,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 10, right: 15, bottom: 0, left: 0 } },
          scales: {
            y: {
              min: 1,
              max: 10,
              ticks: { stepSize: 1, color: "#e0e0e0" },
              grid: { color: "#404060", borderColor: "#e0e0e0" },
            },
            x: {
              ticks: { color: "#e0e0e0", padding: 10 },
              grid: { display: false, borderColor: "#e0e0e0" },
            },
          },
          plugins: { legend: { display: false }, title: { display: false } },
        },
      });
    }
  }



const INTERACTIVE_QUESTIONS = [
  { q: "Did you feel rested after waking up?", score: 1, negative_impact: true },
  { q: "Did you experience a high-stakes, life-threatening situation today?", score: 3, negative_impact: true },
  { q: "Did you take at least one 15-minute uninterrupted break?", score: 2, negative_impact: false },
  { q: "Did you lose your temper or feel constantly irritable?", score: 2, negative_impact: true },
  { q: "Did you eat a proper, balanced meal today?", score: 1, negative_impact: false }
];


// ------------------------------
// 2️⃣ SURVEY PAGE LOGIC
// ------------------------------
if (document.body.classList.contains("page-survey")) {
  console.log("Survey page logic active ✅");

  const qText = document.getElementById("question-text");
  const btnYes = document.getElementById("answer-yes");
  const btnNo = document.getElementById("answer-no");
  const progressBar = document.getElementById("progress-bar");

  const INTERACTIVE_QUESTIONS_SURVEY = INTERACTIVE_QUESTIONS || [];
  const submitUrl = "/submit-survey";

  let currentQIndex = 0;
  let answers = [];

  function updateProgress() {
    if (progressBar) {
      const total = INTERACTIVE_QUESTIONS_SURVEY.length;
      const percent = (currentQIndex / total) * 100;
      progressBar.style.width = `${percent}%`;
    }
  }

  // 🔹 Load next question
  function loadSurveyQuestion() {
    if (!qText) return;

    const answerButtonsContainer = document.querySelector('.answer-buttons');

    if (currentQIndex < INTERACTIVE_QUESTIONS_SURVEY.length) {
      if (answerButtonsContainer) {
            answerButtonsContainer.classList.remove('hidden');
        }
      qText.textContent = INTERACTIVE_QUESTIONS_SURVEY[currentQIndex].q;
      btnYes.disabled = false;
      btnNo.disabled = false;
    } else {
      qText.textContent = "Survey completed. Thank you!";
      btnYes.disabled = true;
      btnNo.disabled = true;
      if (answerButtonsContainer) {
            answerButtonsContainer.classList.add('hidden'); 
        }

      // ✅ Automatically send answers to backend when last question done
      sendAnswersToBackend();
    }

    updateProgress();
  }

  // 🔹 Handle answer click
  function handleSurveyAnswer(answer) {
    const val = answer === "yes" ? 1 : 0;
    answers.push(val);

    currentQIndex++;
    loadSurveyQuestion();
  }

  // 🔹 Send collected answers to backend
  function sendAnswersToBackend() {
    if (answers.length === 0) return;

    console.log("Sending answers:", answers);

    fetch(submitUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: answers }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          alert("Survey submitted successfully!");
        } else {
          alert("Submission failed: " + data.message);
        }
      })
      .catch((err) => {
        console.error("Survey submission error:", err);
        alert("Submission failed. Check console.");
      });
  }

  // Button click listeners
  btnYes?.addEventListener("click", () => handleSurveyAnswer("yes"));
  btnNo?.addEventListener("click", () => handleSurveyAnswer("no"));

  // Load first question
  loadSurveyQuestion();
}




  // ------------------------------
  // 4️⃣ OTHER PAGE LOGIC
  // ------------------------------
  if (document.querySelector(".contact-container")) {
    console.log("Contact page JS loaded ✅");
  }
});
