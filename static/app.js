// =========================================================
// FUNNEL ANALYTICS - SHOPEASY LIVE TRACKING
// =========================================================

// IMPORTANT:
// ShopEasy is hosted on GitHub Pages.
// FunnelAnalytics Flask API is hosted on Render.
//
// DO NOT use "/api/event" here.
// Use the Render backend URL.

const API_BASE =
  "https://funnel-analysis-1.onrender.com";


// =========================================================
// SESSION
// =========================================================

let session = {
  started: false,
  userId: "",
  age: 25,
  previousVisits: 0,
  page: "Home",
  pages: 1,
  clicks: 0,
  startedAt: 0
};


// =========================================================
// HELPER
// =========================================================

function $(id) {
  return document.getElementById(id);
}


// =========================================================
// GET / CREATE USER ID
// =========================================================
//
// IMPORTANT:
// Same browser = same user ID.
// So if the user comes back later,
// their old purchase history remains associated
// with the same user.
// =========================================================

function getStoredUserId() {

  let userId =
    localStorage.getItem("shopeasy_user_id");

  if (!userId) {

    userId =
      "U" +
      Date.now() +
      Math.floor(
        Math.random() * 1000
      );

    localStorage.setItem(
      "shopeasy_user_id",
      userId
    );
  }

  return userId;
}


// =========================================================
// START JOURNEY
// =========================================================

function startJourney() {

  session.started = true;

  const inputUser =
    $("userId")
      ? $("userId").value.trim()
      : "";

  // Use manually entered ID if available.
  // Otherwise use persistent browser ID.
  session.userId =
    inputUser ||
    getStoredUserId();

  // Save it permanently.
  localStorage.setItem(
    "shopeasy_user_id",
    session.userId
  );


  session.age =
    $("age")
      ? Number(
          $("age").value || 25
        )
      : 25;


  session.previousVisits =
    $("previousVisits")
      ? Number(
          $("previousVisits").value || 0
        )
      : 0;


  session.page = "Home";

  session.pages = 1;

  session.clicks = 0;

  session.startedAt =
    Date.now();


  if ($("journeyArea")) {

    $("journeyArea")
      .classList
      .remove("hidden");

  }


  updatePredictionAndSave();
}


// =========================================================
// GO TO PAGE
// =========================================================

async function go(page) {

  if (!session.started) {

    // Automatically start using
    // stored user ID if necessary.

    session.started = true;

    session.userId =
      getStoredUserId();

    session.age = 25;

    session.previousVisits = 0;

    session.pages = 1;

    session.clicks = 0;

    session.startedAt =
      Date.now();
  }


  session.page = page;


  if (page !== "Home") {

    session.pages += 1;

  }


  session.clicks += 1;


  await updatePredictionAndSave();
}


// =========================================================
// RESET JOURNEY
// =========================================================
//
// IMPORTANT:
// Resetting the current SESSION must NOT delete
// the user's old database history.
// =========================================================

function resetJourney() {

  session.page = "Home";

  session.pages = 1;

  session.clicks = 0;

  session.startedAt =
    Date.now();


  updatePredictionAndSave();
}


// =========================================================
// SESSION DURATION
// =========================================================

function duration() {

  return session.startedAt

    ? Math.floor(
        (Date.now() -
          session.startedAt) /
        1000
      )

    : 0;
}


// =========================================================
// SEND EVENT TO FLASK
// =========================================================

async function updatePredictionAndSave() {

  if (!session.userId) {

    session.userId =
      getStoredUserId();

  }


  const payload = {

    user_id:
      session.userId,

    current_page:
      session.page,

    age:
      session.age,

    pages_visited:
      session.pages,

    session_duration:
      duration(),

    clicks:
      session.clicks,

    previous_visits:
      session.previousVisits,

    device:
      /Mobi|Android|iPhone|iPad/i.test(
        navigator.userAgent
      )
        ? "Mobile"
        : "Desktop"

  };


  console.log(
    "Sending Funnel Event:",
    payload
  );


  try {

    const r =
      await fetch(
        API_BASE +
        "/api/event",
        {

          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify(payload)

        }
      );


    if (!r.ok) {

      throw new Error(
        "Server returned " +
        r.status
      );

    }


    const d =
      await r.json();


    console.log(
      "Funnel Event Saved:",
      d
    );


    const pct =
      Number(
        d.percentage || 0
      );


    // =====================================================
    // CURRENT PAGE
    // =====================================================

    if ($("currentPage")) {

      $("currentPage")
        .textContent =
        session.page;

    }


    // =====================================================
    // PROBABILITY
    // =====================================================

    if ($("probability")) {

      $("probability")
        .textContent =
        pct.toFixed(2) +
        "%";

    }


    // =====================================================
    // RISK
    // =====================================================

    if (
      $("risk") &&
      d.user
    ) {

      $("risk")
        .textContent =
        d.user.risk;

    }


    // =====================================================
    // PAGES
    // =====================================================

    if ($("pages")) {

      $("pages")
        .textContent =
        session.pages;

    }


    // =====================================================
    // PREDICTION PAGE
    // =====================================================

    if ($("predPage")) {

      $("predPage")
        .textContent =
        session.page;

    }


    if ($("predProbability")) {

      $("predProbability")
        .textContent =
        pct.toFixed(2) +
        "%";

    }


    if (
      $("predRisk") &&
      d.user
    ) {

      $("predRisk")
        .textContent =
        d.user.risk;

    }


    // =====================================================
    // SESSION INFORMATION
    // =====================================================

    if ($("sessionInfo")) {

      $("sessionInfo")
        .textContent =
        duration() +
        " sec · " +
        session.clicks +
        " clicks";

    }


    // =====================================================
    // RISK BAR
    // =====================================================

    if ($("riskBar")) {

      $("riskBar")
        .style
        .width =
        Math.max(
          2,
          pct
        ) +
        "%";

    }


    // =====================================================
    // RECOMMENDATION
    // =====================================================

    if (
      session.page ===
      "Purchase"
    ) {

      if ($("recommendation")) {

        $("recommendation")
          .textContent =
          "🟢 Purchase completed. " +
          "Drop-off probability is 0% " +
          "and the journey is complete.";

      }

    }

    else if (
      d.user &&
      d.user.risk ===
      "HIGH"
    ) {

      if ($("recommendation")) {

        $("recommendation")
          .textContent =
          "🚨 High-risk user. " +
          "Consider immediate assistance, " +
          "an offer, or a relevant recommendation.";

      }

    }

    else if (
      d.user &&
      d.user.risk ===
      "MEDIUM"
    ) {

      if ($("recommendation")) {

        $("recommendation")
          .textContent =
          "⚠️ Medium-risk user. " +
          "Consider additional product information " +
          "or personalized guidance.";

      }

    }

    else {

      if ($("recommendation")) {

        $("recommendation")
          .textContent =
          "🟢 Low-risk user. " +
          "User appears engaged.";

      }

    }


    // =====================================================
    // REFRESH LIVE DASHBOARD
    // =====================================================

    await refreshLiveTable();

  }

  catch (e) {

    console.error(
      "FUNNEL EVENT ERROR:",
      e
    );

  }

}


// =========================================================
// REFRESH LIVE TABLE
// =========================================================

async function refreshLiveTable() {

  const table =
    $("liveTable");


  if (!table) {

    return;

  }


  try {

    const r =
      await fetch(

        API_BASE +
        "/api/live?ts=" +
        Date.now(),

        {
          method: "GET",

          cache: "no-store"
        }

      );


    if (!r.ok) {

      throw new Error(
        "Live API returned " +
        r.status
      );

    }


    const d =
      await r.json();


    const events =
      d.events || [];


    // =====================================================
    // EVENT COUNT
    // =====================================================

    if ($("eventCount")) {

      $("eventCount")
        .textContent =
        events.length +
        " users · auto refresh 2s";

    }


    // =====================================================
    // NO EVENTS
    // =====================================================

    if (!events.length) {

      table.innerHTML =
        '<div class="empty">' +
        "Waiting for ShopEasy user activity..." +
        "</div>";

      return;

    }


    // =====================================================
    // TABLE COLUMNS
    // =====================================================

    const cols = [

      "user_id",

      "current_page",

      "clicks",

      "pages_visited",

      "device",

      "session_duration",

      "dropout_probability",

      "risk",

      "timestamp"

    ];


    const labels = {

      user_id:
        "User ID",

      current_page:
        "Current Page",

      clicks:
        "Clicks",

      pages_visited:
        "Pages Visited",

      device:
        "Device",

      session_duration:
        "Session Time",

      dropout_probability:
        "Drop-Off Prediction",

      risk:
        "Risk",

      timestamp:
        "Time"

    };


    // =====================================================
    // BUILD TABLE
    // =====================================================

    let h =
      "<table>" +
      "<thead>" +
      "<tr>" +

      cols
        .map(
          c =>
            "<th>" +
            labels[c] +
            "</th>"
        )
        .join("") +

      "</tr>" +
      "</thead>" +
      "<tbody>";


    // =====================================================
    // ADD USERS
    // =====================================================

    for (
      const row of events
    ) {

      h += "<tr>";


      for (
        const c of cols
      ) {

        let v =
          row[c] ?? "";


        // =================================================
        // DROPOUT PERCENTAGE
        // =================================================

        if (

          c ===
          "dropout_probability" &&

          v !== ""

        ) {

          v =
            (
              Number(v) *
              100
            ).toFixed(2) +
            "%";

        }


        // =================================================
        // SESSION TIME
        // =================================================

        if (
          c ===
          "session_duration" &&
          v !== ""
        ) {

          v =
            v + " sec";

        }


        // =================================================
        // RISK BADGE
        // =================================================

        if (
          c === "risk"
        ) {

          const riskValue =
            String(v);


          v =
            '<span class="risk-' +
            riskValue.toLowerCase() +
            '">' +
            riskValue +
            "</span>";

        }


        // =================================================
        // DEVICE ICON
        // =================================================

        if (
          c === "device"
        ) {

          const device =
            String(v);


          if (
            device
              .toLowerCase()
              .includes("mobile")
          ) {

            v =
              "📱 " +
              device;

          }

          else {

            v =
              "💻 " +
              device;

          }

        }


        // =================================================
        // HTML ESCAPE
        // =================================================

        const safeValue =
          String(v)
            .replaceAll(
              "&",
              "&amp;"
            )
            .replaceAll(
              "<",
              "&lt;"
            )
            .replaceAll(
              ">",
              "&gt;"
            )
            .replaceAll(
              '"',
              "&quot;"
            );


        h +=
          "<td>" +
          safeValue +
          "</td>";

      }


      h +=
        "</tr>";

    }


    h +=
      "</tbody>" +
      "</table>";


    table.innerHTML =
      h;

  }


  catch (e) {

    console.error(
      "LIVE TABLE ERROR:",
      e
    );

  }

}


// =========================================================
// INITIAL LIVE TABLE LOAD
// =========================================================

if (
  $("liveTable")
) {

  refreshLiveTable();


  // Refresh every 2 seconds.

  setInterval(
    refreshLiveTable,
    2000
  );


  // Update session duration
  // every second.

  setInterval(
    () => {

      if (
        session.started
      ) {

        if (
          $("sessionInfo")
        ) {

          $("sessionInfo")
            .textContent =
            duration() +
            " sec · " +
            session.clicks +
            " clicks";

        }

      }

    },
    1000
  );

}


// =========================================================
// EXPOSE FUNCTIONS
// =========================================================
//
// Required if dashboard buttons use:
// onclick="startJourney()"
// onclick="go('Product')"
// etc.
// =========================================================

window.startJourney =
  startJourney;

window.go =
  go;

window.resetJourney =
  resetJourney;

window.refreshLiveTable =
  refreshLiveTable;